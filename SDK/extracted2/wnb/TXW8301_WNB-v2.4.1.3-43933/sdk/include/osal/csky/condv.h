#ifndef __CSKY_COND_H_
#define __CSKY_COND_H_
#include "csi_kernel.h"
#include "osal/atomic.h"

#ifdef __cplusplus
extern "C" {
#endif

struct os_condv {
    uint32 magic;
    atomic_t waitings;
    k_sem_handle_t    sema;
};

#ifdef __cplusplus
}
#endif

#endif


