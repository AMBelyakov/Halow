/*
 * HalowModuleUpdater — ESP32 сам прошивает модуль TX-AH образом, вшитым в скетч (08.10.2026).
 *
 * ЗАЧЕМ. Модуль шьётся по XMODEM ~70 с непрерывного обмена. Обычный путь — мост
 * HalowPassthrough + tools/fwupg.py: байты идут ПК -> USB -> ESP -> UART -> модуль. 07–08.10
 * USB камеры перестал держать непрерывный обмен дольше 1–2 с (залипает, лечится только
 * передёргиванием кабеля, а оно сбрасывает и модуль). Здесь USB в передаче не участвует:
 * образ лежит во флеше ESP (module_image.h), ESP шлёт его модулю сам по UART на плате.
 * Через USB нужно залить только этот скетч — а это идёт кусками (tools/flash_parts.py).
 *
 * ПОРЯДОК ПРИ ВКЛЮЧЕНИИ:
 *   1. AT+NOP2P в стартовое окно модуля, пока не ответит OK (окно — от подачи питания);
 *   2. сверка образа: метка 69 5a 00 1c и CRC16-MODBUS тела с 0x2000 против поля +0x14
 *      (неверный CRC окирпичивает модуль — см. tools/fwupg.py, check_image_crc);
 *   3. AT+FWUPG, ждать 'C', XMODEM-CRC по 128 байт, на блок до 10 повторов;
 *   4. EOT, ответ модуля; успех записывается в NVS (updater/crc) — при следующих включениях
 *      прошивка не повторяется (только печать «уже прошито»).
 *
 * СВЕТОДИОД (GPIO 38): мигает часто — идёт передача; горит ровно — успех; мигает редко —
 * отказ (модуль пишет в НЕАКТИВНЫЙ слот, при отказе поднимется прежняя прошивка). Итог
 * печатается в USB раз в 2 с — его можно прочитать в любой момент.
 *
 * ПОСЛЕ УСПЕХА: обесточить плату (модуль поднимет новый слот) и залить обратно скетч камеры.
 */
#include <Arduino.h>
#include <Preferences.h>
#include "utilities.h"
#include "module_image.h"

#define AT_BAUD       115200
#define WINDOW_MS     25000     /* сколько ловить окно модуля после включения */
#define BLOCK         128
#define BLOCK_TRIES   10
#define BLOCK_WAIT_MS 5000

#define SOH 0x01
#define EOT 0x04
#define ACK 0x06
#define NAK 0x15
#define CAN 0x18

static String g_result = "ещё не начинали";
static int    g_state = 0;              /* 0 — идёт, 1 — успех, 2 — отказ, 3 — уже прошито */

static uint16_t crc16_modbus(const uint8_t *p, size_t n)
{
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < n; i++) {
        crc ^= p[i];
        for (int k = 0; k < 8; k++) {
            crc = (crc & 1) ? (uint16_t)((crc >> 1) ^ 0xA001) : (uint16_t)(crc >> 1);
        }
    }
    return crc;
}

static uint16_t crc16_xmodem(const uint8_t *p, size_t n)
{
    uint16_t crc = 0;
    for (size_t i = 0; i < n; i++) {
        crc ^= (uint16_t)p[i] << 8;
        for (int k = 0; k < 8; k++) {
            crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

static void drain(uint32_t ms)
{
    uint32_t t0 = millis();
    while (millis() - t0 < ms) {
        while (SerialAT.available()) {
            SerialAT.read();
        }
        delay(5);
    }
}

/* Ждать один из байтов (ACK/NAK/CAN/'C'); прочий текст модуля пропускаем. */
static int wait_byte(const uint8_t *want, int nwant, uint32_t ms)
{
    uint32_t t0 = millis();
    while (millis() - t0 < ms) {
        if (SerialAT.available()) {
            int c = SerialAT.read();
            for (int i = 0; i < nwant; i++) {
                if (c == want[i]) {
                    return c;
                }
            }
        } else {
            delay(1);
        }
    }
    return -1;
}

static String at_cmd(const char *cmd, uint32_t ms)
{
    drain(20);
    SerialAT.print(cmd);
    String r;
    uint32_t t0 = millis();
    while (millis() - t0 < ms) {
        while (SerialAT.available()) {
            r += (char)SerialAT.read();
        }
        delay(5);
    }
    return r;
}

static void led_blink_task(void *)
{
    for (;;) {
        if (g_state == 0) {
            digitalWrite(BOARD_LED, !digitalRead(BOARD_LED));
            delay(100);
        } else if (g_state == 1 || g_state == 3) {
            digitalWrite(BOARD_LED, HIGH);
            delay(200);
        } else {
            digitalWrite(BOARD_LED, !digitalRead(BOARD_LED));
            delay(1000);
        }
    }
}

static bool image_ok(uint16_t *crc_out)
{
    const uint8_t *d = module_img;
    if (MODULE_IMG_LEN < 0x2000 + 16 || d[0] != 0x69 || d[1] != 0x5a || d[2] != 0x00 || d[3] != 0x1c) {
        g_result = "образ без метки 69 5a 00 1c";
        return false;
    }
    uint16_t want = (uint16_t)(d[0x14] | (d[0x15] << 8));
    uint16_t got = crc16_modbus(d + 0x2000, MODULE_IMG_LEN - 0x2000);
    *crc_out = got;
    if (got != want) {
        g_result = String("CRC тела ") + String(got, HEX) + " не сходится с заголовком " + String(want, HEX);
        return false;
    }
    return true;
}

static bool flash_module()
{
    /* 1. Окно модуля. */
    uint32_t t0 = millis();
    bool latched = false;
    int tries = 0;
    while (millis() - t0 < WINDOW_MS) {
        tries++;
        String r = at_cmd("AT+NOP2P\r\n", 350);
        if (r.indexOf("OK") >= 0) {
            latched = true;
            break;
        }
    }
    if (!latched) {
        g_result = "модуль не ответил на AT+NOP2P за окно — ничего не писали";
        return false;
    }
    at_cmd("AT+SYSDBG=WNB,0\r\n", 300);
    at_cmd("AT+PRINT_PERIOD=600000\r\n", 300);
    String ver = at_cmd("AT+VERSION\r\n", 500);
    ver.trim();
    SerialMon.printf("AT+NOP2P с %d-й попытки; модуль: %s\r\n", tries, ver.c_str());
    if (ver.indexOf("VERSION") < 0) {
        g_result = "модуль не отвечает на AT+VERSION — ничего не писали";
        return false;
    }

    /* 2. Режим XMODEM. */
    drain(50);
    SerialAT.print("AT+FWUPG\r\n");
    const uint8_t want_c[] = { 'C' };
    if (wait_byte(want_c, 1, 20000) < 0) {
        g_result = "модуль не перешёл в XMODEM (нет 'C') — ничего не писали";
        return false;
    }

    /* 3. Блоки. */
    const uint32_t total = (MODULE_IMG_LEN + BLOCK - 1) / BLOCK;
    uint8_t frame[3 + BLOCK + 2];
    const uint8_t want_an[] = { ACK, NAK, CAN };
    uint32_t naks = 0;
    uint32_t tx0 = millis();
    for (uint32_t i = 0; i < total; i++) {
        uint32_t off = i * BLOCK;
        uint32_t n = MODULE_IMG_LEN - off < BLOCK ? MODULE_IMG_LEN - off : BLOCK;
        frame[0] = SOH;
        frame[1] = (uint8_t)((i + 1) & 0xFF);
        frame[2] = (uint8_t)(0xFF - frame[1]);
        memcpy(frame + 3, module_img + off, n);
        if (n < BLOCK) {
            memset(frame + 3 + n, 0x1A, BLOCK - n);          /* добивка CTRL-Z */
        }
        uint16_t c = crc16_xmodem(frame + 3, BLOCK);
        frame[3 + BLOCK] = (uint8_t)(c >> 8);
        frame[4 + BLOCK] = (uint8_t)(c & 0xFF);
        int r = -1;
        for (int a = 0; a < BLOCK_TRIES; a++) {
            SerialAT.write(frame, sizeof(frame));
            SerialAT.flush();
            r = wait_byte(want_an, 3, BLOCK_WAIT_MS);
            if (r == ACK) {
                break;
            }
            if (r == CAN) {
                break;
            }
            naks++;
        }
        if (r != ACK) {
            g_result = String("блок ") + (i + 1) + "/" + total + (r == CAN ? ": модуль отменил (CAN)" : ": без ACK") +
                       " — прежняя прошивка модуля должна подняться";
            return false;
        }
        if ((i + 1) % 400 == 0 || i + 1 == total) {
            SerialMon.printf("  %lu/%lu блоков, %lu с, повторов %lu\r\n", (unsigned long)(i + 1),
                             (unsigned long)total, (unsigned long)((millis() - tx0) / 1000),
                             (unsigned long)naks);
        }
    }

    /* 4. Конец. */
    SerialAT.write((uint8_t)EOT);
    SerialAT.flush();
    const uint8_t want_ack[] = { ACK };
    if (wait_byte(want_ack, 1, 20000) < 0) {
        g_result = "EOT без ACK — данные, скорее всего, записаны; проверить после включения";
        return false;
    }
    String tail = at_cmd("", 2500);
    tail.trim();
    g_result = String("УСПЕХ: ") + total + " блоков за " + ((millis() - tx0) / 1000) + " с, повторов " + naks +
               ". Модуль: " + tail.substring(0, 200);
    return true;
}

void setup()
{
    SerialMon.begin(115200);
    SerialAT.setRxBufferSize(2048);
    SerialAT.begin(AT_BAUD, SERIAL_8N1, SERIAL_AT_RXD, SERIAL_AT_TXD);
    pinMode(BOARD_LED, OUTPUT);
    xTaskCreate(led_blink_task, "led", 2048, NULL, 1, NULL);

    uint16_t crc = 0;
    if (!image_ok(&crc)) {
        g_state = 2;                               /* образ испорчен — модуль не трогаем */
        return;
    }
    Preferences pr;
    pr.begin("updater", false);
    uint32_t done = pr.getUInt("crc", 0);
    if (done == (0x10000u | crc)) {
        g_state = 3;
        g_result = String("уже прошито этим образом (CRC ") + String(crc, HEX) +
                   ") — повторно не пишу. Залейте скетч камеры.";
        pr.end();
        return;
    }
    bool ok = flash_module();
    if (ok) {
        pr.putUInt("crc", 0x10000u | crc);
        g_state = 1;
    } else {
        g_state = 2;
    }
    pr.end();
}

void loop()
{
    static uint32_t t = 0;
    if (millis() - t >= 2000) {
        t = millis();
        SerialMon.printf("[%lu с] ПРОШИВАЛЬЩИК МОДУЛЯ %s (md5 %s): %s\r\n",
                         (unsigned long)(millis() / 1000), MODULE_IMG_NAME, MODULE_IMG_MD5,
                         g_result.c_str());
    }
    while (SerialMon.available()) {
        SerialMon.read();                          /* USB читать обязательно, см. скетч камеры */
    }
    while (SerialAT.available()) {
        SerialAT.read();
    }
    delay(20);
}
