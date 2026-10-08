#ifndef _SDK_SYSEVT_H_
#define _SDK_SYSEVT_H_

typedef enum {
    SYSEVT_CONTINUE = 0,
    SYSEVT_CONSUMED = 1,
} sysevt_hdl_res;

typedef sysevt_hdl_res(*sysevt_hdl)(uint32 event_id, uint32 data, uint32 priv);

#ifdef SYS_EVENT_SUPPORT
int32 sys_event_init(uint16 evt_max_cnt);
int32 sys_event_new(uint32 event_id, uint32 data);
int32 sys_event_take(uint32 event_id, sysevt_hdl hdl, uint32 priv);
void sys_event_untake(uint32 event_id, sysevt_hdl hdl);
#else
#define sys_event_init(cnt)
#define sys_event_new(id, data)
#define sys_event_take(id, hdl, priv)
#define sys_event_untake(id, hdl)
#endif

#define SYS_EVENT(main, sub) ((main)<<16|(sub&0xffff))

enum SYSEVT_MAINID { /* uint16 */
    SYS_EVENT_NETWORK = 1,
    SYS_EVENT_WIFI,
    SYS_EVENT_LMAC,
    SYS_EVENT_SYSTEM,
    SYS_EVENT_BLE,

    ////////////////////////////////////
    SYSEVT_MAINID_ID,
};

//////////////////////////////////////////
enum SYSEVT_SYSTEM_SUBEVT { /* uint16 */
    SYSEVT_SYSTEM_RESUME = 1,
    SYSEVT_SYSTEM_SD_MOUNT,
    SYSEVT_SYSTEM_SD_UNMOUNT,
};
#define SYSEVT_NEW_SYSTEM_EVT(subevt, data)    sys_event_new(SYS_EVENT(SYS_EVENT_SYSTEM, subevt), data)

//////////////////////////////////////////
enum SYSEVT_LMAC_SUBEVT { /* uint16 */
    SYSEVT_LMAC_ACS_DONE = 1,
};
#define SYSEVT_NEW_LMAC_EVT(subevt, data)    sys_event_new(SYS_EVENT(SYS_EVENT_LMAC, subevt), data)

//////////////////////////////////////////
enum SYSEVT_WIFI_SUBEVT { /* uint16 */
    SYSEVT_WIFI_CONNECT_START = 1,
    SYSEVT_WIFI_CONNECTTED,
    SYSEVT_WIFI_CONNECT_FAIL,
    SYSEVT_WIFI_DISCONNECT,
    SYSEVT_WIFI_SCAN_START,
    SYSEVT_WIFI_SCAN_DONE,
    SYSEVT_WIFI_STA_DISCONNECT,
    SYSEVT_WIFI_STA_CONNECTTED,
    SYSEVT_WIFI_STA_PS_START,
    SYSEVT_WIFI_STA_PS_END,
    SYSEVT_WIFI_PAIR_DONE,
    SYSEVT_WIFI_TX_SUCCESS,
    SYSEVT_WIFI_TX_FAIL,    
    SYSEVT_WIFI_UNPAIR,
    SYSEVT_WIFI_WRONG_KEY,
    SYSEVT_WIFI_INTERFACE_ENABLE,
    SYSEVT_WIFI_INTERFACE_DISABLE,
    SYSEVT_WIFI_WAKEUP_HOST,
};
#define SYSEVT_NEW_WIFI_EVT(subevt, data)    sys_event_new(SYS_EVENT(SYS_EVENT_WIFI, subevt), data)

//////////////////////////////////////////
enum SYSEVT_NETWORK_SUBEVT { /* uint16 */
    SYSEVT_GMAC_LINK_UP = 1,
    SYSEVT_GMAC_LINK_DOWN,
    SYSEVT_LWIP_DHCPC_START,
    SYSEVT_LWIP_DHCPC_DONE,
    SYSEVT_WIFI_DHCPC_START,
    SYSEVT_WIFI_DHCPC_DONE,
    SYSEVT_DHCPD_NEW_IP,
    SYSEVT_DHCPD_IPPOOL_FULL,
    SYSEVT_NTP_UPDATE,
};
#define SYSEVT_NEW_NETWORK_EVT(subevt, data) sys_event_new(SYS_EVENT(SYS_EVENT_NETWORK, subevt), data)

//////////////////////////////////////////
enum SYSEVT_BLE_SUBEVT { /* uint16 */
    SYSEVT_BLE_CONNECTED = 1,
    SYSEVT_BLE_DISCONNECT,
    SYSEVT_BLE_NETWORK_CONFIGURED,
};
#define SYSEVT_NEW_BLE_EVT(subevt, data) sys_event_new(SYS_EVENT(SYS_EVENT_BLE, subevt), data)

#endif
