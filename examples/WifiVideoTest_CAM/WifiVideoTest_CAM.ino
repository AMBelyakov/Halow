/*
 * WifiVideoTest_CAM — плата с камерой, видео по Wi-Fi 2,4 ГГц (IEEE 802.11) самого ESP32-S3.
 *
 * Зачем (09.10). Задание требует сравнить Wi-Fi HaLow с IEEE 802.11 «на идентичной
 * аппаратной платформе», а до сих пор для Wi-Fi был только расчёт по паспорту.
 * Этот скетч гонит тот же видеопоток, что HalowVideoP2P_STA, но через встроенный
 * Wi-Fi той же платы T-HaLow; радиомодуль TX-AH не используется (его UART не трогаем).
 *
 * Что одинаково с HaLow-версией, чтобы сравнение было честным:
 *   - камера OV5640, 480x320, RGB565 и программное сжатие JPEG с тем же качеством 70;
 *   - куски до 1400 байт с тем же заголовком halow_app_hdr_t ('HLW2', CRC всего JPEG);
 *   - камера — точка доступа, приёмник — станция, как в итоговой версии HaLow;
 *   - мощность по умолчанию 14 дБм, как у HaLow (норма для 2,4 ГГц — до 20 дБм ЭИИМ);
 *   - квитанция приёмника на каждый собранный кадр и строка «RTT ср … мин … макс …»;
 *   - лог камеры уходит по воздуху, и halow_viewer.py пишет его так же, как для HaLow.
 * Чего здесь нет: FEC и досылки кусков. Повторы делает MAC Wi-Fi сам.
 *
 * Связка: эта плата (SoftAP) --Wi-Fi--> WifiVideoTest_RX (STA) --USB--> halow_viewer.py.
 *
 * Команды в USB-консоль (115200):
 *   p <дБм>   мощность передатчика, 2..20 (по умолчанию TX_POWER_DBM)
 *   q <1..100> качество JPEG
 *   f <к/с>   предел частоты кадров, 0 — без предела (проверка пропускной способности)
 *   s         состояние
 */

#include <Arduino.h>
#include <errno.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_camera.h>
#include <img_converters.h>
#include <lwip/sockets.h>
#include "utilities.h"
#include "halow_proto.h"
#include "halow_stream.h"
#include "wifi_test_common.h"

// ---------------------------- настройки ----------------------------

#define TX_POWER_DBM   14     // как у HaLow; 20 — предел нормы для 2,4 ГГц
#define JPEG_QUALITY   70     // как JPEG_QUALITY_SW итоговой версии HaLow
#define FPS_LIMIT      5      // как в итоговой версии HaLow (5 к/с на 480x320)
#define STAT_PERIOD_MS 5000   // период строк статистики (как у камеры HaLow)
#define RTT_SLOTS      16     // сколько кадров помним для подсчёта задержки

// ---------------------------- состояние ----------------------------

static int sock = -1;
static struct sockaddr_in peer;          // приёмник; известен после его 'H'
static bool have_peer = false;
static uint32_t peer_seen_ms = 0;

static int tx_power_dbm = TX_POWER_DBM;
static int jpeg_q = JPEG_QUALITY;
static int fps_limit = FPS_LIMIT;

static uint32_t frame_id = 0;
static uint16_t log_seq = 0;

static struct { uint32_t id, t_send, t_cap; } rtt_ring[RTT_SLOTS];

/* за период статистики */
static uint32_t st_frames = 0, st_bytes = 0, st_acks = 0, st_drop = 0;
static uint32_t st_rtt_sum = 0, st_rtt_min = UINT32_MAX, st_rtt_max = 0, st_cap_max = 0;
static uint32_t st_t0 = 0;

static wt_nf_t nf;                       // фон эфира у этой платы (promiscuous)

// ---------------------------- лог: в USB и по воздуху ----------------------------

/* Строка уходит в USB и пакетом 'T' приёмнику (тот отдаёт её в просмотрщик записью 'L'). */
static void cam_log(const char *fmt, ...)
{
    char buf[256];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (n <= 0) {
        return;
    }
    if (n > (int)sizeof(buf) - 1) {
        n = sizeof(buf) - 1;
    }
    SerialMon.write((const uint8_t *)buf, n);
    if (!have_peer) {
        return;
    }
    uint8_t pkt[1 + 2 + sizeof(buf)];
    pkt[0] = WT_TYPE_LOG;
    pkt[1] = (uint8_t)(log_seq & 0xff);
    pkt[2] = (uint8_t)(log_seq >> 8);
    memcpy(pkt + 3, buf, n);
    log_seq++;
    sendto(sock, pkt, 3 + n, 0, (struct sockaddr *)&peer, sizeof(peer));
}

// ---------------------------- камера ----------------------------

static bool camera_init(void)
{
    camera_config_t c;
    memset(&c, 0, sizeof(c));
    c.ledc_channel = LEDC_CHANNEL_0;
    c.ledc_timer = LEDC_TIMER_0;
    c.pin_d0 = CAMERA_PIN_Y2;
    c.pin_d1 = CAMERA_PIN_Y3;
    c.pin_d2 = CAMERA_PIN_Y4;
    c.pin_d3 = CAMERA_PIN_Y5;
    c.pin_d4 = CAMERA_PIN_Y6;
    c.pin_d5 = CAMERA_PIN_Y7;
    c.pin_d6 = CAMERA_PIN_Y8;
    c.pin_d7 = CAMERA_PIN_Y9;
    c.pin_xclk = CAMERA_PIN_XCLK;
    c.pin_pclk = CAMERA_PIN_PCLK;
    c.pin_vsync = CAMERA_PIN_VSYNC;
    c.pin_href = CAMERA_PIN_HREF;
    c.pin_sccb_sda = CAMERA_PIN_SIOD;
    c.pin_sccb_scl = CAMERA_PIN_SIOC;
    c.pin_pwdn = CAMERA_PIN_PWDN;
    c.pin_reset = CAMERA_PIN_RESET;
    c.xclk_freq_hz = XCLK_FREQ_HZ;
    c.pixel_format = PIXFORMAT_RGB565;   // как в итоговой версии: сжатие программное
    c.frame_size = FRAMESIZE_HVGA;       // 480x320
    c.fb_count = 3;
    c.fb_location = CAMERA_FB_IN_PSRAM;
    c.grab_mode = CAMERA_GRAB_WHEN_EMPTY; // только дописанные кадры, см. HalowVideoP2P_STA
    if (esp_camera_init(&c) != ESP_OK) {
        return false;
    }
    sensor_t *s = esp_camera_sensor_get();
    if (s) {
        s->set_vflip(s, 1);
    }
    return true;
}

// ---------------------------- отправка кадра ----------------------------

/* Отправка с повтором при переполнении очереди lwip: ENOMEM — не потеря в эфире. */
static bool send_pkt(const uint8_t *p, int len)
{
    for (int i = 0; i < 50; i++) {
        if (sendto(sock, p, len, 0, (struct sockaddr *)&peer, sizeof(peer)) == len) {
            return true;
        }
        if (errno != ENOMEM && errno != EAGAIN) {
            return false;
        }
        delay(1);
    }
    return false;
}

static void send_frame(const uint8_t *jpg, size_t len, uint32_t t_cap)
{
    static uint8_t pkt[1 + HALOW_APP_HDR_LEN + HALOW_MAX_PAYLOAD];
    uint16_t cnt = (uint16_t)((len + HALOW_MAX_PAYLOAD - 1) / HALOW_MAX_PAYLOAD);
    uint16_t crc = halow_crc16(jpg, (uint16_t)len);   // JPEG 480x320 заведомо < 64 КБ
    int8_t rssi = (int8_t)wt_ap_sta_rssi();
    uint32_t id = ++frame_id;
    uint32_t t_send = millis();

    rtt_ring[id % RTT_SLOTS] = { id, t_send, t_cap };
    for (uint16_t i = 0; i < cnt; i++) {
        size_t off = (size_t)i * HALOW_MAX_PAYLOAD;
        uint16_t plen = (uint16_t)min((size_t)HALOW_MAX_PAYLOAD, len - off);
        halow_app_hdr_t h;
        memcpy(h.magic, "HLW2", 4);
        h.frame_id = id;
        h.frame_len = (uint32_t)len;
        h.chunk_idx = i;
        h.chunk_cnt = cnt;
        h.payload_len = plen;
        h.frame_crc = crc;
        h.rssi = rssi;
        h.flags = (i == cnt - 1) ? HALOW_FLAG_LAST : 0;
        pkt[0] = WT_TYPE_VIDEO;
        memcpy(pkt + 1, &h, HALOW_APP_HDR_LEN);
        memcpy(pkt + 1 + HALOW_APP_HDR_LEN, jpg + off, plen);
        if (!send_pkt(pkt, 1 + HALOW_APP_HDR_LEN + plen)) {
            st_drop++;
        }
    }
    st_frames++;
    st_bytes += len;
}

// ---------------------------- приём: hello и квитанции ----------------------------

static void poll_rx(void)
{
    uint8_t buf[64];
    struct sockaddr_in from;
    socklen_t fl = sizeof(from);
    int n;

    while ((n = recvfrom(sock, buf, sizeof(buf), MSG_DONTWAIT, (struct sockaddr *)&from, &fl)) > 0) {
        if (buf[0] == WT_TYPE_HELLO) {
            if (!have_peer || peer.sin_addr.s_addr != from.sin_addr.s_addr) {
                SerialMon.printf("Приёмник: %s\n", inet_ntoa(from.sin_addr));
            }
            peer = from;
            have_peer = true;
            peer_seen_ms = millis();
        } else if (buf[0] == WT_TYPE_ACK && n >= 5) {
            uint32_t id;
            memcpy(&id, buf + 1, 4);
            if (rtt_ring[id % RTT_SLOTS].id == id) {
                uint32_t now = millis();
                uint32_t rtt = now - rtt_ring[id % RTT_SLOTS].t_send;
                uint32_t cap = now - rtt_ring[id % RTT_SLOTS].t_cap;
                rtt_ring[id % RTT_SLOTS].id = 0;
                st_acks++;
                st_rtt_sum += rtt;
                st_rtt_min = min(st_rtt_min, rtt);
                st_rtt_max = max(st_rtt_max, rtt);
                st_cap_max = max(st_cap_max, cap);
            }
        }
        fl = sizeof(from);
    }
    if (have_peer && millis() - peer_seen_ms > 5000) {
        have_peer = false;              // приёмник пропал: hello шлёт раз в секунду
    }
}

// ---------------------------- статистика ----------------------------

static void stats(void)
{
    uint32_t now = millis();
    float dt = (now - st_t0) / 1000.0f;
    if (dt <= 0) {
        return;
    }
    int rssi = wt_ap_sta_rssi();
    int nfl = wt_nf_take(&nf);
    cam_log("[%s] %.1f fps %lu кбит/с, кадров %lu, отказов отправки %lu\n",
         have_peer ? "связь" : "нет связи", st_frames / dt,
         (unsigned long)(st_bytes * 8 / 1000 / dt), (unsigned long)st_frames,
         (unsigned long)st_drop);
    if (st_acks) {
        cam_log("RTT ср %lu мин %lu макс %lu мс | съёмка->подтверждение макс %lu мс | квитанций %lu из %lu\n",
             (unsigned long)(st_rtt_sum / st_acks), (unsigned long)st_rtt_min,
             (unsigned long)st_rtt_max, (unsigned long)st_cap_max,
             (unsigned long)st_acks, (unsigned long)st_frames);
    }
    /* snr — запас над фоном у этой платы; nf=0 — фон не измерен */
    cam_log("WIFI rssi=%d nf=%d snr=%d pwr=%d ch=%d q=%d fps_lim=%d\n", rssi, nfl,
         (rssi && nfl) ? rssi - nfl : 0, tx_power_dbm, WT_CHANNEL, jpeg_q, fps_limit);
    st_frames = st_bytes = st_acks = st_drop = st_rtt_sum = st_rtt_max = st_cap_max = 0;
    st_rtt_min = UINT32_MAX;
    st_t0 = now;
}

// ---------------------------- консоль ----------------------------

static void console(void)
{
    static char line[32];
    static uint8_t n = 0;
    while (SerialMon.available()) {
        char ch = (char)SerialMon.read();
        if (ch != '\n' && ch != '\r') {
            if (n < sizeof(line) - 1) {
                line[n++] = ch;
            }
            continue;
        }
        line[n] = 0;
        n = 0;
        int v = atoi(line + 1);
        switch (line[0]) {
        case 'p':
            tx_power_dbm = constrain(v, 2, 20);
            wt_set_tx_power(tx_power_dbm);
            cam_log("МОЩНОСТЬ: %d дБм (факт %d)\n", tx_power_dbm, wt_get_tx_power());
            break;
        case 'q':
            jpeg_q = constrain(v, 1, 100);
            cam_log("КАЧЕСТВО: %d\n", jpeg_q);
            break;
        case 'f':
            fps_limit = constrain(v, 0, 30);
            cam_log("ПРЕДЕЛ ЧАСТОТЫ: %d к/с (0 — без предела)\n", fps_limit);
            break;
        case 's':
            cam_log("СОСТОЯНИЕ: приёмник %s, мощность %d дБм, канал %d, режим %s\n",
                 have_peer ? inet_ntoa(peer.sin_addr) : "нет", wt_get_tx_power(), WT_CHANNEL,
                 WT_PROTO_NAME);
            break;
        default:
            break;
        }
    }
}

// ---------------------------- setup / loop ----------------------------

void setup()
{
    SerialMon.begin(115200);
    SerialMon.setTxTimeoutMs(0);         // камера обычно от powerbank: без хоста не ждать
    delay(1500);
    SerialMon.println("\n=== T-Halow: камера, видео по Wi-Fi 2,4 ГГц (тест сравнения) ===");

    if (!camera_init()) {
        SerialMon.println("Камера: ошибка инициализации, стоп");
        while (true) {
            delay(1000);
        }
    }

    WiFi.mode(WIFI_AP);
    wt_set_protocol(WIFI_IF_AP);
    WiFi.softAP(WT_SSID, WT_PASS, WT_CHANNEL, 0, 1);
    esp_wifi_set_bandwidth(WIFI_IF_AP, WIFI_BW_HT20);
    wt_set_tx_power(tx_power_dbm);
    wt_nf_start(&nf);
    SerialMon.printf("Точка доступа %s, канал %d, режим %s, мощность %d дБм, IP %s\n", WT_SSID,
                     WT_CHANNEL, WT_PROTO_NAME, wt_get_tx_power(),
                     WiFi.softAPIP().toString().c_str());

    sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    struct sockaddr_in a = {};
    a.sin_family = AF_INET;
    a.sin_port = htons(WT_CAM_PORT);
    a.sin_addr.s_addr = htonl(INADDR_ANY);
    bind(sock, (struct sockaddr *)&a, sizeof(a));
    st_t0 = millis();
}

void loop()
{
    static uint32_t next_frame = 0;
    static uint32_t last_stat = 0;

    console();
    poll_rx();

    uint32_t now = millis();
    if (now - last_stat >= STAT_PERIOD_MS) {
        last_stat = now;
        stats();
    }
    if (!have_peer || (fps_limit && (int32_t)(now - next_frame) < 0)) {
        delay(1);
        return;
    }
    next_frame = now + (fps_limit ? 1000 / fps_limit : 0);

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        return;
    }
    uint32_t t_cap = millis();
    uint8_t *jpg = NULL;
    size_t jlen = 0;
    bool ok = fmt2jpg(fb->buf, fb->len, fb->width, fb->height, PIXFORMAT_RGB565,
                      (uint8_t)jpeg_q, &jpg, &jlen);
    esp_camera_fb_return(fb);
    if (ok && jlen) {
        send_frame(jpg, jlen, t_cap);
    }
    free(jpg);
}
