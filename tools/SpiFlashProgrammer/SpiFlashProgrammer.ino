/*
 * SpiFlashProgrammer — программатор SPI NOR флеша на ESP32-S3 (плата T-Halow).
 *
 * Зачем: восстановить STA-модуль T-Halow после неудачной прошивки. Модуль
 * ушёл в циклический ребут (hg_gmac_open assert) и по UART недоступен —
 * живёт ~0.1 с, а XMODEM идёт минуту. Остаётся вынуть флеш из кроватки и
 * прошить снаружи. Этим скетчем.
 *
 * Работает в паре с tools/flash_tool.py — тот гонит .bin по USB.
 *
 * ------------------------------------------------------------------
 * ПОДКЛЮЧЕНИЕ (флеш SOP8, стандартная распиновка W25Q/MX25/GD25)
 * ------------------------------------------------------------------
 *   Флеш                        ESP32-S3 (T-Halow)
 *   1  /CS   ---------------->  IO15
 *   2  DO    (MISO) --------->  IO7
 *   3  /WP   ---------------->  3V3    <-- ОБЯЗАТЕЛЬНО, иначе запись не пойдёт
 *   4  GND   ---------------->  GND
 *   5  DI    (MOSI) --------->  IO40
 *   6  CLK   ---------------->  IO41
 *   7  /HOLD ---------------->  3V3    <-- ОБЯЗАТЕЛЬНО, иначе чип молчит
 *   8  VCC   ---------------->  3V3
 *
 * Ключ (точка/срез) на корпусе — со стороны ножки 1.
 * Питание строго 3.3 В. 5 В убьёт чип.
 *
 * Все четыре вывода выбраны так, чтобы они были на боковых гребёнках
 * T-Halow и ни с чем не конфликтовали: не камера (там 1,2,8..14,16..18,21,
 * 47,48), не UART модуля (4,5), не светодиод (38) и не strapping-выводы
 * ESP32-S3 (0,3,45,46). Первая версия скетча использовала выводы слота
 * TF-карты (39..42) — 39 и 42 на гребёнку не выведены, подключиться к ним
 * было бы нечем.
 *
 * ------------------------------------------------------------------
 * ПРОТОКОЛ (текстовые команды, бинарные данные)
 * ------------------------------------------------------------------
 *   PING              -> OK
 *   ID                -> JEDEC <mfr> <type> <cap> SIZE <bytes>
 *   ERASE             -> OK (полное стирание, может занять до минуты)
 *   W <addr> <len>    -> RDY, затем принимает len байт, -> OK <crc32>
 *   R <addr> <len>    -> DATA <len>, затем отдаёт len байт
 *
 * Скетч ничего не делает по своей инициативе: стирание и запись только по
 * явной команде. Верификация — обязанность flash_tool.py, он читает обратно
 * и сравнивает побайтово.
 */

#include <Arduino.h>
#include <SPI.h>

// --- пины: все выведены на боковые гребёнки T-Halow ---
#define PIN_CS    15
#define PIN_MOSI  40
#define PIN_SCK   41
#define PIN_MISO  7

// 20 МГц — с запасом надёжно для проводов "соплями". Штатно чипы держат 50+,
// но на макетке длинные незаземлённые провода дают наводки, а нам важнее
// один успешный проход, чем скорость.
#define SPI_HZ    20000000

// --- команды SPI NOR ---
#define CMD_WRITE_ENABLE  0x06
#define CMD_READ_STATUS   0x05
#define CMD_PAGE_PROGRAM  0x02
#define CMD_READ_DATA     0x03
#define CMD_CHIP_ERASE    0xC7
#define CMD_SECTOR_ERASE  0x20     // стирает 4 КБ — только нужный диапазон
#define CMD_JEDEC_ID      0x9F

#define SECTOR_SIZE       4096

#define PAGE_SIZE         256      // максимум за одну команду записи
#define STATUS_WIP        0x01     // Write In Progress

static SPIClass spiflash(HSPI);
static uint32_t flash_size = 0;

static inline void cs_low()  { digitalWrite(PIN_CS, LOW);  }
static inline void cs_high() { digitalWrite(PIN_CS, HIGH); }

static void spi_begin_txn() {
    spiflash.beginTransaction(SPISettings(SPI_HZ, MSBFIRST, SPI_MODE0));
}
static void spi_end_txn() {
    spiflash.endTransaction();
}

// Ждём снятия бита WIP. timeout_ms — чтобы не зависнуть навсегда на дохлом
// чипе: полное стирание у 8-мегабитных занимает единицы секунд, у крупных
// десятки, поэтому вызывающий передаёт запас.
static bool wait_ready(uint32_t timeout_ms) {
    uint32_t start = millis();
    while (millis() - start < timeout_ms) {
        spi_begin_txn();
        cs_low();
        spiflash.transfer(CMD_READ_STATUS);
        uint8_t st = spiflash.transfer(0x00);
        cs_high();
        spi_end_txn();
        if (!(st & STATUS_WIP)) return true;
        delay(1);
    }
    return false;
}

static void write_enable() {
    spi_begin_txn();
    cs_low();
    spiflash.transfer(CMD_WRITE_ENABLE);
    cs_high();
    spi_end_txn();
}

static void read_jedec(uint8_t *mfr, uint8_t *type, uint8_t *cap) {
    spi_begin_txn();
    cs_low();
    spiflash.transfer(CMD_JEDEC_ID);
    *mfr  = spiflash.transfer(0x00);
    *type = spiflash.transfer(0x00);
    *cap  = spiflash.transfer(0x00);
    cs_high();
    spi_end_txn();
}

static void flash_read(uint32_t addr, uint8_t *buf, uint32_t len) {
    spi_begin_txn();
    cs_low();
    spiflash.transfer(CMD_READ_DATA);
    spiflash.transfer((addr >> 16) & 0xFF);
    spiflash.transfer((addr >> 8) & 0xFF);
    spiflash.transfer(addr & 0xFF);
    for (uint32_t i = 0; i < len; i++) buf[i] = spiflash.transfer(0x00);
    cs_high();
    spi_end_txn();
}

// Запись одной страницы. Пересекать границу 256 байт нельзя — чип завернёт
// адрес на начало страницы и молча испортит данные, поэтому режем выше.
static bool flash_write_page(uint32_t addr, const uint8_t *buf, uint32_t len) {
    write_enable();
    spi_begin_txn();
    cs_low();
    spiflash.transfer(CMD_PAGE_PROGRAM);
    spiflash.transfer((addr >> 16) & 0xFF);
    spiflash.transfer((addr >> 8) & 0xFF);
    spiflash.transfer(addr & 0xFF);
    for (uint32_t i = 0; i < len; i++) spiflash.transfer(buf[i]);
    cs_high();
    spi_end_txn();
    return wait_ready(100);
}

static uint32_t crc32_update(uint32_t crc, const uint8_t *data, size_t len) {
    crc = ~crc;
    while (len--) {
        crc ^= *data++;
        for (int k = 0; k < 8; k++)
            crc = (crc >> 1) ^ (0xEDB88320 & (-(int32_t)(crc & 1)));
    }
    return ~crc;
}

// Читает ровно n байт из Serial с таймаутом. Возвращает false, если хост
// оборвался на середине — лучше честно сообщить, чем записать мусор.
static bool serial_read_exact(uint8_t *buf, uint32_t n, uint32_t timeout_ms) {
    uint32_t got = 0;
    uint32_t last = millis();
    while (got < n) {
        int avail = Serial.available();
        if (avail > 0) {
            int r = Serial.readBytes((char *)(buf + got), min((uint32_t)avail, n - got));
            got += r;
            last = millis();
        } else if (millis() - last > timeout_ms) {
            return false;
        }
    }
    return true;
}

static String read_line() {
    String s;
    while (true) {
        while (!Serial.available()) delay(1);
        char c = Serial.read();
        if (c == '\n') break;
        if (c != '\r') s += c;
    }
    return s;
}

void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);

    pinMode(PIN_CS, OUTPUT);
    cs_high();
    spiflash.begin(PIN_SCK, PIN_MISO, PIN_MOSI, -1);   // CS дёргаем вручную

    delay(200);
    Serial.println("SpiFlashProgrammer ready");
}

void loop() {
    String line = read_line();
    line.trim();
    if (line.length() == 0) return;

    if (line == "PING") {
        Serial.println("OK");

    } else if (line == "ID") {
        uint8_t mfr, type, cap;
        read_jedec(&mfr, &type, &cap);
        // Ёмкость кодируется степенью двойки в третьем байте: 0x13 = 2^19 = 512 КБ,
        // 0x14 = 1 МБ, 0x15 = 2 МБ и так далее. Работает у Winbond, Macronix, GD.
        flash_size = (cap >= 0x10 && cap <= 0x1A) ? (1UL << cap) : 0;
        Serial.printf("JEDEC %02X %02X %02X SIZE %lu\n",
                      mfr, type, cap, (unsigned long)flash_size);

    } else if (line.startsWith("SE ")) {
        // Стирание одного сектора 4 КБ. Именно этим пользуется обычная
        // заливка: чип 4 МБ, прошивка ~335 КБ, всё остальное — параметры
        // с MAC и калибровкой, которые полное стирание бы уничтожило.
        uint32_t addr = strtoul(line.substring(3).c_str(), NULL, 10);
        write_enable();
        spi_begin_txn();
        cs_low();
        spiflash.transfer(CMD_SECTOR_ERASE);
        spiflash.transfer((addr >> 16) & 0xFF);
        spiflash.transfer((addr >> 8) & 0xFF);
        spiflash.transfer(addr & 0xFF);
        cs_high();
        spi_end_txn();
        Serial.println(wait_ready(2000) ? "OK" : "ERR sector erase timeout");

    } else if (line == "ERASE") {
        write_enable();
        spi_begin_txn();
        cs_low();
        spiflash.transfer(CMD_CHIP_ERASE);
        cs_high();
        spi_end_txn();
        // 120 с — с запасом даже для 16-мегабитных
        Serial.println(wait_ready(120000) ? "OK" : "ERR erase timeout");

    } else if (line.startsWith("W ")) {
        int sp = line.indexOf(' ', 2);
        uint32_t addr = strtoul(line.substring(2, sp).c_str(), NULL, 10);
        uint32_t len  = strtoul(line.substring(sp + 1).c_str(), NULL, 10);

        static uint8_t buf[4096];
        if (len > sizeof(buf)) { Serial.println("ERR chunk too big"); return; }

        Serial.println("RDY");
        if (!serial_read_exact(buf, len, 5000)) { Serial.println("ERR timeout"); return; }

        uint32_t written = 0;
        bool ok = true;
        while (written < len) {
            // не пересекаем границу страницы
            uint32_t page_off = (addr + written) % PAGE_SIZE;
            uint32_t n = min(PAGE_SIZE - page_off, len - written);
            if (!flash_write_page(addr + written, buf + written, n)) { ok = false; break; }
            written += n;
        }
        if (ok) Serial.printf("OK %08lX\n", (unsigned long)crc32_update(0, buf, len));
        else    Serial.println("ERR write timeout");

    } else if (line.startsWith("R ")) {
        int sp = line.indexOf(' ', 2);
        uint32_t addr = strtoul(line.substring(2, sp).c_str(), NULL, 10);
        uint32_t len  = strtoul(line.substring(sp + 1).c_str(), NULL, 10);

        static uint8_t buf[4096];
        if (len > sizeof(buf)) { Serial.println("ERR chunk too big"); return; }

        flash_read(addr, buf, len);
        Serial.printf("DATA %lu\n", (unsigned long)len);
        Serial.write(buf, len);

    } else {
        Serial.println("ERR unknown");
    }
}
