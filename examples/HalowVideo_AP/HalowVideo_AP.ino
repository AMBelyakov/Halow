/*
 * HalowVideo_AP — приёмная плата (сторона AP).
 *
 * ВАЖНО про доставку до ПК. Изначально расчёт был на штатный Ethernet-мост
 * модуля: кадры от камеры должны были сами уходить из эфира в RJ45 и дальше на
 * сетевую карту ПК как обычный UDP. На практике мост НЕ выпускает в RJ45 кадры,
 * которые STA инжектировала через AT+TXDATA (адаптер на ПК показывает «Принято:
 * 0»), хотя на UART этого приёмника те же кадры исправно приходят как "+RXDATA"
 * (диагностика показала растущий счётчик +RXDATA). Поэтому доставку до ПК ведём
 * через USB приёмника:
 *
 *   эфир --> модуль AP --UART("+RXDATA")--> этот ESP32 --USB--> ПК (halow_viewer.py)
 *
 * Что делает прошивка:
 *   1. поднимает модуль в режиме AP с нужным SSID и полосой;
 *   2. вычленяет из "+RXDATA" наш прикладной пакет (halow_app_hdr_t + кусок JPEG)
 *      и гонит его в USB-Serial с простым кадрированием (см. halow_proto.h);
 *   3. раз в пару секунд шлёт метрики (conn/RSSI) тем же потоком записью 'M';
 *   4. показывает состояние на OLED, если он распаян.
 *
 * ESP32-S3 не имеет Ethernet-MAC, а RJ45 на плате принадлежит HaLow-модулю,
 * поэтому никакого ETH.begin() здесь нет и быть не может.
 */

#include <Arduino.h>
#include "utilities.h"
#include "halow_proto.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ---------------------------- настройки ----------------------------

#define HALOW_SSID   "halow_video"  // должен совпадать с прошивкой STA
#define HALOW_BSS_BW 8              // ширина канала, МГц: 1/2/4/8

// MCS широковещательных кадров (0..7) — держать таким же, как на STA.
// Подробности компромисса см. в комментарии HalowVideo_STA.ino.
#define HALOW_MCAST_MCS 7

#define POLL_PERIOD_MS 2000

// Сторож "протухшей" ассоциации — ВЫКЛЮЧЕН. Задумывался на случай, если AP
// держит "+CONNECTED" сколько угодно долго без новых "+RXDATA" из-за протухшей
// записи об ассоциации. Настоящая причина обрывов оказалась другой — утечка
// памяти в самом модуле STA ("no skb", см. память thalow-tx-ah-throughput-
// stability), которая лечится только сбросом питания STA, а не AT-командами на
// AP. Код оставлен на будущее (вдруг пригодится для другого сценария), но сейчас
// от него только вред: дёргает AT+MODE=AP на живом AP и заставляет conn
// дребезжать 0/1 без пользы.
#define AP_WATCHDOG_ENABLED 0
#define STALE_RX_TIMEOUT_MS 15000

// Максимальный размер одного "+RXDATA": наш пакет — HALOW_HDRS_LEN(62)+1400=1462,
// с запасом на возможный Ethernet-заголовок от модуля. Что больше — отбрасываем.
#define RX_BUF_LEN 2048

// Скорость UART ESP32 <-> модуль, жёстко (подробности и методика проверки — в
// HalowVideo_STA.ino). У AP свой модуль и своя UART-пара, значение не обязано
// совпадать со STA. Менять только вместе с ПОЛНЫМ обесточиванием платы: модуль
// подхватывает сохранённое AT+BAUDRATE только при своей загрузке, а Reset на
// ESP32 его не перезагружает.
#define AT_BAUD 115200   // 115200 — штатное; 230400 — проверяемое

// -------------------------------------------------------------------

#define AT_OK    1
#define AT_ERROR 2

static Adafruit_SSD1306 display(128, 64, &Wire);

static bool oled_ok = false;
static bool tx_ah_ok = false;
static bool link_up = false;
static int8_t link_rssi = 0;

static uint32_t poll_tick = 0;
static bool led_state = false;

static uint32_t frames_fwd = 0;   // сколько видеопакетов отдали в USB

static uint32_t last_progress_ms = 0;      // millis() последнего роста rxdata_hdrs
static uint32_t last_rxdata_hdrs_seen = 0;
static uint32_t watchdog_resets = 0;

// --- диагностика: видно обычным монитором порта (просмотрщик её пропускает) ---
static uint32_t rxdata_hdrs = 0;  // сколько строк "+RXDATA:" разобрали
static int      last_rx_len = 0;  // длина последнего "+RXDATA"
static int      last_hlw_off = -2; // -2: ещё не было; -1: магию HLW1 не нашли; >=0: смещение
static uint32_t rx_total = 0;     // всего байт прочитано с UART модуля (решающий счётчик)
static uint8_t  dbg_buf[32];      // последние байты UART для hex-дампа (когда +RXDATA нет)
static uint8_t  dbg_idx = 0;

//****************************[ USB: кадрирование в ПК ]*********************************

// Одна запись потока: [0xA5][0x5A][type][len_lo][len_hi][payload].
static void usbSendRecord(char type, const uint8_t *data, uint16_t len)
{
    uint8_t hdr[5];
    hdr[0] = HALOW_USB_SYNC0;
    hdr[1] = HALOW_USB_SYNC1;
    hdr[2] = (uint8_t)type;
    hdr[3] = (uint8_t)(len & 0xff);
    hdr[4] = (uint8_t)(len >> 8);
    SerialMon.write(hdr, sizeof(hdr));
    if (len) {
        SerialMon.write(data, len);
    }
}

// Из сырых байт "+RXDATA" вычленяем прикладной пакет: ищем магию "HLW1" (так
// работает независимо от того, оставляет модуль Ethernet/IP/UDP-заголовки или
// уже снял их) и отдаём в USB ровно halow_app_hdr_t + payload_len байт.
static void forwardVideo(const uint8_t *buf, int len)
{
    int off = -1;
    for (int i = 0; i + HALOW_APP_HDR_LEN <= len; i++) {
        if (buf[i] == 'H' && buf[i + 1] == 'L' && buf[i + 2] == 'W' && buf[i + 3] == '1') {
            off = i;
            break;
        }
    }
    last_hlw_off = off;
    if (off < 0) {
        return; // не наш пакет (или заголовок бьётся) — молча пропускаем
    }

    uint16_t payload_len = (uint16_t)buf[off + HALOW_APP_OFF_PAYLOAD_LEN] |
                           ((uint16_t)buf[off + HALOW_APP_OFF_PAYLOAD_LEN + 1] << 8);
    int total = HALOW_APP_HDR_LEN + payload_len;
    if (payload_len > HALOW_MAX_PAYLOAD || off + total > len) {
        return; // длина не сходится с тем, что реально пришло
    }

    usbSendRecord(HALOW_USB_TYPE_VIDEO, buf + off, (uint16_t)total);
    frames_fwd++;
}

//************************[ TX-AH: единый разбор UART модуля ]***************************

// Весь приём с SerialAT идёт через pumpAT(): он же вычленяет бинарные "+RXDATA",
// он же копит текстовые ответы AT в atResp. Так опрос RSSI (atExchange) не глотает
// видеокадры — они продолжают форвардиться прямо во время ожидания ответа.

static uint8_t  rx_buf[RX_BUF_LEN];
static int      rx_len = 0;
static int      rx_need = 0;
static bool     rx_binary = false;
static bool     rx_discard = false;   // "+RXDATA" длиннее буфера — глотаем вхолостую
static String   at_line;              // накопитель текущей текстовой строки
static String   at_resp;              // накопленные текстовые ответы AT для atExchange

static void pumpAT(void)
{
    while (SerialAT.available()) {
        if (!rx_binary) {
            int ci = SerialAT.read();
            if (ci < 0) {
                break;
            }
            char c = (char)ci;
            rx_total++;
            dbg_buf[dbg_idx++ & 31] = (uint8_t)c;
            at_line += c;
            if (at_line.length() > 300) {
                at_line.remove(0, at_line.length() - 64);
            }
            if (c == '\n') {
                String l = at_line;
                l.trim();
                at_line = "";
                if (l.startsWith("+RXDATA")) {
                    // Формат обычно "+RXDATA:<meta>,<len>", но у разных прошивок
                    // модуля разделитель бывает ':' или '='. Берём длину как
                    // ПОСЛЕДНЕЕ число в строке — так разбор не зависит от формата.
                    int end = l.length();
                    while (end > 0 && !(l[end - 1] >= '0' && l[end - 1] <= '9')) {
                        end--;
                    }
                    int start = end;
                    while (start > 0 && l[start - 1] >= '0' && l[start - 1] <= '9') {
                        start--;
                    }
                    int need = (end > start) ? l.substring(start, end).toInt() : 0;
                    if (need > 0) {
                        rxdata_hdrs++;
                        last_rx_len = need;
                        rx_binary = true;
                        rx_len = 0;
                        rx_need = need;
                        rx_discard = (need > RX_BUF_LEN);
                    }
                } else if (l.length()) {
                    at_resp += l;
                    at_resp += '\n';
                    if (at_resp.length() > 512) {
                        at_resp.remove(0, at_resp.length() - 128);
                    }
                }
            }
        } else {
            int avail = SerialAT.available();
            if (avail <= 0) {
                break;
            }
            if (rx_discard) {
                // Отбрасываем неожиданно длинный кадр, но синхронизацию держим:
                // ровно rx_need байт уходят в никуда.
                int drop = min(avail, rx_need - rx_len);
                for (int i = 0; i < drop; i++) {
                    SerialAT.read();
                }
                rx_total += drop;
                rx_len += drop;
            } else {
                int want = min(avail, rx_need - rx_len);
                int n = SerialAT.read(rx_buf + rx_len, want);
                if (n <= 0) {
                    break;
                }
                rx_total += n;
                rx_len += n;
            }
            if (rx_len >= rx_need) {
                if (!rx_discard) {
                    forwardVideo(rx_buf, rx_need);
                }
                rx_binary = false;
                rx_len = rx_need = 0;
                rx_discard = false;
            }
        }
    }
}

// Отправляет AT-команду и кооперативно ждёт ответа, продолжая качать pumpAT()
// (значит, видео не теряется на время опроса). Возвращает true, если встретился
// tok_ok. Накопленный текст ответа кладёт в out.
static bool atExchange(const char *cmd, const char *tok_ok, const char *tok_err,
                       uint32_t timeout_ms, String &out)
{
    at_resp = "";
    SerialAT.print("AT");
    SerialAT.print(cmd);
    SerialAT.print("\r\n");

    uint32_t start = millis();
    while (millis() - start < timeout_ms) {
        pumpAT();
        if (tok_ok && at_resp.indexOf(tok_ok) >= 0) {
            out = at_resp;
            return true;
        }
        if (tok_err && at_resp.indexOf(tok_err) >= 0) {
            out = at_resp;
            return false;
        }
        delay(1);
    }
    out = at_resp;
    return false;
}

// --- Инициализация модуля (до старта loop, "+RXDATA" тут ещё нет) ---

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

// Для команд, которые отвечают НЕ "OK", а произвольным текстом (например
// "+MCAST_BW" -> "tx bw=8 MHz", "+SHORT_GI=1" -> "short GI enabled"). Обычный
// atCommand() на них всегда рапортует FAIL, хотя команда сработала: он ждёт
// именно "OK". Здесь просто печатаем, что реально ответил модуль.
static void atCommandShow(const String &cmd, uint32_t timeout_ms = 400)
{
    while (SerialAT.available()) {
        SerialAT.read();
    }
    SerialAT.print("AT" + cmd + "\r\n");

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
    while (SerialAT.available()) {
        SerialAT.read();
    }
    SerialAT.print("AT" + cmd + "\r\n");
    String data;
    bool ok = (waitResponse(timeout_ms, data) == AT_OK);
    SerialMon.printf("  AT%s -> %s\n", cmd.c_str(), ok ? "OK" : "FAIL");
    return ok;
}

// Открывает UART к модулю на AT_BAUD. Без согласования: неверная скорость сразу
// видна по FAIL на всех AT-командах в TX_AH_init().
static void openAtUart(void)
{
    SerialAT.begin(AT_BAUD, SERIAL_8N1, SERIAL_AT_RXD, SERIAL_AT_TXD);
    SerialMon.printf("UART к модулю: %u бод\n", (unsigned)AT_BAUD);
}

static bool TX_AH_init(void)
{
    int err = 0;

    SerialMon.println("Настройка TX-AH (AP):");
    // Глушит отладочную статистику LMAC, чтобы она не лезла в AT-UART. На части
    // прошивок модуля команда отвечает ERROR — это не мешает работе.
    atCommand("+SYSDBG=LMAC,0");
    // Дебаг сетевого уровня диагностировали и выключили обратно — включали
    // временно (см. git-историю), чтобы поймать причину самопроизвольных
    // +DISCONNECT на STA (нашли: "malloc fail"/"no skb" — нехватка памяти в
    // самом модуле). В рабочей прошивке не нужен, только шумит в логах.
    atCommand("+SYSDBG=WNB,0");
    err += atCommand("+BSS_BW=" + String(HALOW_BSS_BW)) ? 0 : 1;
    err += atCommand("+MODE=AP") ? 0 : 1;
    err += atCommand("+KEYMGMT=NONE") ? 0 : 1;
    err += atCommand("+SSID=" HALOW_SSID) ? 0 : 1;

    // Раунд 2 (2026-08-04) — см. подробный комментарий в HalowVideo_STA.ino:
    // прошлый обрыв, вероятно, был из-за перегрузки приёмника на дистанции ~1м,
    // а не от самих команд. Пробуем ещё раз на нормальной дистанции.
    atCommandShow("+MCAST_BW=" + String(HALOW_BSS_BW));
    atCommandShow("+MCAST_MCS=" + String(HALOW_MCAST_MCS));
    atCommandShow("+SHORT_GI=1");

    return err == 0;
}

static void pollLink(void)
{
    String resp;

    link_up = atExchange("+CONN_STATE", "+CONNECTED", "+DISCONNECT", 800, resp);
    if (!link_up) {
        link_rssi = 0;
        return;
    }

    // Ответ модуля: "+RSSI:-30\r\nOK". Индекс 1 — первая подключённая STA.
    atExchange("+RSSI=1", "OK", "ERROR", 800, resp);
    int at = resp.indexOf("+RSSI:");
    if (at >= 0) {
        link_rssi = (int8_t)resp.substring(at + 6).toInt();
    }
}

//************************************[ OLED ]*******************************************

static bool oled_init(void)
{
    Wire.beginTransmission(0x3C);
    if (Wire.endTransmission() != 0) {
        return false;
    }
    return display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
}

static void oled_show(void)
{
    if (!oled_ok) {
        return;
    }
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("T-Halow RX (AP)");
    display.println("---------------------");
    display.printf("TX-AH: %s\n", tx_ah_ok ? "OK" : "---");
    display.printf("SSID : %s\n", HALOW_SSID);
    if (link_up) {
        display.printf("RSSI : %d dBm\n", link_rssi);
        display.printf("USB  : %lu кадров\n", (unsigned long)frames_fwd);
    } else {
        display.println("Нет связи с STA");
    }
    display.display();
}

//************************************[ ARDUINO ]****************************************

void setup()
{
    SerialMon.begin(115200);   // USB CDC: скорость номинальна, поток идёт на полной
    delay(2000);

    SerialMon.println();
    SerialMon.println("=== T-Halow: приёмник (AP) ===");
    SerialMon.println("Видео из +RXDATA форвардится в USB (RJ45-мост инжект не выпускает).");

    Wire.begin(BOARD_I2C_SDA, BOARD_I2C_SCL);
    openAtUart();
    pinMode(BOARD_LED, OUTPUT);

    oled_ok = oled_init();
    tx_ah_ok = TX_AH_init();

    SerialMon.printf("OLED: %s, TX-AH: %s\n",
                     oled_ok ? "OK" : "нет",
                     tx_ah_ok ? "OK" : "ОШИБКА");
    oled_show();

    last_progress_ms = millis(); // старт отсчёта таймаута сторожа
}

void loop()
{
    // Главное дело — непрерывно вычёрпывать UART модуля и форвардить кадры.
    pumpAT();

    if (millis() - poll_tick > POLL_PERIOD_MS) {
        poll_tick = millis();

        // pollLink внутри тоже качает pumpAT(), так что кадры не теряются.
        pollLink();

        char js[80];
        int n = snprintf(js, sizeof(js),
                         "{\"role\":\"ap\",\"conn\":%d,\"rssi\":%d,\"fwd\":%lu}",
                         link_up ? 1 : 0, link_rssi, (unsigned long)frames_fwd);
        usbSendRecord(HALOW_USB_TYPE_META, (const uint8_t *)js, (uint16_t)n);

        // Текстовая диагностика для обычного монитора порта (без просмотрщика).
        // Просмотрщик её игнорирует — он ищет двухбайтовый маркер 0xA5 0x5A.
        // Как читать:
        //   conn=0        — нет связи с камерой (проверь STA);
        //   rx_hdr не растёт — модуль не отдаёт "+RXDATA" (кадры не долетают);
        //   rx_hdr растёт, hlw=-1 — кадр пришёл, но магии HLW1 в нём нет
        //                            (пришли сырые байты — нужен разбор формата);
        //   fwd растёт     — всё ок, кадры уходят в USB, ищи проблему на ПК.
        SerialMon.printf("DIAG conn=%d rssi=%d uart=%lu rx_hdr=%lu last_len=%d hlw=%d fwd=%lu\n",
                         link_up ? 1 : 0, link_rssi, (unsigned long)rx_total,
                         (unsigned long)rxdata_hdrs, last_rx_len, last_hlw_off,
                         (unsigned long)frames_fwd);

        // Пришли байты, но ни одного "+RXDATA" не разобрали — покажем, ЧТО
        // именно шлёт модуль (ASCII-заголовок "+RXDATA:" или сырой бинарь).
        if (rxdata_hdrs == 0 && rx_total > 0) {
            char hex[3 * 32 + 1];
            int p = 0;
            for (int i = 0; i < 32; i++) {
                uint8_t b = dbg_buf[(uint8_t)(dbg_idx + i) & 31]; // от старого к новому
                p += snprintf(hex + p, sizeof(hex) - p, "%02X ", b);
            }
            SerialMon.printf("DIAGHEX %s\n", hex);
        }

        // Сторож протухшей ассоциации (см. AP_WATCHDOG_ENABLED выше — сейчас выключен).
        if (rxdata_hdrs != last_rxdata_hdrs_seen) {
            last_rxdata_hdrs_seen = rxdata_hdrs;
            last_progress_ms = millis();
        } else if (AP_WATCHDOG_ENABLED && link_up && millis() - last_progress_ms > STALE_RX_TIMEOUT_MS) {
            watchdog_resets++;
            SerialMon.printf("WATCHDOG #%lu: conn=1, но +RXDATA нет %lu мс — похоже AP "
                             "держит протухшую ассоциацию, переинициализирую модуль\n",
                             (unsigned long)watchdog_resets,
                             (unsigned long)(millis() - last_progress_ms));
            tx_ah_ok = TX_AH_init();
            link_up = false;
            link_rssi = 0;
            last_progress_ms = millis(); // не долбить переинициализацией каждый цикл
        }

        led_state = !led_state;
        digitalWrite(BOARD_LED, link_up ? led_state : LOW);
        oled_show();
    }
}
