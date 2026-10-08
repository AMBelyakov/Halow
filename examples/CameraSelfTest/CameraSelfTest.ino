/*
 * CameraSelfTest — минимальный изолированный тест камеры.
 *
 * Никакого HaLow, UART, WiFi, светодиодов. Только инициализация камеры
 * (дословно как в рабочем CameraWebServer от LilyGo) и цикл захвата кадров
 * с печатью результата. Цель — на 100% отделить камеру от остального кода:
 * если тут кадров нет, значит проблема не в прошивке видеомоста, а в
 * камере/плате.
 *
 * Собирать на той же платформе, что и разработчики: espressif32@6.3.0.
 */

#include <Arduino.h>
#include "utilities.h"
#include "esp_camera.h"

camera_config_t config;

static bool camera_init(void)
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
    // ВАЖНО: снимаем в RGB565, а не JPEG. Аппаратный JPEG у OV5640 на драйвере
    // esp32-camera часто виснет и отдаёт пустые кадры — это и подозреваем.
    // RGB565 QVGA (320x240 = 153600 байт) кладём в PSRAM.
    config.pixel_format = PIXFORMAT_RGB565;
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

    if (psramFound()) {
        Serial.println("PSRAM: есть");
        config.fb_location = CAMERA_FB_IN_PSRAM;
    } else {
        Serial.println("PSRAM: нет");
        config.fb_location = CAMERA_FB_IN_DRAM;
    }

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("esp_camera_init FAILED, ошибка 0x%x\n", err);
        return false;
    }

    sensor_t *s = esp_camera_sensor_get();
    if (s) {
        camera_sensor_info_t *info = esp_camera_sensor_get_info(&(s->id));
        Serial.printf("Сенсор опознан: %s, PID 0x%x\n",
                      info ? info->name : "?", s->id.PID);
        if (s->id.PID == OV5640_PID) {
            s->set_vflip(s, 1);
        }
    }
    return true;
}

void setup()
{
    Serial.begin(115200);
    delay(3000);
    Serial.println();
    Serial.println("=== CameraSelfTest: RGB565 QVGA (обход JPEG) ===");

    if (!camera_init()) {
        Serial.println("Инициализация камеры не удалась — стоп.");
        return;
    }
    Serial.println("Камера инициализирована. Пробую захватывать кадры:");
}

uint32_t ok_cnt = 0;
uint32_t fail_cnt = 0;
uint32_t tick = 0;

void loop()
{
    if (millis() - tick < 300) {
        return;
    }
    tick = millis();

    camera_fb_t *fb = esp_camera_fb_get();
    if (fb) {
        ok_cnt++;
        Serial.printf("КАДР ОК: %u байт  %ux%u  (успехов %u / пусто %u)\n",
                      (unsigned)fb->len, fb->width, fb->height, ok_cnt, fail_cnt);
        esp_camera_fb_return(fb);
    } else {
        fail_cnt++;
        Serial.printf("кадр пустой  (успехов %u / пусто %u)\n", ok_cnt, fail_cnt);
    }
}
