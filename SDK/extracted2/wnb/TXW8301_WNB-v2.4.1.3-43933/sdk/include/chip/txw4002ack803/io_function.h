/**
  ******************************************************************************
  * @file       sdk\include\chip\txw4002ack803\io_function.h
  * @author     HUGE-IC Application Team
  * @version    V1.0.0
  * @date       2022-02-23
  * @brief      This file contains all the GPIO functions.
  * @copyright  Copyright (c) 2016-2022 HUGE-IC
  ******************************************************************************
  * @attention
  * Only used for txw4002a.
  * 
  *
  *
  *
  ******************************************************************************
  */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __IO_FUNCTION_H
#define __IO_FUNCTION_H

#ifdef __cplusplus
extern "C" {
#endif

#include "typesdef.h"

/** @addtogroup Docxygenid_GPIO_enum
  * @{
  */

/**
  * @brief Enumeration constant for GPIO command.
  * @note
  *       Enum number start from 0x101.
  */
enum gpio_cmd {
    /*! GPIO cmd afio set
     */
    GPIO_CMD_AFIO_SET = 0x101,

    /*! GPIO pin driver strength config
     */
    GPIO_CMD_DRIVER_STRENGTH,

    /*! GPIO speed config
     */
    GPIO_CMD_SPEED,
};


/**
  * @breif : enum of GPIO afio set
  */
enum gpio_afio_set {
    GPIO_AF_0  = 0,
    GPIO_AF_1,
    GPIO_AF_2,
    GPIO_AF_3,
    GPIO_AF_4,
    GPIO_AF_5,
    GPIO_AF_6,
    GPIO_AF_7,
    GPIO_AF_8,
    GPIO_AF_9,
    GPIO_AF_10,
    GPIO_AF_11,
    GPIO_AF_12,
    GPIO_AF_13,
    GPIO_AF_14,
    GPIO_AF_15,
};

/**
  * @breif : enum of GPIO pull level
  */
enum gpio_pull_level {
    /*! gpio pull level : NONE
     */
    GPIO_PULL_LEVEL_NONE = 0,
    /*! gpio pull level : 100K
     */
    GPIO_PULL_LEVEL_100K = 1,
    /*! gpio pull level : 10K
     */
    GPIO_PULL_LEVEL_10K  = 2,
    /*! gpio pull level : 3.4k
     */
    GPIO_PULL_LEVEL_3_4K = 6,
};

/**
  * @breif : enum of GPIO driver strength
  */
enum pin_driver_strength {
    GPIO_DS_7MA = 0, //6.8mA in mars
    GPIO_DS_14MA,    //13.5mA in mars
    GPIO_DS_21MA,    //20mA in mars
    GPIO_DS_28MA,    //27mA in mars
    GPIO_DS_33MA,
    GPIO_DS_40MA,
    GPIO_DS_47MA,
    GPIO_DS_53MA
} ;

/**
  * @breif : enum of GPIO speed
  */
enum gpio_speed_en {
    /*! gpio speed low
     */
    GPIO_SPEED_LOW = 0,
    /*! gpio speed high
     */
    GPIO_SPEED_HIGH = 1,
};

/** @} Docxygenid_IO_function_enum*/

int32 gpio_driver_strength(uint32 pin, enum pin_driver_strength strength);
int32 gpio_set_altnt_func(uint32 pin, enum gpio_afio_set afio);
int32 gpio_analog(uint32 pin, enum gpio_afio_set afio);


#ifdef __cplusplus
}
#endif
#endif

/*************************** (C) COPYRIGHT 2016-2022 HUGE-IC ***** END OF FILE *****/

