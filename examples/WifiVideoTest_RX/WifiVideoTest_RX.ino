/*
 * WifiVideoTest_RX — приёмная плата теста Wi-Fi 2,4 ГГц (пара к WifiVideoTest_CAM), 09.10.
 *
 * Плата T-HaLow подключается станцией к точке доступа камеры, принимает куски видео по UDP
 * и отдаёт их в USB ТЕМИ ЖЕ записями, что HalowVideoP2P_AP:
 *   [0xA5][0x5A][type][len_lo][len_hi][crc_lo][crc_hi][payload]
 *   'V' — halow_app_hdr_t + кусок JPEG, 'L' — лог камеры, 'M' — JSON с метриками приёмника.
 * Значит, просмотрщик и запись CSV — прежние:
 *   python tools/halow_viewer.py --serial-video COM7 --csv --note wifi_5m_14dbm
 * В CSV столбец ap_rssi — уровень сигнала камеры у приёмника, ap_bgr — фон эфира у приёмника.
 *
 * На каждый собранный кадр уходит квитанция 'A' — по ней камера считает задержку (RTT),
 * как в HaLow-версии.
 *
 * Команды в USB-консоль: p <дБм> — мощность передатчика приёмника (квитанции), 2..20.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <lwip/sockets.h>
#include "utilities.h"
#include "halow_proto.h"
#include "halow_stream.h"
#include "wifi_test_common.h"

#define TX_POWER_DBM   14
#define META_PERIOD_MS 2000
#define FRAME_SLOTS    8      // сколько кадров одновременно собираем для квитанций

static int sock = -1;
static struct sockaddr_in cam;
static int tx_power_dbm = TX_POWER_DBM;
static wt_nf_t nf;

static uint32_t cnt_pkts = 0, cnt_bad = 0, cnt_frames_acked = 0;

/* учёт кусков кадра — только для квитанции; сборкой кадра занят просмотрщик */
static struct { uint32_t id; uint16_t cnt; uint64_t mask; bool acked; } slot[FRAME_SLOTS];

// ---------------------------- USB ----------------------------

static void usb_record(char type, const uint8_t *data, uint16_t len)
{
    uint16_t crc = halow_crc16(data, len);
    uint8_t hdr[7] = { HALOW_USB_SYNC0, HALOW_USB_SYNC1, (uint8_t)type,
                       (uint8_t)(len & 0xff), (uint8_t)(len >> 8),
                       (uint8_t)(crc & 0xff), (uint8_t)(crc >> 8) };
    SerialMon.write(hdr, sizeof(hdr));
    if (len) {
        SerialMon.write(data, len);
    }
}

static void send_meta(void)
{
    wifi_ap_record_t ap;
    bool conn = WiFi.status() == WL_CONNECTED;
    int rssi = (conn && esp_wifi_sta_get_ap_info(&ap) == ESP_OK) ? ap.rssi : 0;
    char js[160];
    int n = snprintf(js, sizeof(js),
                     "{\"role\":\"ap\",\"conn\":%d,\"rssi\":%d,\"ok\":%lu,\"crc_err\":%lu,"
                     "\"bgr\":%d,\"fwd\":%lu,\"link\":\"wifi24\",\"pwr\":%d}",
                     conn ? 1 : 0, rssi, (unsigned long)cnt_pkts, (unsigned long)cnt_bad,
                     wt_nf_take(&nf), (unsigned long)cnt_frames_acked, wt_get_tx_power());
    usb_record(HALOW_USB_TYPE_META, (const uint8_t *)js, (uint16_t)n);
}

// ---------------------------- квитанции ----------------------------

static void note_chunk(const halow_app_hdr_t *h)
{
    if (h->chunk_cnt == 0 || h->chunk_cnt > 64 || h->chunk_idx >= h->chunk_cnt) {
        return;
    }
    int k = h->frame_id % FRAME_SLOTS;
    if (slot[k].id != h->frame_id) {
        slot[k].id = h->frame_id;
        slot[k].cnt = h->chunk_cnt;
        slot[k].mask = 0;
        slot[k].acked = false;
    }
    slot[k].mask |= 1ULL << h->chunk_idx;
    uint64_t full = (h->chunk_cnt == 64) ? ~0ULL : ((1ULL << h->chunk_cnt) - 1);
    if (!slot[k].acked && slot[k].mask == full) {
        uint8_t a[5] = { WT_TYPE_ACK };
        memcpy(a + 1, &h->frame_id, 4);
        sendto(sock, a, sizeof(a), 0, (struct sockaddr *)&cam, sizeof(cam));
        slot[k].acked = true;
        cnt_frames_acked++;
    }
}

static void poll_rx(void)
{
    static uint8_t buf[1 + HALOW_APP_HDR_LEN + HALOW_MAX_PAYLOAD + 16];
    int n;
    while ((n = recv(sock, buf, sizeof(buf), MSG_DONTWAIT)) > 0) {
        if (buf[0] == WT_TYPE_VIDEO && n > 1 + HALOW_APP_HDR_LEN) {
            halow_app_hdr_t h;
            memcpy(&h, buf + 1, HALOW_APP_HDR_LEN);
            if (memcmp(h.magic, "HLW2", 4) != 0 || h.payload_len != n - 1 - HALOW_APP_HDR_LEN) {
                cnt_bad++;
                continue;
            }
            cnt_pkts++;
            usb_record(HALOW_USB_TYPE_VIDEO, buf + 1, (uint16_t)(n - 1));
            note_chunk(&h);
        } else if (buf[0] == WT_TYPE_LOG && n > 3) {
            usb_record(HALOW_USB_TYPE_LOG, buf + 1, (uint16_t)(n - 1));
        }
    }
}

// ---------------------------- setup / loop ----------------------------

void setup()
{
    SerialMon.begin(115200);
    SerialMon.setTxTimeoutMs(100);       // как у HalowVideoP2P_AP: плата у ноутбука
    SerialMon.setTimeout(20);            // чтение команды не должно останавливать приём
    delay(1500);
    SerialMon.println("\n=== T-Halow: приёмник, видео по Wi-Fi 2,4 ГГц (тест сравнения) ===");

    WiFi.mode(WIFI_STA);
    wt_set_protocol(WIFI_IF_STA);
    WiFi.setSleep(false);                // без энергосбережения: иначе задержка от сна станции
    WiFi.begin(WT_SSID, WT_PASS);

    sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    struct sockaddr_in a = {};
    a.sin_family = AF_INET;
    a.sin_port = htons(WT_RX_PORT);
    a.sin_addr.s_addr = htonl(INADDR_ANY);
    bind(sock, (struct sockaddr *)&a, sizeof(a));
    int rcv = 32 * 1024;
    setsockopt(sock, SOL_SOCKET, SO_RCVBUF, &rcv, sizeof(rcv));

    memset(&cam, 0, sizeof(cam));
    cam.sin_family = AF_INET;
    cam.sin_port = htons(WT_CAM_PORT);
    inet_aton(WT_CAM_IP, &cam.sin_addr);
}

void loop()
{
    static uint32_t last_hello = 0, last_meta = 0;
    static bool was_conn = false;
    uint32_t now = millis();

    bool conn = WiFi.status() == WL_CONNECTED;
    if (conn && !was_conn) {
        wt_set_tx_power(tx_power_dbm);   // мощность ставится после подключения
        wt_nf_start(&nf);
        SerialMon.printf("Подключено к %s, канал %d, режим %s, мощность %d дБм\n", WT_SSID,
                         WiFi.channel(), WT_PROTO_NAME, wt_get_tx_power());
    }
    was_conn = conn;

    if (conn && now - last_hello >= 1000) {
        last_hello = now;
        uint8_t h = WT_TYPE_HELLO;
        sendto(sock, &h, 1, 0, (struct sockaddr *)&cam, sizeof(cam));
    }
    if (now - last_meta >= META_PERIOD_MS) {
        last_meta = now;
        send_meta();
    }
    if (conn) {
        poll_rx();
    }

    if (SerialMon.available()) {
        String s = SerialMon.readStringUntil('\n');
        if (s.length() > 1 && s[0] == 'p') {
            tx_power_dbm = constrain(s.substring(1).toInt(), 2, 20);
            wt_set_tx_power(tx_power_dbm);
            SerialMon.printf("Мощность приёмника: %d дБм\n", wt_get_tx_power());
        }
    }
    delay(1);
}
