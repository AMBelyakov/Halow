#include "sys_config.h"
#include "typesdef.h"
#include "list.h"
#include "dev.h"
#include "devid.h"
#include "osal/string.h"
#include "osal/semaphore.h"
#include "osal/mutex.h"
#include "osal/irq.h"
#include "osal/work.h"
#include "osal/sleep.h"
#include "osal/timer.h"
#include "hal/gpio.h"
#include "hal/uart.h"
#include "lib/common/common.h"
#include "lib/common/sysevt.h"
#include "lib/heap/sysheap.h"
#include "lib/syscfg/syscfg.h"
#include "lib/lmac/lmac.h"
#include "lib/skb/skbpool.h"
#include "lib/atcmd/libatcmd.h"
#include "lib/bus/xmodem/xmodem.h"
#include "lib/net/skmonitor/skmonitor.h"
#include "lib/net/dhcpd/dhcpd.h"
#include "lib/umac/ieee80211.h"
#include "lwip/err.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include "lwip/sys.h"
#include "lwip/ip_addr.h"
#include "lwip/tcpip.h"
#include "netif/ethernetif.h"
#include "syscfg.h"

#if SYS_APP_PAIR
static struct os_work ledctrl_wk;
static struct os_work pairkey_wk;
static struct os_work rolekey_wk;

struct {
    uint8 init: 1, last_val: 1, def_val: 1, success: 1;
} sys_pairctrl;

struct {
    uint8 init: 1, last_val: 1, def_val: 1;
} sys_rolectrl;

struct {
    uint8 init: 1, conn: 1, rssi1: 1, rssi2: 1, rssi3: 1, val: 1, pair: 1;
    uint8 wk_delay;
} sys_ledctrl;

int32 sys_ieee80211_event_pairled(uint8 ifidx, uint16 evt, uint32 param1, uint32 param2)
{
    int32 sta_cnt = 0;
    switch (evt) {
        case IEEE80211_EVENT_CONNECTED:
            sys_ledctrl.conn  = 1;
            break;
        case IEEE80211_EVENT_DISCONNECTED:
            sta_cnt = ieee80211_conf_get_stacnt(ifidx);
            if (sta_cnt == 0) {
                sys_ledctrl.conn  = 0;
                sys_ledctrl.rssi1 = 0;
                sys_ledctrl.rssi2 = 0;
                sys_ledctrl.rssi3 = 0;
            }
            break;
        case IEEE80211_EVENT_RSSI:
            sta_cnt = ieee80211_conf_get_stacnt(ifidx);
            if (sta_cnt == 0) {
                sys_ledctrl.rssi1 = 0;
                sys_ledctrl.rssi2 = 0;
                sys_ledctrl.rssi3 = 0;
            } else if (sta_cnt == 1) {
                // param2 -> aid=0 表示来自sta的信号，中继只显示来自ap的信号
                if (MODE_IS_REPEATER(sys_cfgs.wifi_mode) && (uint16)param2 != 0) {
                    break;
                }
                sys_ledctrl.conn  = 1;
                sys_ledctrl.rssi1 = ((int8)param1 > -72) ? 1 : 0;
                sys_ledctrl.rssi2 = ((int8)param1 > -60) ? 1 : 0;
                sys_ledctrl.rssi3 = ((int8)param1 > -48) ? 1 : 0;
            } else if (sta_cnt > 1) {
                // 排除中继连接2个sta，会来回闪
                if (MODE_IS_REPEATER(sys_cfgs.wifi_mode)) {
                    break;
                }
                sys_ledctrl.conn  = 1;
                sys_ledctrl.rssi1 = 1;
                sys_ledctrl.rssi2 = 1;
                sys_ledctrl.rssi3 = 1;
            }
            break;
        case IEEE80211_EVENT_INTERFACE_DISABLE:
            sys_ledctrl.conn  = 0;
            sys_ledctrl.rssi1 = 0;
            sys_ledctrl.rssi2 = 0;
            sys_ledctrl.rssi3 = 0;
            break;
        case IEEE80211_EVENT_PAIR_START:
            sys_ledctrl.pair  = 1;
            sys_ledctrl.wk_delay = 255;
            break;
        case IEEE80211_EVENT_PAIR_SUCCESS:
            sys_pairctrl.success = 1;
            sys_ledctrl.wk_delay = 80;
            break;
        case IEEE80211_EVENT_PAIR_DONE:
            sta_cnt = ieee80211_conf_get_stacnt(ifidx);
            sys_ledctrl.conn = (sta_cnt > 0) ? 1 : 0;
            sys_ledctrl.pair = 0;
            sys_ledctrl.wk_delay = 100;
            break;
        default:
            break;
    }
    return RET_OK;
}

static int32 sys_pairkey_val(void)
{
    int32 i, v;
    int32 v0 = 0, v1 = 0;

    for (i = 0; i < 50; i++) {
        v = gpio_get_val(WNB_PAIRKEY_IO);
        if (v) {
            v1++;
        } else  {
            v0++;
        }
    }
    return (v1 > v0 ? 1 : 0);
}

static int32 sys_pairled_work(struct os_work *work)
{
    if (!sys_ledctrl.init) {
        sys_ledctrl.init = 1;
        sys_ledctrl.wk_delay = 100;
        sys_ledctrl.val      = 1;
        sys_ledctrl.pair     = 0;
        jtag_map_set(0); // AH网桥默认使用了调试口做信号灯，需要关闭调试功能
        gpio_set_dir(WNB_CONN_IO, GPIO_DIR_OUTPUT);
        gpio_set_dir(WNB_RSSI_IO1, GPIO_DIR_OUTPUT);
        gpio_set_dir(WNB_RSSI_IO2, GPIO_DIR_OUTPUT);
        gpio_set_dir(WNB_RSSI_IO3, GPIO_DIR_OUTPUT);
        // 初始化闪烁
        for (int i = 0; i < 4; ++i) {
            gpio_set_val(WNB_CONN_IO, i & 0x01);
            gpio_set_val(WNB_RSSI_IO1, i & 0x01);
            gpio_set_val(WNB_RSSI_IO2, i & 0x01);
            gpio_set_val(WNB_RSSI_IO3, i & 0x01);
            os_sleep_ms(500);
        }
    }

    if (!sys_ledctrl.pair) {
        gpio_set_val(WNB_CONN_IO, !sys_ledctrl.conn);
        gpio_set_val(WNB_RSSI_IO1, !sys_ledctrl.rssi1);
        gpio_set_val(WNB_RSSI_IO2, !sys_ledctrl.rssi2);
        gpio_set_val(WNB_RSSI_IO3, !sys_ledctrl.rssi3);
    } else {
        gpio_set_val(WNB_CONN_IO, sys_ledctrl.val);
        sys_ledctrl.val = !sys_ledctrl.val;
    }

    os_run_work_delay(&ledctrl_wk, sys_ledctrl.wk_delay);
    return 0;
}

static int32 sys_pairkey_work(struct os_work *work)
{
    int32 new_val;

    if (!sys_pairctrl.init) {
        sys_pairctrl.init = 1;
        gpio_set_dir(WNB_PAIRKEY_IO, GPIO_DIR_INPUT);
        gpio_set_mode(WNB_PAIRKEY_IO, GPIO_PULL_UP, GPIO_PULL_LEVEL_10K);
        new_val = sys_pairkey_val();
        sys_pairctrl.def_val  = new_val;
        sys_pairctrl.last_val = new_val;
    } else {
        new_val = sys_pairkey_val();
        if (new_val != sys_pairctrl.last_val) {
            if (new_val == sys_pairctrl.def_val) {
                ieee80211_pairing(sys_cfgs.wifi_mode, 0);
            } else {
                sys_pairctrl.success = 0;
                ieee80211_pairing(sys_cfgs.wifi_mode, 1);
            }
            sys_pairctrl.last_val = new_val;
        }
    }
    os_run_work_delay(&pairkey_wk, 100);
    return 0;
}

static int32 sys_rolekey_work(struct os_work *work)
{
    int32 new_val;

    if (!sys_rolectrl.init) {
        sys_rolectrl.init = 1;
        // 已提前初始化
        new_val = gpio_get_val(WNB_ROLEKEY_IO);
        sys_rolectrl.def_val  = new_val;
        sys_rolectrl.last_val = new_val;
    } else {
        new_val = gpio_get_val(WNB_ROLEKEY_IO);
        if (new_val != sys_rolectrl.last_val) {
            mcu_reset();
            sys_rolectrl.last_val = new_val;
        }
    }
    os_run_work_delay(&rolekey_wk, 1000);
    return 0;
}

int sys_pairled_init(void)
{
    OS_WORK_INIT(&ledctrl_wk, sys_pairled_work, 0);
    OS_WORK_INIT(&pairkey_wk, sys_pairkey_work, 0);
    OS_WORK_INIT(&rolekey_wk, sys_rolekey_work, 0);
    os_run_work_delay(&ledctrl_wk, 100);
    os_run_work_delay(&pairkey_wk, 100);
    os_run_work(&rolekey_wk);
    return 0;
}

#endif

