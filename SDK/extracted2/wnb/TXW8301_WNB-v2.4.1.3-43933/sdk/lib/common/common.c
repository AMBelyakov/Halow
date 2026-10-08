#include "sys_config.h"
#include "typesdef.h"
#include "errno.h"
#include "list.h"
#include "dev.h"
#include "devid.h"
#include "osal/task.h"
#include "osal/sleep.h"
#include "osal/string.h"
#include "osal/irq.h"
#include "hal/dma.h"
#include "hal/crc.h"
#include "lib/common/common.h"
#include "lib/heap/sysheap.h"

__bobj uint32 sdk_version = SDK_VERSION;
__bobj uint32 svn_version = SVN_VERSION;
__bobj uint32 app_version = APP_VERSION;

extern void *krhino_mm_alloc(size_t size, void *caller);
extern void  krhino_mm_free(void *ptr);

__bobj uint64 cpu_loading_tick;
#ifdef M2M_DMA
__bobj struct dma_device *m2mdma;
#endif

// 任意模式下sta深度休眠或psmode5/6模式下任意角色休眠时执行hook
__at_section(".dsleep_text") __weak void system_sleep_enter_hook(void){
#if 0
    //首先要通过接口设置PB4为唤醒IO，上升沿唤醒
    //硬件pir检测demo代码；暂时废弃硬件方式了，采用软件检测（在main里）；
    //按键和PIR或后连到PB4，按键再单独连到PB2
    system_sleep_config(SLEEP_SETCFG_WKSRC_DETECT, PB_2, 1);
    //测试结果：
    //1，如果拉高PB2，但是PB4不拉高，
    //2，如果拉高PB4，但是不拉高PB2，唤醒，显示reason：DSLEEP_WK_REASON_PIR
    //3，如果同时拉高PB4和PB2，唤醒，显示reason：DSLEEP_WK_REASON_IO
#endif
};

// 任意模式下sta深度休眠周期唤醒时执行hook，用户利用额外参数和API控制接下来休眠或唤醒行为
__at_section(".dsleep_text") __weak void system_sleep_wakeup_hook(void){};
// 非psmode5/6模式下sta深度休眠唤醒周期内收到数据包执行hook，用户利用额外api控制唤醒行为
__at_section(".dsleep_text") __weak int32 system_sleep_rxdata_hook(uint8 *data, uint32 len)
{
    return 0;
}
// ap在5mA低功耗模式下通过io唤醒执行hook，用于判断多个唤醒源合并到一个io时做额外判断区分
__weak int32 system_ap_sleep_io_wakeup_hook(void)
{
    return 4;// DSLEEP_WK_REASON_IO 返回唤醒原因，默认返回IO唤醒，返回0不唤醒
}
// ap在任意低功耗模式下收到sta数据包或null包执行hook，用于唤醒时执行额外操作
__weak int32 system_ap_sleep_rxdata_hook(uint8 *data, uint32 len)
{
    return 1; // 0:ignore, 1: wakeup
}
// ap在任意低功耗模式下周期唤醒执行hook，用于周期唤醒做电源或其他额外检查
__weak void system_ap_sleep_wakeup_hook(void){};

void cpu_loading_print(uint8 all, struct os_task_info *tsk_info, uint32 size)
{
    uint32 i = 0;
    uint32 diff_tick = 0;
    uint32 irq_time;
    uint32 count;
    uint64 jiff = os_jiffies();

    if(tsk_info == NULL) return;
    count = os_task_runtime(tsk_info, size);
    diff_tick = DIFF_JIFFIES(cpu_loading_tick, jiff);
    cpu_loading_tick = jiff;

    irq_time = irq_status();
    os_printf("---------------------------------------------------\r\n");
    os_printf("Task Runtime Statistic, interval:%dms\r\n", diff_tick);
    os_printf("PID     Name            %%CPU(Time)    Stack  Prio \r\n", diff_tick);
    os_printf("---------------------------------------------------\r\n");
    if(irq_time > 0){
        os_printf("SYS IRQ: %d%%\r\n", 100 * os_msecs_to_jiffies(irq_time/1000) / diff_tick);
        os_printf("---------------------------------------------------\r\n");
    }
    for (i = 0; i < count; i++) {
        if (tsk_info[i].time > 0 || all) {
            os_printf("%2d     %-12s\t%2d%%(%6d)   %4d  %2d (%p)\r\n",
                      tsk_info[i].id,
                      tsk_info[i].name ? tsk_info[i].name : (const uint8 *)"----",
                      (tsk_info[i].time * 100) / diff_tick,
                      tsk_info[i].time,
                      tsk_info[i].stack * 4,
                      tsk_info[i].prio,
                      tsk_info[i].arg);
        }
    }
    os_printf("---------------------------------------------------\r\n");
}

int strncasecmp(const char *s1, const char *s2, int n)
{
    size_t i = 0;

    for (i = 0; i < n && s1[i] && s2[i]; i++) {
        if (s1[i] == s2[i] || s1[i] + 32 == s2[i] || s1[i] - 32 == s2[i]) {
        } else {
            break;
        }
    }
    return (i != n);
}

int strcasecmp(const char *s1, const char *s2)
{
    while (*s1 || *s2) {
        if (*s1 == *s2 || *s1 + 32 == *s2 || *s1 - 32 == *s2) {
            s1++; s2++;
        } else {
            return -1;
        }
    }
    return 0;
}

#ifdef M2M_DMA
void hw_memcpy(void *dest, const void *src, uint32 size)
{
    if (dest && src) {
        if (m2mdma && size > 45) {
#ifdef MEM_TRACE
#ifdef PSRAM_HEAP
            struct sys_heap *heap = sysheap_valid_addr(&psram_heap, dest) ? &psram_heap : &sram_heap;
#else
            struct sys_heap *heap = &sram_heap;
#endif
            int32 ret = sysheap_of_check(heap, dest, size);
            if (ret == -1) {
                //os_printf("%s: WARING: OF CHECK 0x%x\r\n", dest, __FUNCTION__);
            } else {
                if (!ret) {
                    os_printf("check addr fail: %x, size:%d \r\n", dest, size);
                }
                ASSERT(ret == 1);
            }
#endif
            dma_memcpy(m2mdma, dest, src, size);
        } else {
            os_memcpy(dest, src, size);
        }
    }
}

void hw_memcpy0(void *dest, const void *src, uint32 size)
{
    if (m2mdma && size > 45) {
#ifdef MEM_TRACE
#ifdef PSRAM_HEAP
        struct sys_heap *heap = sysheap_valid_addr(&psram_heap, dest) ? &psram_heap : &sram_heap;
#else
        struct sys_heap *heap = &sram_heap;
#endif
        int32 ret = sysheap_of_check(heap, dest, size);
        if (ret == -1) {
            //os_printf("%s: WARING: OF CHECK 0x%x\r\n", dest, __FUNCTION__);
        } else {
            if (!ret) {
                os_printf("check addr fail: %x, size:%d \r\n", dest, size);
            }
            ASSERT(ret == 1);
        }
#endif
        dma_memcpy(m2mdma, dest, src, size);
    } else {
        os_memcpy(dest, src, size);
    }
}

void hw_memset(void *dest, uint8 val, uint32 n)
{
    if (dest) {
        if (m2mdma && n > 12) {
#ifdef MEM_TRACE
#ifdef PSRAM_HEAP
            struct sys_heap *heap = sysheap_valid_addr(&psram_heap, dest) ? &psram_heap : &sram_heap;
#else
            struct sys_heap *heap = &sram_heap;
#endif
            int32 ret = sysheap_of_check(heap, dest, n);
            if (ret == -1) {
                //os_printf("%s: WARING: OF CHECK 0x%x\r\n", dest, __FUNCTION__);
            } else {
                if (!ret) {
                    os_printf("check addr fail: %x, size:%d \r\n", dest, n);
                }
                ASSERT(ret == 1);
            }
#endif
            dma_memset(m2mdma, dest, val, n);
        } else {
            os_memset(dest, val, n);
        }
    }
}
#endif

void *os_memdup(const void *ptr, uint32 len)
{
    void *p;
    if (!ptr || len == 0) {
        return NULL;
    }
    p = os_malloc(len);
    if (p) {
        hw_memcpy(p, ptr, len);
    }
    return p;
}


int32 os_random_bytes(uint8 *data, int32 len)
{
    int32 i = 0;
    int32 seed;
#ifdef TXW4002ACK803
    seed = csi_coret_get_value() ^ (csi_coret_get_value() << 8) ^ (csi_coret_get_value() >> 8);
#else
    seed = csi_coret_get_value() ^ sysctrl_get_trng() ^ (sysctrl_get_trng() >> 8);
#endif
    for (i = 0; i < len; i++) {
        seed = seed * 214013L + 2531011L;
        data[i] = (uint8)(((seed >> 16) & 0x7fff) & 0xff);
    }
    return 0;
}

char *sdk_version_str(void)
{
    return VERSION_STR;
}

uint32 hw_crc(enum CRC_DEV_TYPE type, uint8 *data, uint32 len)
{
    uint32 crc = 0xffff;
    struct crc_dev_req req;
    struct crc_dev *crcdev = (struct crc_dev *)dev_get(HG_CRC_DEVID);
    if (crcdev) {
        req.type = type;
        req.data = data;
        req.len  = len;
        ASSERT((uint32)data % 4 == 0); // crc模块数据地址必须4字节对齐检查
        crc_dev_calc(crcdev, &req, &crc, 0);
    } else {
        os_printf("no crc dev\r\n");
        crc = (uint32)os_jiffies();
    }
    return crc;
}

