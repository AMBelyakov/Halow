
// @file    pin_function.c
// @author  wangying
// @brief   This file contains all the mars pin functions.

// Revision History
// V1.0.0  06/01/2019  First Release, copy from 4001a project
// V1.0.1  07/05/2019  add lmac pin-func
// V1.0.2  07/06/2019  add sdio pull-up regs config
// V1.0.3  07/09/2019  add agc/rx-bw/lo-freq-idx gpio control
// V1.0.4  07/18/2019  change gpio-agc default index to 5
// V1.0.5  07/19/2019  uart1 only init tx
// V1.0.6  07/23/2019  add uart-rx pull-up resistor config
// V1.0.7  07/24/2019  switch-en1 disable; delete fdd/tdd macro-def switch
// V1.0.8  07/26/2019  not use pb17 for mac debug for it is used to reset ext-rf
// V1.0.9  07/29/2019  add function dbg_pin_func()
// V1.1.0  02/11/2020  add spi-pin-function
// V1.1.1  02/27/2020  fix uart1 pin-function
// V1.2.0  03/02/2020  add uart0-pin code and rf-pin code
// V1.2.1  03/26/2020  fix vmode pin
// V1.2.2  04/14/2020  use pa2 as lmac debug1:rx_req
// V1.2.3  09/12/2020  uart0 fix to A10/A11, uart1 fix to A12/A13

#include "sys_config.h"
#include "typesdef.h"
#include "errno.h"
#include "list.h"
#include "dev.h"
#include "devid.h"
#include "hal/gpio.h"
#include "lib/misc/mcu/mcu_util.h"

/** 
  * @brief  Configure the GPIO pin driver strength.
  * @param  pin       : which pin to set.\n
  *                     This parameter can be Px_y where x can be (A..C) and y can be (0..15)\n
  *                     But the value of the y only be (0..5) when x is C.
  * @strength         : Driver strength to configure the GPIO pin, reference @ref gpio_private_pin_driver_strength.
  * @return
  *         - RET_OK  : Configure the GPIO pin driver strength successfully.
  *         - RET_ERR : Configure the GPIO pin driver strength unsuccessfully.
  */
int32 gpio_driver_strength(uint32 pin, enum pin_driver_strength strength)
{
    struct gpio_device *gpio = gpio_get(pin);
    if (gpio && ((const struct gpio_hal_ops *)gpio->dev.ops)->ioctl) {
        return ((const struct gpio_hal_ops *)gpio->dev.ops)->ioctl(gpio, pin, GPIO_CMD_DRIVER_STRENGTH, strength, 0);
    }
    return RET_ERR;
}


/** 
  * @brief  Configure the GPIO module AFIO.
  * @param  pin       : which pin to set.\n
  *                     This parameter can be Px_y where x can be (A..C) and y can be (0..15)\n
  *                     But the value of the y only be (0..5) when x is C.
  * @afio             : AFIO value, reference @ref gpio_private_afio_set.
  * @return
  *         - RET_OK  : GPIO module configure AFIO successfully.
  *         - RET_ERR : GPIO module configure AFIO unsuccessfully.
  */
int32 gpio_set_altnt_func(uint32 pin, enum gpio_afio_set afio)
{
    struct gpio_device *gpio = gpio_get(pin);
    if (gpio && ((const struct gpio_hal_ops *)gpio->dev.ops)->ioctl) {
        return ((const struct gpio_hal_ops *)gpio->dev.ops)->ioctl(gpio, pin, GPIO_CMD_AFIO_SET, afio, 0);
    }
    return RET_ERR;
}


int32 gpio_analog(uint32 pin, enum gpio_afio_set afio)
{
    struct gpio_device *gpio = gpio_get(pin);
    if (gpio && ((const struct gpio_hal_ops *)gpio->dev.ops)->ioctl) {
        return ((const struct gpio_hal_ops *)gpio->dev.ops)->ioctl(gpio, pin, GPIO_GENERAL_ANALOG, afio, 0);
    }
    return RET_ERR;
}

__weak void user_pin_func(int dev_id, int request){};

static int uart_pin_func(int dev_id, int request)
{
    int ret = RET_OK;

    switch (dev_id) {
        case HG_UART0_DEVID:
#ifdef DUAL_UART_DBG_PRINT
                if (request) {
                    gpio_set_altnt_func(PA_31, 9);
                } else {
                    gpio_set_dir(PA_31, GPIO_DIR_INPUT);
                }
#else
                if (request) {
                    gpio_set_mode(PIN_UART0_RX_A10_F4, GPIO_PULL_UP, GPIO_PULL_LEVEL_10K);
                    gpio_set_altnt_func(PIN_UART0_RX_A10_F4, 4);
                    gpio_set_altnt_func(PIN_UART0_TX_A11_F4, 4);
                } else {
                    gpio_set_dir(PIN_UART0_RX_A10_F4, GPIO_DIR_INPUT);
                    gpio_set_dir(PIN_UART0_TX_A11_F4, GPIO_DIR_INPUT);
                }
#endif
            break;
        case HG_UART1_DEVID:
            if (request) {
#ifdef UART_TX_PA31
                jtag_map_set(0);
                gpio_set_altnt_func(PA_13, 10);//uart1-rx
                gpio_set_mode(PA_13, GPIO_PULL_UP, GPIO_PULL_LEVEL_10K);
                gpio_set_altnt_func(PA_31, 10);//uart1-tx
                gpio_set_mode(PA_31, GPIO_PULL_UP, GPIO_PULL_LEVEL_NONE);
#else
                gpio_set_altnt_func(PIN_UART1_RX_A12_F3, 3);//uart1-rx
                gpio_set_mode(PIN_UART1_RX_A12_F3, GPIO_PULL_UP, GPIO_PULL_LEVEL_10K);
                gpio_set_altnt_func(PIN_UART1_TX_A13_F3, 3);//uart1-tx
                gpio_set_mode(PA_13, GPIO_PULL_UP, GPIO_PULL_LEVEL_NONE);
#endif
            } else {
#ifdef UART_TX_PA31
                gpio_set_dir(PA_13, GPIO_DIR_INPUT);
                gpio_set_dir(PA_31, GPIO_DIR_INPUT);
#else
                gpio_set_dir(PA_13, GPIO_DIR_INPUT);
                gpio_set_dir(PA_12, GPIO_DIR_INPUT);
#endif
            }
            break;
        default:
            ret = EINVAL;
            break;
    }
    return ret;
}

static int gmac_pin_func(int dev_id, int request)
{
    int ret = RET_OK;

    switch (dev_id) {
        case HG_GMAC_DEVID:
            if (request) {
                gpio_set_altnt_func(PIN_GMAC_RMII_REF_CLKIN, 2);
//                gpio_set_altnt_func(PIN_GMAC_RMII_RX_ER, 2);
                gpio_set_altnt_func(PIN_GMAC_RMII_RXD0, 2);
                gpio_set_altnt_func(PIN_GMAC_RMII_RXD1, 2);
                gpio_set_altnt_func(PIN_GMAC_RMII_TXD0, 2);
                gpio_set_altnt_func(PIN_GMAC_RMII_TXD1, 2);
                gpio_set_altnt_func(PIN_GMAC_RMII_CRS_DV, 2);
                gpio_set_altnt_func(PIN_GMAC_RMII_TX_EN, 2);
#ifndef HG_GMAC_IO_SIMULATION
                gpio_set_altnt_func(PIN_GMAC_RMII_MDIO, 2);
                gpio_set_altnt_func(PIN_GMAC_RMII_MDC, 2);
#endif
                /* Enable the hysteresis function to reduce the effect of
                 * glitches as much as possible.
                 */
                gpio_ioctl(PIN_GMAC_RMII_REF_CLKIN, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_GMAC_RMII_RXD0, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_GMAC_RMII_RXD1, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_GMAC_RMII_TXD0, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_GMAC_RMII_TXD1, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_GMAC_RMII_CRS_DV, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_GMAC_RMII_TX_EN, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
            } else {
                gpio_set_dir(PIN_GMAC_RMII_REF_CLKIN, GPIO_DIR_INPUT);
//                gpio_set_dir(PIN_GMAC_RMII_RX_ER, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_GMAC_RMII_RXD0, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_GMAC_RMII_RXD1, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_GMAC_RMII_TXD0, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_GMAC_RMII_TXD1, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_GMAC_RMII_CRS_DV, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_GMAC_RMII_TX_EN, GPIO_DIR_INPUT);
//                gpio_set_dir(PIN_GMAC_RMII_MDIO, GPIO_DIR_INPUT);
//                gpio_set_dir(PIN_GMAC_RMII_MDC, GPIO_DIR_INPUT);
            }
            break;
        default:
            ret = EINVAL;
            break;
    }
    return ret;
}

//To fix gmac bugs
void gmac_csr_dv_disable(int dev_id)
{
    gpio_set_dir(PIN_GMAC_RMII_CRS_DV, GPIO_DIR_INPUT);
}

//To fix gmac bugs
void gmac_csr_dv_enable(int dev_id)
{
    gpio_set_altnt_func(PIN_GMAC_RMII_CRS_DV, 2);
}

static int usb_pin_func(int dev_id, int request)
{
    int ret = RET_OK;

    switch (dev_id) {
        case HG_USBDEV_DEVID:
            if (request) {
                gpio_analog(PIN_USB_DM_ANA, 1);
                gpio_analog(PIN_USB_DP_ANA, 1);
            } else {
                gpio_set_dir(PIN_USB_DM_ANA, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_USB_DP_ANA, GPIO_DIR_INPUT);
            }
            break;
        default:
            ret = EINVAL;
            break;
    }
    return ret;
}

static int sdio_pin_func(int dev_id, int request)
{
    int ret = RET_OK;

    switch (dev_id) {
        case HG_SDIOSLAVE_DEVID:
            if (request) {
                gpio_set_altnt_func(PIN_SDCLK, 0);
                gpio_set_altnt_func(PIN_SDCMD, 0);
                gpio_set_mode(PIN_SDCMD, GPIO_PULL_UP, GPIO_PULL_LEVEL_100K);
                gpio_set_altnt_func(PIN_SDDAT0, 0);
                gpio_set_mode(PIN_SDDAT0, GPIO_PULL_UP, GPIO_PULL_LEVEL_100K);
                gpio_set_altnt_func(PIN_SDDAT1, 0);
                gpio_set_mode(PIN_SDDAT1, GPIO_PULL_UP, GPIO_PULL_LEVEL_100K);
                gpio_set_altnt_func(PIN_SDDAT2, 0);
                gpio_set_mode(PIN_SDDAT2, GPIO_PULL_UP, GPIO_PULL_LEVEL_100K);
                gpio_set_altnt_func(PIN_SDDAT3, 0);
                gpio_set_mode(PIN_SDDAT3, GPIO_PULL_UP, GPIO_PULL_LEVEL_100K);
//              #ifdef RAISE_SDIO_DS
                gpio_driver_strength(PIN_SDCMD, GPIO_DS_14MA);
                gpio_driver_strength(PIN_SDDAT0, GPIO_DS_14MA);
                gpio_driver_strength(PIN_SDDAT1, GPIO_DS_14MA);
                gpio_driver_strength(PIN_SDDAT2, GPIO_DS_14MA);
                gpio_driver_strength(PIN_SDDAT3, GPIO_DS_14MA);
//              #endif

                gpio_ioctl(PIN_SDCMD, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_SDCLK, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_SDDAT0, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_SDDAT1, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_SDDAT2, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
                gpio_ioctl(PIN_SDDAT3, GPIO_INPUT_DELAY_ON_OFF, 1, 0);
            } else {
                gpio_set_dir(PIN_SDCLK, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_SDCMD, GPIO_DIR_INPUT);
                gpio_set_mode(PIN_SDCMD, GPIO_PULL_UP, GPIO_PULL_LEVEL_NONE);
                gpio_set_dir(PIN_SDDAT0, GPIO_DIR_INPUT);
                gpio_set_mode(PIN_SDDAT0, GPIO_PULL_UP, GPIO_PULL_LEVEL_NONE);
                gpio_set_dir(PIN_SDDAT1, GPIO_DIR_INPUT);
                gpio_set_mode(PIN_SDDAT1, GPIO_PULL_UP, GPIO_PULL_LEVEL_NONE);
                gpio_set_dir(PIN_SDDAT2, GPIO_DIR_INPUT);
                gpio_set_mode(PIN_SDDAT2, GPIO_PULL_UP, GPIO_PULL_LEVEL_NONE);
                gpio_set_dir(PIN_SDDAT3, GPIO_DIR_INPUT);
                gpio_set_mode(PIN_SDDAT3, GPIO_PULL_UP, GPIO_PULL_LEVEL_NONE);
            }
            break;
        default:
            ret = EINVAL;
            break;
    }
    return ret;
}

static int spi_pin_func(int dev_id, int request)
{
    int ret = RET_OK;

    switch (dev_id) {
        case HG_SPI0_DEVID:
            if (request) {
                gpio_set_dir(PIN_SPI0_CS, GPIO_DIR_OUTPUT);
                gpio_set_val(PIN_SPI0_CS, 1);
                gpio_set_altnt_func(PIN_SPI0_CLK, 0);
                gpio_set_altnt_func(PIN_SPI0_IO0, 0);
                gpio_set_altnt_func(PIN_SPI0_IO1, 0);
            } else {
                //gpio_set_dir(PIN_SPI0_CS, GPIO_DIR_INPUT);//201218
                gpio_set_dir(PIN_SPI0_CS, GPIO_DIR_OUTPUT);
                gpio_set_val(PIN_SPI0_CS, 1);
                gpio_set_dir(PIN_SPI0_CLK, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_SPI0_IO0, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_SPI0_IO1, GPIO_DIR_INPUT);
                gpio_set_altnt_func(PIN_MAC_DBG1_A2_F8, 8);
                //switch to uart0
                if (PIN_UART0_RX == PIN_UART0_RX_A2_F4) {
                    gpio_set_altnt_func(PIN_UART0_RX_A2_F4, 4);
                }
                if (PIN_UART0_TX == PIN_UART0_TX_A3_F4) {
                    gpio_set_altnt_func(PIN_UART0_TX_A3_F4, 4);
                }
#if defined K_VMODE_CNTL
                gpio_set_dir(PIN_PA_VMODE, GPIO_DIR_OUTPUT);
                gpio_set_val(PIN_PA_VMODE, 0); //PA3 PA_VMODE=0 to select ePA high power output
#endif
            }
            break;
        case HG_SPI1_DEVID:
            if (request) {
                gpio_set_dir(PIN_SPI1_CS, GPIO_DIR_OUTPUT);
                gpio_set_val(PIN_SPI1_CS, 1);
                gpio_set_altnt_func(PIN_SPI1_CLK, 3);
                gpio_set_altnt_func(PIN_SPI1_IO0, 3);
                gpio_set_altnt_func(PIN_SPI1_IO1, 3);
            } else {
                //gpio_set_dir(PIN_SPI1_CS, GPIO_DIR_INPUT);//201218
                gpio_set_dir(PIN_SPI1_CS, GPIO_DIR_OUTPUT);
                gpio_set_val(PIN_SPI1_CS, 1);
                gpio_set_dir(PIN_SPI1_CLK, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_SPI1_IO0, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_SPI1_IO1, GPIO_DIR_INPUT);
            }
            break;
        case HG_SPI3_DEVID:
            if (request) {
                gpio_set_altnt_func(PIN_SPI3_CS, 1);
                gpio_set_altnt_func(PIN_SPI3_CLK, 1);
                gpio_set_altnt_func(PIN_SPI3_IO0, 1);
                gpio_set_altnt_func(PIN_SPI3_IO1, 1);
            } else {
                gpio_set_dir(PIN_SPI3_CS, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_SPI3_CLK, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_SPI3_IO0, GPIO_DIR_INPUT);
                gpio_set_dir(PIN_SPI3_IO1, GPIO_DIR_INPUT);
            }
            break;
        default:
            ret = EINVAL;
            break;
    }
    return ret;
}

static int iic_pin_func(int dev_id, int request)
{
    int ret = RET_OK;

    switch (dev_id) {
        case HG_I2C0_DEVID:
//            gpio_set_dir(PIN_IIC0_SCL_MAP0, GPIO_DIR_OUTPUT);
//            gpio_set_dir(PIN_IIC0_SDA_MAP0, GPIO_DIR_OUTPUT);
//            SYSCTRL->IO_MAP |= IO_MAP_IIC0_MAP0_MSK;
//            gpio_release(PIN_IIC0_SCL_MAP0);
//            gpio_release(PIN_IIC0_SDA_MAP0);
            break;
        default:
            ret = EINVAL;
            break;
    }
    return ret;
}

int pin_func(int dev_id, int request)
{
    int ret = RET_OK;

    sysctrl_unlock();
    
    switch (dev_id) {
        case HG_UART0_DEVID:
        case HG_UART1_DEVID:
            ret = uart_pin_func(dev_id, request);
            break;
        case HG_GMAC_DEVID:
            ret = gmac_pin_func(dev_id, request);
            break;
        case HG_USBDEV_DEVID:
            ret = usb_pin_func(dev_id, request);
            break;
        case HG_SDIOSLAVE_DEVID:
            ret = sdio_pin_func(dev_id, request);
            break;
        case HG_SPI0_DEVID:
        case HG_SPI1_DEVID:
        case HG_SPI3_DEVID:
            ret = spi_pin_func(dev_id, request);
            break;
        case HG_I2C0_DEVID:
            ret = iic_pin_func(dev_id, request);
            break;
        default:
            break;
    }
    user_pin_func(dev_id, request);
    sysctrl_lock();    
    return ret;
}

