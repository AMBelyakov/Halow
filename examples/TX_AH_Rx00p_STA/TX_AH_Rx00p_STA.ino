#include "utilities.h"
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include "FS.h"
#include "SD.h"
#include "SPI.h"
#include "esp_camera.h"

#define BUF_MAX_LEN 20

#define AH_Rx00P_RESPONE_OK 1
#define AH_Rx00P_RESPONE_ERROR 2

bool ssd1306_ret = false;
bool camera_ret = false;
bool sdcard_ret = false;
bool tx_ah_ret = false;
char buf[BUF_MAX_LEN] = {0};
char recv_data[128] = {0};

camera_config_t config;
Adafruit_SSD1306 display = Adafruit_SSD1306(128, 64, &Wire);
SemaphoreHandle_t debuglock;


//************************************[ TX-AH ]******************************************
#if 1
int8_t waitResponse(uint32_t timeouts, String &data, const char *r1 = "OK", const char *r2 = "ERROR")
{
    int index = 0;
    uint32_t start_tick = millis();

    do {
        while (SerialAT.available() > 0) {
            int a = SerialAT.read();
            if (a < 0)
                continue; // Skip 0x00 bytes, just in case

            data.reserve(1024);
            data += static_cast<char>(a);

            // SerialMon.println(data.c_str());

            if(data.endsWith(r1)){
                index = AH_Rx00P_RESPONE_OK;
                SerialMon.println(data.c_str());
                goto finish;
            } else if(data.endsWith(r2)){
                index = AH_Rx00P_RESPONE_ERROR;
                SerialMon.println(data.c_str());
                goto finish;
            }
        }
    } while (millis() - start_tick < timeouts);

finish:
    return index;
}

int8_t waitResponse(uint32_t timeouts)
{
    String data;
    return waitResponse(timeouts, data);
}
int8_t waitResponse(void)
{
    return waitResponse(1000);
}
void sendAT(String s)
{
    s = "AT" + s;
    SerialAT.write(s.c_str());
}
bool TX_AH_init(void)
{
    int at_cnt = 0;

    sendAT("+SYSDBG=LMAC,0");
    if (waitResponse() == AH_Rx00P_RESPONE_OK)
        SerialMon.println("AT+SYSDBG SUCCEED");
    else
    {
        at_cnt++;
        SerialMon.println("AT+SYSDBG ERROR");
    }

    sendAT("+BSS_BW=8");
    if (waitResponse() == AH_Rx00P_RESPONE_OK)
        SerialMon.println("AT+BSS_BW SUCCEED");
    else
    {
        at_cnt++;
        SerialMon.println("AT+BSS_BW FAILD");
    }

    sendAT("+MODE=STA");
    if (waitResponse() == AH_Rx00P_RESPONE_OK)
        SerialMon.println("AT+MODE=STA SUCCEED");
    else
    {
        at_cnt++;
        SerialMon.println("AT+MODE=STA FAILD");
    }

    return (at_cnt == 0);
}
#endif
//************************************[ CAMERA ]******************************************
bool camera_init(void)
{
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
    config.xclk_freq_hz = XCLK_FREQ_HZ;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_96X96;
    config.jpeg_quality = 12;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

    if (config.pixel_format == PIXFORMAT_JPEG)
    {
        if (psramFound())
        {
            config.jpeg_quality = 10;
            config.fb_count = 2;
            config.grab_mode = CAMERA_GRAB_LATEST;
        }
        else
        {
            config.frame_size = FRAMESIZE_SVGA;
            config.fb_location = CAMERA_FB_IN_DRAM;
        }
    }

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK)
    {
        Serial.printf("Camera init failed with error 0x%x", err);
        return false;
    }
    return true;
}


// ========== ФУНКЦИЯ ОТПРАВКИ КАДРА ==========
void sendFrame(camera_fb_t *fb) {
    int len = fb->len;
    char cmd[32];
    snprintf(cmd, sizeof(cmd), "+TXDATA=%d", len);
    sendAT(cmd);
    if (waitResponse(2000) == AH_Rx00P_RESPONE_OK) {
        SerialAT.write(fb->buf, len);
        Serial.printf("Frame sent: %d bytes\n", len);
    } else {
        Serial.println("Send command failed");
    }
}

void setup()
{
    Serial.begin(115200);

    delay(3000);

    debuglock = xSemaphoreCreateBinary();
    assert(debuglock);
    xSemaphoreGive(debuglock);

    Wire.begin(BOARD_I2C_SDA, BOARD_I2C_SCL);
    SPI.begin(TF_SPI_SCK, TF_SPI_MISO, TF_SPI_MOSI, TF_SPI_CS);
    SerialAT.begin(115200, SERIAL_8N1, SERIAL_AT_RXD, SERIAL_AT_TXD);

    ssd1306_ret = ssd1306_init();
    camera_ret = camera_init();
    sdcard_ret = sdcard_init();
    tx_ah_ret = TX_AH_init();

    lcd_info_show();
    pinMode(BOARD_LED, OUTPUT);
}

uint32_t last_tick = 0;
uint32_t rssi_tick = 0;
uint32_t lastFrame = 0;
const uint32_t FRAME_INTERVAL_MS = 500;   // 2 кадра в секунду

String recv_str = "";
int indx = 0;
bool led_flag = 0;

void loop()
{
    if (millis() - last_tick > 1000)
    {
        last_tick = millis();
        digitalWrite(BOARD_LED, led_flag);
        led_flag = !led_flag;
    }

    if (millis() - rssi_tick > 3000)
    {
        rssi_tick = millis();

        String data;
        sendAT("+CONN_STATE");
        if (waitResponse(1000, data, "+CONNECTED", "+DISCONNECT") == AH_Rx00P_RESPONE_OK) {
            tx_ah_conn_status = true;
        }
        else {
            tx_ah_conn_status = false;
        }

        if(tx_ah_conn_status) {
            String rssi_data;
            sendAT("+RSSI=1");
            if (waitResponse(1000, rssi_data) == AH_Rx00P_RESPONE_OK) {
                int startIndex = rssi_data.indexOf(':');
                int endIndex = rssi_data.lastIndexOf('\n');
                String substr = rssi_data.substring(startIndex + 1, endIndex -1);
                strcpy(rssi_buf, substr.c_str());
            }
        }

        lcd_info_show();
    }

    // ---------- ЗАХВАТ И ОТПРАВКА КАДРА ----------
    if (tx_ah_conn_status && camera_ret) {
        if (millis() - lastFrame >= FRAME_INTERVAL_MS) {
            lastFrame = millis();

            camera_fb_t *fb = esp_camera_fb_get();
            if (fb) {
                sendFrame(fb);
                esp_camera_fb_return(fb);
            } else {
                Serial.println("Frame capture failed");
            }
        }
    }

    // Обработка входящих данных от AP (необязательно, можно оставить для отладки)
    while (SerialAT.available()) {
        SerialMon.write(SerialAT.read());
    }
    while (SerialMon.available()) {
        SerialAT.write(SerialMon.read());
    }

    delay(1);
}