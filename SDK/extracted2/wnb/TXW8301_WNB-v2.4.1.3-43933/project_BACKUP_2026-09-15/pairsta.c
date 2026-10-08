#include "sys_config.h"
#include "typesdef.h"
#include "list.h"
#include "dev.h"
#include "devid.h"
#include "osal/string.h"
#include "osal/semaphore.h"
#include "osal/mutex.h"
#include "osal/irq.h"
#include "osal/task.h"
#include "osal/sleep.h"
#include "osal/timer.h"
#include "osal/string.h"
#include "osal/work.h"
#include "hal/gpio.h"
#include "hal/sysaes.h"
#include "lib/common/common.h"
#include "lib/common/sysevt.h"
#include "lib/syscfg/syscfg.h"
#include "lib/heap/sysheap.h"
#include "lib/skb/skb.h"
#include "lib/skb/skb_list.h"
#include "lib/bus/macbus/mac_bus.h"
#include "lib/lmac/lmac.h"
#include "lib/bus/xmodem/xmodem.h"
#include "lib/atcmd/libatcmd.h"
#include "lwip/err.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include "lwip/sys.h"
#include "lwip/ip_addr.h"
#include "lwip/tcpip.h"
#include "netif/ethernetif.h"
#include "lib/net/dhcpd/dhcpd.h"
#include "lib/umac/ieee80211.h"
#include "lib/umac/wifi_mgr.h"
#include "lib/umac/wifi_cfg.h"
#include "pairled.h"
#include "syscfg.h"


#if SYS_SAVE_PAIRSTA
static int32 sys_check_pairsta(uint8 *mac)
{
    int8 i = 0;
    for (i = 0; i < SYS_STA_MAX; i++) {
        if (MAC_EQU(sys_cfgs.pair_stas[i], mac)) {
            return 0;
        }
    }
    return 1;
}

static void sys_save_pairsta(uint8 *mac, uint8 del)
{
    int8 i = 0;
    struct ieee80211_stainfo stainfo;

    // STA mode only save one AP
    if (MODE_IS_STA(sys_cfgs.wifi_mode)) {
        if (del) {
            os_memset(sys_cfgs.pair_stas[0], 0, 6);
        } else {
            os_memcpy(sys_cfgs.pair_stas[0], mac, 6);
        }
        return;
    }

    // AP mode can save SYS_STA_MAX stas
    if (!del && !sys_check_pairsta(mac)) {
        return;
    }

    for (i = 0; i < SYS_STA_MAX; i++) {
        if (del) {
            if (MAC_EQU(sys_cfgs.pair_stas[i], mac)) {
                os_memset(sys_cfgs.pair_stas[i], 0, 6);
                return;
            }
        } else {
            if (IS_ZERO_ADDR(sys_cfgs.pair_stas[i])) {
                os_memcpy(sys_cfgs.pair_stas[i], mac, 6);
                return;
            }
        }
    }

    // find a disconnected sta if no empty stas when add save paired sta
    if (!del) {
        for (i = 0; i < SYS_STA_MAX; i++) {
            os_memset(&stainfo, 0, sizeof(stainfo));
            ieee80211_conf_get_stainfo(sys_cfgs.wifi_mode, 0, sys_cfgs.pair_stas[i], &stainfo);
            if (!stainfo.connected) {
                os_memcpy(sys_cfgs.pair_stas[i], mac, 6);
                return;
            }
        }
    }
}

int32 sys_ieee80211_event_pairsta(uint8 ifidx, uint16 evt, uint32 param1, uint32 param2)
{
    switch (evt) {
        case IEEE80211_EVENT_PAIR_SUCCESS:
            sys_save_pairsta((uint8 *)param1, 0);
            break;
        case IEEE80211_EVENT_UNPAIR_SUCCESS:
            sys_save_pairsta((uint8 *)param1, 1);
            break;
        case IEEE80211_EVENT_PRE_AUTH:
        case IEEE80211_EVENT_PRE_ASSOC:
            if (sys_cfgs.pair_conn_only) {
                return sys_check_pairsta((uint8 *)param1);
            }
            break;
    }
    return RET_OK;
}

#endif

