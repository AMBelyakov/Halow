#include "sys_config.h"
#include "basic_include.h"
#include "hal/netdev.h"
#include "lib/atcmd/libatcmd.h"
#include "lib/umac/ieee80211.h"
#include "lib/umac/wifi_cfg.h"
#include "lib/bus/xmodem/xmodem.h"
#include "lib/lmac/lmac_def.h"
#if BLE_SUPPORT
#include "lib/ble/ble_demo.h"
#include "lib/ble/ble_def.h"
#endif

#ifdef CONFIG_UMAC4
#include "lwip/ip_addr.h"
#include "lwip/icmp.h"
#include "lwip/apps/lwiperf.h"
#endif

#include "syscfg.h"

int32 sys_atcmd_loaddef(const char *cmd, char *argv[], uint32 argc)
{
    syscfg_loaddef("syscfg");
    mcu_reset();
    return 0;
}

int32 sys_atcmd_reset(const char *cmd, char *argv[], uint32 argc)
{
    atcmd_ok;
    mcu_reset();
    return 0;
}

int32 sys_atcmd_jtag(const char *cmd, char *argv[], uint32 argc)
{
    if (argc == 1) {
        jtag_map_set(os_atoi(argv[0]) ? 1 : 0);
        atcmd_ok;
    }
    return 0;
}

int32 sys_syscfg_dump_hdl(const char *cmd, char *argv[], uint32 argc)
{
    void syscfg_dump(void);
    syscfg_dump();
    return 0;
}

#ifdef CONFIG_UMAC4
int32 sys_atcmd_ping(const char *cmd, char *argv[], uint32 argc)
{
    int32 loop_cnt = 10;
    int32 pkt_size = 32;
    if(argc > 0){
        if(argc > 1) loop_cnt = os_atoi(argv[1]);
        if(argc > 2) pkt_size = os_atoi(argv[2]);
        lwip_ping(argv[0], pkt_size, loop_cnt);
    }
    return 0;
}

int32 sys_atcmd_icmp_mntr(const char *cmd, char *argv[], uint32 argc)
{
    struct netdev *ndev;
    if(argc == 2){
        ndev = (struct netdev *)dev_get(HG_WIFI0_DEVID + os_atoi(argv[0]));
        if(ndev){
            netdev_ioctl(ndev, NETDEV_IOCTL_ENABLE_ICMPMNTR, os_atoi(argv[1]), 0);
            atcmd_ok;
        }else{
            atcmd_err("invalid input");
        }
    }else{
        atcmd_err("invalid input");
    }
    return 0;
}

int32 sys_atcmd_iperf2(const char *cmd, char *argv[], uint32 argc)
{
    char *mode = NULL;

    if(argc > 0){
        mode = argv[0];
        if(os_strncmp(argv[0], "c", 1) == 0 || os_strncmp(argv[0], "C", 1) == 0) {
            atcmd_printf("%s:iperf2 TCP CLIENT mode,remote IP:%s,port:%d,time:%d\n",
                __FUNCTION__,argv[1],os_atoi(argv[2]), os_atoi(argv[3]));
            sys_lwiperf_tcp_client_start(argv[1], os_atoi(argv[2]), os_atoi(argv[3]));
        } else if (os_strncmp(argv[0], "s", 1) == 0 || os_strncmp(argv[0], "S", 1) == 0) {
            atcmd_printf("%s:iperf2 TCP Server mode,port:%d\n",__FUNCTION__,os_atoi(argv[1]));
            sys_lwiperf_tcp_server_start(os_atoi(argv[1]));
        } else {
            atcmd_printf("Unknow iperf mode:%s\n",mode);
        }
    }
    return 0;
}

int32 sys_wifi_atcmd_set_channel(const char *cmd, char *argv[], uint32 argc)
{
    int32 chan = 0, chan_max;
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("%d", ieee80211_conf_get_channel(ifidx));
    } else if (argc == 1) {
        chan = os_atoi(argv[0]);
#ifdef TXW4002ACK803
        chan_max = 16;
#else
        chan_max = 13;
#endif
        if ((chan < 1) || (chan > chan_max)) {
            atcmd_printf("+CHANNEL: ERROR, INVALID CHANNEL %d\r\n", chan);
            atcmd_error;
            return 0;
        }
        if (ifidx < 0) {
            ieee80211_conf_set_channel(WIFI_MODE_AP, chan);
            ieee80211_conf_set_channel(WIFI_MODE_WNBAP, chan);
            sys_cfgs.channel = ieee80211_conf_get_channel(WIFI_MODE_AP);
        } else {
            ieee80211_conf_set_channel(ifidx, chan);
            sys_cfgs.channel = ieee80211_conf_get_channel(ifidx);
        }
        syscfg_save();
        atcmd_ok;
    }
    return 0;
}

int32 sys_wifi_atcmd_set_encrypt(const char *cmd, char *argv[], uint32 argc)
{
    uint8 mode_sta = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
#if WIFI_REPEATER_SUPPORT
    uint8 mode_ap  = wificfg_get_ifidx(sys_cfgs.wifi_mode, 1);
#endif
    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("%d", sys_cfgs.key_mgmt == WPA_KEY_MGMT_PSK);
    } else if (argc == 1) {
        if ('1' == argv[0][0]) {
            sys_cfgs.key_mgmt = WPA_KEY_MGMT_PSK;
            if (mode_sta < 0) {
                ieee80211_conf_set_keymgmt(WIFI_MODE_AP, sys_cfgs.key_mgmt);
                ieee80211_conf_set_keymgmt(WIFI_MODE_WNBAP, sys_cfgs.key_mgmt);
            } else {
                ieee80211_conf_set_keymgmt(mode_sta, sys_cfgs.key_mgmt);
            }
#if WIFI_REPEATER_SUPPORT
            sys_cfgs.r_key_mgmt = WPA_KEY_MGMT_PSK;
            if (MODE_IS_REPEATER(sys_cfgs.wifi_mode)) {
                atcmd_printf("wifimode = %d mode = %d, r_key_mgmt = %d\r\n", sys_cfgs.wifi_mode, mode_ap, sys_cfgs.r_key_mgmt);
                ieee80211_conf_set_keymgmt(mode_ap, sys_cfgs.r_key_mgmt);
            }
#endif
            atcmd_printf("Set encrypt!\r\n");
            syscfg_save();
            atcmd_ok;
        } else if ('0' == argv[0][0]) {
            sys_cfgs.key_mgmt = WPA_KEY_MGMT_NONE;
            if (mode_sta < 0) {
                ieee80211_conf_set_keymgmt(WIFI_MODE_AP, sys_cfgs.key_mgmt);
                ieee80211_conf_set_keymgmt(WIFI_MODE_WNBAP, sys_cfgs.key_mgmt);
            } else {
                ieee80211_conf_set_keymgmt(mode_sta, sys_cfgs.key_mgmt);
            }
#if WIFI_REPEATER_SUPPORT
            sys_cfgs.r_key_mgmt = WPA_KEY_MGMT_NONE;
            if (MODE_IS_REPEATER(sys_cfgs.wifi_mode)) {
                ieee80211_conf_set_keymgmt(mode_ap, sys_cfgs.r_key_mgmt);
            }
#endif
            atcmd_printf("Clear encrypt!\r\n");
            syscfg_save();
            atcmd_ok;
        } else {
            atcmd_error;
            atcmd_printf("encrypt atcmd err\r\n");
        }
    }
    return 0;
}

int32 sys_wifi_atcmd_set_ssid(const char *cmd, char *argv[], uint32 argc)
{
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    uint8 ssid[SSID_MAX_LEN+1];
    uint8 ssid_len;

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_printf("SSID: %s\r\n", sys_cfgs.ssid);
        atcmd_ok;
        return 0;

    } else if (argc == 1) {

        ssid_len = os_strlen(argv[0]);
        if (ssid_len > SSID_MAX_LEN) {
            atcmd_printf("Input SSID length is %d, > SSID_MAX_LEN(32)\r\n",ssid_len);
            atcmd_error;
            return 0;
        }

        os_strncpy(ssid, argv[0], SSID_MAX_LEN);
        if (os_strncmp(sys_cfgs.ssid, ssid, SSID_MAX_LEN)) {
            os_memset(sys_cfgs.bssid, 0, 6);
            os_strncpy(sys_cfgs.ssid, ssid, SSID_MAX_LEN);
            atcmd_printf("set new ssid: %s\r\n", sys_cfgs.ssid);
            if (os_strlen(sys_cfgs.passwd) > 0) {
                wpa_passphrase(sys_cfgs.ssid, sys_cfgs.passwd, sys_cfgs.psk);
            }
            ieee80211_conf_set_bssid(WIFI_MODE_STA, NULL);
            ieee80211_conf_set_bssid(WIFI_MODE_WNBSTA, NULL);
            if (ifidx < 0) {
                ieee80211_conf_set_ssid(WIFI_MODE_AP, sys_cfgs.ssid);
                ieee80211_conf_set_psk(WIFI_MODE_AP, sys_cfgs.psk);
                ieee80211_conf_set_ssid(WIFI_MODE_WNBAP, sys_cfgs.ssid);
                ieee80211_conf_set_psk(WIFI_MODE_WNBAP, sys_cfgs.psk);
            } else {
                ieee80211_conf_set_ssid(ifidx, sys_cfgs.ssid);
                ieee80211_conf_set_psk(ifidx, sys_cfgs.psk);
            }
            syscfg_save();
            atcmd_ok;
            return 0;
        } else {
            atcmd_printf("set same ssid: %s\r\n", sys_cfgs.ssid);
            return 0;
        }
    }

    atcmd_error;
    return 0;
}

int32 sys_wifi_atcmd_set_key(const char *cmd, char *argv[], uint32 argc)
{
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    uint8 passwd[PASSWD_MAX_LEN+1];

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("+KEY");
        atcmd_resp("%s", sys_cfgs.passwd);
        return 0;
    } else if (argc == 1) {
        if (os_strlen(argv[0]) < 8) {
            atcmd_resp("key needs 8 bytes at least\r\n");
            atcmd_error;
        } else {
            os_strncpy(passwd, argv[0], PASSWD_MAX_LEN);
            if (os_strcmp(sys_cfgs.passwd, passwd)) {
                os_strncpy(sys_cfgs.passwd, passwd, PASSWD_MAX_LEN);
                if (os_strlen(sys_cfgs.ssid) > 0) {
                    atcmd_printf("Wpa_passphrase...\r\n");
                    wpa_passphrase(sys_cfgs.ssid, sys_cfgs.passwd, sys_cfgs.psk);
                }
                if (ifidx < 0) {
                    ieee80211_conf_set_psk(WIFI_MODE_AP, sys_cfgs.psk);
                    ieee80211_conf_set_psk(WIFI_MODE_WNBAP, sys_cfgs.psk);
                } else {
                    ieee80211_conf_set_psk(ifidx, sys_cfgs.psk);
                }
                atcmd_resp("Set new key:%s\r\n", sys_cfgs.passwd);
                syscfg_save();
                atcmd_ok;
                return 0;
           } else {
                atcmd_resp("Set same Key!\r\n");
           }
        }
    }

    return 0;
}

int32 sys_wifi_atcmd_set_psk(const char *cmd, char *argv[], uint32 argc)
{
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    int32 i = 0;
    uint8 psk[32];

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("+PSK");
        for (i = 0; i < 32; i++) {
            atcmd_printf("%02x", sys_cfgs.psk[i]);
        }
        return 0;
    } else if (argc == 1) {
        if (os_strlen(argv[0]) >= 64 && hex2bin(argv[0], psk, 32)==32) {
            if(os_memcmp(psk, sys_cfgs.psk, 32)){
                os_memset(sys_cfgs.psk, 0, sizeof(sys_cfgs.psk));
                os_memcpy(sys_cfgs.psk, psk, 32);
                if (ifidx < 0) {
                    ieee80211_conf_set_psk(WIFI_MODE_AP, sys_cfgs.psk);
                    ieee80211_conf_set_psk(WIFI_MODE_WNBAP, sys_cfgs.psk);
                } else {
                    ieee80211_conf_set_psk(ifidx, sys_cfgs.psk);
                }
                atcmd_printf("set new psk\r\n");
                syscfg_save();
            }
            atcmd_ok;
            return 0;
        }
    }
    atcmd_error;
    return 0;
}

int32 sys_wifi_atcmd_set_wifimode(const char *cmd, char *argv[], uint32 argc)
{
    uint8 mode = 0;//new_mode
    uint8 old_mode;

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("%s", wificfg_wifimode_str());
    } else if (argc == 1) {
        old_mode = sys_cfgs.wifi_mode;
        atcmd_printf("mode=%s ",argv[0]);
        if (os_strcasecmp(argv[0], "ap") == 0) {
            mode = WIFI_MODE_AP;
        } else if (os_strcasecmp(argv[0], "sta") == 0) {
            mode = WIFI_MODE_STA;
        } else if (os_strcasecmp(argv[0], "apsta") == 0) {
            mode = WIFI_MODE_AP_STA;
        }
#if WIFI_WNBSTA_SUPPORT
        else if (os_strcasecmp(argv[0], "wnbsta") == 0) {
            mode = WIFI_MODE_WNBSTA;
        } else if (os_strcasecmp(argv[0], "apwnbsta") == 0) {
            mode = WIFI_MODE_AP_WNBSTA;
        } else if (os_strcasecmp(argv[0], "wnbapwnbsta") == 0) {
            mode = WIFI_MODE_WNBAP_WNBSTA;
        }
#endif
#if WIFI_WNBAP_SUPPORT
        else if (os_strcasecmp(argv[0], "wnbap") == 0) {
            mode = WIFI_MODE_WNBAP;
        } else if (os_strcasecmp(argv[0], "wnbapsta") == 0) {
            mode = WIFI_MODE_WNBAP_STA;
        } else if (os_strcasecmp(argv[0], "apwnbap") == 0) {
            mode = WIFI_MODE_AP_WNBAP;
        } 
#endif
        else {
            printf("is not supported!\r\n");
            return 0;//-EINVAL;
        }

        printf("is supported!\r\n");
        if (mode != old_mode) {
            wificfg_set_mode(mode);
            syscfg_save();
        }
        atcmd_ok;
    }
    return 0;
}

int32 sys_wifi_atcmd_loaddef(const char *cmd, char *argv[], uint32 argc)
{
    syscfg_loaddef("syscfg");
    mcu_reset();
    return 0;
}

int32 sys_wifi_atcmd_scan(const char *cmd, char *argv[], uint32 argc)
{
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);

    if (argc == 2) {
        struct ieee80211_scandata scan;
        os_memset(&scan, 0, sizeof(scan));
        scan.chan_bitmap = 0xffff;
        scan.scan_cnt = os_atoi(argv[0]);
        scan.scan_time = os_atoi(argv[1]);
        if (ifidx < 0) {
            ieee80211_scan(WIFI_MODE_AP, 1, &scan);
            ieee80211_scan(WIFI_MODE_WNBAP, 1, &scan);
        } else {
            ieee80211_scan(ifidx, 1, &scan);
        }
    } else {
        if (ifidx < 0) {
            ieee80211_scan(WIFI_MODE_AP, 1, NULL);
            ieee80211_scan(WIFI_MODE_WNBAP, 1, NULL);
        } else {
            ieee80211_scan(ifidx, 1, NULL);
        }
    }
    atcmd_ok;
    return 0;
}

int32 sys_wifi_atcmd_pair(const char *cmd, char *argv[], uint32 argc)
{
    uint32 magic = os_atoi(argv[0]);
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);

    if(magic==0) {
        atcmd_printf("Stop pairing!\r\n");
    } else if(magic==1){
        atcmd_printf("Start pairing!\r\n");
    } else {
        atcmd_printf("Start pairing in group %d!\r\n", magic);
    }

    if (ifidx < 0) {
        ieee80211_pairing(WIFI_MODE_AP, magic);
        ieee80211_pairing(WIFI_MODE_WNBAP, magic);
    } else {
        ieee80211_pairing(ifidx, magic);
    }
    atcmd_ok;
    return 0;
}

int32 sys_wifi_atcmd_unpair(const char *cmd, char *argv[], uint32 argc)
{
    uint8 mac[6];
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    if (argc > 0 && argv[0][0] != '?') {
        STR2MAC(argv[0], mac);
        atcmd_printf("unpair:"MACSTR"\r\n", MAC2STR(mac));
        if (ifidx < 0) {
            ieee80211_unpair(WIFI_MODE_AP, mac);
            ieee80211_unpair(WIFI_MODE_WNBAP, mac);
        } else {
            ieee80211_unpair(ifidx, mac);
        }
        atcmd_ok;
    }
    return 0;
}

int32 sys_wifi_atcmd_aphide(const char *cmd, char *argv[], uint32 argc)
{
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("%d", sys_cfgs.ap_hide);
    } else if (argc == 1) {
        sys_cfgs.ap_hide = os_atoi(argv[0]) ? 1 : 0;
        if(sys_cfgs.ap_hide){
            atcmd_printf("AP_Hide enabled!\r\n");
        }else{
            atcmd_printf("AP_Hide disabled!\r\n");
        }
        if (ifidx < 0) {
            ieee80211_conf_set_aphide(WIFI_MODE_AP, sys_cfgs.ap_hide);
            ieee80211_conf_set_aphide(WIFI_MODE_WNBAP, sys_cfgs.ap_hide);
        } else {
            ieee80211_conf_set_aphide(ifidx, sys_cfgs.ap_hide);
        }
        syscfg_save();
        atcmd_ok;
    }
    return 0;
}

int32 sys_wifi_atcmd_hwmode(const char *cmd, char *argv[], uint32 argc)
{
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    if (ifidx < 0) {
        ifidx = WIFI_MODE_AP;
    }

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("%d", sys_cfgs.wifi_hwmode);
    } else if (argc == 1) {
        sys_cfgs.wifi_hwmode = os_atoi(argv[0]);
        ieee80211_conf_set_hwmode(ifidx, sys_cfgs.wifi_hwmode);
        syscfg_save();
        atcmd_ok;
    }
    return 0;
}

int32 sys_wifi_atcmd_roam(const char *cmd, char *argv[], uint32 argc)
{
    int32 chg = 0;
    int32 roaming, roam_rssi_th, roam_rssi_diff, roam_rssi_int;
    if (argc > 0 && argv[0][0] != '?') {
        roaming          = (argc > 0) ? os_atoi(argv[0]) : sys_cfgs.roam_start;
        //roaming_samefreq = (argc > 1) ? os_atoi(argv[1]) : sys_cfgs.roaming_samefreq;
        roam_rssi_th     = (argc > 2) ? os_atoi(argv[2]) : sys_cfgs.roam_rssi_th;
        roam_rssi_diff   = (argc > 3) ? os_atoi(argv[3]) : sys_cfgs.roam_rssi_diff;
        roam_rssi_int    = (argc > 4) ? os_atoi(argv[4]) : sys_cfgs.roam_rssi_int;

        chg |= (roaming != sys_cfgs.roam_start);
        //chg |= (roaming_samefreq != wnb->cfg->roaming_samefreq);
        chg |= (roam_rssi_th != sys_cfgs.roam_rssi_th);
        chg |= (roam_rssi_diff != sys_cfgs.roam_rssi_diff);
        chg |= (roam_rssi_int != sys_cfgs.roam_rssi_int);

        sys_cfgs.roam_start = roaming;
        //sys_cfgs.roaming_samefreq = roaming_samefreq;
        sys_cfgs.roam_rssi_th = roam_rssi_th;
        sys_cfgs.roam_rssi_diff = roam_rssi_diff;
        sys_cfgs.roam_rssi_int = roam_rssi_int;

        ieee80211_conf_set_roaming(sys_cfgs.wifi_mode, sys_cfgs.roam_start);
        ieee80211_conf_set_roam_config(sys_cfgs.wifi_mode, sys_cfgs.roam_rssi_th, 
                                       sys_cfgs.roam_rssi_diff, sys_cfgs.roam_rssi_int);
        atcmd_printf("set roaming %s\r\n", sys_cfgs.roam_start ? "enable" : "disable");        
        if(chg){
            syscfg_save();
        }
        atcmd_ok;
    } else {
        atcmd_resp("%s", sys_cfgs.roam_start ? "enable" : "disable");
    }
    return 0;
}

int32 sys_ble_atcmd_blenc(const char *cmd, char *argv[], uint32 argc)
{
#if BLE_SUPPORT
    extern void *g_ops;

    uint8 mode = 0;
    struct lmac_ops *lops = (struct lmac_ops *)g_ops;
    struct bt_ops *bt_ops = (struct bt_ops *)lops->btops;

    if (argc == 1) {
        mode = os_atoi(argv[0]);
        switch (mode) {
            case 0:
                if (ble_demo_stop(bt_ops)) {
                    atcmd_error;
                } else {
                    atcmd_printf("\n\nble close \r\n\n");
                }
                break;
            case 1:
            case 2:
            case 3:
                if (ble_demo_start(bt_ops, mode - 1)) {
                    atcmd_error;
                } else {
                    atcmd_printf("\n\nset ble mode = %d \r\n\n", mode);
                }
                break;
            default:
                break;
        }
    } 
#endif
    return 0;
}

int32 sys_wifi_atcmd_ft(const char *cmd, char *argv[], uint32 argc)
{
#ifdef CONFIG_IEEE80211R
    struct ieee80211_ft_param ft;
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);

    os_memset(&ft, 0, sizeof(ft));
    str2mac(argv[0], ft.bssid_new);
    atcmd_printf("FT_start: target_bssid= "MACSTR" argc= %d\r\n", MAC2STR(ft.bssid_new), argc);
    ieee80211_conf_set_ft(ifidx, &ft);
    atcmd_ok;
#endif
    return 0;
}

int32 sys_wifi_atcmd_passwd(const char *cmd, char *argv[], uint32 argc)
{
#ifdef CONFIG_SAE
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    //ieee80211_conf_set_passwd(ifidx, argv[0]);//too late, interface set
    atcmd_ok;
#endif
    return 0;
}

int32 sys_wifi_atcmd_wakeup(const char *cmd, char *argv[], uint32 argc)
{
    int32 ret = RET_OK;
    int32 ret1 = RET_ERR;
    uint8 addr[6];
    uint16 aid = 0;
    uint32 reason = DSLEEP_WK_REASON_APWK;
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 1);

    if(argc > 1) reason = os_atoi(argv[1]);
    if(argc >= 1){
        os_memset(addr, 0, 6);
        if(os_strlen(argv[0]) >= 17){
            str2mac(argv[0], addr);
        }else{
            aid = os_atoi(argv[0]);
        }

        if (ifidx < 0) {
            ret = ieee80211_conf_wakeup_sta(WIFI_MODE_AP, addr, aid, reason);
            ret1 = ieee80211_conf_wakeup_sta(WIFI_MODE_WNBAP, addr, aid, reason);
        } else {
            ret = ieee80211_conf_wakeup_sta(ifidx, addr, aid, reason);
        }

        ret = ret & ret1;
        if(ret == RET_OK){
            atcmd_ok;
        }else{
            atcmd_printf("WAKE_ERR:%d\r\n", ret);
        }
    }
    return 0;
}

int32 sys_wifi_atcmd_get_rssi(const char *cmd, char *argv[], uint32 argc)
{
    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("%d", sys_status.rssi);
    }
    return 0;
}
#endif

#if WIFI_REPEATER_SUPPORT
int32 sys_wifi_atcmd_set_rssid(const char *cmd, char *argv[], uint32 argc)
{
    uint8 mode_sta = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    uint8 mode_ap = wificfg_get_ifidx(sys_cfgs.wifi_mode, 1);
    uint8 r_ssid[SSID_MAX_LEN+1];

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("+R_SSID");
        atcmd_resp("%s", sys_cfgs.r_ssid);
        return 0;
    } else if (argc == 1) {
        os_strncpy(r_ssid, argv[0], SSID_MAX_LEN);
        if (os_strcmp(sys_cfgs.r_ssid, r_ssid)) {
            os_memset(sys_cfgs.r_ssid, 0, sizeof(sys_cfgs.r_ssid));
            os_strncpy(sys_cfgs.r_ssid, r_ssid, SSID_MAX_LEN);
            sys_cfgs.r_key_mgmt = sys_cfgs.key_mgmt;
            if (os_strlen(sys_cfgs.r_passwd) > 0) {
                wpa_passphrase(sys_cfgs.r_ssid, sys_cfgs.r_passwd, sys_cfgs.r_psk);
            }
            sys_cfgs.cfg_init = 1;
            if (MODE_IS_REPEATER(sys_cfgs.wifi_mode)) {
                ieee80211_conf_set_ssid(mode_ap, sys_cfgs.r_ssid);
                ieee80211_conf_set_keymgmt(mode_ap, sys_cfgs.r_key_mgmt);
                ieee80211_conf_set_psk(mode_ap, sys_cfgs.r_psk);
                if (sys_status.wifi_connected) {
                    ieee80211_iface_start(mode_ap);
                } else {
                    ieee80211_iface_stop(mode_ap);
                    wificfg_flush(mode_sta);
                    ieee80211_iface_start(mode_sta);
                }
            }
            syscfg_save();
            atcmd_ok;
            return 0;
        }
    }
    atcmd_error;
    return 0;
}

int32 sys_wifi_atcmd_set_rkey(const char *cmd, char *argv[], uint32 argc)
{
    uint8 mode_sta = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    uint8 mode_ap = wificfg_get_ifidx(sys_cfgs.wifi_mode, 1);
    uint8 r_passwd[PASSWD_MAX_LEN+1];


    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("+R_KEY");
        atcmd_resp("%s", sys_cfgs.r_passwd);
        return 0;
    } else if (argc == 1) {
        if (os_strlen(argv[0]) < 8) {
            atcmd_printf("rkey needs 8 bytes at least\r\n");
        } else {
            os_strncpy(r_passwd, argv[0], PASSWD_MAX_LEN);
            if (os_strcmp(sys_cfgs.r_passwd, r_passwd)) {
                os_memset(sys_cfgs.r_passwd, 0, sizeof(sys_cfgs.r_passwd));
                os_strncpy(sys_cfgs.r_passwd, r_passwd, PASSWD_MAX_LEN);
                sys_cfgs.r_key_mgmt = sys_cfgs.key_mgmt;
                if (os_strlen(sys_cfgs.r_ssid) > 0) {
                    wpa_passphrase(sys_cfgs.r_ssid, sys_cfgs.r_passwd, sys_cfgs.r_psk);
                }
                sys_cfgs.cfg_init = 1;
                if (MODE_IS_REPEATER(sys_cfgs.wifi_mode)) {
                    ieee80211_conf_set_psk(mode_ap, sys_cfgs.r_psk);
                    ieee80211_conf_set_keymgmt(mode_ap, sys_cfgs.r_key_mgmt);
                    if (sys_status.wifi_connected) {
                        ieee80211_iface_start(mode_ap);
                    } else {
                        ieee80211_iface_stop(mode_ap);
                        wificfg_flush(mode_sta);
                        ieee80211_iface_start(mode_sta);
                    }
                }
                syscfg_save();
                atcmd_ok;
                return 0;
            }
        }
    }
    atcmd_error;
    return 0;
}

int32 sys_wifi_atcmd_set_rpsk(const char *cmd, char *argv[], uint32 argc)
{
    uint8 mode_sta = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    uint8 mode_ap = wificfg_get_ifidx(sys_cfgs.wifi_mode, 1);
    int32 i = 0;
    uint8 r_psk[32];

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("+R_PSK");
        for (i = 0; i < 32; i++) {
            atcmd_printf("%02x", sys_cfgs.r_psk[i]);
        }
        return 0;
    } else if (argc == 1) {
        if (os_strlen(argv[0]) >= 64 && hex2bin(argv[0], r_psk, 32)==32) {
            if (os_memcmp(sys_cfgs.r_psk, r_psk, 32)) {
                os_memset(sys_cfgs.r_psk, 0, sizeof(sys_cfgs.r_psk));
                os_memcpy(sys_cfgs.r_psk, r_psk, 32);
                sys_cfgs.r_key_mgmt = sys_cfgs.key_mgmt;
                sys_cfgs.cfg_init = 1;
                if (MODE_IS_REPEATER(sys_cfgs.wifi_mode)) {
                    ieee80211_conf_set_psk(mode_ap, sys_cfgs.r_psk);
                    ieee80211_conf_set_keymgmt(mode_ap, sys_cfgs.r_key_mgmt);
                    if (sys_status.wifi_connected) {
                        ieee80211_iface_start(mode_ap);
                    } else {
                        ieee80211_iface_stop(mode_ap);
                        wificfg_flush(mode_sta);
                        ieee80211_iface_start(mode_sta);
                    }
                }
                syscfg_save();
                atcmd_ok;
                return 0;
            }
        }
    }
    atcmd_error;
    return 0;
}
#endif

int32 sys_wifi_atcmd_bss_bw(const char *cmd, char *argv[], uint32 argc)
{
    uint8 bw;
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    if (ifidx < 0) {
        ifidx = WIFI_MODE_AP;
    }

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("%d", sys_cfgs.bss_bw);
    } else if (argc == 1) {
        bw = os_atoi(argv[0]);
        if (AH_VALID_BW(bw)) {
            if (sys_cfgs.bss_bw!=bw) {
                sys_cfgs.bss_bw = bw;
                ieee80211_conf_set_bssbw(ifidx, sys_cfgs.bss_bw);
                syscfg_save();
            }
            atcmd_ok;
        } else {
            atcmd_error;
        }
    }
    return 0;
}

int32 sys_wifi_atcmd_chan_list(const char *cmd, char *argv[], uint32 argc)
{
    uint8 chan_cnt, i;
    uint16 chan_list[16];
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    
    if (argc == 1 && argv[0][0] == '?') {
        atcmd_printf("+CHAN_LIST:");
        for (i = 0; i < sys_cfgs.chan_cnt; ++i) {
            if (i + 1 < sys_cfgs.chan_cnt) {
                atcmd_printf("%d,", sys_cfgs.chan_list[i]);
            } else {
                atcmd_printf("%d\r\n", sys_cfgs.chan_list[i]);
            }
        }
    } else {
        chan_cnt = argc > 16 ? 16 : argc;
        for (i = 0; i < chan_cnt; ++i) {
            //printf("os_atoi(argv[i])=%d........\r\n",os_atoi(argv[i]));
            if (os_atoi(argv[i])<65536) {
                chan_list[i] = os_atoi(argv[i]);
            } else {
                atcmd_printf("invalid freq param: %d\r\n", os_atoi(argv[i]));
                atcmd_error;
                return 0;
            }
            if(sysctrl_freq_type_match(chan_list[i])==RET_ERR){
                atcmd_printf("invalid freq param: %d, module_type:%d\r\n", chan_list[i], module_efuse_info.module_type);
                atcmd_error;
                return 0;
            }
        }

        if (sys_cfgs.chan_cnt != chan_cnt || os_memcmp(chan_list, sys_cfgs.chan_list, chan_cnt * sizeof(uint16))) {
            sys_cfgs.chan_cnt = chan_cnt;
            os_memcpy(sys_cfgs.chan_list, chan_list, chan_cnt * sizeof(uint16));
            if (ifidx < 0) {
                ieee80211_conf_set_chanlist(WIFI_MODE_AP, sys_cfgs.chan_list, sys_cfgs.chan_cnt);
                ieee80211_conf_set_channel(WIFI_MODE_AP, 1);
                ieee80211_conf_set_channel(WIFI_MODE_WNBAP, 1);
                sys_cfgs.channel = ieee80211_conf_get_channel(WIFI_MODE_AP);
            } else {
                ieee80211_conf_set_chanlist(ifidx, sys_cfgs.chan_list, sys_cfgs.chan_cnt);
                ieee80211_conf_set_channel(ifidx, 1);
                sys_cfgs.channel = ieee80211_conf_get_channel(ifidx);
            }
            syscfg_save();
            atcmd_ok;
        } else {
			atcmd_ok;
		}
    }
    return 0;
}

int32 sys_wifi_atcmd_version(const char *cmd, char *argv[], uint32 argc)
{
    atcmd_resp(" v%u.%u.%u.%u-%u, app:%u\r\n", 
                (sdk_version >> 24) & 0xff,
                (sdk_version >> 16) & 0xff,
                (sdk_version >> 8) & 0xff,
                sdk_version & 0xff,
                svn_version,
                app_version);

    return 0;
}

#ifdef CONFIG_SLEEP
int32 sys_wifi_atcmd_ap_psmode(const char *cmd, char *argv[], uint32 argc)
{
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("%d", sys_cfgs.ap_psmode);
    } else if (argc == 1) {
        sys_cfgs.ap_psmode = os_atoi(argv[0]);
        ieee80211_conf_set_ap_psmode_en(ifidx, sys_cfgs.ap_psmode);
        atcmd_ok;
        syscfg_save();
    }
    return 0;
}

int32 sys_wifi_atcmd_dsleep(const char *cmd, char *argv[], uint32 argc)
{
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    struct system_sleep_param args;
    uint8 ps;

    if (argc == 1 && argv[0][0] == '?') {
        atcmd_resp("%d", sys_cfgs.ap_psmode);
    } else if (argc == 1) {
        ps = os_atoi(argv[0]);
        args.sleep_ms = 0;
        ieee80211_iface_sleep(ifidx, ps);
        if (ps == 0) {
            system_resume(ps, 0);
        } else {
            system_sleep(1, &args);
        }
        //mgr->host_alive = sys_cfgs.auto_sleep_time / sys_cfgs.beacon_int;
        atcmd_ok;
    }
    return 0;
}
#endif


int32 sys_wifi_atcmd_set_wmm_param(const char *cmd, char *argv[], uint32 argc)
{
    uint8 ac;
	uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);
    struct ieee80211_wmm_param param;
	  
    if (argc == 1 && argv[0][0] == '?') {
        ieee80211_conf_get_wmm_param(ifidx, 0, &param);
        atcmd_printf("BE cw_min=%d cw_max=%d \r\n", param.cw_min, param.cw_max);
        ieee80211_conf_get_wmm_param(ifidx, 1, &param);
        atcmd_printf("BK cw_min=%d cw_max=%d \r\n", param.cw_min, param.cw_max);
        ieee80211_conf_get_wmm_param(ifidx, 2, &param);
        atcmd_printf("VI cw_min=%d cw_max=%d \r\n", param.cw_min, param.cw_max);
        ieee80211_conf_get_wmm_param(ifidx, 3, &param);
        atcmd_printf("VO cw_min=%d cw_max=%d \r\n", param.cw_min, param.cw_max);
    } else if (argc == 3) {
        ac = os_atoi(argv[0]);
        if (ac<4) {
            ieee80211_conf_get_wmm_param(ifidx, ac, &param);
            param.cw_min = os_atoi(argv[1]);
            param.cw_max = os_atoi(argv[2]);
            ieee80211_conf_set_wmm_param(ifidx, ac, &param);
            atcmd_ok;
        } else {
            atcmd_error;
        }
    }
    
    return 0;
}
