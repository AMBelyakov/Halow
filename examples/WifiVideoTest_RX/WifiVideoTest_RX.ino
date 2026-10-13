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
#include <freertos/ringbuf.h>
#include "utilities.h"
#include "halow_proto.h"
#include "halow_stream.h"
#include "wifi_test_common.h"

#define TX_POWER_DBM   14
#define META_PERIOD_MS 2000
#define FRAME_SLOTS    8      // сколько кадров одновременно собираем для квитанций

static int sock = -1;                    // приём видео (задача rx_task) и hello с порта WT_RX_PORT
static int sock_ack = -1;                // квитанции из loop: сокет не делим между задачами
static RingbufHandle_t rxq = NULL;       // пакеты от rx_task к loop
static volatile bool g_conn = false;
static volatile uint32_t cnt_qdrop = 0;  // пакетов выброшено: буфер полон (USB не успевает)
/* заливка: считаем прямо в rx_task, в USB не отдаём (USB сам по себе ~1 МБ/с) */
static volatile uint32_t fl_pkts = 0, fl_bytes = 0, fl_lost = 0, fl_last_ms = 0;
static uint32_t fl_seq = 0;
static struct sockaddr_in cam;
static int tx_power_dbm = TX_POWER_DBM;
static wt_nf_t nf;

static uint32_t cnt_pkts = 0, cnt_bad = 0, cnt_frames_acked = 0;
static volatile int last_reason = 0;     // причина последнего обрыва/отказа станции (wifi_err_reason_t)

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
                     "\"bgr\":%d,\"fwd\":%lu,\"link\":\"wifi24\",\"pwr\":%d,\"why\":%d,\"qdrop\":%lu}",
                     conn ? 1 : 0, rssi, (unsigned long)cnt_pkts, (unsigned long)cnt_bad,
                     wt_nf_take(&nf), (unsigned long)cnt_frames_acked, wt_get_tx_power(), (int)last_reason,
                     (unsigned long)cnt_qdrop);
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
        sendto(sock_ack, a, sizeof(a), 0, (struct sockaddr *)&cam, sizeof(cam));
        slot[k].acked = true;
        cnt_frames_acked++;
    }
}

/*
 * 13.10: приём в отдельной задаче. Очередь UDP в lwip — 6 пакетов, а камера выпускает кадр
 * пачкой ~16 кусков за пару миллисекунд; loop в это время сидел в записи в USB, и остаток
 * пачки выбрасывался (6 целых кадров из 45). Задача сразу перекладывает пакет в буфер 64 КБ,
 * а в USB его пишет loop. Hello тоже отсюда: камера берёт адрес и порт приёмника из hello.
 */
static void rx_task(void *)
{
    static uint8_t buf[1 + HALOW_APP_HDR_LEN + HALOW_MAX_PAYLOAD + 16];
    uint32_t last_hello = 0;
    for (;;) {
        if (!g_conn) {
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }
        if (millis() - last_hello >= 1000) {
            last_hello = millis();
            uint8_t h = WT_TYPE_HELLO;
            sendto(sock, &h, 1, 0, (struct sockaddr *)&cam, sizeof(cam));
        }
        int n = recv(sock, buf, sizeof(buf), 0);         // SO_RCVTIMEO 100 мс
        if (n >= 5 && buf[0] == WT_TYPE_FLOOD) {
            uint32_t q;
            memcpy(&q, buf + 1, 4);
            if (fl_seq && q > fl_seq + 1 && q - fl_seq < 100000) {
                fl_lost += q - fl_seq - 1;
            }
            if (q > fl_seq || q + 100000 < fl_seq) {
                fl_seq = q;
            }
            fl_pkts++;
            fl_bytes += n;
            fl_last_ms = millis();
            continue;
        }
        if (n > 0 && xRingbufferSend(rxq, buf, n, 0) != pdTRUE) {
            cnt_qdrop++;
        }
    }
}

static void poll_rx(void)
{
    size_t n;
    uint8_t *buf;
    while ((buf = (uint8_t *)xRingbufferReceive(rxq, &n, 0)) != NULL) {
        if (buf[0] == WT_TYPE_VIDEO && n > 1 + HALOW_APP_HDR_LEN) {
            halow_app_hdr_t h;
            memcpy(&h, buf + 1, HALOW_APP_HDR_LEN);
            if (memcmp(h.magic, "HLW2", 4) != 0 || h.payload_len != n - 1 - HALOW_APP_HDR_LEN) {
                cnt_bad++;
            } else {
                cnt_pkts++;
                note_chunk(&h);                          // квитанция раньше записи в USB
                usb_record(HALOW_USB_TYPE_VIDEO, buf + 1, (uint16_t)(n - 1));
            }
        } else if (buf[0] == WT_TYPE_LOG && n > 3) {
            usb_record(HALOW_USB_TYPE_LOG, buf + 1, (uint16_t)(n - 1));
        }
        vRingbufferReturnItem(rxq, buf);
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

    WiFi.onEvent([](arduino_event_id_t, arduino_event_info_t info) {
        last_reason = info.wifi_sta_disconnected.reason;
    }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
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
    struct timeval tv = { 0, 100000 };
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    sock_ack = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    rxq = xRingbufferCreate(64 * 1024, RINGBUF_TYPE_NOSPLIT);

    memset(&cam, 0, sizeof(cam));
    cam.sin_family = AF_INET;
    cam.sin_port = htons(WT_CAM_PORT);
    inet_aton(WT_CAM_IP, &cam.sin_addr);
    /* 13.10: приоритет 19 — выше tcpip (18). Очередь UDP в lwip всего 6 пакетов
     * (CONFIG_LWIP_UDP_RECVMBOX_SIZE, ядро собрано заранее), и при приоритете 5 tcpip успевал
     * положить пачку кадра целиком, а остаток выбрасывался: «потери Wi-Fi» были нашими. */
    xTaskCreatePinnedToCore(rx_task, "rx", 4096, NULL, 19, NULL, 1);
}

void loop()
{
    static uint32_t last_meta = 0;
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
    g_conn = conn;

    /* 13.10: включённый раньше камеры приёмник не находил её точку и больше не пробовал —
     * повторяем подключение сами, раз в 10 с без связи. */
    static uint32_t last_try = 0;
    if (conn) {
        last_try = now;
    } else if (now - last_try >= 10000) {
        last_try = now;
        WiFi.disconnect();
        WiFi.begin(WT_SSID, WT_PASS);
    }

    if (now - last_meta >= META_PERIOD_MS) {
        last_meta = now;
        send_meta();
    }
    poll_rx();

    /* раз в секунду, пока идёт заливка: строка текста в USB (просмотрщик кладёт её в ap_console) */
    static uint32_t fl_t = 0, fl_p0 = 0, fl_b0 = 0, fl_l0 = 0;
    if (now - fl_t >= 1000) {
        uint32_t p = fl_pkts, b = fl_bytes, l = fl_lost;
        if (p != fl_p0) {
            wifi_ap_record_t ap;
            int rssi = (conn && esp_wifi_sta_get_ap_info(&ap) == ESP_OK) ? ap.rssi : 0;
            SerialMon.printf("\nFLOOD t=%lu rx_kbps=%lu pkts=%lu lost=%lu rssi=%d\n",
                             (unsigned long)now, (unsigned long)((b - fl_b0) * 8 / (now - fl_t)),
                             (unsigned long)(p - fl_p0), (unsigned long)(l - fl_l0), rssi);
        }
        fl_t = now;
        fl_p0 = p;
        fl_b0 = b;
        fl_l0 = l;
    }

    if (SerialMon.available()) {
        String s = SerialMon.readStringUntil('\n');
        if (s.length() > 1 && s[0] == 'w') {
            /* w <секунд> — камера льёт вместо видео; w 0 — стоп. Трижды: UDP без гарантии. */
            int sec = constrain(s.substring(1).toInt(), 0, 600);
            uint8_t c[3] = { WT_TYPE_CMD, (uint8_t)(sec & 0xff), (uint8_t)(sec >> 8) };
            for (int i = 0; i < 3; i++) {
                sendto(sock_ack, c, sizeof(c), 0, (struct sockaddr *)&cam, sizeof(cam));
                delay(20);
            }
            SerialMon.printf("\nFLOOD cmd %d s\n", sec);
        } else if (s.length() > 1 && s[0] == 'p') {
            tx_power_dbm = constrain(s.substring(1).toInt(), 2, 20);
            wt_set_tx_power(tx_power_dbm);
            /* 13.10: та же мощность камере (трижды: UDP без гарантии) — у неё нет консоли */
            uint8_t c[2] = { WT_TYPE_PWR, (uint8_t)tx_power_dbm };
            for (int i = 0; i < 3; i++) {
                sendto(sock_ack, c, sizeof(c), 0, (struct sockaddr *)&cam, sizeof(cam));
                delay(20);
            }
            SerialMon.printf("\nМощность приёмника и камеры: %d дБм (факт у приёмника %d)\n",
                             tx_power_dbm, wt_get_tx_power());
        }
    }
    delay(1);
}
