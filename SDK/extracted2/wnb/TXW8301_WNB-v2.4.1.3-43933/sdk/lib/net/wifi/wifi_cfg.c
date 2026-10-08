#include "sys_config.h"
#include "typesdef.h"
#include "list.h"
#include "dev.h"
#include "devid.h"
#include "osal/string.h"
#include "osal/mutex.h"
#include "osal/task.h"
#include "osal/semaphore.h"
#include "osal/timer.h"
#include "osal/work.h"
#include "hal/gpio.h"
#include "hal/dma.h"
#include "lib/heap/sysheap.h"
#include "lib/syscfg/syscfg.h"
#include "lib/umac/wifi_mgr.h"
#include "lib/atcmd/libatcmd.h"
#include "lib/lmac/lmac.h"
#include "syscfg.h"

__weak int32 wificfg_save(int8 force)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_ifidx(uint8 wifi_mode, uint8 switch_ap)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_mode(uint8 mode)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_mode(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_conn_state(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_stacnt(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_bss_bw(uint8 bss_bw)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_bss_bw(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_tx_mcs(uint8 tx_mcs)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_channel(uint8 channel)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_chan_list(uint16 *chan_list, uint8 chan_cnt)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_macaddr(uint8 *addr)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_ssid(uint8 *ssid)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_bssid(uint8 *bssid)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_mcast_key(uint8 *key)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_wpa_psk(uint8 *key)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_psk(uint8 *key)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_key_mgmt(uint32 key_mgmt)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_ssid(uint8 ssid[32])
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_bssid(uint8 *bssid)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_wpa_psk(uint8 psk[32])
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_chan_list(uint16 *chan_list, uint8 chan_cnt)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_acs(uint8 acs, uint8 tmo)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_pri_chan(uint8 pri_chan)
{return -ENOTSUPP;}

__weak int32 wificfg_set_tx_power(uint8 txpower)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_txpower(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_beacon_int(uint32 beacon_int)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_heartbeat_int(uint32 heartbeat_int)
{return -ENOTSUPP;}

__weak int32 wificfg_set_bss_maxidle(uint32 max_idle)
{return -ENOTSUPP;}

__weak int32 wificfg_set_wkio_mode(uint8 mode)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_dtim_period(uint32 dtim_period)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_psmode(uint8 psmode)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_wkdata_save(uint8 wkdata_save)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_autosleep(uint8 autosleep)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_psconnect(uint8 period, uint8 roundup)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_load_def(uint8 reset)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_sleep_aplost_time(uint32 time)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_agg_cnt(uint8 agg_cnt)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_agg_cnt(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_auto_chan_switch(uint8 disable)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_reassoc_wkhost(uint8 enable)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_wakeup_io(uint8 io, uint8 edge)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_auto_sleep_time(uint8 time)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_pair_autostop(uint8 en)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_super_pwr(uint8 super_pwr)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_repeater_ssid(uint8 *ssid)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_repeater_psk(uint8 *psk, uint32 len)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_auto_save(uint8 off)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_dcdc13(uint8 en)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_acktmo(uint16 tmo)
{return -ENOTSUPP;}

__weak int32 wificfg_set_pa_pwrctrl_dis(uint8 dis)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_reason_code(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_status_code(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_dhcpc_en(uint8 en)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_mcast_txparam(uint8 *data)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_ant_auto_off(uint8 off)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_ant_sel(uint8 sel)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_ant_sel(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_wkhost_reasons(uint8 *reasons, uint8 count)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_mac_filter_en(uint8 en)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_use2addr(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_roaming(uint8 *vals, uint8 count)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_ap_hide(uint8 en)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_dual_ant(uint8 en)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_max_txcnt(uint8 frm_max, uint8 rts_max)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_dup_filter_en(uint8 en)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_dis_1v1_m2u(uint8 dis)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_rtc(uint8 *data)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_dis_psconnect(uint8 dis)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_freq_range(uint16 *freq_start, uint16 *freq_end, uint8 *chan_bw)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_cca_for_ce(uint8 en)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_ap_psmode(uint8 en)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_tx_bw(uint8 tx_bw)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_ap_chan_switch(uint8 chan, uint8 counter)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_get_curr_freq(void)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_radio_onoff(uint8 data)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_connect_paironly(uint8 en)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_paired_stas(uint8 *mac_list, uint8 cnt)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_wait_psmode(uint8 mode)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_standby(uint8 channel, uint32 period_ms)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_wkupdata_mask(uint8 offset, uint8 *mask, uint32 mask_len)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_wakeup_data(uint8 *data, uint32 data_len)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_wkdata_svr_ip(uint32 svr_ip)
{
    return -ENOTSUPP;
}
__weak int32 wificfg_set_passwd(uint8 *passwd)
{
    return -ENOTSUPP;
}

