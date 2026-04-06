#ifndef RADAR_AXI_DMA_COMMON_H
#define RADAR_AXI_DMA_COMMON_H

#include <stdint.h>
#include <stdio.h>

#define DMA_BASE_ADDR      0x60000000UL
#define DDR_BASE_ADDR      0x80000000UL
#define DDR_UNCACHED_ALIAS_OFFSET 0x1000000000UL
#define RADAR_BUF_IN_BASE         0x81000000UL
#define RADAR_BUF_MID0_BASE       0x81800000UL
#define RADAR_BUF_MID1_BASE       0x82000000UL
#define RADAR_BUF_OUT_BASE        0x82800000UL
#define RADAR_BUF_DESC_BASE       0x83000000UL
#define RADAR_BUF_REGION_BYTES    0x00800000UL
#define RADAR_BUF_DESC_BYTES      0x00100000UL
#define RADAR_STAGE_TX_OFFSET     0x00000000UL
#define RADAR_STAGE_RX_OFFSET     0x00001000UL
#define RADAR_STAGE_EVICT_OFFSET  0x00010000UL
#define TX_BUFFER_ADDR            (RADAR_BUF_IN_BASE + RADAR_STAGE_TX_OFFSET)
#define RX_BUFFER_ADDR            (RADAR_BUF_IN_BASE + RADAR_STAGE_RX_OFFSET)
#define EVICT_BUFFER_ADDR         (RADAR_BUF_IN_BASE + RADAR_STAGE_EVICT_OFFSET)
#define TEST_WORD_COUNT    64UL
#define TEST_BYTE_COUNT    (TEST_WORD_COUNT * sizeof(uint32_t))
#define EVICT_WORD_COUNT   4096UL
#define DMA_TIMEOUT_CYCLES 10000000UL

#define MM2S_DMACR   0x00UL
#define MM2S_DMASR   0x04UL
#define MM2S_SA      0x18UL
#define MM2S_SA_MSB  0x1CUL
#define MM2S_LENGTH  0x28UL

#define S2MM_DMACR   0x30UL
#define S2MM_DMASR   0x34UL
#define S2MM_DA      0x48UL
#define S2MM_DA_MSB  0x4CUL
#define S2MM_LENGTH  0x58UL

#define PREPROC_CTRL           0x200UL
#define PREPROC_MODE           0x204UL
#define PREPROC_PARAM0         0x208UL
#define PREPROC_PARAM1         0x20CUL
#define PREPROC_STATUS         0x210UL
#define PREPROC_IN_BEATS       0x214UL
#define PREPROC_OUT_BEATS      0x218UL
#define PREPROC_FRAME_COUNT    0x21CUL
#define PREPROC_LAST_KEEP      0x220UL
#define PREPROC_CAPABILITIES   0x224UL

#define QMLP_CTRL             0x240UL
#define QMLP_STATUS           0x244UL
#define QMLP_IN_BEATS         0x248UL
#define QMLP_OUT_BEATS        0x24CUL
#define QMLP_FRAME_COUNT      0x250UL
#define QMLP_LAST_KEEP        0x254UL
#define QMLP_LAST_LOGIT0      0x258UL
#define QMLP_LAST_LOGIT1      0x25CUL
#define QMLP_RUN_CYCLES       0x260UL
#define QMLP_CAPABILITIES     0x264UL
#define QMLP_SAMPLE_BYTES     0x268UL
#define QMLP_OUTPUT_BYTES     0x26CUL

#define PREPROC_CTRL_ENABLE        (1u << 0)
#define PREPROC_CTRL_CLR_COUNTS    (1u << 1)

#define QMLP_CTRL_ENABLE           (1u << 0)
#define QMLP_CTRL_CLR_COUNTS       (1u << 1)

#define PREPROC_MODE_BYPASS        0u
#define PREPROC_MODE_ADD32         1u
#define PREPROC_MODE_SHIFT16_AR    2u
#define PREPROC_MODE_RELU16        3u
#define PREPROC_MODE_SWAP32        4u

#define DMACR_RS         (1u << 0)
#define DMACR_RESET      (1u << 2)
#define DMACR_IOC_IRQEN  (1u << 12)
#define DMACR_ERR_IRQEN  (1u << 14)
#define DMACR_RUN_MASK   (DMACR_RS | DMACR_IOC_IRQEN | DMACR_ERR_IRQEN)
#define DMASR_HALTED     (1u << 0)
#define DMASR_IDLE       (1u << 1)
#define DMASR_ERR_MASK   ((1u << 4) | (1u << 5) | (1u << 6) | (1u << 8) | (1u << 9) | (1u << 10) | (1u << 14))
#define DMASR_IRQ_MASK   ((1u << 12) | (1u << 13) | (1u << 14))
#define DMASR_CLEAR_MASK (DMASR_ERR_MASK | DMASR_IRQ_MASK)

static inline void mmio_write32(uintptr_t addr, uint32_t value)
{
  *(volatile uint32_t *)addr = value;
  asm volatile ("fence iorw, iorw" ::: "memory");
}

static inline uint32_t mmio_read32(uintptr_t addr)
{
  uint32_t value = *(volatile uint32_t *)addr;
  asm volatile ("fence iorw, iorw" ::: "memory");
  return value;
}

static inline void riscv_fence_rw_rw(void)
{
  asm volatile ("fence rw, rw" ::: "memory");
}

typedef enum {
  RADAR_BUF_VIEW_CACHED = 0,
  RADAR_BUF_VIEW_UNCACHED = 1
} radar_buffer_view_t;

typedef enum {
  RADAR_BUF_REGION_IN = 0,
  RADAR_BUF_REGION_MID0 = 1,
  RADAR_BUF_REGION_MID1 = 2,
  RADAR_BUF_REGION_OUT = 3,
  RADAR_BUF_REGION_DESC = 4
} radar_buffer_region_t;

typedef struct {
  const char *name;
  uintptr_t dma_base;
  uintptr_t cpu_cached_base;
  uintptr_t cpu_uncached_base;
  unsigned long size_bytes;
} radar_buffer_region_desc_t;

static inline radar_buffer_region_desc_t radar_buffer_region_desc(radar_buffer_region_t region)
{
  switch (region) {
    case RADAR_BUF_REGION_IN:
      return (radar_buffer_region_desc_t){
        "buf_in",
        RADAR_BUF_IN_BASE,
        RADAR_BUF_IN_BASE,
        RADAR_BUF_IN_BASE + DDR_UNCACHED_ALIAS_OFFSET,
        RADAR_BUF_REGION_BYTES
      };
    case RADAR_BUF_REGION_MID0:
      return (radar_buffer_region_desc_t){
        "buf_mid0",
        RADAR_BUF_MID0_BASE,
        RADAR_BUF_MID0_BASE,
        RADAR_BUF_MID0_BASE + DDR_UNCACHED_ALIAS_OFFSET,
        RADAR_BUF_REGION_BYTES
      };
    case RADAR_BUF_REGION_MID1:
      return (radar_buffer_region_desc_t){
        "buf_mid1",
        RADAR_BUF_MID1_BASE,
        RADAR_BUF_MID1_BASE,
        RADAR_BUF_MID1_BASE + DDR_UNCACHED_ALIAS_OFFSET,
        RADAR_BUF_REGION_BYTES
      };
    case RADAR_BUF_REGION_OUT:
      return (radar_buffer_region_desc_t){
        "buf_out",
        RADAR_BUF_OUT_BASE,
        RADAR_BUF_OUT_BASE,
        RADAR_BUF_OUT_BASE + DDR_UNCACHED_ALIAS_OFFSET,
        RADAR_BUF_REGION_BYTES
      };
    case RADAR_BUF_REGION_DESC:
    default:
      return (radar_buffer_region_desc_t){
        "desc_ring",
        RADAR_BUF_DESC_BASE,
        RADAR_BUF_DESC_BASE,
        RADAR_BUF_DESC_BASE + DDR_UNCACHED_ALIAS_OFFSET,
        RADAR_BUF_DESC_BYTES
      };
  }
}

static inline uintptr_t radar_buffer_dma_addr(radar_buffer_region_t region, uintptr_t offset_bytes)
{
  radar_buffer_region_desc_t desc = radar_buffer_region_desc(region);
  return desc.dma_base + offset_bytes;
}

static inline uintptr_t radar_buffer_cpu_addr(radar_buffer_region_t region,
                                              radar_buffer_view_t view,
                                              uintptr_t offset_bytes)
{
  radar_buffer_region_desc_t desc = radar_buffer_region_desc(region);
  return (view == RADAR_BUF_VIEW_UNCACHED ? desc.cpu_uncached_base : desc.cpu_cached_base) + offset_bytes;
}

static inline volatile uint32_t *radar_buffer_ptr32(radar_buffer_region_t region,
                                                    radar_buffer_view_t view,
                                                    uintptr_t offset_bytes)
{
  return (volatile uint32_t *)radar_buffer_cpu_addr(region, view, offset_bytes);
}

static inline void radar_describe_buffer_protocol(void)
{
  radar_buffer_region_desc_t in = radar_buffer_region_desc(RADAR_BUF_REGION_IN);
  radar_buffer_region_desc_t mid0 = radar_buffer_region_desc(RADAR_BUF_REGION_MID0);
  radar_buffer_region_desc_t mid1 = radar_buffer_region_desc(RADAR_BUF_REGION_MID1);
  radar_buffer_region_desc_t out = radar_buffer_region_desc(RADAR_BUF_REGION_OUT);

  printf("Buffer protocol: IN=0x%08lx MID0=0x%08lx MID1=0x%08lx OUT=0x%08lx uncached_offset=0x%lx\n",
         (unsigned long)in.dma_base,
         (unsigned long)mid0.dma_base,
         (unsigned long)mid1.dma_base,
         (unsigned long)out.dma_base,
         (unsigned long)DDR_UNCACHED_ALIAS_OFFSET);
}

static inline void preproc_write32(uintptr_t reg_off, uint32_t value)
{
  mmio_write32(DMA_BASE_ADDR + reg_off, value);
}

static inline uint32_t preproc_read32(uintptr_t reg_off)
{
  return mmio_read32(DMA_BASE_ADDR + reg_off);
}

static inline void preproc_clear_counters(void)
{
  preproc_write32(PREPROC_CTRL, PREPROC_CTRL_CLR_COUNTS);
  preproc_write32(PREPROC_CTRL, 0u);
}

static inline void preproc_configure(uint32_t mode, uint32_t param0, uint32_t param1, int enable)
{
  preproc_write32(PREPROC_MODE, mode);
  preproc_write32(PREPROC_PARAM0, param0);
  preproc_write32(PREPROC_PARAM1, param1);
  preproc_write32(PREPROC_CTRL, enable ? PREPROC_CTRL_ENABLE : 0u);
}

static inline void preproc_disable(void)
{
  preproc_configure(PREPROC_MODE_BYPASS, 0u, 0u, 0);
}

static inline void preproc_dump_status(const char *tag)
{
  printf("%s preproc: CTRL=0x%08x MODE=0x%08x PARAM0=0x%08x PARAM1=0x%08x STATUS=0x%08x IN=%u OUT=%u FRAMES=%u KEEP=0x%08x CAPS=0x%08x\n",
         tag,
         preproc_read32(PREPROC_CTRL),
         preproc_read32(PREPROC_MODE),
         preproc_read32(PREPROC_PARAM0),
         preproc_read32(PREPROC_PARAM1),
         preproc_read32(PREPROC_STATUS),
         preproc_read32(PREPROC_IN_BEATS),
         preproc_read32(PREPROC_OUT_BEATS),
         preproc_read32(PREPROC_FRAME_COUNT),
         preproc_read32(PREPROC_LAST_KEEP),
         preproc_read32(PREPROC_CAPABILITIES));
}

static inline void qmlp_write32(uintptr_t reg_off, uint32_t value)
{
  mmio_write32(DMA_BASE_ADDR + reg_off, value);
}

static inline uint32_t qmlp_read32(uintptr_t reg_off)
{
  return mmio_read32(DMA_BASE_ADDR + reg_off);
}

static inline void qmlp_clear_counters(void)
{
  qmlp_write32(QMLP_CTRL, QMLP_CTRL_CLR_COUNTS);
  qmlp_write32(QMLP_CTRL, 0u);
}

static inline void qmlp_enable(int enable)
{
  qmlp_write32(QMLP_CTRL, enable ? QMLP_CTRL_ENABLE : 0u);
}

static inline void qmlp_dump_status(const char *tag)
{
  printf("%s qmlp: CTRL=0x%08x STATUS=0x%08x IN=%u OUT=%u FRAMES=%u KEEP=0x%08x LOGIT0=%d LOGIT1=%d CYC=%u CAPS=0x%08x SAMPLE=%u OUTPUT=%u\n",
         tag,
         qmlp_read32(QMLP_CTRL),
         qmlp_read32(QMLP_STATUS),
         qmlp_read32(QMLP_IN_BEATS),
         qmlp_read32(QMLP_OUT_BEATS),
         qmlp_read32(QMLP_FRAME_COUNT),
         qmlp_read32(QMLP_LAST_KEEP),
         (int32_t)qmlp_read32(QMLP_LAST_LOGIT0),
         (int32_t)qmlp_read32(QMLP_LAST_LOGIT1),
         qmlp_read32(QMLP_RUN_CYCLES),
         qmlp_read32(QMLP_CAPABILITIES),
         qmlp_read32(QMLP_SAMPLE_BYTES),
         qmlp_read32(QMLP_OUTPUT_BYTES));
}

static inline volatile uint32_t *tx_buffer(void)
{
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_CACHED, RADAR_STAGE_TX_OFFSET);
}

static inline volatile uint32_t *rx_buffer(void)
{
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_CACHED, RADAR_STAGE_RX_OFFSET);
}

static inline volatile uint32_t *evict_buffer(void)
{
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_CACHED, RADAR_STAGE_EVICT_OFFSET);
}

static inline void dma_dump_channel_regs(const char *name,
                                         uintptr_t cr_off,
                                         uintptr_t sr_off,
                                         uintptr_t addr_lo_off,
                                         uintptr_t addr_hi_off,
                                         uintptr_t len_off)
{
  printf("%s regs: DMACR=0x%08x DMASR=0x%08x ADDR_LO=0x%08x ADDR_HI=0x%08x LEN=0x%08x\n",
         name,
         mmio_read32(DMA_BASE_ADDR + cr_off),
         mmio_read32(DMA_BASE_ADDR + sr_off),
         mmio_read32(DMA_BASE_ADDR + addr_lo_off),
         mmio_read32(DMA_BASE_ADDR + addr_hi_off),
         mmio_read32(DMA_BASE_ADDR + len_off));
}

static inline void dma_dump_buffers_preview(void)
{
  volatile uint32_t *tx = tx_buffer();
  volatile uint32_t *rx = rx_buffer();

  printf("TX preview: %08x %08x %08x %08x\n", tx[0], tx[1], tx[2], tx[3]);
  printf("RX preview: %08x %08x %08x %08x\n", rx[0], rx[1], rx[2], rx[3]);
}

static inline int dma_reset_channel(const char *name, uintptr_t cr_off, uintptr_t sr_off)
{
  unsigned long timeout = DMA_TIMEOUT_CYCLES;

  printf("%s reset begin\n", name);
  mmio_write32(DMA_BASE_ADDR + cr_off, DMACR_RESET);

  while ((mmio_read32(DMA_BASE_ADDR + cr_off) & DMACR_RESET) != 0u) {
    if (timeout-- == 0UL) {
      printf("%s reset timeout: DMACR=0x%08x DMASR=0x%08x\n",
             name,
             mmio_read32(DMA_BASE_ADDR + cr_off),
             mmio_read32(DMA_BASE_ADDR + sr_off));
      return -1;
    }
  }

  mmio_write32(DMA_BASE_ADDR + sr_off, DMASR_CLEAR_MASK);
  return 0;
}

static inline int dma_wait_running(const char *name, uintptr_t sr_off)
{
  unsigned long timeout = DMA_TIMEOUT_CYCLES;

  while (timeout-- > 0UL) {
    uint32_t status = mmio_read32(DMA_BASE_ADDR + sr_off);
    if ((status & DMASR_HALTED) == 0u) {
      return 0;
    }
  }

  printf("%s failed to leave HALTED: DMASR=0x%08x\n", name, mmio_read32(DMA_BASE_ADDR + sr_off));
  return -1;
}

static inline void dma_start_simple_s2mm(uintptr_t dst_addr, uint32_t length)
{
  mmio_write32(DMA_BASE_ADDR + S2MM_DMASR, DMASR_CLEAR_MASK);
  mmio_write32(DMA_BASE_ADDR + S2MM_DMACR, DMACR_RUN_MASK);
  if (dma_wait_running("S2MM", S2MM_DMASR) != 0) return;
  mmio_write32(DMA_BASE_ADDR + S2MM_DA, (uint32_t)dst_addr);
  mmio_write32(DMA_BASE_ADDR + S2MM_DA_MSB, 0u);
  mmio_write32(DMA_BASE_ADDR + S2MM_LENGTH, length);
}

static inline void dma_start_simple_mm2s(uintptr_t src_addr, uint32_t length)
{
  mmio_write32(DMA_BASE_ADDR + MM2S_DMASR, DMASR_CLEAR_MASK);
  mmio_write32(DMA_BASE_ADDR + MM2S_DMACR, DMACR_RUN_MASK);
  if (dma_wait_running("MM2S", MM2S_DMASR) != 0) return;
  mmio_write32(DMA_BASE_ADDR + MM2S_SA, (uint32_t)src_addr);
  mmio_write32(DMA_BASE_ADDR + MM2S_SA_MSB, 0u);
  mmio_write32(DMA_BASE_ADDR + MM2S_LENGTH, length);
}

static inline int dma_wait_done(const char *name, uintptr_t sr_off)
{
  unsigned long timeout = DMA_TIMEOUT_CYCLES;

  while (timeout-- > 0UL) {
    uint32_t status = mmio_read32(DMA_BASE_ADDR + sr_off);

    if ((status & DMASR_ERR_MASK) != 0u) {
      printf("%s error: DMASR=0x%08x\n", name, status);
      return -1;
    }

    if ((status & DMASR_IRQ_MASK) != 0u) {
      mmio_write32(DMA_BASE_ADDR + sr_off, DMASR_IRQ_MASK);
      return 0;
    }

    if ((status & DMASR_IDLE) != 0u && (status & DMASR_HALTED) == 0u) {
      return 0;
    }
  }

  printf("%s timeout: DMASR=0x%08x\n", name, mmio_read32(DMA_BASE_ADDR + sr_off));
  return -1;
}

static inline void fill_tx_pattern_words(unsigned long word_count, uint32_t base)
{
  volatile uint32_t *tx = tx_buffer();

  for (unsigned long i = 0; i < word_count; ++i) {
    tx[i] = base | (uint32_t)i;
  }
}

static inline void clear_rx_words(unsigned long word_count)
{
  volatile uint32_t *rx = rx_buffer();

  for (unsigned long i = 0; i < word_count; ++i) {
    rx[i] = 0u;
  }
}

static inline uint32_t dma_cache_sweep(const char *tag)
{
  volatile uint32_t *buf = evict_buffer();
  uint32_t accum = 0;

  for (unsigned long i = 0; i < EVICT_WORD_COUNT; ++i) {
    buf[i] = 0x5A5A0000u | (uint32_t)i;
  }
  riscv_fence_rw_rw();

  for (unsigned long i = 0; i < EVICT_WORD_COUNT; ++i) {
    accum ^= buf[i];
  }

  printf("%s cache sweep complete, accum=0x%08x\n", tag, accum);
  return accum;
}

static inline void dma_prepare_cpu_to_device(const char *tag)
{
  riscv_fence_rw_rw();
  dma_cache_sweep(tag);
  riscv_fence_rw_rw();
}

static inline void dma_prepare_device_to_cpu(const char *tag)
{
  dma_cache_sweep(tag);
  riscv_fence_rw_rw();
}

static inline long compare_buffers_words(unsigned long word_count, const char *tag)
{
  volatile uint32_t *tx = tx_buffer();
  volatile uint32_t *rx = rx_buffer();

  for (unsigned long i = 0; i < word_count; ++i) {
    uint32_t tx_word = tx[i];
    uint32_t rx_word = rx[i];
    if (tx_word != rx_word) {
      printf("%s mismatch at word %lu: tx=0x%08x rx=0x%08x\n", tag, i, tx_word, rx_word);
      return (long)i;
    }
  }

  printf("%s compare passed\n", tag);
  return -1;
}

static inline int dma_run_loopback_once(uintptr_t src_addr, uintptr_t dst_addr, uint32_t length)
{
  if (dma_reset_channel("MM2S", MM2S_DMACR, MM2S_DMASR) != 0) return -1;
  if (dma_reset_channel("S2MM", S2MM_DMACR, S2MM_DMASR) != 0) return -1;

  dma_start_simple_s2mm(dst_addr, length);
  dma_start_simple_mm2s(src_addr, length);

  if (dma_wait_done("MM2S", MM2S_DMASR) != 0) return -1;
  if (dma_wait_done("S2MM", S2MM_DMASR) != 0) return -1;
  return 0;
}

static inline int dma_run_stream_once(uintptr_t src_addr,
                                      uint32_t mm2s_length,
                                      uintptr_t dst_addr,
                                      uint32_t s2mm_length)
{
  if (dma_reset_channel("MM2S", MM2S_DMACR, MM2S_DMASR) != 0) return -1;
  if (dma_reset_channel("S2MM", S2MM_DMACR, S2MM_DMASR) != 0) return -1;

  dma_start_simple_s2mm(dst_addr, s2mm_length);
  dma_start_simple_mm2s(src_addr, mm2s_length);

  if (dma_wait_done("MM2S", MM2S_DMASR) != 0) return -1;
  if (dma_wait_done("S2MM", S2MM_DMASR) != 0) return -1;
  return 0;
}

#endif
