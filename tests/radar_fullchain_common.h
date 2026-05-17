#ifndef RADAR_FULLCHAIN_COMMON_H
#define RADAR_FULLCHAIN_COMMON_H

#include <stdint.h>
#include <stdio.h>

#define FULLCHAIN_BASE_ADDR 0x60000000UL

#define FULLCHAIN_DMA_MM2S_DMACR   0x000UL
#define FULLCHAIN_DMA_MM2S_DMASR   0x004UL
#define FULLCHAIN_DMA_MM2S_SA      0x018UL
#define FULLCHAIN_DMA_MM2S_SA_MSB  0x01CUL
#define FULLCHAIN_DMA_MM2S_LENGTH  0x028UL
#define FULLCHAIN_DMA_S2MM_DMACR   0x030UL
#define FULLCHAIN_DMA_S2MM_DMASR   0x034UL
#define FULLCHAIN_DMA_S2MM_DA      0x048UL
#define FULLCHAIN_DMA_S2MM_DA_MSB  0x04CUL
#define FULLCHAIN_DMA_S2MM_LENGTH  0x058UL

#define FULLCHAIN_ACCEL_BASE          0x200UL
#define FULLCHAIN_ACCEL_CTRL          0x200UL
#define FULLCHAIN_ACCEL_RANGE_CFG     0x204UL
#define FULLCHAIN_ACCEL_DOPPLER_CFG   0x208UL
#define FULLCHAIN_ACCEL_CFAR_CFG      0x20CUL
#define FULLCHAIN_ACCEL_STATUS        0x210UL
#define FULLCHAIN_ACCEL_IN_WORDS      0x214UL
#define FULLCHAIN_ACCEL_MID_WORDS     0x218UL
#define FULLCHAIN_ACCEL_OUT_WORDS     0x21CUL
#define FULLCHAIN_ACCEL_DET_WORDS     0x220UL
#define FULLCHAIN_ACCEL_STALL_IN      0x224UL
#define FULLCHAIN_ACCEL_STALL_MID     0x228UL
#define FULLCHAIN_ACCEL_STALL_OUT     0x22CUL
#define FULLCHAIN_ACCEL_EXPECTED_IN   0x230UL
#define FULLCHAIN_ACCEL_EXPECTED_OUT  0x234UL
#define FULLCHAIN_ACCEL_CFAR_DIMS     0x238UL
#define FULLCHAIN_ACCEL_VERSION       0x23CUL

#define FULLCHAIN_DMACR_RS         (1u << 0)
#define FULLCHAIN_DMACR_RESET      (1u << 2)
#define FULLCHAIN_DMACR_IOC_IRQEN  (1u << 12)
#define FULLCHAIN_DMACR_ERR_IRQEN  (1u << 14)
#define FULLCHAIN_DMASR_ERR_MASK   ((1u << 4) | (1u << 5) | (1u << 6) | \
                                    (1u << 8) | (1u << 9) | (1u << 10) | (1u << 14))
#define FULLCHAIN_DMASR_IRQ_MASK   ((1u << 12) | (1u << 13) | (1u << 14))
#define FULLCHAIN_DMASR_CLEAR_MASK (FULLCHAIN_DMASR_ERR_MASK | FULLCHAIN_DMASR_IRQ_MASK)

#define FULLCHAIN_CTRL_START        (1u << 0)
#define FULLCHAIN_CTRL_SOFT_RESET   (1u << 1)
#define FULLCHAIN_CTRL_IRQ_ENABLE   (1u << 2)
#define FULLCHAIN_CTRL_CLEAR_STATUS (1u << 3)

#define FULLCHAIN_STATUS_BUSY       (1u << 0)
#define FULLCHAIN_STATUS_DONE       (1u << 1)
#define FULLCHAIN_STATUS_ERROR      (1u << 2)
#define FULLCHAIN_STATUS_CFG_ILLEGAL (1u << 3)
#define FULLCHAIN_STATUS_CFAR_OVERFLOW (1u << 4)

#define FULLCHAIN_RANGE_SIZE_128    3u
#define FULLCHAIN_DOPPLER_SIZE_64   2u
#define FULLCHAIN_WINDOW_NONE       0u
#define FULLCHAIN_WINDOW_HANN       1u
#define FULLCHAIN_WINDOW_HAMMING    2u
#define FULLCHAIN_INPUT_REAL        1u
#define FULLCHAIN_SCALE_MODE_1      1u

static inline void fullchain_write32(uintptr_t offset, uint32_t value)
{
  *(volatile uint32_t *)(FULLCHAIN_BASE_ADDR + offset) = value;
  asm volatile ("fence iorw, iorw" ::: "memory");
}

static inline uint32_t fullchain_read32(uintptr_t offset)
{
  uint32_t value = *(volatile uint32_t *)(FULLCHAIN_BASE_ADDR + offset);
  asm volatile ("fence iorw, iorw" ::: "memory");
  return value;
}

static inline uint32_t fullchain_pack_range_cfg(uint32_t size, uint32_t window,
                                                uint32_t real_input, uint32_t ifft)
{
  return (size & 0x7u) |
         ((window & 0x3u) << 3) |
         ((real_input & 0x1u) << 5) |
         ((ifft & 0x1u) << 6);
}

static inline uint32_t fullchain_pack_doppler_cfg(uint32_t size, uint32_t window,
                                                  uint32_t ifft, uint32_t scale_mode)
{
  return (size & 0x7u) |
         ((window & 0x3u) << 3) |
         ((ifft & 0x1u) << 5) |
         ((scale_mode & 0x3u) << 6);
}

static inline uint32_t fullchain_pack_cfar_cfg(uint32_t ref_a, uint32_t ref_b,
                                               uint32_t wrapper_en, uint32_t alpha)
{
  return (ref_a & 0x7u) |
         ((ref_b & 0x7u) << 4) |
         ((wrapper_en & 0x1u) << 8) |
         ((alpha & 0xffu) << 9);
}

static inline void fullchain_configure_128x64_default(void)
{
  fullchain_write32(FULLCHAIN_ACCEL_CTRL, FULLCHAIN_CTRL_SOFT_RESET);
  fullchain_write32(FULLCHAIN_ACCEL_RANGE_CFG,
                    fullchain_pack_range_cfg(FULLCHAIN_RANGE_SIZE_128,
                                             FULLCHAIN_WINDOW_HANN,
                                             FULLCHAIN_INPUT_REAL,
                                             0u));
  fullchain_write32(FULLCHAIN_ACCEL_DOPPLER_CFG,
                    fullchain_pack_doppler_cfg(FULLCHAIN_DOPPLER_SIZE_64,
                                               FULLCHAIN_WINDOW_HAMMING,
                                               0u,
                                               FULLCHAIN_SCALE_MODE_1));
  fullchain_write32(FULLCHAIN_ACCEL_CFAR_CFG, fullchain_pack_cfar_cfg(5u, 5u, 1u, 8u));
  fullchain_write32(FULLCHAIN_ACCEL_CTRL, FULLCHAIN_CTRL_CLEAR_STATUS);
}

static inline void fullchain_dump_core_status(const char *tag)
{
  printf("%s fullchain: VERSION=0x%08x CTRL=0x%08x RANGE=0x%08x DOPPLER=0x%08x CFAR=0x%08x STATUS=0x%08x EXPECT_IN=%u EXPECT_OUT=%u DIMS=0x%08x\n",
         tag,
         fullchain_read32(FULLCHAIN_ACCEL_VERSION),
         fullchain_read32(FULLCHAIN_ACCEL_CTRL),
         fullchain_read32(FULLCHAIN_ACCEL_RANGE_CFG),
         fullchain_read32(FULLCHAIN_ACCEL_DOPPLER_CFG),
         fullchain_read32(FULLCHAIN_ACCEL_CFAR_CFG),
         fullchain_read32(FULLCHAIN_ACCEL_STATUS),
         fullchain_read32(FULLCHAIN_ACCEL_EXPECTED_IN),
         fullchain_read32(FULLCHAIN_ACCEL_EXPECTED_OUT),
         fullchain_read32(FULLCHAIN_ACCEL_CFAR_DIMS));
}

#endif
