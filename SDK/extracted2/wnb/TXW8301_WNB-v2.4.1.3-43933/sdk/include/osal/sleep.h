
#ifndef __OS_SLEEP_H_
#define __OS_SLEEP_H_

#ifdef __CSKY__
#include "osal/csky/sleep.h"
#endif

#include "typesdef.h"
#include "osal/time.h"

#ifdef __cplusplus
extern "C" {
#endif

/*jiffies is 64bit*/
#ifndef DIFF_JIFFIES
#define DIFF_JIFFIES(j1,j2) ((j2)-(j1))
#endif

#ifndef TIME_AFTER
/* returns true if the time a is after time b. */
#define TIME_AFTER(a,b)     ((int64)(b) - (int64)(a) < 0)
#endif

typedef enum {
    SYSTEM_SLEEP_TYPE_SRAM_WIFI      = 1,
    SYSTEM_SLEEP_TYPE_WIFI_DSLEEP    = 2,
    SYSTEM_SLEEP_TYPE_SRAM_ONLY      = 3,
    SYSTEM_SLEEP_TYPE_LIGHT_SLEEP    = 4,
    SYSTEM_SLEEP_TYPE_RTCC           = 5,
} SYSTEM_SLEEP_TYPE;

typedef enum {
    DSLEEP_WK_REASON_NORMAL             = 0,
    DSLEEP_WK_REASON_TIMER              = 1,
    DSLEEP_WK_REASON_TIM                = 2,
    DSLEEP_WK_REASON_BC_TIM             = 3,
    DSLEEP_WK_REASON_IO                 = 4,
    DSLEEP_WK_REASON_BEACON_LOST        = 5,
    DSLEEP_WK_REASON_AP_ERROR           = 6,
    DSLEEP_WK_REASON_HB_TIMEOUT         = 7,
    DSLEEP_WK_REASON_WK_DATA            = 8,
    DSLEEP_WK_REASON_MCLR               = 9,
    DSLEEP_WK_REASON_LVD                = 10,
    DSLEEP_WK_REASON_PIR                = 11,
    DSLEEP_WK_REASON_APWK               = 12,
    DSLEEP_WK_REASON_PS_DISCONNECT      = 13,
    DSLEEP_WK_REASON_STANDBY            = 14,
    DSLEEP_WK_REASON_MAX_IDLE_TMO       = 15,
    DSLEEP_WK_REASON_LOW_BAT            = 16,
//    DSLEEP_WK_REASON_OTHER              = 17,

    DSLEEP_WK_REASON_STA_ERROR          = 20,
    DSLEEP_WK_REASON_SLEEPED_STA_ERROR  = 21,
    DSLEEP_WK_REASON_STA_DATA           = 22,
    DSLEEP_WK_REASON_AP_PAIR            = 23,
    DSLEEP_WK_REASON_KEY_UPDATE         = 24,
} DSLEEP_WK_REASON;

typedef enum {
    SYS_SLEEPCB_ACTION_RESUME  = 0,
    SYS_SLEEPCB_ACTION_SUSPEND = 1,
} SYS_SLEEPCB_ACTION;

typedef enum {
    SYS_SLEEPCB_STEP_1,
    SYS_SLEEPCB_STEP_2,
    SYS_SLEEPCB_STEP_3,
    SYS_SLEEPCB_STEP_4,
} SYS_SLEEPCB_STEP;

struct system_sleep_param {
    uint32 sleep_ms;
    uint8  wkup_io_sel[6];//sel IO0 - IO5
    uint8  wkup_io_en;//0: dis; 1 en
    uint8  wkup_io_edge;//0:Rising ; 1: Falling
};

struct sys_sleepcb_param {
    uint8 action, step;
    union {
        struct {
            uint8 wkreason;
        } resume;
        struct {
            struct system_sleep_param *param;
        } suspend;
    };
};

typedef int32(*sys_sleepcb)(uint16 type, struct sys_sleepcb_param *args, void *priv);

void os_sleep(int sec);
void os_sleep_ms(int msec);
extern void os_sleep_us(int us);

void usleep(unsigned long usec);
unsigned int sleep(unsigned int us);
void delay_us(uint32 n);

int sys_sleepcb_init(void);
int sys_register_sleepcb(sys_sleepcb cb, void *priv);
int sys_suspend(uint16 type, struct system_sleep_param *args);
int sys_resume(uint16 type, uint8 wkreason);

void sys_wakeup_host(void);
void sys_enter_sleep(void);
uint8 sys_wakeup_reason(void);

void system_sleep(uint16 type, struct system_sleep_param *args);
void system_resume(uint16 type, uint8 wkreason);

#ifdef __cplusplus
}
#endif

#endif

