/**
  ******************************************************************************
  * @file    hg_sysaes_v2.c
  * @author  HUGE-IC Application Team
  * @version V1.0.0
  * @date
  * @brief   private aes support aes 256
  ******************************************************************************
  * @attention
  *
  * <h2><center>&copy; COPYRIGHT 2019 HUGE-IC</center></h2>
  *
  *
  *
  ******************************************************************************
  */

#include "typesdef.h"
#include "list.h"
#include "errno.h"
#include "dev.h"
#include "devid.h"
#include "osal/string.h"
#include "osal/semaphore.h"
#include "osal/mutex.h"
#include "osal/irq.h"
#include "dev/sysaes/hg_sysaes.h"
#include "hal/sysaes.h"

static void hg_sysaes_irq_handler(void *data)
{
    struct hg_sysaes *sysaes = (struct hg_sysaes *)data;
    sysaes->hw->AES_STAT = AES_STAT_COMP_PD_MSK;
    os_sema_up(&sysaes->done);
}

static void hg_sysaes_fill_key(struct sysaes_dev *dev, struct sysaes_para *para)
{
    struct hg_sysaes *sysaes = (struct hg_sysaes *)dev;
    os_memcpy(sysaes->hw->KEY, para->key, 32);
    /*for (uint8 i = 0; i < 8; ++i) {
        sysaes->hw->KEY[i] = para->key[i];
    }*/
}


static int32 hg_sysaes_hdl(struct sysaes_dev *dev, struct sysaes_para *para, uint32 flags)
{
    int32 ret;
    struct hg_sysaes *sysaes = (struct hg_sysaes *)dev;

    if (para->key_len != AES_KEY_LEN_BIT_256) {
        return RET_ERR;
    }
    ret = os_mutex_lock(&sysaes->lock, 10);
    if (ret) {
        if (flags == ENCRYPT) {
            SYS_AES_ERR_PRINTF("sysaes encrypt lock timeout!\r\n");
        } else {
            SYS_AES_ERR_PRINTF("sysaes decrypt lock timeout!\r\n");
        }
        os_mutex_unlock(&sysaes->lock);
        return RET_ERR;
    }
    if (flags == ENCRYPT) {
        sysaes->hw->AES_CTRL &= ~AES_CTRL_EOD_MSK;
    } else {
        sysaes->hw->AES_CTRL |= AES_CTRL_EOD_MSK;
    }
    sysaes->hw->AES_CTRL |= AES_CTRL_IRQ_EN_MSK;
    sysaes->hw->SADDR = (uint32)para->src;
    sysaes->hw->DADDR = (uint32)para->dest;
    sysaes->hw->BLOCK_NUM = para->block_num;
    sysaes->hw->AES_CTRL &= ~AES_CTRL_MOD_MSK;
//    for (uint8 i = 0; i < 8; ++i) {
//        sysaes->hw->KEY[i] = para->key[i];
//    }
    sysaes->hw->AES_STAT = AES_STAT_COMP_PD_MSK;
    sysaes->hw->AES_CTRL |= AES_CTRL_START_MSK;
    ret = os_sema_down(&sysaes->done, 10);
    if (!ret) {
        os_mutex_unlock(&sysaes->lock);
        return RET_ERR;
    }
    os_mutex_unlock(&sysaes->lock);
    return RET_OK;
}

static int32 hg_sysaes_encrypt(struct sysaes_dev *dev, struct sysaes_para *para)
{
    if (para->mode > AES_MODE_CBC) {
        return RET_ERR;
    }

    hg_sysaes_fill_key(dev, para);

    if (para->mode == AES_MODE_ECB) {
        return hg_sysaes_hdl(dev, para, ENCRYPT);
    }
    if (para->mode == AES_MODE_CBC) {
        uint8 cbc[AES_BLOCK_SIZE] __aligned(4);
        uint8 *pos = para->dest;
        int i, j, blocks;
        uint8 *src_bak = para->src;
        uint8 *dst_bak = para->dest;

        hw_memcpy(cbc, para->iv, AES_BLOCK_SIZE);
        if (para->src != para->dest) {
            hw_memcpy(para->dest, para->src, AES_BLOCK_SIZE * para->block_num);
        }

        blocks = para->block_num;
        para->src = cbc;
        para->dest = cbc;
        para->block_num = 1;
        for (i = 0; i < blocks; i++) {
            for (j = 0; j < AES_BLOCK_SIZE; j++){ 
                cbc[j] ^= pos[j]; 
            }
            hg_sysaes_hdl(dev, para, ENCRYPT);
            hw_memcpy(pos, cbc, AES_BLOCK_SIZE);
            pos += AES_BLOCK_SIZE;
        }
        para->src = src_bak;
        para->dest = dst_bak;
        para->block_num = blocks;

        return RET_OK;
    }
    return RET_ERR;
}

static int32 hg_sysaes_decrypt(struct sysaes_dev *dev, struct sysaes_para *para)
{
    if (para->mode > AES_MODE_CBC) {
        return RET_ERR;
    }

    hg_sysaes_fill_key(dev, para);

    if (para->mode == AES_MODE_ECB) {
        return hg_sysaes_hdl(dev, para, DECRYPT);
    }

    if (para->mode == AES_MODE_CBC) {
        uint8 cbc[AES_BLOCK_SIZE] __aligned(4);
        uint8 tmp[AES_BLOCK_SIZE] __aligned(4);
        uint8 *pos = para->dest;
        int i, j, blocks;
        uint8 *src_bak = para->src;
        uint8 *dst_bak = para->dest;

        if (para->src != para->dest) {
            hw_memcpy(para->dest, para->src, AES_BLOCK_SIZE * para->block_num);
        }
        hw_memcpy(cbc, para->iv, AES_BLOCK_SIZE);

        blocks = para->block_num;
        para->block_num = 1;
        for (i = 0; i < blocks; i++) {
            para->src = pos;
            para->dest = pos;
            hw_memcpy(tmp, pos, AES_BLOCK_SIZE);
            hg_sysaes_hdl(dev, para, DECRYPT);
            for (j = 0; j < AES_BLOCK_SIZE; j++){ 
                pos[j] ^= cbc[j]; 
            }
            hw_memcpy(cbc, tmp, AES_BLOCK_SIZE);
            pos += AES_BLOCK_SIZE;
        }
        para->src = src_bak;
        para->dest = dst_bak;
        para->block_num = blocks;

        return RET_OK;
    }

    return RET_ERR;
}

static const struct aes_hal_ops aes_ops = {
    .encrypt     = hg_sysaes_encrypt,
    .decrypt     = hg_sysaes_decrypt,
};

int32 hg_sysaes_attach(uint32 dev_id, struct hg_sysaes *sysaes)
{
    sysaes->dev.dev.ops = (const struct devobj_ops *)&aes_ops;
    os_mutex_init(&sysaes->lock);
    os_sema_init(&sysaes->done, 0);
    SYSCTRL_REG_OPT(
        sysctrl_sysaes_clk_open();
        sysctrl_sysaes_reset();
    );
    request_irq(sysaes->irq_num, hg_sysaes_irq_handler, sysaes);
    irq_enable(sysaes->irq_num);
    dev_register(dev_id, (struct dev_obj *)sysaes);
    return RET_OK;
}

