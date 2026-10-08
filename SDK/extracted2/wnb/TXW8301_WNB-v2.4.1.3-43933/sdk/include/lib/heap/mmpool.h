#ifndef _HGIC_MMPOOL_H_
#define _HGIC_MMPOOL_H_

#ifdef __cplusplus
extern "C" {
#endif

#include "list.h"

struct mmpool {
    uint32 size;
    uint32 region_cnt:4, align:5, headsize:6, tailsize:4, trace_off:4, ofchk_off:4, rev:5;
    uint32 regions[2][2];
    struct list_head free_list;
    struct list_head used_list;
};

#define REGION_CNT (12)
struct mmpool2 {
    uint32 size;
    uint32 region_cnt:4, align:5, headsize:6, tailsize:4, trace_off:4, ofchk_off:4, rev:5;
    uint32 regions[2][2];
    struct list_head list[REGION_CNT];
    struct list_head used_list;
};

void *mmpool_alloc(struct mmpool *mp, uint32 size, const char *func, int32 line);
void mmpool_free(struct mmpool *mp, void *ptr);
int32 mmpool_init(struct mmpool *mp, uint32 addr, uint32 size);
int32 mmpool_free_state(struct mmpool *mp, uint32 *stat_buf, int32 size, uint32 *tot_size);
int32 mmpool_used_state(struct mmpool *mp, uint32 *stat_buf, int32 size, uint32 *tot_size, uint32 mini_size);
int32 mmpool_add_region(struct mmpool *mp, uint32 addr, uint32 size);
uint32 mmpool_free_size(struct mmpool *mp, uint32 min);
int32 mmpool_of_check(struct mmpool *mp, uint32 addr, uint32 size);
int32 mmpool_valid_addr(struct mmpool *mp, uint32 addr);

void *mmpool2_alloc(struct mmpool2 *mp, uint32 size, const char *func, int32 line);
void mmpool2_free(struct mmpool2 *mp, void *ptr);
int32 mmpool2_init(struct mmpool2 *mp, uint32 addr, uint32 size);
int32 mmpool2_free_state(struct mmpool2 *mp, uint32 *stat_buf, int32 size, uint32 *tot_size);
int32 mmpool2_used_state(struct mmpool2 *mp, uint32 *stat_buf, int32 size, uint32 *tot_size, uint32 mini_size);
int32 mmpool2_add_region(struct mmpool2 *mp, uint32 addr, uint32 size);
uint32 mmpool2_free_size(struct mmpool2 *mp, uint32 min);
int32 mmpool2_of_check(struct mmpool2 *mp, uint32 addr, uint32 size);
int32 mmpool2_valid_addr(struct mmpool2 *mp, uint32 addr);

#ifdef __cplusplus
}
#endif
#endif
