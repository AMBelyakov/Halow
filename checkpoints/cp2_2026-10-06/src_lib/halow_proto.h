#pragma once

#include <stdint.h>
#include <string.h>

/*
 * Формат пакета видеопотока T-Halow.
 *
 * Штатная прошивка TX-AH собрана в режиме "один-ко-многим" (WNB_STA_COUNT=8),
 * поэтому AT+TXDATA принимает не сырые данные, а готовый Ethernet-кадр:
 * первые 14 байт обязаны быть Ethernet-заголовком, и длина в AT+TXDATA=<len>
 * его включает.
 *
 * Модуль AP мостит эфир в свой Ethernet-порт (IP101G/RJ45), поэтому если внутри
 * Ethernet-кадра собрать настоящие IPv4+UDP заголовки, то ПК, воткнутый патч-кордом
 * в приёмную плату, получит обычную UDP-датаграмму. Никаких raw-сокетов,
 * Npcap и прав администратора на стороне ПК не требуется.
 *
 *   [Ethernet 14][IPv4 20][UDP 8][halow_app_hdr_t 20][кусок JPEG]
 *
 * Лимит модуля — 1500 байт на пакет вместе с Ethernet-заголовком.
 */

#define HALOW_ETH_HDR_LEN 14
#define HALOW_IP_HDR_LEN  20
#define HALOW_UDP_HDR_LEN 8
#define HALOW_APP_HDR_LEN 22
#define HALOW_HDRS_LEN    (HALOW_ETH_HDR_LEN + HALOW_IP_HDR_LEN + HALOW_UDP_HDR_LEN + HALOW_APP_HDR_LEN)

/* 62 + 1400 = 1462, с запасом влезает в 1500 */
#define HALOW_MAX_PAYLOAD 1400
#define HALOW_PKT_BUF_LEN (HALOW_HDRS_LEN + HALOW_MAX_PAYLOAD)

#define HALOW_FLAG_LAST 0x01

/*
 * Кадрирование USB-моста приёмника (AP -> ПК).
 *
 * Штатный Ethernet-мост модуля НЕ выпускает в RJ45 кадры, которые мы сами
 * инжектировали через AT+TXDATA (проверено: адаптер на ПК видит 0 байт, а на
 * UART приёмника те же кадры исправно приходят как "+RXDATA"). Поэтому доставку
 * до ПК ведём через USB приёмника: HalowVideo_AP вычленяет из "+RXDATA" наш
 * прикладной пакет и гонит его в USB-Serial, а tools/halow_viewer.py читает
 * COM-порт вместо UDP.
 *
 * Поток из USB приёмника — это последовательность записей:
 *   [0xA5][0x5A][type][len_lo][len_hi][payload(len байт)]
 * Просмотрщик ресинхронизируется по двухбайтовому маркеру 0xA5 0x5A.
 *   type 'V' — видеопакет: halow_app_hdr_t + кусок JPEG (ровно то, что ждёт
 *              on_packet() просмотрщика, т.е. Ethernet/IP/UDP уже сняты).
 *   type 'M' — строка JSON с метриками приёмника, например
 *              {"role":"ap","conn":1,"rssi":-34}.
 */
#define HALOW_USB_SYNC0      0xA5
#define HALOW_USB_SYNC1      0x5A
#define HALOW_USB_TYPE_VIDEO 'V'
#define HALOW_USB_TYPE_META  'M'
#define HALOW_USB_TYPE_LOG   'L'   /* 28.09: тело пакета 'T' камеры как есть (seq + текст) */

/* Смещение payload_len внутри halow_app_hdr_t (magic4+frame_id4+frame_len4+idx2+cnt2) */
#define HALOW_APP_OFF_PAYLOAD_LEN 16

/*
 * Прикладной заголовок, little-endian (его же разбирает tools/halow_viewer.py).
 *
 * Метка 'HLW2' с 15.08: добавлено поле frame_crc. Оно закрывает последнюю
 * дыру в цепочке проверок. Раньше каждое звено проверялось по отдельности —
 * пакет по радио, запись по USB — но никто не проверял КАДР ЦЕЛИКОМ, уже
 * собранный из чанков. Теперь камера считает CRC всего JPEG, а просмотрщик
 * сверяет её после склейки: совпало значит показанный кадр побайтно тот же,
 * что уехал с камеры, и любые артефакты на нём родом из камеры, а не из
 * доставки. Не совпало — дыра у нас, и видно сразу.
 *
 * Старые скетчи HalowVideo_AP|STA рассчитаны на 20-байтовый заголовок и с
 * новым просмотрщиком несовместимы. Они и так нерабочие: AT+TXDATA, на
 * котором они держались, в SDK 2.4 отсутствует.
 */
typedef struct __attribute__((packed)) {
    uint8_t  magic[4];    /* 'H','L','W','2' */
    uint32_t frame_id;
    uint32_t frame_len;   /* полный размер JPEG, чтобы приёмник сразу знал сколько ждать */
    uint16_t chunk_idx;
    uint16_t chunk_cnt;
    uint16_t payload_len;
    uint16_t frame_crc;   /* CRC16-CCITT всего JPEG — сквозная проверка кадра */
    int8_t   rssi;        /* RSSI со стороны камеры, dBm; 0 = неизвестно */
    uint8_t  flags;
} halow_app_hdr_t;

static inline void halow_put_be16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v >> 8);
    p[1] = (uint8_t)(v & 0xff);
}

static inline uint16_t halow_checksum16(const uint8_t *p, int len)
{
    uint32_t sum = 0;
    int i;

    for (i = 0; i + 1 < len; i += 2) {
        sum += ((uint32_t)p[i] << 8) | p[i + 1];
    }
    if (i < len) {
        sum += (uint32_t)p[i] << 8;
    }
    while (sum >> 16) {
        sum = (sum & 0xffff) + (sum >> 16);
    }
    return (uint16_t)(~sum);
}

/*
 * Собирает один готовый к отправке пакет в out (размер буфера >= HALOW_PKT_BUF_LEN).
 * Возвращает полную длину пакета — ровно её нужно передать в AT+TXDATA=<len>.
 */
static inline int halow_build_packet(uint8_t *out,
                                     const uint8_t src_mac[6], const uint8_t dst_mac[6],
                                     const uint8_t src_ip[4], const uint8_t dst_ip[4],
                                     uint16_t sport, uint16_t dport, uint16_t ip_id,
                                     const halow_app_hdr_t *app,
                                     const uint8_t *payload, uint16_t payload_len)
{
    uint8_t *eth = out;
    uint8_t *ip  = out + HALOW_ETH_HDR_LEN;
    uint8_t *udp = ip + HALOW_IP_HDR_LEN;
    uint8_t *app_out = udp + HALOW_UDP_HDR_LEN;
    uint16_t udp_len = (uint16_t)(HALOW_UDP_HDR_LEN + HALOW_APP_HDR_LEN + payload_len);
    uint16_t ip_len  = (uint16_t)(HALOW_IP_HDR_LEN + udp_len);

    if (payload_len > HALOW_MAX_PAYLOAD) {
        return -1;
    }

    memcpy(eth + 0, dst_mac, 6);
    memcpy(eth + 6, src_mac, 6);
    halow_put_be16(eth + 12, 0x0800); /* IPv4 */

    ip[0] = 0x45;                     /* версия 4, IHL 5 слов */
    ip[1] = 0x00;                     /* DSCP/ECN */
    halow_put_be16(ip + 2, ip_len);
    halow_put_be16(ip + 4, ip_id);
    halow_put_be16(ip + 6, 0x0000);   /* без фрагментации: режем сами */
    ip[8]  = 64;                      /* TTL */
    ip[9]  = 17;                      /* UDP */
    ip[10] = 0;                       /* контрольная сумма, считается ниже */
    ip[11] = 0;
    memcpy(ip + 12, src_ip, 4);
    memcpy(ip + 16, dst_ip, 4);
    halow_put_be16(ip + 10, halow_checksum16(ip, HALOW_IP_HDR_LEN));

    halow_put_be16(udp + 0, sport);
    halow_put_be16(udp + 2, dport);
    halow_put_be16(udp + 4, udp_len);
    halow_put_be16(udp + 6, 0x0000);  /* в IPv4 контрольная сумма UDP необязательна */

    memcpy(app_out, app, HALOW_APP_HDR_LEN);
    memcpy(app_out + HALOW_APP_HDR_LEN, payload, payload_len);

    return HALOW_HDRS_LEN + payload_len;
}
