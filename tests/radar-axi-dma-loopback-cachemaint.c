#include <stdint.h>
#include <stdio.h>

#define DMA_BASE_ADDR      0x60000000UL
#define TX_BUFFER_ADDR     0x81000000UL
#define RX_BUFFER_ADDR     0x81001000UL
#define EVICT_BUFFER_ADDR  0x81010000UL
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

static volatile uint32_t *tx_buffer(void) { return (volatile uint32_t *)TX_BUFFER_ADDR; }
static volatile uint32_t *rx_buffer(void) { return (volatile uint32_t *)RX_BUFFER_ADDR; }
static volatile uint32_t *evict_buffer(void) { return (volatile uint32_t *)EVICT_BUFFER_ADDR; }

static int dma_reset_channel(const char *name, uintptr_t cr_off, uintptr_t sr_off)
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

static int dma_wait_running(const char *name, uintptr_t sr_off)
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

static int dma_wait_done(const char *name, uintptr_t sr_off)
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

static void dma_start_simple_s2mm(uintptr_t dst_addr, uint32_t length)
{
  mmio_write32(DMA_BASE_ADDR + S2MM_DMASR, DMASR_CLEAR_MASK);
  mmio_write32(DMA_BASE_ADDR + S2MM_DMACR, DMACR_RUN_MASK);
  if (dma_wait_running("S2MM", S2MM_DMASR) != 0) return;
  mmio_write32(DMA_BASE_ADDR + S2MM_DA, (uint32_t)dst_addr);
  mmio_write32(DMA_BASE_ADDR + S2MM_DA_MSB, 0u);
  mmio_write32(DMA_BASE_ADDR + S2MM_LENGTH, length);
}

static void dma_start_simple_mm2s(uintptr_t src_addr, uint32_t length)
{
  mmio_write32(DMA_BASE_ADDR + MM2S_DMASR, DMASR_CLEAR_MASK);
  mmio_write32(DMA_BASE_ADDR + MM2S_DMACR, DMACR_RUN_MASK);
  if (dma_wait_running("MM2S", MM2S_DMASR) != 0) return;
  mmio_write32(DMA_BASE_ADDR + MM2S_SA, (uint32_t)src_addr);
  mmio_write32(DMA_BASE_ADDR + MM2S_SA_MSB, 0u);
  mmio_write32(DMA_BASE_ADDR + MM2S_LENGTH, length);
}

static void fill_tx_pattern(uint32_t base)
{
  volatile uint32_t *tx = tx_buffer();
  for (unsigned long i = 0; i < TEST_WORD_COUNT; ++i) {
    tx[i] = base | (uint32_t)i;
  }
}

static void clear_rx_buffer(void)
{
  volatile uint32_t *rx = rx_buffer();
  for (unsigned long i = 0; i < TEST_WORD_COUNT; ++i) {
    rx[i] = 0u;
  }
}

static uint32_t sweep_cache(const char *tag)
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

static long compare_buffers(void)
{
  volatile uint32_t *tx = tx_buffer();
  volatile uint32_t *rx = rx_buffer();

  for (unsigned long i = 0; i < TEST_WORD_COUNT; ++i) {
    uint32_t tx_word = tx[i];
    uint32_t rx_word = rx[i];
    if (tx_word != rx_word) {
      printf("Mismatch at word %lu: tx=0x%08x rx=0x%08x\n", i, tx_word, rx_word);
      return (long)i;
    }
  }

  printf("Compare passed\n");
  return -1;
}

int main(void)
{
  printf("AXI DMA loopback cache-maint probe start\n");
  printf("TX_BUFFER_ADDR=0x%08lx RX_BUFFER_ADDR=0x%08lx EVICT_BUFFER_ADDR=0x%08lx\n",
         (unsigned long)TX_BUFFER_ADDR,
         (unsigned long)RX_BUFFER_ADDR,
         (unsigned long)EVICT_BUFFER_ADDR);

  fill_tx_pattern(0xC3C30000u);
  clear_rx_buffer();
  riscv_fence_rw_rw();
  sweep_cache("Pre-DMA");
  riscv_fence_rw_rw();

  if (dma_reset_channel("MM2S", MM2S_DMACR, MM2S_DMASR) != 0) return 1;
  if (dma_reset_channel("S2MM", S2MM_DMACR, S2MM_DMASR) != 0) return 1;

  dma_start_simple_s2mm(RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT);
  dma_start_simple_mm2s(TX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT);

  if (dma_wait_done("MM2S", MM2S_DMASR) != 0) return 1;
  if (dma_wait_done("S2MM", S2MM_DMASR) != 0) return 1;

  sweep_cache("Post-DMA");
  riscv_fence_rw_rw();

  if (compare_buffers() >= 0) {
    printf("CACHE_MAINT_PROBE_FAILED\n");
    return 1;
  }

  printf("CACHE_MAINT_PROBE_PASSED\n");
  return 0;
}
