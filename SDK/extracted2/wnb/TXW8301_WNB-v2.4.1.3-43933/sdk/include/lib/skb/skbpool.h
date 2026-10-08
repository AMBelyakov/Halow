#ifndef _HGIC_SKBPOOL_H_
#define _HGIC_SKBPOOL_H_

enum SKBPOOL_FLAGS {
    SKBPOOL_FLAGS_MGMTFRM_INHEAP = BIT(0),
};

extern int32 skbpool_init(uint32 addr, uint32 size, uint32 max, uint8 flags);
extern uint32 skbpool_freesize(int8 tx);
extern int32 skbpool_collect_init(void);
extern void skbpool_status(uint32 *status_buf, uint32 size, uint32 mini_size);
extern int32 skbpool_max_usage(uint8 max);
extern int32 skbpool_add_region(uint32 addr, uint32 size);
#endif

