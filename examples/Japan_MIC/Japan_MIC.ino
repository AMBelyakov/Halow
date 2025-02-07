

#include "utilities.h"
#include <SPI.h>
#include <Wire.h>

#include "FS.h"
#include "SD.h"
#include "SPI.h"

#define BUF_MAX_LEN 20

#define AH_Rx00P_RESPONE_OK 1
#define AH_Rx00P_RESPONE_ERROR 2

TaskHandle_t led_handle;

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

    sendAT("+test_start=1");  //进入测试模式；
    delay(100);

    sendAT("+lo_freq=920000"); //配置中心频点，这里以 920M 举例；
    delay(100);

    sendAT("+bss_bw=2");        //配置工作 BSS 带宽，这里以 bss_bw 2M 为例；
    delay(100);

    sendAT("+Txpower=20");    //如果希望修改发射功率， 则设置 Txpower，最大为 20（默认值） ，
    delay(100);                            //可以往小调整，但是不建议小于 14，否则 Tx 性能会变差；

    sendAT("+tx_start=1");  //使能TX
    delay(100);

    sendAT("+tx_delay=100");     //将 tx 两个 packet 之间的延时设置为 100ms
    delay(100);

    sendAT("+tx_cont=1");     //如果希望发送信号连续，设置 tx_cont=1，按正常封包发送时 tx_cont=0；默认是 0；
    delay(100);


    // sendAT("+SYSDBG=LMAC,0");
    // if (waitResponse() == AH_Rx00P_RESPONE_OK)
    //     SerialMon.println("AT+SYSDBG SUCCEED");
    // else
    // {
    //     at_cnt++;
    //     SerialMon.println("AT+SYSDBG ERROR");
    // }

    // sendAT("+BSS_BW=8");
    // if (waitResponse() == AH_Rx00P_RESPONE_OK)
    //     SerialMon.println("AT+BSS_BW SUCCEED");
    // else
    // {
    //     at_cnt++;
    //     SerialMon.println("AT+BSS_BW FAILD");
    // }

    // sendAT("+MODE=AP");
    // if (waitResponse() == AH_Rx00P_RESPONE_OK)
    //     SerialMon.println("AT+MODE=AP SUCCEED");
    // else
    // {
    //     at_cnt++;
    //     SerialMon.println("AT+MODE=AP FAILD");
    // }

    return (at_cnt == 0);
}
#endif


void led_task(void *param)
{
    while (1)
    {
        digitalWrite(BOARD_LED, !digitalRead(BOARD_LED));
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void setup()
{
    Serial.begin(115200);

    delay(3000);

    Wire.begin(BOARD_I2C_SDA, BOARD_I2C_SCL);
    SPI.begin(TF_SPI_SCK, TF_SPI_MISO, TF_SPI_MOSI, TF_SPI_CS);
    SerialAT.begin(115200, SERIAL_8N1, SERIAL_AT_RXD, SERIAL_AT_TXD);

    TX_AH_init();

    pinMode(BOARD_LED, OUTPUT);
    xTaskCreate(led_task, "led_task", 1024 * 3, NULL, 1, &led_handle);
}

void loop()
{
    while (SerialAT.available())
    {
        SerialMon.write(SerialAT.read());
    }
    while (SerialMon.available())
    {
        SerialAT.write(SerialMon.read());
    }
}
