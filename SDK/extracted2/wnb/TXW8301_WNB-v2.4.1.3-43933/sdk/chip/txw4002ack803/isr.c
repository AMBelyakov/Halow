
/******************************************************************************
 * @file     isr.c
 * @brief    source file for the interrupt server route
 * @version  V1.0
 * @date     02. June 2017
 ******************************************************************************/
#include <csi_config.h>
#include "soc.h"
#ifndef CONFIG_KERNEL_NONE
#include <csi_kernel.h>
#endif
#include "sys_config.h"
#include "typesdef.h"
#include "errno.h"
#include "osal/irq.h"
#include "osal/string.h"

extern void ck_usart_irqhandler(int32_t idx);
extern void dw_timer_irqhandler(int32_t idx);
extern void dw_gpio_irqhandler(int32_t idx);
extern void systick_handler(void);
extern void xPortSysTickHandler(void);
extern void OSTimeTick(void);
static struct sys_hwirq sys_irqs[IRQ_NUM];

#if defined(CONFIG_SUPPORT_TSPEND) || defined(CONFIG_KERNEL_NONE)
#define  ATTRIBUTE_ISR __attribute__((isr))
#else
#define  ATTRIBUTE_ISR
#endif

#define readl(addr) ({ unsigned int __v = (*(volatile unsigned int *) (addr)); __v; })

#if defined(CONFIG_KERNEL_RHINO)
#define SYSTICK_HANDLER systick_handler
#elif defined(CONFIG_KERNEL_FREERTOS)
#define SYSTICK_HANDLER xPortSysTickHandler
#elif defined(CONFIG_KERNEL_UCOS)
#define SYSTICK_HANDLER OSTimeTick
#endif

#if !defined(CONFIG_KERNEL_FREERTOS) && !defined(CONFIG_KERNEL_NONE)
#define  CSI_INTRPT_ENTER() csi_kernel_intrpt_enter()
#define  CSI_INTRPT_EXIT()  csi_kernel_intrpt_exit()
#else
#define  CSI_INTRPT_ENTER()
#define  CSI_INTRPT_EXIT()
#endif


#ifdef SYS_IRQ_STAT
#define SYS_IRQ_STATE_ST(irqn)  uint32 _t1_, _t2_; _t1_ = csi_coret_get_value();
#define SYS_IRQ_STATE_END(irqn) do{ \
            _t2_ = csi_coret_get_value();\
            _t1_ = ((_t1_>_t2_)?(_t1_-_t2_):(csi_coret_get_load()-_t2_+_t1_));\
            sys_irqs[irqn].tot_time += _t1_;\
            sys_irqs[irqn].trig_cnt++;\
            if (_t1_ > sys_irqs[irqn].max_time) {\
                sys_irqs[irqn].max_time = _t1_;\
            }\
        }while(0)
#else
#define SYS_IRQ_STATE_ST(irqn)
#define SYS_IRQ_STATE_END(irqn)
#endif

#define SYSTEM_IRQ_HANDLE_FUNC(func_name,irqn)\
    ATTRIBUTE_ISR void func_name(void)\
    {\
        SYS_IRQ_STATE_ST(irqn);\
        CSI_INTRPT_ENTER();\
        if (sys_irqs[irqn].handle) {\
            sys_irqs[irqn].handle(sys_irqs[irqn].data);\
        }\
        CSI_INTRPT_EXIT();\
        SYS_IRQ_STATE_END(irqn);\
    }

int32_t request_irq(uint32_t irq_num, irq_handle handle, void *data)
{
    if (irq_num < IRQ_NUM) {
        sys_irqs[irq_num].data = data;
        sys_irqs[irq_num].handle = handle;
        return RET_OK;
    } else {
        return -EINVAL;
    }
}

int32_t release_irq(uint32_t irq_num)
{
    if (irq_num < IRQ_NUM) {
        irq_disable(irq_num);
        sys_irqs[irq_num].handle = NULL;
        sys_irqs[irq_num].data   = NULL;
        return RET_OK;
    } else {
        return -EINVAL;
    }
}

uint32 irq_status(void)
{
    uint32 tot_time = 0;
#ifdef SYS_IRQ_STAT
    int i;
    uint32_t v1, v2, v3;
    os_printf("SYS IRQ:\r\n");
    for (i = 0; i < IRQ_NUM; i++) {
        if (sys_irqs[i].trig_cnt) {
            v1 = sys_irqs[i].trig_cnt;
            v2 = sys_irqs[i].tot_time/(DEFAULT_SYS_CLK/1000000);
            v3 = sys_irqs[i].max_time/(DEFAULT_SYS_CLK/1000000);
            tot_time += v2;
            sys_irqs[i].trig_cnt = 0;
            sys_irqs[i].tot_time = 0;
            sys_irqs[i].max_time = 0;
            os_printf("  IRQ%-2d: trig:%-8d tot_time:%-8d max:%-8d\r\n", i, v1, v2, v3);
        }
    }
#endif
    return tot_time;
}

ATTRIBUTE_ISR void CORET_IRQHandler(void)
{
    SYS_IRQ_STATE_ST(CORET_IRQn);
    CSI_INTRPT_ENTER();
    readl(0xE000E010);
    SYSTICK_HANDLER();
    CSI_INTRPT_EXIT();
    SYS_IRQ_STATE_END(CORET_IRQn);
}

SYSTEM_IRQ_HANDLE_FUNC(IIC0_IRQHandler, IIC0_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(UART0_IRQHandler, UART0_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(UART1_IRQHandler, UART1_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(SPI0_IRQHandler, SPI0_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(SPI1_IRQHandler, SPI1_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(SPI3_IRQHandler, SPI3_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(WDT_IRQHandler, WDT_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(ADKEY_IRQHandler, ADKEY_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(DMAC_IRQHandler, DMAC_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(GPIOA_IRQHandler, GPIOA_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(TIM0_IRQHandler, TIM0_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(TIM1_IRQHandler, TIM1_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(TIM2_IRQHandler, TIM2_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(TIM3_IRQHandler, TIM3_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(SDIO_SLAVE_IRQHandler, HGSDIO20_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(SDIO_SLAVE_RST_IRQHandler, HGSDIO20_RST_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(PD_TMR_IRQHandler, PD_TMR_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(TDMA_IRQHandler, TDMA_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(GMAC_IRQHandler, GMAC_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(USB_CTL_IRQHandler, USB_CTL_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(USB_SOF_IRQHandler, USB_SOF_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(CE_IRQHandler, CE_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(GPIOB_IRQHandler, GPIOB_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(LMAC_IRQHandler, LMAC_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(CRC_IRQHandler, CRC_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(WAKEUP_IRQHandler, WKPND_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(SYS_ERR_IRQHandler, SYS_ERR_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(LVD_IRQHandler, LVD_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(SYS_AES_IRQHandler, SYS_AES_IRQn)
SYSTEM_IRQ_HANDLE_FUNC(MIPI_IRQHandler, MIPI_IRQn)

