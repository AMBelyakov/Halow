#pragma once
/*
 * Общее для пары скетчей теста Wi-Fi 2,4 ГГц (WifiVideoTest_CAM / WifiVideoTest_RX), 09.10.
 *
 * Пакеты по UDP, первый байт — тип:
 *   'V' камера -> приёмник: halow_app_hdr_t + кусок JPEG (как у HaLow-версии);
 *   'T' камера -> приёмник: seq(2, LE) + строка лога камеры;
 *   'H' приёмник -> камера: «я здесь», раз в секунду (камера берёт из него адрес);
 *   'A' приёмник -> камера: frame_id(4, LE) собранного кадра — квитанция для RTT.
 * Приёмник отдаёт 'V' и 'T' в USB теми же записями, что HalowVideoP2P_AP ('V', 'L', 'M'),
 * поэтому tools/halow_viewer.py работает без правок.
 */

#include <Arduino.h>
#include <esp_wifi.h>

#define WT_SSID      "THALOW-WIFI-TEST"
#define WT_PASS      "halowtest1"
/* Канал 2,4 ГГц: выбрать наименее занятый на месте опыта (1, 6 или 11). Одинаков у обеих плат
 * автоматически: станция идёт на канал точки доступа. */
#define WT_CHANNEL   6
#define WT_CAM_PORT  5001
#define WT_RX_PORT   5000
#define WT_CAM_IP    "192.168.4.1"

/*
 * Режим физического уровня (на обеих платах одинаковый):
 *   0 — 802.11b/g/n (обычный Wi-Fi, скорость выбирает сам драйвер);
 *   1 — только 802.11b (1–11 Мбит/с, чувствительность −98,4 дБм на 1 Мбит/с);
 *   2 — Espressif LR (собственный дальнобойный режим, 0,25–0,5 Мбит/с; не IEEE 802.11).
 */
#define WT_PROTO 0

#if WT_PROTO == 1
#define WT_PROTO_NAME "802.11b"
#define WT_PROTO_MASK (WIFI_PROTOCOL_11B)
#elif WT_PROTO == 2
#define WT_PROTO_NAME "Espressif LR"
#define WT_PROTO_MASK (WIFI_PROTOCOL_LR)
#else
#define WT_PROTO_NAME "802.11b/g/n"
#define WT_PROTO_MASK (WIFI_PROTOCOL_11B | WIFI_PROTOCOL_11G | WIFI_PROTOCOL_11N)
#endif

/* Фон эфира по служебному полю принятых пакетов (режим promiscuous). 0 — не мерить. */
#define WT_MEASURE_NF 1

#define WT_TYPE_VIDEO 'V'
#define WT_TYPE_LOG   'T'
#define WT_TYPE_HELLO 'H'
#define WT_TYPE_ACK   'A'

static inline void wt_set_protocol(wifi_interface_t ifx)
{
    esp_wifi_set_protocol(ifx, WT_PROTO_MASK);
}

/* Мощность в дБм; драйвер принимает в единицах 0,25 дБм, диапазон 8..84 (2..21 дБм). */
static inline void wt_set_tx_power(int dbm)
{
    esp_wifi_set_max_tx_power((int8_t)constrain(dbm * 4, 8, 84));
}

static inline int wt_get_tx_power(void)
{
    int8_t p = 0;
    esp_wifi_get_max_tx_power(&p);
    return p / 4;
}

/* RSSI станции на точке доступа (камера); 0 — станций нет. */
static inline int wt_ap_sta_rssi(void)
{
    wifi_sta_list_t l;
    if (esp_wifi_ap_get_sta_list(&l) != ESP_OK || l.num == 0) {
        return 0;
    }
    return l.sta[0].rssi;
}

/* ---- фон эфира ---- */

typedef struct {
    volatile int32_t sum;
    volatile uint32_t n;
} wt_nf_t;

static wt_nf_t *wt_nf_ptr = NULL;

static void wt_nf_cb(void *buf, wifi_promiscuous_pkt_type_t type)
{
    (void)type;
    const wifi_promiscuous_pkt_t *p = (const wifi_promiscuous_pkt_t *)buf;
    if (wt_nf_ptr && p->rx_ctrl.noise_floor) {
        wt_nf_ptr->sum += p->rx_ctrl.noise_floor;
        wt_nf_ptr->n++;
    }
}

/* Включить сбор после запуска Wi-Fi. Единицы поля — дБм; если на практике выйдут значения
 * ниже −150, это единицы 0,25 дБм и их надо делить на 4 (проверить по первому прогону). */
static inline void wt_nf_start(wt_nf_t *nf)
{
#if WT_MEASURE_NF
    nf->sum = 0;
    nf->n = 0;
    wt_nf_ptr = nf;
    wifi_promiscuous_filter_t f;
    f.filter_mask = WIFI_PROMIS_FILTER_MASK_MGMT | WIFI_PROMIS_FILTER_MASK_DATA;
    esp_wifi_set_promiscuous_filter(&f);
    esp_wifi_set_promiscuous_rx_cb(wt_nf_cb);
    esp_wifi_set_promiscuous(true);
#else
    (void)nf;
#endif
}

/* Средний фон за период и сброс; 0 — пакетов не было или замер выключен. */
static inline int wt_nf_take(wt_nf_t *nf)
{
    uint32_t n = nf->n;
    int32_t s = nf->sum;
    nf->sum = 0;
    nf->n = 0;
    return n ? (int)(s / (int32_t)n) : 0;
}
