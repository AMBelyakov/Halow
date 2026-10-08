/*
 * HalowVideo_STA — плата с камерой (сторона STA).
 *
 * Снимает JPEG, режет на чанки и отправляет их через AT+TXDATA как готовые
 * Ethernet+IPv4+UDP пакеты (сам формат IP/UDP модулю не нужен — это на случай,
 * если RJ45-мост AP когда-нибудь заработает; на практике доставка идёт не через
 * него, а через USB приёмника, см. память thalow-delivery-usb-not-rj45).
 * Разбирает пакеты tools/halow_viewer.py.
 *
 * RSSI своего линка кладётся в заголовок каждого кадра — так метрика доезжает
 * до браузера тем же путём, что и видео.
 *
 * Узкое место всей цепочки — UART ESP32<->TX-AH, жёстко 115200 (~90 кбит/с).
 * Поднять его нельзя: скорость своего конца модуль берёт из своей прошивки
 * (TAIXIN-usb), а AT+BAUDRATE в ней не применяется — подробности в комментарии
 * к AT_BAUD ниже и в памяти thalow-tx-ah-throughput-stability. Кадр держим
 * маленьким ещё и потому, что у модуля течёт внутренняя память ("no skb") —
 * это второе, независимое ограничение сверху.
 */

#include <Arduino.h>
#include "utilities.h"
#include "esp_camera.h"
#include "img_converters.h"   // frame2jpg() — программное сжатие, если сенсор не умеет JPEG
#include "halow_proto.h"

// ---------------------------- настройки ----------------------------

#define HALOW_SSID    "halow_video"  // должен совпадать с прошивкой AP
#define HALOW_BSS_BW  8              // ширина канала, МГц: 1/2/4/8

// MCS для широковещательных кадров (0..7). У broadcast нет автоподбора скорости,
// поэтому это фиксированный компромисс: 7 — максимум скорости, но требует
// хорошего сигнала; на дистанции связь оборвётся резко, без деградации. Для
// замеров дальности лучше 3-4, либо (правильнее) HALOW_UNICAST=1 ниже — тогда
// модуль подбирает MCS сам.
#define HALOW_MCAST_MCS 7

// ВАЖНО про OV5640 на этой плате: аппаратный JPEG-энкодер сенсора виснет и
// отдаёт пустые кадры (esp_camera_fb_get() == NULL) на любом разрешении. Проверено
// на обеих платформах и двух модулях. Рабочий режим — снимать в RGB565 и сжимать
// в JPEG программно через frame2jpg(). В нём кадры идут стабильно.
//
// FRAME_SIZE и JPEG_QUALITY_SW вместе определяют байт/с в дырявый буфер модуля
// (см. память thalow-tx-ah-throughput-stability, "no skb") — разрешение влияет
// сильнее качества. QQVGA(160x120) слишком блочный на весь плеер, QVGA(320x240)
// перегружает модуль, HQVGA(240x176) — рабочая середина. Подбирайте оба значения
// вместе, глядя на fps/КБ/с в мониторе и на частоту обрывов связи.
#define FRAME_SIZE      FRAMESIZE_HQVGA  // QQVGA(160x120) | HQVGA(240x176) | QVGA(320x240)
#define CAM_XCLK_HZ     16000000        // чуть ниже 20 МГц — запас против EV-VSYNC-OVF
#define JPEG_QUALITY_SW 20               // 1..100, меньше — сильнее сжатие и выше fps

// CHUNK_GAP_MS/FRAME_GAP_MS были подобраны на штатных 115200 бод, когда сама
// пересылка байт по UART занимала заметную часть времени кадра. Теперь, когда
// negotiateBaud() поднимает UART до 400000, пересылка стала в разы быстрее, а эти
// паузы — фиксированные и от скорости UART не зависят, поэтому именно они, а не
// UART, стали держать итоговый fps/кбит/с внизу. Пробуем срезать паузы вдвое —
// это эксперимент: если "no skb"/обрывы участятся, здесь и нужно будет отступить
// обратно к 25/150 (см. память thalow-tx-ah-throughput-stability).
#define CHUNK_GAP_MS  12   // было 25 — пауза между чанками, чтобы модуль не захлёбывался
#define FRAME_GAP_MS  80   // было 150 — пауза после каждого кадра

// Скорость UART ESP32 <-> модуль. Никакого согласования: жёстко берём отсюда.
//
// РАЗГОН ЭТОГО КАНАЛА НЕВОЗМОЖЕН — проверено экспериментально, не пытаться снова:
//   1. AT+BAUDRATE=230400 принимается ("OK") и сохраняется между отключениями
//      питания — "AT+BAUDRATE=?" потом честно отвечает "+BAUDRATE:230400".
//   2. Но AT-канал остаётся на 115200: модуль спокойно общается на 115200 сразу
//      после этой команды.
//   3. Решающая проверка: выставили здесь 230400, ПОЛНОСТЬЮ обесточили плату
//      (вынули USB, не Reset — от Reset ESP32 модуль не перезагружается), включили
//      заново. Модуль всё равно стартовал на 115200: в логе мусор от несовпадения
//      скоростей ("raw=\"?fx????~??fx...\"") и FAIL на всех AT-командах.
// Вывод: сохранённое значение относится к другой шине модуля (в PDF-мануале рядом
// с командой перечислены два UART: UART0 A10/A11 и UART1 A12/A13), а не к тому,
// по которому с ним говорит ESP32. Видео идёт через AT+TXDATA по этому же
// AT-каналу, поэтому его потолок ~90 кбит/с этой командой не поднять.
// Подробности: память thalow-tx-ah-throughput-stability.
#define AT_BAUD 115200   // единственное рабочее с прошивкой TAIXIN-usb, см. выше

#define UDP_SPORT     5000
#define UDP_DPORT     5000

#define RSSI_PERIOD_MS  3000
#define STATS_PERIOD_MS 2000

/*
 * Кому адресуем кадры на уровне Ethernet — это ВАЖНО для радио, а не только для
 * доставки. Изначально стоял broadcast (ff:ff:...), и статистика модуля
 * (AT+LMAC_DBGSEL / "LMAC STATUS") показала цену этого решения:
 * "mcast(bw:mcs)=2:0", est_rate ~120-290 кбит/с. Broadcast в Wi-Fi всегда идёт
 * на минимальной скорости, БЕЗ подтверждений (ACK), без переспроса потерянных
 * кадров и без агрегации — отсюда же и наши 12-14% потерь пакетов.
 *
 * Unicast на MAC приёмника включает всё это разом: ACK, ретрансмиссии, авто-MCS
 * (rate adaptation). Для замеров на дистанции это принципиально: broadcast с
 * фиксированным MCS просто обрывается при ослаблении сигнала, а unicast сам
 * плавно сползает на более медленный, но живучий MCS.
 *
 * MAC приёмной платы: спросить у неё AT+MAC_ADDR=? (через HalowPassthrough) или
 * посмотреть на STA-стороне в AT+WNBCFG строку "STA0:[...]" — там MAC партнёра.
 */
// Временно 0: после включения unicast связь стала обрываться заметно чаще, чем
// на broadcast — похоже, ожидание ACK/ретраи на unicast только усугубляют
// нехватку буферов у модуля ("no skb"). Проверяем изолированно: с этим флагом
// в 0 радионастройки (MCAST_BW/MCS/SHORT_GI) остаются, только адресация кадров
// возвращается к broadcast — если стабильность вернётся к прежней, дело именно
// в unicast, и его нужно доводить отдельно (см. thalow-tx-ah-throughput-stability).
#define HALOW_UNICAST 0   // 1 — unicast (ACK+ретраи+авто-MCS, но менее стабильно на практике)

static const uint8_t AP_MAC[6]  = {0xc6, 0xe8, 0x35, 0x70, 0x7a, 0x68};
static const uint8_t BCAST_MAC[6] = {0xff, 0xff, 0xff, 0xff, 0xff, 0xff};
#if HALOW_UNICAST
#define DST_MAC AP_MAC
#else
#define DST_MAC BCAST_MAC
#endif

static const uint8_t SRC_IP[4]  = {10, 10, 10, 2};
static const uint8_t DST_IP[4]  = {255, 255, 255, 255};

// -------------------------------------------------------------------

#define AT_OK    1
#define AT_ERROR 2

static uint8_t src_mac[6] = {0x02, 0x00, 0x00, 0x00, 0x00, 0x01}; // запасной, если AT+MAC_ADDR не ответит
static uint8_t pkt[HALOW_PKT_BUF_LEN];

static bool camera_ok = false;
// Описание камеры дублируем в периодическую строку статуса: стартовый лог
// улетает вверх, а диагноз нужен в любой момент.
static char cam_info[64] = "не инициализирована";
static bool tx_ah_ok = false;
static bool link_up = false;
static int8_t link_rssi = 0;

static uint32_t frame_id = 0;
static uint16_t ip_id = 0;

static uint32_t frames_sent = 0;
static uint32_t bytes_sent = 0;
static uint32_t rssi_tick = 0;
static uint32_t stats_tick = 0;

// Разбивка времени на кадр по стадиям — чтобы понимать, во что реально упирается
// fps: в камеру/сжатие (не связано с риском "no skb" у модуля) или в обмен с
// модулем (связано напрямую). Копится между STATS_PERIOD_MS, печатается в
// той же строке статистики, что и fps/КБ/с, потом сбрасывается.
static uint32_t cam_ms_acc   = 0; // esp_camera_fb_get()
static uint32_t jpeg_ms_acc  = 0; // frame2jpg()
static uint32_t send_ms_acc  = 0; // sendFrame() — все чанки, все AT+TXDATA, без FRAME_GAP_MS
static uint32_t stage_frames = 0; // сколько кадров вошло в накопители выше (для среднего)

//************************************[ TX-AH ]******************************************

static int8_t waitResponse(uint32_t timeout_ms, String &data,
                           const char *r1 = "OK", const char *r2 = "ERROR")
{
    uint32_t start = millis();

    data.reserve(256);
    do {
        while (SerialAT.available() > 0) {
            int c = SerialAT.read();
            if (c < 0) {
                continue;
            }
            data += static_cast<char>(c);

            // Модуль может подмешивать асинхронные сообщения (+RXDATA и т.п.),
            // поэтому не даём буферу расти бесконечно, но хвост сохраняем.
            if (data.length() > 1024) {
                data.remove(0, data.length() - 256);
            }
            if (data.endsWith(r1)) {
                return AT_OK;
            }
            if (data.endsWith(r2)) {
                return AT_ERROR;
            }
        }
    } while (millis() - start < timeout_ms);

    return 0;
}

static int8_t waitResponse(uint32_t timeout_ms = 1000)
{
    String data;
    return waitResponse(timeout_ms, data);
}

static void sendAT(const String &cmd)
{
    // Выбрасываем всё, что осталось в приёмном буфере от прошлых ответов,
    // иначе waitResponse() поймает чужой "OK".
    while (SerialAT.available()) {
        SerialAT.read();
    }
    SerialAT.print("AT" + cmd + "\r\n");
}

// Для команд, которые отвечают НЕ "OK", а произвольным текстом (например
// "+MCAST_BW" -> "tx bw=8 MHz", "+SHORT_GI=1" -> "short GI enabled"). Обычный
// atCommand() на них всегда рапортует FAIL, хотя команда сработала: он ждёт
// именно "OK". Здесь просто печатаем, что реально ответил модуль.
static void atCommandShow(const String &cmd, uint32_t timeout_ms = 400)
{
    sendAT(cmd);

    String data;
    uint32_t start = millis();
    while (millis() - start < timeout_ms) {
        while (SerialAT.available()) {
            data += (char)SerialAT.read();
        }
        delay(1);
    }
    data.trim();
    SerialMon.printf("  AT%s -> %s\n", cmd.c_str(),
                     data.length() ? data.c_str() : "(нет ответа)");
}

static bool atCommand(const String &cmd, uint32_t timeout_ms = 1000)
{
    sendAT(cmd);
    bool ok = (waitResponse(timeout_ms) == AT_OK);
    SerialMon.printf("  AT%s -> %s\n", cmd.c_str(), ok ? "OK" : "FAIL");
    return ok;
}

// Спрашиваем у модуля его собственный MAC — используем как source в Ethernet-заголовке,
// чтобы мост на стороне AP не отбросил кадр с незнакомым отправителем.
static void readModuleMac(void)
{
    String data;

    sendAT("+MAC_ADDR=?");
    if (waitResponse(1000, data) != AT_OK) {
        SerialMon.println("MAC: нет ответа, используем запасной 02:00:00:00:00:01");
        return;
    }

    unsigned int m[6];
    int at = -1;
    for (int i = 0; i + 16 <= (int)data.length(); i++) {
        if (sscanf(data.c_str() + i, "%02x:%02x:%02x:%02x:%02x:%02x",
                   &m[0], &m[1], &m[2], &m[3], &m[4], &m[5]) == 6) {
            at = i;
            break;
        }
    }
    if (at < 0) {
        SerialMon.println("MAC: не разобрали ответ, используем запасной");
        return;
    }
    for (int i = 0; i < 6; i++) {
        src_mac[i] = (uint8_t)m[i];
    }
    SerialMon.printf("MAC модуля: %02x:%02x:%02x:%02x:%02x:%02x\n",
                     src_mac[0], src_mac[1], src_mac[2], src_mac[3], src_mac[4], src_mac[5]);
}

// Открывает UART к модулю на AT_BAUD. Никакого согласования/угадывания: если
// скорость не та, это сразу видно по FAIL на всех AT-командах в TX_AH_init().
static void openAtUart(void)
{
    SerialAT.begin(AT_BAUD, SERIAL_8N1, SERIAL_AT_RXD, SERIAL_AT_TXD);
    SerialMon.printf("UART к модулю: %u бод\n", (unsigned)AT_BAUD);
}

static bool TX_AH_init(void)
{
    int err = 0;

    SerialMon.println("Настройка TX-AH (STA):");
    // Глушит отладочную статистику LMAC, чтобы она не лезла в AT-UART. На части
    // прошивок модуля команда отвечает ERROR — это не мешает работе, поэтому
    // в счётчик ошибок её не берём.
    atCommand("+SYSDBG=LMAC,0");
    // Дебаг сетевого уровня диагностировали и выключили обратно — включали
    // временно (см. git-историю), чтобы поймать причину самопроизвольных
    // +DISCONNECT. Нашли: "malloc fail"/"no skb" — нехватка памяти в самом
    // модуле, а не рассинхрон состояний. В рабочей прошивке не нужен.
    atCommand("+SYSDBG=WNB,0");
    err += atCommand("+BSS_BW=" + String(HALOW_BSS_BW)) ? 0 : 1;
    err += atCommand("+MODE=STA") ? 0 : 1;
    err += atCommand("+KEYMGMT=NONE") ? 0 : 1;
    err += atCommand("+SSID=" HALOW_SSID) ? 0 : 1;

    // Раунд 2 (2026-08-04): AT+MCAST_BW/MCAST_MCS/SHORT_GI подняли est_rate в
    // LMAC STATUS (~120-290 -> ~1300 кбит/с). В первый раз после этого связь резко
    // обрывалась — но платы тогда стояли ~1м друг от друга, где приёмник почти
    // наверняка перегружен (см. память thalow-tx-ah-throughput-stability и более
    // раннюю про положительный RSSI на близкой дистанции). MCS7 — самая
    // требовательная к чистоте сигнала модуляция, ей перегрузка вредит сильнее,
    // чем авто-MCS. Пробуем ещё раз на нормальной дистанции (не вплотную).
    // Если обрыв повторится и на дистанции — версия с "заводским"/тестовым
    // интерфейсом снова в силе, откатывать так же, как в прошлый раз.
    atCommandShow("+MCAST_BW=" + String(HALOW_BSS_BW));
    atCommandShow("+MCAST_MCS=" + String(HALOW_MCAST_MCS));
    atCommandShow("+SHORT_GI=1");

    readModuleMac();

    return err == 0;
}

static void pollLink(void)
{
    String data;

    sendAT("+CONN_STATE");
    int8_t st = waitResponse(1000, data, "+CONNECTED", "+DISCONNECT");
    link_up = (st == AT_OK);
    if (!link_up) {
        link_rssi = 0;
        // Разбираем ДВА разных случая, которые раньше схлопывались в одно
        // "нет связи": AT_ERROR — модуль сам ответил "+DISCONNECT" (реальный
        // разрыв ассоциации на его стороне); 0 — за 1с не пришло ни "+CONNECTED",
        // ни "+DISCONNECT" (таймаут: либо модуль завис/не успел ответить, либо
        // ответ пришёл вперемешку с чем-то ещё и не распознался). Это разные
        // причины и чинятся по-разному, поэтому печатаем сырой ответ модуля.
        SerialMon.printf("LINK poll: %s, raw=\"%s\"\n",
                         st == AT_ERROR ? "+DISCONNECT от модуля" : "нет ответа за 1с (таймаут)",
                         data.c_str());
        return;
    }

    // Ответ модуля: "+RSSI:-30\r\nOK"
    String rssi_data;
    sendAT("+RSSI=1");
    if (waitResponse(1000, rssi_data) != AT_OK) {
        return;
    }
    int at = rssi_data.indexOf("+RSSI:");
    if (at >= 0) {
        link_rssi = (int8_t)rssi_data.substring(at + 6).toInt();
    }
}

//************************************[ CAMERA ]******************************************

static const char *fs_name(framesize_t fs)
{
    switch (fs) {
        case FRAMESIZE_96X96: return "96x96";
        case FRAMESIZE_QQVGA: return "160x120";
        case FRAMESIZE_HQVGA: return "240x176";
        case FRAMESIZE_QVGA:  return "320x240";
        case FRAMESIZE_VGA:   return "640x480";
        case FRAMESIZE_SVGA:  return "800x600";
        default:              return "?";
    }
}

/*
 * Инициализация камеры.
 *
 * Снимаем в RGB565, а НЕ в JPEG: аппаратный JPEG-энкодер OV5640 на этой плате
 * виснет и отдаёт пустые кадры. В RGB565 захват стабилен, а в JPEG кадр мы жмём
 * потом сами через frame2jpg(). Буфер большой (QVGA RGB565 = 150 КБ), поэтому
 * держим его в PSRAM.
 */
static bool camera_init(void)
{
    camera_config_t config;

    memset(&config, 0, sizeof(config));
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = CAMERA_PIN_Y2;
    config.pin_d1 = CAMERA_PIN_Y3;
    config.pin_d2 = CAMERA_PIN_Y4;
    config.pin_d3 = CAMERA_PIN_Y5;
    config.pin_d4 = CAMERA_PIN_Y6;
    config.pin_d5 = CAMERA_PIN_Y7;
    config.pin_d6 = CAMERA_PIN_Y8;
    config.pin_d7 = CAMERA_PIN_Y9;
    config.pin_xclk = CAMERA_PIN_XCLK;
    config.pin_pclk = CAMERA_PIN_PCLK;
    config.pin_vsync = CAMERA_PIN_VSYNC;
    config.pin_href = CAMERA_PIN_HREF;
    config.pin_sccb_sda = CAMERA_PIN_SIOD;
    config.pin_sccb_scl = CAMERA_PIN_SIOC;
    config.pin_pwdn = CAMERA_PIN_PWDN;
    config.pin_reset = CAMERA_PIN_RESET;
    config.xclk_freq_hz = CAM_XCLK_HZ;
    config.pixel_format = PIXFORMAT_RGB565;
    config.frame_size = FRAME_SIZE;

    SerialMon.printf("PSRAM: %s\n", psramFound() ? "есть" : "нет");
    if (psramFound()) {
        // ДВА буфера: пока мы держим кадр на время frame2jpg, сенсор пишет
        // в свободный буфер. Иначе следующий кадр приходит в занятый буфер ->
        // EV-VSYNC-OVF -> драйвер логирует из cam_task -> краш по стеку.
        config.fb_count = 2;
        config.grab_mode = CAMERA_GRAB_LATEST;
        config.fb_location = CAMERA_FB_IN_PSRAM;
    } else {
        // Без PSRAM QVGA RGB565 в DRAM не влезет — падаем на 160x120, один буфер.
        config.fb_count = 1;
        config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
        config.fb_location = CAMERA_FB_IN_DRAM;
        config.frame_size = FRAMESIZE_QQVGA;
    }

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        SerialMon.printf("Камера не поднялась, ошибка 0x%x\n", err);
        snprintf(cam_info, sizeof(cam_info), "НЕ НАЙДЕНА (0x%x)", err);
        return false;
    }

    sensor_t *s = esp_camera_sensor_get();
    camera_sensor_info_t *info = s ? esp_camera_sensor_get_info(&(s->id)) : NULL;
    const char *name = info ? info->name : "?";
    SerialMon.printf("Сенсор: %s (PID 0x%x)\n", name, s ? s->id.PID : 0);
    if (s && s->id.PID == OV5640_PID) {
        s->set_vflip(s, 1);
    }

    snprintf(cam_info, sizeof(cam_info), "%s %s RGB565->JPEG",
             name, fs_name(config.frame_size));
    SerialMon.printf("Режим камеры: %s\n", cam_info);
    return true;
}

//************************************[ ОТПРАВКА ]***************************************

static bool sendChunk(const uint8_t *payload, uint16_t len,
                      uint16_t idx, uint16_t cnt, uint32_t total_len)
{
    halow_app_hdr_t hdr;

    hdr.magic[0] = 'H';
    hdr.magic[1] = 'L';
    hdr.magic[2] = 'W';
    hdr.magic[3] = '1';
    hdr.frame_id = frame_id;
    hdr.frame_len = total_len;
    hdr.chunk_idx = idx;
    hdr.chunk_cnt = cnt;
    hdr.payload_len = len;
    hdr.rssi = link_rssi;
    hdr.flags = (idx + 1 == cnt) ? HALOW_FLAG_LAST : 0;

    int pkt_len = halow_build_packet(pkt, src_mac, DST_MAC, SRC_IP, DST_IP,
                                     UDP_SPORT, UDP_DPORT, ip_id++, &hdr, payload, len);
    if (pkt_len < 0) {
        return false;
    }

    // AT+TXDATA=<len>, ждём OK, только потом отдаём ровно len байт.
    // Таймаут короткий: здоровый OK приходит за десятки мс, а длинный таймаут
    // на неудаче зря тормозил бы весь кадр.
    sendAT("+TXDATA=" + String(pkt_len));
    String txResp;
    int8_t txSt = waitResponse(300, txResp);
    if (txSt != AT_OK) {
        // Тоже разбираем ERROR (модуль ответил, но отказал) от таймаута
        // (модуль вообще не ответил за 300мс — значит был чем-то занят).
        SerialMon.printf("TXDATA чанк %u/%u: %s, raw=\"%s\"\n", idx + 1, cnt,
                         txSt == AT_ERROR ? "ERROR" : "нет ответа за 300мс (таймаут)",
                         txResp.c_str());
        return false;
    }
    SerialAT.write(pkt, pkt_len);
    SerialAT.flush();

    bytes_sent += pkt_len;

    // Даём модулю время передать пакет в эфир и освободить очередь. Без паузы
    // он захлёбывается на 3-м подряд AT+TXDATA и возвращает ERROR.
    delay(CHUNK_GAP_MS);
    return true;
}

static void sendFrame(const uint8_t *buf, uint32_t total_len)
{
    uint16_t cnt = (uint16_t)((total_len + HALOW_MAX_PAYLOAD - 1) / HALOW_MAX_PAYLOAD);

    frame_id++;
    for (uint16_t i = 0; i < cnt; i++) {
        uint32_t off = (uint32_t)i * HALOW_MAX_PAYLOAD;
        uint16_t len = (uint16_t)min((uint32_t)HALOW_MAX_PAYLOAD, total_len - off);

        if (!sendChunk(buf + off, len, i, cnt, total_len)) {
            SerialMon.printf("Кадр %u: чанк %u/%u не ушёл\n", frame_id, i + 1, cnt);
            return; // битый кадр приёмник всё равно отбросит, дожимать смысла нет
        }
    }
    frames_sent++;
}

//************************************[ ARDUINO ]****************************************

void setup()
{
    SerialMon.begin(115200);
    delay(2000);

    SerialMon.println();
    SerialMon.println("=== T-Halow: камера (STA) ===");

    openAtUart();
    pinMode(BOARD_LED, OUTPUT);

    camera_ok = camera_init();
    tx_ah_ok = TX_AH_init();

    SerialMon.printf("Камера: %s, TX-AH: %s\n",
                     camera_ok ? "OK" : "ОШИБКА",
                     tx_ah_ok ? "OK" : "ОШИБКА");
    SerialMon.println("Ждём соединения с AP...");
}

void loop()
{
    if (millis() - rssi_tick > RSSI_PERIOD_MS) {
        rssi_tick = millis();
        // Опрашиваем между кадрами: во время передачи чанка UART занят.
        pollLink();
        digitalWrite(BOARD_LED, link_up);
    }

    if (millis() - stats_tick > STATS_PERIOD_MS) {
        uint32_t dt = millis() - stats_tick;
        stats_tick = millis();
        // Считаем в целых числах (fps*10 и КБ/с*10), без float в printf: dtoa у
        // newlib жрёт много стека, а мы близко к пределу.
        uint32_t fps10 = dt ? frames_sent * 10000u / dt : 0;
        uint32_t kbps10 = dt ? bytes_sent * 10000u / 1024u / dt : 0;
        SerialMon.printf("[%s] RSSI %d dBm | %u.%u fps | %u.%u КБ/с | камера: %s | PSRAM:%s | RAM %u\n",
                         link_up ? "связь" : "нет связи", link_rssi,
                         fps10 / 10, fps10 % 10, kbps10 / 10, kbps10 % 10,
                         cam_info, psramFound() ? "да" : "НЕТ",
                         (unsigned)ESP.getFreeHeap());
        // Средние мс на кадр по стадиям + сколько от них "неучтено" — это как раз
        // FRAME_GAP_MS/CHUNK_GAP_MS плюс накладные расходы цикла loop().
        if (stage_frames) {
            uint32_t cam_avg = cam_ms_acc / stage_frames;
            uint32_t jpeg_avg = jpeg_ms_acc / stage_frames;
            uint32_t send_avg = send_ms_acc / stage_frames;
            uint32_t frame_period = stage_frames ? dt / stage_frames : 0;
            uint32_t gaps_avg = frame_period > (cam_avg + jpeg_avg + send_avg)
                                ? frame_period - (cam_avg + jpeg_avg + send_avg) : 0;
            SerialMon.printf("  STAGE камера %ums | JPEG %ums | AT+TXDATA %ums | "
                             "паузы+прочее %ums | итого на кадр %ums\n",
                             (unsigned)cam_avg, (unsigned)jpeg_avg, (unsigned)send_avg,
                             (unsigned)gaps_avg, (unsigned)frame_period);
        }
        frames_sent = 0;
        bytes_sent = 0;
        cam_ms_acc = jpeg_ms_acc = send_ms_acc = stage_frames = 0;
    }

    if (!link_up || !camera_ok) {
        delay(10);
        return;
    }

    uint32_t t_cam0 = millis();
    camera_fb_t *fb = esp_camera_fb_get();
    uint32_t t_cam1 = millis();
    if (!fb) {
        SerialMon.println("Кадр с камеры не получен");
        delay(10);
        return;
    }

    // Кадр приходит в RGB565 — сжимаем в JPEG программно в отдельный буфер и
    // СРАЗУ возвращаем кадр камере. Иначе, пока мы медленно шлём чанки по UART,
    // cam_task остаётся без свободного буфера и падает по переполнению стека.
    uint8_t *jpg = NULL;
    size_t jpg_len = 0;
    bool ok = frame2jpg(fb, JPEG_QUALITY_SW, &jpg, &jpg_len);
    uint32_t t_jpeg1 = millis();
    esp_camera_fb_return(fb);

    if (ok) {
        sendFrame(jpg, jpg_len);
        uint32_t t_send1 = millis();
        free(jpg);

        cam_ms_acc  += (t_cam1 - t_cam0);
        jpeg_ms_acc += (t_jpeg1 - t_cam1);
        send_ms_acc += (t_send1 - t_jpeg1);
        stage_frames++;

        delay(FRAME_GAP_MS);
    } else {
        SerialMon.println("Не удалось сжать кадр в JPEG");
    }
}
