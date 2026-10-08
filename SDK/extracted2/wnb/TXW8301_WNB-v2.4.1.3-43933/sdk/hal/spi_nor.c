#include "typesdef.h"
#include "list.h"
#include "errno.h"
#include "dev.h"
#include "osal/mutex.h"
#include "osal/string.h"
#include "hal/spi.h"
#include "hal/spi_nor.h"

int32 spi_nor_open(struct spi_nor_flash *flash)
{
    int32 ret;

    if (flash == NULL) {
        return -ENODEV;
    }

    ASSERT(flash->bus);
    os_mutex_lock(&flash->lock, osWaitForever);
    ret = spi_open(flash->spidev, flash->spi_config.clk, SPI_MASTER_MODE,
                   flash->spi_config.wire_mode, flash->spi_config.clk_mode);
    ASSERT(!ret);
    if (flash->bus->open) {
        flash->bus->open(flash);
    }
    if (ret) {
        os_mutex_unlock(&flash->lock);
    }
    return ret;
}

void spi_nor_close(struct spi_nor_flash *flash)
{
    if (flash) {
        ASSERT(flash->bus);
        if (flash->bus->close) {
            flash->bus->close(flash);
        }
        spi_set_cs(flash->spidev, flash->spi_config.cs, 1);
        spi_close(flash->spidev);
        os_mutex_unlock(&flash->lock);
    }
}

void spi_nor_read(struct spi_nor_flash *flash, uint32 addr, uint8 *buf, uint32 len)
{
    if (flash) {
        ASSERT(flash->bus);
        flash->bus->read(flash, addr, buf, len);
    }
}

void spi_nor_write(struct spi_nor_flash *flash, uint32 addr, uint8 *buf, uint32 len)
{
    uint32 remain_size;

    if (flash == NULL) {
        return;
    }

    ASSERT(flash->bus);
    /* Flash is written according to page */
    remain_size = flash->page_size - (addr % flash->page_size);
    if (remain_size && (len > remain_size)) {
        flash->bus->program(flash, addr, buf, remain_size);
        addr += remain_size;
        buf  += remain_size;
        len  -= remain_size;
    }
    while (len > flash->page_size) {
        flash->bus->program(flash, addr, buf, flash->page_size);
        addr += flash->page_size;
        buf  += flash->page_size;
        len  -= flash->page_size;
    }

    flash->bus->program(flash, addr, buf, len);
}

void spi_nor_sector_erase(struct spi_nor_flash *flash, uint32 sector_addr)
{
    if (flash) {
        ASSERT(flash->bus);
        flash->bus->sector_erase(flash, sector_addr);
    }
}

void spi_nor_block_erase(struct spi_nor_flash *flash, uint32 block_addr)
{
    if (flash) {
        ASSERT(flash->bus);
        flash->bus->block_erase(flash, block_addr);
    }
}

void spi_nor_chip_erase(struct spi_nor_flash *flash)
{
    if (flash) {
        ASSERT(flash->bus);
        flash->bus->chip_erase(flash);
    }
}

void spi_nor_erase_security_reg(struct spi_nor_flash *flash, uint32 addr)
{
    if (flash) {
        ASSERT(flash->bus);
        flash->bus->erase_security_reg(flash, addr);
    }
}

void spi_nor_program_security_reg(struct spi_nor_flash *flash, uint32 addr, uint8 *buf, uint32 size)
{
    if (flash) {
        ASSERT(flash->bus);
        flash->bus->program_security_reg(flash, addr, buf, size);
    }
}

void spi_nor_read_security_reg(struct spi_nor_flash *flash, uint32 addr, uint8 *buf, uint32 size)
{
    if (flash) {
        ASSERT(flash->bus);
        flash->bus->read_security_reg(flash, addr, buf, size);
    }
}

__init int32 spi_nor_attach(struct spi_nor_flash *flash, uint32 dev_id)
{
    uint8 id[3];

    ASSERT(flash->size && flash->sector_size);
    flash->bits_of_addr = flash->size > 0x1000000 ? 32 : 24;

    os_mutex_init(&flash->lock);
    flash->bus = spi_nor_bus_get(flash->mode);
    ASSERT(flash->bus);

    spi_nor_open(flash);
    spi_nor_standard_read_jedec_id(flash, id);
    spi_nor_close(flash);

    if ((id[0] | id[1] | id[2]) == 0 || ((id[0] & id[1] & id[2]) == 0xff)) {
        return -EIO;
    }

    flash->vendor_id  = id[0];
    flash->product_id = (id[1] << 8) | id[2];
    return dev_register(dev_id, (struct dev_obj *)flash);
}

