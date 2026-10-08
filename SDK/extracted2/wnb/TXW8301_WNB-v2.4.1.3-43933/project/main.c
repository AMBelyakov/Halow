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
#include "lib/bus/macbus/mac_bus.h"
#include "lib/bus/xmodem/xmodem.h"
#include "lib/net/skmonitor/skmonitor.h"
#include "lib/net/dhcpd/dhcpd.h"
#include "lib/umac/ieee80211.h"
#include "lib/umac/wifi_mgr.h"
#include "lib/umac/wifi_cfg.h"
#include "lib/net/utils.h"
#include "lib/common/atcmd.h"
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

#include "atcmd.c"

static struct os_work main_wk;
extern uint32_t srampool_start;
extern uint32_t srampool_end;
struct system_status  sys_status=
{
    .dbg_lmac=2,
};

void *lmacops;

extern void sys_tcptest_init(void);
extern void power_controller_init(void);
extern void lmac_transceive_statics(uint8 en);
extern int32 sys_ieee80211_event_cb(uint8 ifidx, uint16 evt, uint32 param1, uint32 param2);
extern sysevt_hdl_res sys_event_hdl(uint32 event_id, uint32 data, uint32 priv);
extern void wifi_dev_status(uint32 dev_id);

__init static void sys_cfg_load(void)
{
    if (syscfg_init("syscfg", &sys_cfgs, sizeof(sys_cfgs)) == RET_OK) {
        return;
    }

    os_printf("use default params.\r\n");
    syscfg_set_default_val();
    syscfg_save();
}


__init static void sys_role_key_init(void)
{
#if ROLE_KEY_EN
    gpio_set_dir(WNB_ROLEKEY_IO, GPIO_DIR_INPUT);
    gpio_set_mode(WNB_ROLEKEY_IO, GPIO_PULL_DOWN, GPIO_PULL_LEVEL_100K);
    // 中继模式忽略角色按键
    if (sys_cfgs.wifi_mode == WIFI_MODE_AP || sys_cfgs.wifi_mode == WIFI_MODE_STA) {
        sys_cfgs.wifi_mode = gpio_get_val(WNB_ROLEKEY_IO) ? WIFI_MODE_AP : WIFI_MODE_STA;
    }
#endif
}

__init static void sys_wifi_ap_init(void)
{
    ieee80211_iface_create_ap(WIFI_MODE_AP, IEEE80211_BAND_S1GHZ);
    ieee80211_pair_enable(WIFI_MODE_AP, WIFI_PAIR_MAGIC);
    wificfg_flush(WIFI_MODE_AP);
}

__init static void sys_wifi_sta_init(void)
{
    ieee80211_iface_create_sta(WIFI_MODE_STA, IEEE80211_BAND_S1GHZ);
    ieee80211_pair_enable(WIFI_MODE_STA, WIFI_PAIR_MAGIC);
    if (!sys_cfgs.use4addr) {
        ieee80211_conf_stabr_table(WIFI_MODE_STA, 128, 10 * 60);
    }
    wificfg_flush(WIFI_MODE_STA);
}

__init static void sys_wifi_wnbap_init(void)
{
    ieee80211_iface_create_wnbap(WIFI_MODE_WNBAP, IEEE80211_BAND_S1GHZ);
    ieee80211_pair_enable(WIFI_MODE_WNBAP, WIFI_PAIR_MAGIC);
    wificfg_flush(WIFI_MODE_WNBAP);
}

__init static void sys_wifi_wnbsta_init(void)
{
    ieee80211_iface_create_wnbsta(WIFI_MODE_WNBSTA, IEEE80211_BAND_S1GHZ);
    ieee80211_pair_enable(WIFI_MODE_WNBSTA, WIFI_PAIR_MAGIC);
    ieee80211_wnb_roam_enable(WIFI_MODE_WNBSTA);
    wificfg_flush(WIFI_MODE_WNBSTA);
}

__init static void sys_wifi_start(void)
{
    uint8 ifidx = wificfg_get_ifidx(sys_cfgs.wifi_mode, 0);

    if (ifidx < 0) {
        ieee80211_iface_start(WIFI_MODE_AP);
        ieee80211_iface_start(WIFI_MODE_WNBAP);
    } else {
        ieee80211_iface_start(ifidx);
    }
}

__init static void sys_wifi_start_acs(void *ops)
{
    int32 ret;
    struct lmac_acs_ctl acs_ctl;

    if (sys_cfgs.channel == 0 && MODE_IS_AP(sys_cfgs.wifi_mode)) {
        acs_ctl.enable     = sys_cfgs.acs_enable;
        acs_ctl.scan_ms    = sys_cfgs.acs_tmo;
        acs_ctl.chn_bitmap = ~0;
        ret = lmac_start_acs(ops, &acs_ctl, 1);  //阻塞式扫描
        if (ret != RET_ERR) {
            sys_cfgs.channel = ret;
        }
    }
}

__init static void sys_wifi_init(void)
{
    struct lmac_init_param lparam;
    struct ieee80211_initparam param;

    skbpool_init(SKB_POOL_ADDR, (uint32)SKB_POOL_SIZE, 90, 0);
    os_memset(&lparam, 0, sizeof(lparam));
    lparam.rxbuf = WIFI_RX_BUFF_ADDR;
    lparam.rxbuf_size = WIFI_RX_BUFF_SIZE;
    lparam.tdma_buff = TDMA_BUFF_ADDR;
    lparam.tdma_buff_size = TDMA_BUFF_SIZE;

#ifdef DUAL_ANT_OPT
    lparam.dual_ant = 1;//enable dual ant
    lparam.dual_ant_ctrl_io = ANT_CTRL_PIN;
#else
    lparam.dual_ant = 0;//disable dual ant
#endif

    lmacops = lmac_ah_init(&lparam); 
    syscfg_set_default_chanlist();

    os_memset(&param, 0, sizeof(param));
    param.vif_maxcnt = 4;
    param.sta_maxcnt = SYS_STA_MAX;
    param.bss_maxcnt = 32;
    param.bss_lifetime = 300; //300 seconds
    param.evt_cb = sys_ieee80211_event_cb;
    ieee80211_init(&param);
    ieee80211_support_txw830x(lmacops);

    ieee80211_deliver_init(128, 60);

#if WIFI_AP_SUPPORT
    sys_wifi_ap_init();
#endif

#if WIFI_STA_SUPPORT
    sys_wifi_sta_init();
#endif

#if WIFI_WNBAP_SUPPORT
    sys_wifi_wnbap_init();
#endif
    
#if WIFI_WNBSTA_SUPPORT
    sys_wifi_wnbsta_init();
#endif

#if WIFI_PSALIVE_SUPPORT
    wifi_mgr_enable_psalive();
#endif
    sys_wifi_start_acs(lmacops);
    sys_wifi_start();
}

__init static void sys_network_init(void)
{
#if SYS_NETWORK_SUPPORT
    ip_addr_t ipaddr, netmask, gw;
    struct netdev *ndev;

    tcpip_init(NULL, NULL);
    sock_monitor_init();

    /*register wifi netif: w0*/
    ndev = (struct netdev *)dev_get(HG_WIFI0_DEVID);
    if (ndev) {
        ipaddr.addr  = sys_cfgs.ipaddr;
        netmask.addr = sys_cfgs.netmask;
        gw.addr      = sys_cfgs.gw_ip;
        lwip_netif_add(ndev, "w0", &ipaddr, &netmask, &gw);
        lwip_netif_set_default(ndev);
        os_printf("add w0 interface!\r\n");
        if (sys_cfgs.dhcpc_en) {
            sys_status.dhcpc_done = 0;
            lwip_netif_set_dhcp2("w0", 1);
            os_printf("start dhcp client ...\r\n");
        }
    }

#if 0
    /*register gmac netif: e0, can not enable WIFI_BRIDGE_EN*/
    ndev = (struct netdev *)dev_get(HG_GMAC_DEVID);
    if (ndev) {
        lwip_netif_add(ndev, "e0", NULL, NULL, NULL);
        lwip_netif_set_default(ndev);
        lwip_netif_set_dhcp2("e0", 1);
        os_printf("add e0 interface!\r\n");
    }
#endif

#endif
}

static void sys_dhcpd_start()
{
    struct dhcpd_param param;

    if (sys_cfgs.dhcpd_en && sys_cfgs.wifi_mode == WIFI_MODE_AP) {
        os_memset(&param, 0, sizeof(param));
        param.start_ip   = sys_cfgs.dhcpd_startip;
        param.end_ip     = sys_cfgs.dhcpd_endip;
        param.netmask    = sys_cfgs.netmask;
        param.lease_time = sys_cfgs.dhcpd_lease_time;
        param.dns1       = sys_cfgs.ipaddr;
        param.dns2       = sys_cfgs.ipaddr;
        param.router     = sys_cfgs.ipaddr;
        if (dhcpd_start("w0", &param)) {
            os_printf("dhcpd start error\r\n");
        }
    }
}

#if SYS_APP_UART_P2P
static struct os_work uart_p2p_wk;

/* Отложенный старт прозрачного режима. Пока он не сработал, UART0 держит
 * atcmd, и модуль отвечает на AT — это единственное окно, в котором можно
 * запустить AT+FWUPG после перехода на эту прошивку. Подробности и порядок
 * восстановления — в комментарии к AT+NOP2P в atcmd.c. */
static int32 uart_p2p_start_work(struct os_work *work)
{
    if (uart_p2p_inhibit) {
        os_printf("uart_p2p: cancelled by AT+NOP2P, staying in AT mode\r\n");
        return 0;
    }
    uart_p2p_init(UART_P2P_DEV, UART_P2P_BAUDRATE);
    return 0;
}
#endif

__init static void sys_app_init(void)
{
#if SYS_APP_DHCPD
    sys_dhcpd_start();
#endif

#if SYS_APP_WNBOTA
    wnb_ota_init();
#endif

#if SYS_APP_NETAT
    net_atcmd_init();
#endif

#if SYS_APP_PAIR
    sys_pairled_init();
#endif

#if SYS_APP_NETLOG
    netlog_init(64320);
#endif

#if SYS_APP_SNTP && SYS_NETWORK_SUPPORT
    sntp_client_init("ntp.aliyun.com", 60);
#endif

#if SYS_APP_UHTTPD && SYS_NETWORK_SUPPORT
    uhttpd_start(NULL, 80);
#endif

#if SYS_DEV_DOMAIN && SYS_NETWORK_SUPPORT
    dns_redirect_init();
    dns_redirect_add(sys_cfgs.devname, "w0");
#endif

#if SYS_APP_UART_P2P
    OS_WORK_INIT(&uart_p2p_wk, uart_p2p_start_work, 0);
    os_run_work_delay(&uart_p2p_wk, UART_P2P_START_DELAY_MS);
#endif

    /*
        ...
    */
}

static void sys_dhcpc_check(void)
{
    if (sys_cfgs.dhcpc_en && !sys_status.dhcpc_done) {
        ip_addr_t ip = lwip_netif_get_ip2("w0");
        if (ip.addr == 0) {
            lwip_netif_set_dhcp2("w0", 1);
        }
    }
}

static void sys_print_dbgtime(uint32 *buff, uint32 size)
{
#if SYS_APP_SNTP
    struct timeval tv;
    gettimeofday(&tv, 0);
    tv.tv_sec  += 8 * 3600; //时区
    os_printf("system time: %s\r\n", ctime((const time_t *)&tv.tv_sec));
#endif
}

static void sys_print_dbgtop(uint32 *buff, uint32 size)
{
    if (sys_status.dbg_top) {  //打印CPU使用率
        cpu_loading_print(sys_status.dbg_top == 2, (struct os_task_info *)buff, size / sizeof(struct os_task_info));
    }
}

static void sys_print_dbgheap(uint32 *buff, uint32 size)
{
    if (sys_status.dbg_heap) { //打印Heap使用情况
        sysheap_status(&sram_heap, buff, size / 4, 0);
#ifdef PSRAM_HEAP
        sysheap_status(&psram_heap, buff, size / 4, 0);
#endif
    } else {
    }
}

void sys_print_dbglmac(uint32 *buff, uint32 size)
{
    if (sys_status.dbg_lmac) {
        lmac_transceive_statics(sys_status.dbg_lmac);
    }
}

void sys_print_dbgumac(uint32 *buff, uint32 size)
{
    if (sys_status.dbg_umac) { //打印WIFI调试信息
        os_printf("-----------------------------------------------------\r\n");
        ieee80211_status((uint8 *)buff, size);
        wifi_dev_status(HG_WIFI0_DEVID);
    }
}

static void sys_print_dbgnet(uint32 *buff, uint32 size)
{
    struct netif *nif;

    if (sys_status.dbg_net) {
        os_printf("-----------------------------------------------------\r\n");
        os_printf("Network Info:\r\n");
        nif = netif_find("w0");
        if (nif) {
            os_printf("  w0: (%s) "IPSTR"/"IPSTR"/"IPSTR"\r\n",
                      (sys_cfgs.dhcpc_en && sys_status.dhcpc_done) ? "DHCP" : "Static",
                      IP2STR_N(ip_addr_get_ip4_u32(&nif->ip_addr)),
                      IP2STR_N(ip_addr_get_ip4_u32(&nif->netmask)),
                      IP2STR_N(ip_addr_get_ip4_u32(&nif->gw)));
        }

        nif = netif_find("e0");
        if (nif) {
            os_printf("  e0: (%s) "IPSTR"/"IPSTR"/"IPSTR"\r\n", sys_cfgs.dhcpc_en ? "DHCP" : "Static",
                      IP2STR_N(ip_addr_get_ip4_u32(&nif->ip_addr)),
                      IP2STR_N(ip_addr_get_ip4_u32(&nif->netmask)),
                      IP2STR_N(ip_addr_get_ip4_u32(&nif->gw)));
        }

#if IP_NAT
        os_printf("-----------------------------------------------------\r\n");
        ip4_nat_status();
#endif

        if (sys_cfgs.dhcpd_en) {
            os_printf("-----------------------------------------------------\r\n");
            dhcpd_dump_ippool();
        }

    }
}

static void sys_dbginfo_print(void)
{
    static int8 print_interval = 0;
#if 0
    static uint32 _print_buf[256];
#else
    uint32 _print_buf[256];
    ASSERT(sizeof(_print_buf) < 1600); //使用task堆栈，避免堆栈溢出
#endif

    if (print_interval++ >= 5) { // 5秒打印一次
        sys_print_dbgtop(_print_buf, sizeof(_print_buf));
        sys_print_dbgheap(_print_buf, sizeof(_print_buf));
        sys_print_dbglmac(_print_buf, sizeof(_print_buf));
        sys_print_dbgumac(_print_buf, sizeof(_print_buf));
        sys_print_dbgtime(_print_buf, sizeof(_print_buf));
        sys_print_dbgnet(_print_buf, sizeof(_print_buf));
        print_interval = 0;
    }
}

static int32 sys_main_loop(struct os_work *work)
{
    sys_dbginfo_print();

#if SYS_NETWORK_SUPPORT
    sys_dhcpc_check();
#endif

    /*
        ....
    */

    /*run again after 1000 ms.*/
    os_run_work_delay(&main_wk, 1000);
    return 0;
}

__init int main(void)
{
    mcu_watchdog_timeout(5);
    sys_cfg_load();
    syscfg_check();
    sys_event_init(32);
    sys_event_take(0xffffffff, sys_event_hdl, 0);
    sys_atcmd_init();
    sys_role_key_init();
    sys_wifi_init();
    sys_network_init();
    sys_app_init();
    OS_WORK_INIT(&main_wk, sys_main_loop, 0);
    os_run_work_delay(&main_wk, 1000);
    return 0;
}

