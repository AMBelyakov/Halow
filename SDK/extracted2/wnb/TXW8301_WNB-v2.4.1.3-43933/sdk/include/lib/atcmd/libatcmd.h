#ifndef _HUGEIC_ATCMD_H_
#define _HUGEIC_ATCMD_H_

#ifdef __cplusplus
extern "C" {
#endif

typedef void(*hgic_atcmd_outhdl)(void *priv, uint8 *data, int32 len);
typedef int32(*hgic_atcmd_hdl)(const char *cmd, char *argv[], uint32 argc);

struct atcmd_settings{
    uint8  args_count, separator;
    uint16 static_cmdcnt;
    uint32 printbuf_size;
    const struct hgic_atcmd *static_atcmds;
};

struct hgic_atcmd{
    const char *name;
    hgic_atcmd_hdl hdl;
};

struct atcmd_dataif {
    int32(*write)(struct atcmd_dataif *dataif, uint8 *buf, int32 len);
    int32(*read)(struct atcmd_dataif  *dataif, uint8 *buf, int32 len);
};


#define atcmd_dbg(fmt, ...)   //os_printf("%s:%d::"fmt, __FUNCTION__, __LINE__, ##__VA_ARGS__)
#define atcmd_err(fmt, ...)   os_printf(fmt, ##__VA_ARGS__)

#define atcmd_resp(fmt, ...)  atcmd_printf("%s:"fmt"\r\nOK\r\n", cmd+2, ##__VA_ARGS__)
#define atcmd_ok              atcmd_printf("OK\r\n")
#define atcmd_error           atcmd_printf("ERROR\r\n")
#define atcmd_query()        (argc == 1 && argv[0][0] == '?')
#define atcmd_atoi(idx)      (argc>(idx) ? os_atoi(argv[idx]) : 0)

int32 atcmd_init(struct atcmd_dataif *dataif, struct atcmd_settings *settings);
int32 atcmd_uart_init(uint32 uart_id, uint32 baudrate, uint8 rx_tmo, struct atcmd_settings *settings);
int32 atcmd_recv(uint8 *data, int32 len);
int32 atcmd_register(const char *cmd, hgic_atcmd_hdl hdl);
int32 atcmd_unregister(const char *cmd);
void  atcmd_output(uint8 *data, int32 len);
void  atcmd_output_hdl(hgic_atcmd_outhdl output, void *arg);
void  atcmd_printf(const char *format, ...);
int32 atcmd_read(uint8 *buf, int32 len);
void  atcmd_dumphex(char *prestr, uint8 *data, int32 len, uint8 newline);

#ifdef __cplusplus
}
#endif
#endif
