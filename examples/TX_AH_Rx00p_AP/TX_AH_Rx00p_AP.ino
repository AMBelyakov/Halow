#include "utilities.h"
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include <ETH.h>                 // Ethernet (патч-корд)
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>

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

camera_config_t config;
Adafruit_SSD1306 display = Adafruit_SSD1306(128, 64, &Wire);
SemaphoreHandle_t debuglock;

// --- Web-сервер и видео ---
AsyncWebSocket ws("/ws");                // WebSocket для видеокадров
AsyncWebServer server(80);              // HTTP-сервер
uint8_t *lastJpeg = nullptr;            // последний кадр для новых клиентов
size_t lastJpegLen = 0;
SemaphoreHandle_t frameMutex;           // защита lastJpeg

// --- Приём JPEG по UART ---
bool receivingData = false;
uint32_t expectedLen = 0;
uint32_t receivedLen = 0;
uint8_t *jpegBuffer = nullptr;

//************************************[ SSD1306 ]******************************************
bool ssd1306_init(void)
{
    Serial.println("OLED FeatherWing test");
    Wire.beginTransmission(0x3C);
    if (Wire.endTransmission() == 0)
    {
        display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
        return true;
    }
    return false;
}

//************************************[ SDCARD ]******************************************
bool sdcard_init(void)
{
    if (!SD.begin(TF_SPI_CS))
    {
        Serial.println("Card Mount Failed");
        return false;
    }
    uint8_t cardType = SD.cardType();
    if (cardType == CARD_NONE)
    {
        Serial.println("No SD card attached");
        return false;
    }
    Serial.print("SD Card Type: ");
    if (cardType == CARD_MMC)
    {
        Serial.println("MMC");
    }
    else if (cardType == CARD_SD)
    {
        Serial.println("SDSC");
    }
    else if (cardType == CARD_SDHC)
    {
        Serial.println("SDHC");
    }
    else
    {
        Serial.println("UNKNOWN");
    }
    uint64_t cardSize = SD.cardSize() / (1024 * 1024);
    Serial.printf("SD Card Size: %lluMB\n", cardSize);
    return true;
}

//************************************[ TX-AH ]******************************************
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

    sendAT("+MODE=AP");
    if (waitResponse() == AH_Rx00P_RESPONE_OK)
        SerialMon.println("AT+MODE=AP SUCCEED");
    else
    {
        at_cnt++;
        SerialMon.println("AT+MODE=AP FAILD");
    }

    return (at_cnt == 0);
}

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
            // Limit the frame size when PSRAM is not available
            config.frame_size = FRAMESIZE_SVGA;
            config.fb_location = CAMERA_FB_IN_DRAM;
        }
    }

    // camera init
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK)
    {
        Serial.printf("Camera init failed with error 0x%x", err);
        return false;
    }
    return true;
}

//************************************[ Other fun ]******************************************
char *line_align(char *buf, const char *str1, const char *str2)
{
    int max_line_size = BUF_MAX_LEN - 1;
    int16_t w2 = strlen(str2);
    int16_t w1 = max_line_size - w2;
    snprintf(buf, BUF_MAX_LEN, "%-*s%-*s", w1, str1, w2, str2);
    return buf;
}

bool tx_ah_conn_status = false;
char rssi_buf[16];

void lcd_info_show(void)
{
    if (ssd1306_ret == false)
    {
        Serial.println("******************************");
        Serial.println((tx_ah_ret == true ? "TX-AH   PASS" : "TX-AH    ---"));
        Serial.println((ssd1306_ret == true ? "SSD1306 PASS" : "SSD1306  ---"));
        Serial.println((sdcard_ret == true ? "SDCard  PASS" : "SDCard   ---"));
        Serial.println((camera_ret == true ? "CAMERA  PASS" : "CAMERA   ---"));
        Serial.println(" ");

        Serial.println(line_align(buf, "Role:", "AP "));

        if (tx_ah_conn_status) {
            Serial.println(line_align(buf, "RSSI:", rssi_buf));
        } else {
            Serial.println("Disconnect!!!");
        }
    } else {
        // Clear the buffer.
        display.clearDisplay();
        display.display();
        display.setTextSize(1);
        display.setTextColor(SSD1306_WHITE);
        display.setCursor(0, 0);
        display.println(line_align(buf, "LCD:", (ssd1306_ret == true ? "PASS" : "---")));
        display.println(line_align(buf, "SD:", (sdcard_ret == true ? "PASS" : "---")));
        display.println(line_align(buf, "CAM:", (camera_ret == true ? "PASS" : "---")));
        display.println(line_align(buf, "AH:", (tx_ah_ret == true ? "PASS" : "---")));
        display.println(" ");

        display.println(line_align(buf, "Role:", "AP "));

        if (tx_ah_conn_status) {
            display.println(line_align(buf, "RSSI:", rssi_buf));
        } else {
            display.println("Disconnect!!!");
        }
        display.display();
    }
}

// ******************* НАСТРОЙКА WEB-СЕРВЕРА *******************
void setupWebServer() {
    // WebSocket: при новом подключении отдаём последний кадр
    ws.onEvent([](AsyncWebSocket *server, AsyncWebSocketClient *client,
                 AwsEventType type, void *arg, uint8_t *data, size_t len) {
        if (type == WS_EVT_CONNECT) {
            xSemaphoreTake(frameMutex, portMAX_DELAY);
            if (lastJpeg && lastJpegLen > 0) {
                client->binary(lastJpeg, lastJpegLen);
            }
            xSemaphoreGive(frameMutex);
        }
    });
    server.addHandler(&ws);

    // Главная страница с видео
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
        String html = R"rawliteral(
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>HaLow Video</title></head>
<body>
  <h2>Live video from STA (HaLow → Ethernet)</h2>
  <img id="stream" style="width:320px; height:240px; background:#000;" />
  <script>
    const ws = new WebSocket('ws://' + location.host + '/ws');
    ws.binaryType = 'blob';
    ws.onmessage = (e) => {
      const url = URL.createObjectURL(e.data);
      document.getElementById('stream').src = url;
    };
  </script>
</body>
</html>
)rawliteral";
        request->send(200, "text/html", html);
    });

    server.begin();
}

// ******************* ОТПРАВКА КАДРА ВСЕМ КЛИЕНТАМ *******************
void broadcastJpeg(uint8_t *data, size_t len) {
    // Отправить всем подключённым WebSocket-клиентам
    ws.binaryAll(data, len);

    // Сохранить как последний кадр для новых клиентов
    xSemaphoreTake(frameMutex, portMAX_DELAY);
    free(lastJpeg);
    lastJpeg = (uint8_t*)malloc(len);
    if (lastJpeg) {
        memcpy(lastJpeg, data, len);
        lastJpegLen = len;
    }
    xSemaphoreGive(frameMutex);
}

// ******************* ИНИЦИАЛИЗАЦИЯ ETHERNET *******************

// Настройки Ethernet
bool eth_connected = false;

void WiFiEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_ETH_START:
      Serial.println("ETH Started");
      ETH.setHostname("halow-ap");
      break;
    case ARDUINO_EVENT_ETH_CONNECTED:
      Serial.println("ETH Connected");
      break;
    case ARDUINO_EVENT_ETH_GOT_IP:
      Serial.print("ETH Got IP: '");
      Serial.print(ETH.localIP());
      Serial.print("' (");
      Serial.print((uint32_t)ETH.subnetMask());
      Serial.println(")");
      eth_connected = true;
      break;
    case ARDUINO_EVENT_ETH_DISCONNECTED:
      Serial.println("ETH Disconnected");
      eth_connected = false;
      break;
    default:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(3000);

  debuglock = xSemaphoreCreateBinary();
  assert(debuglock);
  xSemaphoreGive(debuglock);

  Wire.begin(BOARD_I2C_SDA, BOARD_I2C_SCL);
  SPI.begin(TF_SPI_SCK, TF_SPI_MISO, TF_SPI_MOSI, TF_SPI_CS);
  SerialAT.begin(115200, SERIAL_8N1, SERIAL_AT_RXD, SERIAL_AT_TXD);

  WiFi.onEvent(WiFiEvent);
  ETH.begin();

  Serial.print("Waiting for Ethernet connection");
  while (!eth_connected) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" Ethernet ready!");


  ETH.config(IPAddress(10, 10, 10, 123), IPAddress(192, 168, 56, 1), IPAddress(255, 0, 0, 0));


  tx_ah_ret = TX_AH_init();  

  frameMutex = xSemaphoreCreateMutex();
  
  setupWebServer();

  
  server.begin();
  Serial.print("HTTP server started on http://");
  Serial.println(ETH.localIP());

  pinMode(BOARD_LED, OUTPUT);
}

uint32_t last_tick = 0;
uint32_t rssi_tick = 0;

String str;
int send_indx = 1;
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
                String substr = rssi_data.substring(startIndex + 1, endIndex);
                strcpy(rssi_buf, substr.c_str());
            }

            String send_data = "11111100000000";
            String data = String(send_indx);
            int len = send_data.length() + data.length();
            String cmd = "+TXDATA=" + String(len);

            send_data = send_data + data;
            Serial.printf("len=%d, send_data=%s, cmd=%s\n", len, send_data.c_str(), cmd.c_str());

            sendAT(cmd);
            if (waitResponse() == AH_Rx00P_RESPONE_OK) {
                SerialAT.write(send_data.c_str());
            }

            send_indx++;
        }

        lcd_info_show();
    }

    // ---------- ОБРАБОТКА ВХОДЯЩИХ ДАННЫХ ОТ HALOW (ПРИЁМ JPEG) ----------
    while (SerialAT.available()) {
        char c = SerialAT.read();
        static String line;

        if (!receivingData) {
            // Ждём строку +RXDATA:<длина>
            line += c;
            if (c == '\n') {
                line.trim();
                if (line.startsWith("+RXDATA:")) {
                    int comma = line.indexOf(',');
                    if (comma != -1) {
                        expectedLen = line.substring(comma+1).toInt();
                        receivingData = true;
                        receivedLen = 0;
                        if (jpegBuffer) free(jpegBuffer);
                        jpegBuffer = (uint8_t*)malloc(expectedLen);
                        if (!jpegBuffer) {
                            Serial.println("Out of memory for JPEG");
                            receivingData = false;
                        } else {
                            Serial.printf("Receiving %d bytes...\n", expectedLen);
                        }
                    }
                } else {
                    // Обычные AT-ответы – выводим в Serial
                    SerialMon.print(line);
                    SerialMon.print('\n');
                }
                line = "";
            }
        } else {
            // Принимаем байты JPEG
            if (receivedLen < expectedLen) {
                jpegBuffer[receivedLen++] = (uint8_t)c;
                if (receivedLen == expectedLen) {
                    Serial.printf("Received JPEG frame, %d bytes\n", expectedLen);

                    // Сохраняем на SD (если нужно)
                    if (sdcard_ret) {
                        String filename = "/frame_" + String(millis()) + ".jpg";
                        File f = SD.open(filename, FILE_WRITE);
                        if (f) {
                            f.write(jpegBuffer, expectedLen);
                            f.close();
                        }
                    }

                    // Отправляем кадр в браузеры
                    broadcastJpeg(jpegBuffer, expectedLen);

                    // Освобождаем буфер, так как мы его уже скопировали в broadcastJpeg
                    free(jpegBuffer);
                    jpegBuffer = nullptr;
                    receivingData = false;
                }
            } else {
                // Ошибка длины
                receivingData = false;
                free(jpegBuffer);
                jpegBuffer = nullptr;
                Serial.println("Data length mismatch");
            }
        }
    }

    // Пересылка из Serial Monitor в HaLow (для ручной отладки)
    while (SerialMon.available()) {
        SerialAT.write(SerialMon.read());
    }

    delay(1);
}