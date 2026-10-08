#ifndef __CSKY_TASK_H_
#define __CSKY_TASK_H_
#include "csi_kernel.h"

#ifdef __cplusplus
extern "C" {
#endif

struct os_task {
    k_task_handle_t     hdl;
    os_task_func_t func;
    const char    *name;
    uint32_t       args;
    uint32_t       priority:10, stack_size:22;
};

#ifdef __cplusplus
}
#endif

#endif

