#ifndef __OS_CONDV_H
#define __OS_CONDV_H

#ifdef __cplusplus
extern "C" {
#endif

struct os_condv;

int32 os_condv_init(struct os_condv *cond);

int32 os_condv_broadcast(struct os_condv *cond);
int32 os_condv_signal(struct os_condv *cond);

int32 os_condv_del(struct os_condv *cond);
int32 os_condv_wait(struct os_condv *cond, struct os_mutex *mutex, uint32 tmo_ms);

#ifdef __cplusplus
}
#endif

#ifdef __CSKY__
#include "osal/csky/condv.h"
#endif

#ifndef osWaitForever
#define osWaitForever 0xFFFFFFFFu
#endif
#endif

