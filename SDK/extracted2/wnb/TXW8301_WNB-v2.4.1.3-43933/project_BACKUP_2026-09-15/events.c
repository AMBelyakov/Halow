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
#include "lib/umac/wifi_cfg.h"
#include "lib/net/utils.h"
#include "lwip/err.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include "lwip/sys.h"
#include "lwip/ip_addr.h"
#include "lwip/tcpip.h"
#include "netif/ethernetif.h"
#include "lwip/apps/netbiosns.h"
#include "pairled.h"
#include "syscfg.h"

extern int32 sys_ieee80211_event_pairsta(uint8 ifidx, uint16 evt, uint32 param1, uint32 param2);
extern int32 sys_ieee80211_event_pairled(uint8 ifidx, uint16 evt, uint32 param1, uint32 param2);

sysevt_hdl_res sys_event_hdl(uint32 event_id, uint32 data, uint32 priv)
{
#if SYS_NETWORK_SUPPORT
    struct netif *nif;
#endif

    switch (event_id) {
        case SYS_EVENT(SYS_EVENT_WIFI, SYSEVT_WIFI_UNPAIR):
            syscfg_save();
            break;
        case SYS_EVENT(SYS_EVENT_WIFI, SYSEVT_WIFI_PAIR_DONE):
            if (data) { //pair success
                syscfg_save();
            }
            break;
        case SYS_EVENT(SYS_EVENT_WIFI, SYSEVT_WIFI_CONNECTTED):
            sys_status.wifi_connected = 1;
#if SYS_NETWORK_SUPPORT
            if(sys_cfgs.dhcpc_en){
                if(sys_cfgs.roam_start && sys_status.dhcpc_done) break;
                os_printf(KERN_NOTICE"wifi connected, start dhcp client ...\r\n");
                sys_status.dhcpc_done = 0;
                lwip_netif_set_dhcp2("w0", 1);
            }
#endif

#if WIFI_REPEATER_SUPPORT
            if (MODE_IS_REPEATER(sys_cfgs.wifi_mode) && sys_cfgs.cfg_init) {
                uint8 mode_ap = wificfg_get_ifidx(sys_cfgs.wifi_mode, 1);
                os_printf("repeater: start hotspot ...\r\n");
                ieee80211_conf_set_ssid(mode_ap, sys_cfgs.r_ssid);
                ieee80211_conf_set_keymgmt(mode_ap, sys_cfgs.r_key_mgmt);
                ieee80211_conf_set_psk(mode_ap, sys_cfgs.r_psk);
                ieee80211_iface_start(mode_ap);
            }
#endif

            break;
        case SYS_EVENT(SYS_EVENT_WIFI, SYSEVT_WIFI_DISCONNECT):
            sys_status.wifi_connected = 0;
#if WIFI_REPEATER_SUPPORT
            if (MODE_IS_REPEATER(sys_cfgs.wifi_mode) && sys_cfgs.cfg_init) {
                uint8 mode_ap = wificfg_get_ifidx(sys_cfgs.wifi_mode, 1);
#if SYS_NETWORK_SUPPORT
                ip_addr_t ipaddr, netmask, gw;
                ipaddr.addr  = sys_cfgs.ipaddr;
                netmask.addr = sys_cfgs.netmask;
                gw.addr      = sys_cfgs.gw_ip;
                lwip_netif_set_ip2("w0", &ipaddr, &netmask, &gw);
#endif
                ieee80211_iface_stop(mode_ap);
            }
#endif
            break;

#if SYS_NETWORK_SUPPORT
        case SYS_EVENT(SYS_EVENT_NETWORK, SYSEVT_LWIP_DHCPC_DONE):
            if (MODE_IS_AP(sys_cfgs.wifi_mode) && sys_cfgs.dhcpd_en == 1) {
                os_printf(KERN_NOTICE"AP: dhcp done, stop dhcpd and restart ap\r\n");
                dhcpd_stop("w0");
                os_printf("dhcpd stop\r\n");
                ieee80211_iface_stop(sys_cfgs.wifi_mode);
                ieee80211_iface_start(sys_cfgs.wifi_mode);
            }

            sys_status.dhcpc_done = 1;
            nif = netif_find("w0");
            sys_cfgs.ipaddr = nif->ip_addr.addr;
            sys_cfgs.netmask = nif->netmask.addr;
            sys_cfgs.gw_ip = nif->gw.addr;
            os_printf(KERN_NOTICE"dhcp done, ip:"IPSTR", mask:"IPSTR", gw:"IPSTR"\r\n",
                      IP2STR_N(sys_cfgs.ipaddr),
                      IP2STR_N(sys_cfgs.netmask),
                      IP2STR_N(sys_cfgs.gw_ip));
            break;
#endif
    }
    return SYSEVT_CONTINUE;
}


int32 sys_ieee80211_event_cb(uint8 ifidx, uint16 evt, uint32 param1, uint32 param2)
{
    int32 ret = RET_OK;

#if SYS_SAVE_PAIRSTA
    ret = sys_ieee80211_event_pairsta(ifidx, evt, param1, param2);
    if (ret) {
        return ret;
    }
#endif

#if SYS_APP_PAIR
    ret = sys_ieee80211_event_pairled(ifidx, evt, param1, param2);
    if (ret) {
        return ret;
    }
#endif

    /*
        add other wifi event proc function at here.
        ....
    */

    switch (evt) {
        case IEEE80211_EVENT_CONNECTED:
            os_memcpy(sys_status.bssid, param1, 6);
            sys_status.channel = ieee80211_conf_get_channel(WIFI_MODE_STA);
            break;
        case IEEE80211_EVENT_RSSI:
            sys_status.rssi = (int8)param1;
            break;
        case IEEE80211_EVENT_EVM:
            sys_status.evm = (int8)param1;
            break;
        case IEEE80211_EVENT_PAIR_START:
            os_printf("inteface%d: pairing start\r\n", ifidx);
            sys_status.pair_success = 0;
            break;
        case IEEE80211_EVENT_PAIR_SUCCESS:
            sys_status.pair_success = 1;
            os_printf("inteface%d: sta "MACSTR" pairing success\r\n", ifidx, MAC2STR((uint8 *)param1));
            break;
        case IEEE80211_EVENT_PAIR_DONE:
            if (sys_status.pair_success && sys_cfgs.wifi_mode == WIFI_MODE_STA) {
                ieee80211_conf_get_ssid(sys_cfgs.wifi_mode, sys_cfgs.ssid);
                ieee80211_conf_get_psk(sys_cfgs.wifi_mode, sys_cfgs.psk);
                sys_cfgs.key_mgmt = ieee80211_conf_get_keymgmt(sys_cfgs.wifi_mode);
                ieee80211_conf_get_bssid(sys_cfgs.wifi_mode, sys_cfgs.bssid);
            }
            sys_event_new(SYS_EVENT(SYS_EVENT_WIFI, SYSEVT_WIFI_PAIR_DONE), sys_status.pair_success);
            os_printf("inteface%d: pairing done\r\n", ifidx);
            break;
        case IEEE80211_EVENT_UNPAIR_SUCCESS:
            if (sys_cfgs.wifi_mode == WIFI_MODE_STA) {
                ieee80211_conf_get_ssid(sys_cfgs.wifi_mode, sys_cfgs.ssid);
                ieee80211_conf_get_psk(sys_cfgs.wifi_mode, sys_cfgs.psk);
                sys_cfgs.key_mgmt = ieee80211_conf_get_keymgmt(sys_cfgs.wifi_mode);
                ieee80211_conf_get_bssid(sys_cfgs.wifi_mode, sys_cfgs.bssid);
            }
            sys_event_new(SYS_EVENT(SYS_EVENT_WIFI, SYSEVT_WIFI_UNPAIR), 0);
            os_printf("inteface%d unpair sta: "MACSTR"\r\n", ifidx, MAC2STR((uint8 *)param1));
            break;
        case IEEE80211_EVENT_CHANNEL_CHANGE:
            os_printf("channel change: %d -> %d\r\n", param1, param2);
            sys_cfgs.channel = param2;
            break;
        default:
            break;
    }
    return ret;
}

