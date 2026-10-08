
int32 sys_atcmd_sysdbg(const char *cmd, char *argv[], uint32 argc)
{
    char *arg = argv[0];
    if (argc == 2) {
        if (os_strcasecmp(arg, "heap") == 0) {
            sys_status.dbg_heap = (os_atoi(argv[1]) == 1);
        }
        if (os_strcasecmp(arg, "top") == 0) {
            sys_status.dbg_top = os_atoi(argv[1]);
        }
        if (os_strcasecmp(arg, "lmac") == 0) {
            sys_status.dbg_lmac = os_atoi(argv[1]);
        }
        if (os_strcasecmp(arg, "umac") == 0) {
            sys_status.dbg_umac = (os_atoi(argv[1]) == 1);
        }
        if (os_strcasecmp(arg, "irq") == 0) {
            sys_status.dbg_irq = (os_atoi(argv[1]) == 1);
        }
        if (os_strcasecmp(arg, "net") == 0) {
            sys_status.dbg_net = (os_atoi(argv[1]) == 1);
        }
        atcmd_ok;
    } else {
        atcmd_error;
    }
    return 0;
}

#if SYS_APP_UART_P2P
/* Аварийный люк для отката прошивки.
 *
 * uart_p2p_init() забирает UART1 себе (uart_request_irq + disable_print),
 * после чего AT-команды на нём мертвы — включая AT+FWUPG. То есть без этого
 * люка перепрошить модуль обратно можно было бы только вынув флеш-чип из
 * панельки (docs/Firmware_burn_1.md / _2.md), потому что оба софтовых пути
 * отката (WNBOTA и NETAT) требуют уже поднявшегося линка.
 *
 * Поэтому uart_p2p стартует не сразу, а через UART_P2P_START_DELAY_MS
 * (см. sys_app_init в main.c). Если в это окно прислать AT+NOP2P, флаг
 * ниже отменяет запуск НАСОВСЕМ до следующей перезагрузки, и AT-режим
 * остаётся доступен без ограничения по времени — этого хватает на
 * AT+FWUPG и минутную передачу по XMODEM.
 *
 * Порядок восстановления: обесточить -> подать питание -> в первые
 * UART_P2P_START_DELAY_MS мс послать AT+NOP2P -> дождаться OK -> AT+FWUPG.
 */
static volatile uint8 uart_p2p_inhibit = 0;

static int32 sys_atcmd_nop2p(const char *cmd, char *argv[], uint32 argc)
{
    uart_p2p_inhibit = 1;
    atcmd_ok;
    return 0;
}
#endif

static const struct hgic_atcmd static_atcmds[] = {
    { "AT+RST", sys_atcmd_reset },
    { "AT+SYSDBG", sys_atcmd_sysdbg },
    { "AT+LOADDEF", sys_atcmd_loaddef },
#if SYS_APP_UART_P2P
    { "AT+NOP2P", sys_atcmd_nop2p },
#endif

    /*TESTMODE ATCMD*/
    { "AT+ACS_START", atcmd_acs_start_hdl },
    { "AT+ACK_TO", atcmd_ack_to_extra_hdl },
    { "AT+ADC_DUMP", atcmd_adc_dump_hdl },
    { "AT+AP_SLEEP_MODE", atcmd_ap_sleep_mode },
    { "AT+ANT_DUAL", atcmd_ant_dual_hdl },
    { "AT+ANT_CTRL", atcmd_ant_ctrl_hdl },
    { "AT+ANT_AUTO", atcmd_ant_auto_hdl },
    { "AT+ANT_DEF", atcmd_ant_def_hdl },
    { "AT+BGRSSI_MARGIN", atcmd_bgrssi_margin_hdl },
    { "AT+BGRSSI_SPUR", atcmd_bgrssi_spur_hdl },
    //{ "AT+BSS_BW", atcmd_bss_bw_hdl },
    { "AT+BUS_WT", atcmd_bus_wt_hdl },
    { "AT+CCA_OBSV", atcmd_cca_obsv_hdl },
    { "AT+CCA_CE", atcmd_cca_ce_hdl },
    { "AT+CCMP_SUPPORT", atcmd_ccmp_support_hdl },
    { "AT+CHAN_SCAN", atcmd_chan_scan_hdl },
    { "AT+CS_CNT", atcmd_cs_cnt_hdl },
    { "AT+CS_EN", atcmd_cs_enable_hdl },
    { "AT+CS_NUM", atcmd_cs_num_hdl },
    { "AT+CS_PERIOD", atcmd_cs_period_hdl },
    { "AT+CS_TH", atcmd_cs_th_hdl },
    { "AT+CTS_DUP", atcmd_cts_dup_hdl },
    { "AT+EDCA_AIFS", atcmd_edca_aifs_hdl },
    { "AT+EDCA_CW", atcmd_edca_cw_hdl },
    { "AT+EDCA_TXOP", atcmd_edca_txop_hdl },
    { "AT+AP_BACKOFF", atcmd_edca_ap_backoff_hdl },
    { "AT+EVM_MARGIN", atcmd_evm_margin_hdl },
    { "AT+FREQ_LIST", atcmd_freq_list_hdl },
#if !defined (TX4001A)
    { "AT+FT_ATT", atcmd_ft_att_hdl },
#endif
    { "AT+LMAC_DBGSEL", atcmd_lmac_dbgsel_hdl },
    { "AT+LO_FREQ", atcmd_lo_freq_hdl },
    //{ "AT+LOADDEF", atcmd_loaddef_hdl },
    { "AT+MAC_ADDR", atcmd_mac_addr_hdl },
    { "AT+MCAST_DUP", atcmd_mcast_dup_hdl },
    { "AT+MCAST_REORDER", atcmd_mcast_reorder_hdl },
    { "AT+MCAST_BW", atcmd_mcast_bw_hdl },
    { "AT+MCAST_MCS", atcmd_mcast_mcs_hdl },
    { "AT+MCAST_RTS", atcmd_mcast_rts_hdl },
    { "AT+NOR_RD", atcmd_nor_rd_hdl },
    { "AT+OBSS_CCA_DIFF", atcmd_obss_cca_diff_hdl },
    { "AT+OBSS_EDCA", atcmd_obss_edca_hdl },
    { "AT+OBSS_NAV_DIFF", atcmd_obss_nav_diff_hdl },
    { "AT+OBSS_SWITCH", atcmd_obss_switch_hdl },
    { "AT+OBSS_TH", atcmd_obss_th_hdl },
    { "AT+PCF_EN", atcmd_pcf_en_hdl },
    { "AT+PCF_PERCENT", atcmd_pcf_percent_hdl },
    { "AT+PCF_PERIOD", atcmd_pcf_period_hdl },
    { "AT+PHY_RESET", atcmd_phy_reset_hdl },
    { "AT+PRI_CHAN", atcmd_set_pri_chan_hdl },
    { "AT+PRINT_PERIOD", atcmd_lmac_print_period_hdl },
    { "AT+QA_ATT", atcmd_qa_att_hdl },
    { "AT+QA_CFG", atcmd_qa_cfg_hdl },
    { "AT+QA_RESULTS", atcmd_qa_results_hdl },
    { "AT+QA_RXTHD", atcmd_qa_rxthd_hdl },
    { "AT+QA_START", atcmd_qa_start_hdl },
    { "AT+QA_TXTHD", atcmd_qa_txthd_hdl },
    { "AT+RC_NEW", atcmd_rc_new_hdl },
    { "AT+REG_RD", atcmd_reg_rd_hdl },
    { "AT+REG_WT", atcmd_reg_wt_hdl },
    //{ "AT+REBOOT", atcmd_reboot_hdl },
    { "AT+RF_RESET", atcmd_rf_reset_hdl },
    { "AT+RTS_DUP", atcmd_rts_dup_hdl },
    { "AT+RX_AGC", atcmd_rx_agc_rd_hdl },
    { "AT+RX_ERR", atcmd_rx_err_rd_hdl },
    { "AT+RX_EVM", atcmd_rx_evm_rd_hdl },
    { "AT+RX_PKTS", atcmd_rx_pkts_rd_hdl },
    { "AT+RX_REORDER", atcmd_rx_ordered_hdl },
    { "AT+RX_RSSI", atcmd_rx_rssi_rd_hdl },
    //{ "AT+RX_ADDR_FILTER", atcmd_rx_addr_filter_hdl },
    //{ "AT+RX_PHY_CHECK", atcmd_rx_phy_check_hdl },
    { "AT+SET_AGC", atcmd_set_agc_hdl },
    { "AT+SET_AGC_TH", atcmd_set_agc_threshold_hdl },
    { "AT+SET_BGRSSI", atcmd_set_bgrssi_hdl },
    { "AT+SET_BGRSSI_AVG", atcmd_set_bgrssi_avg_hdl },
    { "AT+SET_RTS", atcmd_set_rts_hdl },
    { "AT+SHORT_GI", atcmd_short_gi_hdl },
    { "AT+SHORT_TH", atcmd_short_th_hdl },
    { "AT+SLEEP_EN", atcmd_sleep_en_hdl },
    { "AT+T_SENSOR", atcmd_t_sensor_hdl },
    { "AT+TEST_START", atcmd_test_start_hdl },
    { "AT+TX_AGG_AUTO", atcmd_agg_auto_hdl },
    { "AT+TX_ATTN", atcmd_tx_attn_hdl },
    { "AT+TX_CW", atcmd_tx_cw_hdl },
    { "AT+TX_BW", atcmd_tx_bw_hdl },
    { "AT+TX_BW_DYNAMIC", atcmd_tx_bw_dynamic_hdl },
    { "AT+TX_CNT_MAX", atcmd_tx_cnt_max_hdl },
    { "AT+TX_CONT", atcmd_tx_cont_hdl },
    { "AT+TX_DELAY", atcmd_tx_delay_hdl },
    { "AT+TX_DST_ADDR", atcmd_tx_dst_addr_hdl },
    { "AT+TX_FAIL", atcmd_tx_fail_rd_hdl },
    { "AT+TX_FC", atcmd_tx_fc_hdl },
    { "AT+TX_FLAGS", atcmd_tx_flags_hdl },
    { "AT+TX_LEN", atcmd_tx_len_hdl },
    { "AT+TX_MAX_AGG", atcmd_tx_max_agg_hdl },
    { "AT+TX_MAX_SYMS", atcmd_tx_max_syms_hdl },
    { "AT+TX_MCS", atcmd_tx_mcs_hdl },
    { "AT+TX_MCS_MAX", atcmd_tx_mcs_max_hdl },
    { "AT+TX_MCS_MIN", atcmd_tx_mcs_min_hdl },
    { "AT+TX_ORDERED", atcmd_strictly_ordered_hdl },
    { "AT+TX_PHA_AMP", atcmd_tx_pha_amp_hdl },
    { "AT+TX_PKTS", atcmd_tx_pkts_rd_hdl },
    { "AT+TX_PWR_AUTO", atcmd_tx_pwr_auto_hdl },
    { "AT+TX_PWR_MAX", atcmd_tx_pwr_max_hdl },
    { "AT+TX_PWR_SUPER", atcmd_tx_pwr_super_hdl },
    { "AT+TX_PWR_SUPER_TH", atcmd_tx_pwr_super_th_hdl },
    { "AT+TX_RATE_FIXED", atcmd_tx_rate_fixed_hdl },
    { "AT+TX_START", atcmd_tx_start_hdl },
    { "AT+TX_STEP", atcmd_tx_step_hdl },
    { "AT+TX_TRIG", atcmd_tx_trig_hdl },
    { "AT+TX_TYPE", atcmd_tx_type_hdl },
    { "AT+TXOP_EN", atcmd_txop_en_hdl },
    { "AT+TX_TRV_PILOT_EN", atcmd_tx_trv_pilot_en_hdl },
    { "AT+WAKE_EN", atcmd_wake_stas_hdl },
    { "AT+XO_CS", atcmd_xo_cs_hdl },
    { "AT+XO_CS_AUTO", atcmd_xo_cs_auto_hdl },
    { "AT+LO_TABLE", atcmd_lo_table_read_hdl },
    { "AT+PS_CHECK", atcmd_ps_check_hdl },
    { "AT+RADIO_ONOFF", atcmd_radio_onoff_hdl },
    { "AT+STA_INFO", atcmd_sta_info_hdl },
    { "AT+TXPOWER", atcmd_txpower_hdl },
    { "AT+SET_VDD13", atcmd_set_vdd13_hdl },
    { "AT+SMT_DAT", atcmd_smt_dat_hdl },

    { "AT+SYSCFG", sys_syscfg_dump_hdl },
    { "AT+FWUPG", xmodem_fwupgrade_hdl },
    { "AT+SSID", sys_wifi_atcmd_set_ssid },
    { "AT+KEY", sys_wifi_atcmd_set_key },
    { "AT+PSK", sys_wifi_atcmd_set_psk },
    { "AT+ENCRYPT", sys_wifi_atcmd_set_encrypt },
    { "AT+WIFIMODE", sys_wifi_atcmd_set_wifimode },
    { "AT+CHANNEL", sys_wifi_atcmd_set_channel },
    { "AT+APHIDE", sys_wifi_atcmd_aphide },
    { "AT+SCAN", sys_wifi_atcmd_scan },
    { "AT+PAIR", sys_wifi_atcmd_pair },    
    { "AT+ICMPMNTR", sys_atcmd_icmp_mntr},
    { "AT+RSSI", sys_wifi_atcmd_get_rssi},
    
    { "AT+ROAM", sys_wifi_atcmd_roam},
#if SYS_NETWORK_SUPPORT && LWIP_RAW
    { "AT+PING", sys_atcmd_ping},
#endif
#if SYS_NETWORK_SUPPORT
    { "AT+IPERF2", sys_atcmd_iperf2},
#endif
#if WIFI_REPEATER_SUPPORT
    { "AT+R_SSID", sys_wifi_atcmd_set_rssid },
    { "AT+R_KEY", sys_wifi_atcmd_set_rkey },
    { "AT+R_PSK", sys_wifi_atcmd_set_rpsk },
#endif
    // AH特有
    { "AT+BSS_BW", sys_wifi_atcmd_bss_bw },
    { "AT+CHAN_LIST", sys_wifi_atcmd_chan_list },
    { "AT+WAKEUP", sys_wifi_atcmd_wakeup },
    { "AT+VERSION", sys_wifi_atcmd_version },

#ifdef CONFIG_SLEEP
    { "AT+AP_PSMODE", sys_wifi_atcmd_ap_psmode },
    { "AT+DSLEEP", sys_wifi_atcmd_dsleep },
#endif

    { "AT+SET_WMM", sys_wifi_atcmd_set_wmm_param },

};

__init void sys_atcmd_init(void)
{
    struct atcmd_settings setting;
    os_memset(&setting, 0, sizeof(setting));
    setting.args_count = ATCMD_ARGS_COUNT;
    setting.printbuf_size = ATCMD_PRINT_BUF_SIZE;
    setting.static_atcmds = static_atcmds;
    setting.static_cmdcnt = ARRAY_SIZE(static_atcmds);
    atcmd_uart_init(ATCMD_UARTDEV, 115200, 5, &setting);
}

