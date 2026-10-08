
#ifndef _COMMON_ATCMD_H_
#define _COMMON_ATCMD_H_

int32 sys_atcmd_loaddef(const char *cmd, char *argv[], uint32 argc);
int32 sys_atcmd_reset(const char *cmd, char *argv[], uint32 argc);
int32 sys_atcmd_jtag(const char *cmd, char *argv[], uint32 argc);
int32 sys_syscfg_dump_hdl(const char *cmd, char *argv[], uint32 argc);

int32 sys_wifi_atcmd_set_channel(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_set_encrypt(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_set_ssid(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_set_key(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_set_psk(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_set_wifimode(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_loaddef(const char *cmd, char *argv[], uint32 argc);

int32 sys_wifi_atcmd_get_rssi(const char *cmd, char *argv[], uint32 argc);

int32 sys_wifi_atcmd_scan(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_pair(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_unpair(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_aphide(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_hwmode(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_roam(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_ft(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_passwd(const char *cmd, char *argv[], uint32 argc);

int32 sys_ble_atcmd_blenc(const char *cmd, char *argv[], uint32 argc);

int32 sys_atcmd_ping(const char *cmd, char *argv[], uint32 argc);
int32 sys_atcmd_icmp_mntr(const char *cmd, char *argv[], uint32 argc);
int32 sys_atcmd_iperf2(const char *cmd, char *argv[], uint32 argc);

int32 sys_wifi_atcmd_set_rssid(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_set_rkey(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_set_rpsk(const char *cmd, char *argv[], uint32 argc);

int32 sys_wifi_atcmd_bss_bw(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_chan_list(const char *cmd, char *argv[], uint32 argc);

int32 sys_wifi_atcmd_version(const char *cmd, char *argv[], uint32 argc);

int32 sys_wifi_atcmd_wakeup(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_ap_psmode(const char *cmd, char *argv[], uint32 argc);
int32 sys_wifi_atcmd_dsleep(const char *cmd, char *argv[], uint32 argc);

int32 sys_wifi_atcmd_set_wmm_param(const char *cmd, char *argv[], uint32 argc);

#endif
