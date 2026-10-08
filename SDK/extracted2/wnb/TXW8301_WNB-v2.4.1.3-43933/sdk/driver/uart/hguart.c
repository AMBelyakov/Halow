#include "typesdef.h"
#include "list.h"
#include "dev.h"
#include "osal/irq.h"
#include "osal/semaphore.h"
#include "hal/uart.h"
#include "hal/dma.h"
#include "dev/uart/hguart.h"

static void hguart_dma_tx_irq_hdl(struct dma_device *p_dma, uint32 ch, enum dma_irq_type irq, uint32 data)
{
    struct hguart *dev = (struct hguart *)data;
    dma_stop(p_dma, ch); /* release channel */
    os_sema_up(&dev->tx_dma_sema);
}

static void hguart_dma_rx_irq_hdl(struct dma_device *p_dma, uint32 ch, enum dma_irq_type irq, uint32 data)
{
    struct hguart *dev = (struct hguart *)data;
    dma_stop(p_dma, ch); /* release channel */
    //os_sema_up(&dev->rx_dma_sema);
    dev->irq_hdl(UART_IRQ_FLAG_DMA_RX_DONE, dev->irq_data, 0, 0);
}

static int32 hguart_set_baudrate(struct hguart_hw *uart_hw, int32 baudrate)
{
    int32 baudrate_cal = sys_get_apbclk() / baudrate;

#if UART_FIFO_EN
    while ((uart_hw->USR & BIT(2)) == 0);
#else
    while ((uart_hw->LSR & BIT(5)) == 0);
#endif
    uart_hw->LCR |= BIT(7);
    uart_hw->DLL = (uint8)(baudrate_cal >> 4);
    uart_hw->DLH = (uint8)((baudrate_cal >> 4) >> 8);
    uart_hw->DLF = baudrate_cal & 0x0f;
    uart_hw->LCR &= ~BIT(7);
    return RET_OK;
}

static int32 hguart_set_parity(struct hguart_hw *uart_hw, int32 parity)
{
#if UART_FIFO_EN
    while ((uart_hw->USR & BIT(2)) == 0);
#else
    while ((uart_hw->LSR & BIT(5)) == 0);
#endif
    switch (parity) {
        case HGUART_PARITY_NONE: {
            uart_hw->LCR &= ~BIT(3);
            uart_hw->LCR &= ~BIT(4);
        }
        break;
        case HGUART_PARITY_ODD: {
            uart_hw->LCR |=  BIT(3);
            uart_hw->LCR &= ~BIT(4);
        }
        break;
        case HGUART_PARITY_EVEN: {
            uart_hw->LCR |= BIT(3);
            uart_hw->LCR |= BIT(4);
        }
        break;
        default:
            break;
    }
    return RET_OK;
}

static int32 hguart_set_databits(struct hguart_hw *uart_hw, int32 databits)
{
#if UART_FIFO_EN
    while ((uart_hw->USR & BIT(2)) == 0);
#else
    while ((uart_hw->LSR & BIT(5)) == 0);
#endif
    uart_hw->LCR &= ~HGUART_DATABITS_8;
    uart_hw->LCR |= databits;
    return RET_OK;
}

static int32 hguart_set_stopbits(struct hguart_hw *uart_hw, int32 stopbits)
{
    uint32 ret = 0;
#if UART_FIFO_EN
    while ((uart_hw->USR & BIT(2)) == 0);
#else
    while ((uart_hw->LSR & BIT(5)) == 0);
#endif
    if (stopbits == UART_STOP_BIT_1) {
        uart_hw->LCR &= ~HGUART_2_STOPBIT;
    } else if (stopbits == UART_STOP_BIT_1_5) {
        ret = uart_hw->LCR & 0x3;
        if (ret == 0) {
            uart_hw->LCR |= HGUART_2_STOPBIT;
        } else {
            return RET_ERR;
        }
    } else if (stopbits == UART_STOP_BIT_2) {
        ret = uart_hw->LCR & 0x3;
        if (ret != 0) {
            uart_hw->LCR |= HGUART_2_STOPBIT;
        } else {
            return RET_ERR;
        }
    }
    return RET_OK;
}


static int32 hguart_open(struct uart_device *uart_t, uint32 baudrate)
{
    struct hguart *uart = (struct hguart *)uart_t;
    int32 ret;

    if (uart->opened) {
        hguart_set_baudrate(uart->hw, baudrate);
        return RET_OK;
    }

    ret = os_sema_init(&uart->tx_dma_sema, 0);
    if (ret != RET_OK) {
        return ret;
    }
    ret = os_sema_init(&uart->rx_dma_sema, 0);
    if (ret != RET_OK) {
        os_sema_del(&uart->tx_dma_sema);
        return ret;
    }

    pin_func(uart_t->dev.dev_id, 1);
    uart->hw->MCR = 0x00000000;

    hguart_set_baudrate(uart->hw, baudrate);

    uart->hw->LCR = (HGUART_DEFAULT_DATABITS) | (HGUART_DEFAULT_STOPBITS) | (HGUART_DEFAULT_PARITY);
#if UART_FIFO_EN
    //FCR, enable FIFO; reset FIFO; set FIFO trigger
    uart->hw->FCR = 0x01 | 0x06 | (HGUARTx_RXFIFO_TRIG & 0xC0) | (HGUARTx_TXFIFO_TRIG & 0x30);
#else
    //FCR, disable FIFO;
    uart->hw->FCR = 0x00000000;
#endif

    uart->opened = 1;

    return RET_OK;
}

static int32 hguart_close(struct uart_device *uart_t)
{
    struct hguart *uart = (struct hguart *)uart_t;

    if (!uart->opened) {
        return RET_OK;
    }

    pin_func(uart_t->dev.dev_id, 0);
    uart->hw->IER = 0;

    os_sema_del(&uart->tx_dma_sema);
    os_sema_del(&uart->rx_dma_sema);

    uart->opened = 0;

    return RET_OK;
}

static int32 hguart_putc(struct uart_device *uart_t, int8 Data)
{
    struct hguart *uart = (struct hguart *)uart_t;
#if UART_FIFO_EN
    while ((uart->hw->USR & BIT(1)) == 0); //tx fifo full
    uart->hw->RBR = Data;
#else
    uart->hw->RBR = Data;
    while ((uart->hw->LSR & BIT(5)) == 0);
#endif
    return RET_OK;
}

static uint8 hguart_getc(struct uart_device *uart_t)
{
    struct hguart *uart = (struct hguart *)uart_t;

    while ((uart->hw->LSR & BIT(0)) == 0);
    return uart->hw->RBR;
}

static int32 hguart_puts(struct uart_device *uart, uint8 *buf, uint32 size)
{
    uint32 i;
    struct hguart *dev = (struct hguart *)uart;
    struct dma_xfer_data xfer_data;

    if (dev->dma) {
        xfer_data.dest              = (uint32)&dev->hw->THR;
        xfer_data.src               = (uint32)buf;
        xfer_data.element_per_width = DMA_SLAVE_BUSWIDTH_1_BYTE;
        xfer_data.element_num       = size;
        xfer_data.dir               = DMA_XFER_DIR_M2D;
        xfer_data.src_addr_mode     = DMA_XFER_MODE_INCREASE;
        xfer_data.dst_addr_mode     = DMA_XFER_MODE_RECYCLE;
        xfer_data.dst_id            = dev->tx_dma_id;
        xfer_data.src_id            = 0;
        xfer_data.irq_hdl           = hguart_dma_tx_irq_hdl;
        xfer_data.irq_data          = (uint32)dev;
        dma_xfer(dev->dma, &xfer_data);
        os_sema_down(&dev->tx_dma_sema, osWaitForever); /* wait done */
    } else {
        for (i = 0; i < size; i++) {
            hguart_putc(uart, buf[i]);
        }
    }
    return RET_OK;
}

static int32 hguart_gets(struct uart_device *uart, uint8 *buf, uint32 size)
{
    uint32 i;
    struct hguart *dev = (struct hguart *)uart;
    struct dma_xfer_data xfer_data;

    if (dev->dma) {
        xfer_data.dest              = (uint32)buf;
        xfer_data.src               = (uint32)&dev->hw->RBR;
        xfer_data.element_per_width = DMA_SLAVE_BUSWIDTH_1_BYTE;
        xfer_data.element_num       = size;

        xfer_data.dir               = DMA_XFER_DIR_D2M;
        xfer_data.src_addr_mode     = DMA_XFER_MODE_RECYCLE;
        xfer_data.dst_addr_mode     = DMA_XFER_MODE_INCREASE;
        xfer_data.dst_id            = 0;
        xfer_data.src_id            = dev->rx_dma_id;
        
        xfer_data.irq_hdl           = hguart_dma_rx_irq_hdl;
        xfer_data.irq_data          = (uint32)dev;
        dma_xfer(dev->dma, &xfer_data);
        //os_sema_down(&dev->rx_dma_sema, osWaitForever);/* wait done */
    } else {
        for (i = 0; i < size; i++) {
            buf[i] = hguart_getc(uart);
        }
    }
    return RET_OK;
}

/*
 * 24.09.2026. Диагностика и ускорение приёма (проект T-Halow).
 *
 * На 3 Мбод видеотракт развалился, и улики указали на приём ЭТОГО модуля:
 * модуль камеры выпускал в эфир на треть меньше байтов, чем получал от ESP32
 * (на 1 Мбод отношение ~1.07, на 3 Мбод ~0.65-0.77), при этом малые пакеты
 * по всем четырём UART-направлениям проходили целыми, то есть по битам линия
 * исправна, ломается только под потоком.
 *
 * Причина в устройстве приёма: порог FIFO 1 символ (прерывание на каждый
 * байт), а обработчик ниже читал ОДИН байт за вход, даже если в FIFO их уже
 * десять. Колбэк uart_p2p на каждый байт зовёт timer_device_stop/start. На
 * 3 Мбод это 300 тыс. входов в секунду на 96 МГц — 320 тактов на байт на
 * всё, включая программный MAC радио. Однажды опоздав, обработчик догоняет по
 * байту за вход, и FIFO переполняется.
 *
 * Режим задаётся на ходу AT+UARTDRAIN (atcmd.c), чтобы A/B не требовал
 * перепрошивки модуля:
 *   0 — поведение вендора (по умолчанию), но со счётчиками;
 *   1 — выгребать FIFO целиком за один вход, не больше HGUART_DRAIN_MAX байт.
 *
 * Ветка CHAR_TIMEOUT у вендора читает байт из FIFO и ВЫБРАСЫВАЕТ его. При
 * пороге в 1 символ она, скорее всего, почти не срабатывает — счётчики
 * g_uart_cto/g_uart_cto_lost это покажут. В режиме 1 байты из неё отдаются
 * обработчику, а не выбрасываются.
 */
volatile uint32 g_uart_isr      = 0;  /* входов по приёму (данные + таймаут) */
volatile uint32 g_uart_rx       = 0;  /* байт отдано обработчику */
volatile uint32 g_uart_oe       = 0;  /* раз, когда LSR показал переполнение FIFO */
volatile uint32 g_uart_cto      = 0;  /* прерываний «таймаут символа» */
volatile uint32 g_uart_cto_lost = 0;  /* байт, выброшенных веткой CHAR_TIMEOUT */
volatile uint8  g_uart_drain    = 0;  /* 0 — как у вендора, 1 — выгребать FIFO */

/* Потолок на один вход: на 3 Мбод байт приходит раз в 3.3 мкс, и без потолка
 * обработчик мог бы просидеть в прерывании всю пачку чанка (~5 мс), отняв время
 * у программного MAC радио. 64 байта — с запасом больше глубины FIFO. */
#define HGUART_DRAIN_MAX 64

static void hguart_rx_drain(struct hguart *uart)
{
    uint32 n = 0;
    uint32 lsr;

    while (n < HGUART_DRAIN_MAX) {
        lsr = uart->hw->LSR;
        if (lsr & BIT(1)) {
            g_uart_oe++;
        }
        if ((lsr & BIT(0)) == 0) {
            break;
        }
        g_uart_rx++;
        n++;
        uart->irq_hdl(UART_IRQ_FLAG_RX_BYTE, uart->irq_data, uart->hw->RBR, 0);
    }
}

static void hguart_irq_handle(void *data)
{
    uint32 irq_id = 0;
    uint32 irq_clear = 0;
    uint32 rev_data = 0;
    struct hguart *uart = (struct hguart *)data;

    irq_id = uart->hw->IIR;
    irq_clear = irq_clear;
    switch ((irq_id & 0xf)) {
        case HGUART_INTR_MODEM_STATUS:
            if (uart->irq_hdl) {
                //uart->irq_hdl(UART_INTR_MODEM_STATUS, uart->irq_data, 0); // useless
            }
            irq_clear = uart->hw->MSR;  /*clear interrupt flag*/
            break;
        case HGUART_INTR_THR_EMPTY:
            if (uart->irq_hdl) {
                uart->irq_hdl(UART_IRQ_FLAG_TX_BYTE, uart->irq_data, 0, 0);
            }
            irq_clear = uart->hw->RBR;/*clear interrupt flag*/
            break;
        case HGUART_INTR_RX_DATA_AVAIL:
            g_uart_isr++;
            if (uart->irq_hdl) {
                if (g_uart_drain) {
                    hguart_rx_drain(uart);
                } else {
                    /* как у вендора (hguart_getc), но с учётом бита переполнения:
                     * чтение LSR его сбрасывает, поэтому считаем на каждом чтении */
                    uint32 lsr;
                    do {
                        lsr = uart->hw->LSR;
                        if (lsr & BIT(1)) {
                            g_uart_oe++;
                        }
                    } while ((lsr & BIT(0)) == 0);
                    rev_data = uart->hw->RBR;
                    g_uart_rx++;
                    uart->irq_hdl(UART_IRQ_FLAG_RX_BYTE, uart->irq_data, rev_data, 0);
                }
            }
            break;
        case HGUART_INTR_RX_LINE_STATUS:
            if (uart->irq_hdl) {
                //uart->irq_hdl(UART_INTR_RX_LINE_STATUS, uart->irq_data, 0, 0); // useless
            }
            irq_clear = uart->hw->LSR;/*clear interrupt flag*/
            break;
        case HGUART_INTR_BUSY_DETECT:
            if (uart->irq_hdl) {
                //uart->irq_hdl(UART_INTR_BUSY_DETECT, uart->irq_data, 0, 0); // useless
            }
            irq_clear = uart->hw->USR;  /*clear interrupt flag*/
            break;
        case HGUART_INTR_CHAR_TIMEOUT:
            g_uart_isr++;
            g_uart_cto++;
            if (uart->irq_hdl && g_uart_drain) {
                hguart_rx_drain(uart);            /* байты отдаём, а не выбрасываем */
                uart->irq_hdl(UART_IRQ_FLAG_TIME_OUT, uart->irq_data, 0, 0);
                break;
            }
            if (uart->irq_hdl) {
                uart->irq_hdl(UART_IRQ_FLAG_TIME_OUT, uart->irq_data, 0, 0);
            }
            if (uart->hw->LSR & BIT(0)) {
                g_uart_cto_lost++;                /* сейчас вендор выбросит байт */
            }
            irq_clear = uart->hw->RBR;/*clear interrupt flag*/
            break;
    }
}

int32 hguart_request_irq(struct uart_device *uart_t, uart_irq_hdl irq_hdl, uint32 irq_flag, uint32 data)
{
    struct hguart *uart = (struct hguart *)uart_t;
    uart->irq_data = data;
    uart->irq_hdl  = irq_hdl;
    request_irq(uart->irq_num, hguart_irq_handle, uart);

    if (irq_flag & UART_IRQ_FLAG_RX_BYTE) {
        uart->hw->IER |= HGUART_INTR_RX_DATA_AVAIL_EN;
    }
    
    irq_enable(uart->irq_num);
    return RET_OK;
}

static int32 hguart_ioctl(struct uart_device *uart_t, enum uart_ioctl_cmd cmd, uint32 param1, uint32 param2)
{
    int32 ret = RET_OK;
    struct hguart *uart = (struct hguart *)uart_t;

    switch (cmd) {
        case UART_IOCTL_CMD_SET_BAUDRATE:
            ret = hguart_set_baudrate(uart->hw, param1);
            break;
        case UART_IOCTL_CMD_SET_DATA_BIT:
            ret = hguart_set_databits(uart->hw, param1);
            break;
        case UART_IOCTL_CMD_SET_PARITY:
            ret = hguart_set_parity(uart->hw, param1);
            break;
        case UART_IOCTL_CMD_SET_STOP_BIT:
            ret = hguart_set_stopbits(uart->hw, param1);
            break;
        case UART_IOCTL_CMD_USE_DMA:
            uart->dma = (struct dma_device *)param1;
            break;
        case UART_IOCTL_CMD_DATA_RDY:
            ret = (uart->hw->LSR & 0x1);
            break;
        default:
            return RET_ERR;
    }
    return ret;
}

static const struct uart_hal_ops uart_ops = {
    .open             = hguart_open,
    .close            = hguart_close,
    .putc             = hguart_putc,
    .getc             = hguart_getc,
    .puts             = hguart_puts,
    .gets             = hguart_gets,
    .request_irq      = hguart_request_irq,
    .ioctl            = hguart_ioctl,
};

__init void hguart_attach(uint32 dev_id, struct hguart *uart)
{
    uart->opened               = 0;
    uart->irq_hdl              = NULL;
    uart->irq_data             = NULL;
    uart->dev.dev.ops          = (const struct devobj_ops *)&uart_ops;
    irq_disable(uart->irq_num);
    dev_register(dev_id, (struct dev_obj *)uart);
}

