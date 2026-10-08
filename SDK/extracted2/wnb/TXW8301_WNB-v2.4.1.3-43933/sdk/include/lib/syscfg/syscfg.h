#ifndef _HGIC_SYSCFG_H_
#define _HGIC_SYSCFG_H_

#define SYSCFG_MAGIC (0x1234)

struct syscfg_info {
    struct spi_nor_flash *flash1, *flash2;
    uint32 addr1, addr2;
    uint32 size;
};

int32 syscfg_init(const char *name, void *cfg, uint32 size);
int32 syscfg_read(const char *name, void *cfg, uint32 size);
int32 syscfg_write(const char *name, void *cfg, uint32 size);
int32 syscfg_info_get(struct syscfg_info *pinfo, const char *name);
void syscfg_loaddef(const char *name);
int32 syscfg_save(void);

#endif
