#include <stdint.h>
#include <stdio.h>

#define DMA_BASE_ADDR      0x60000000UL
#define DMA_TIMEOUT_CYCLES 1000000UL

#define MM2S_DMACR   0x00UL
#define MM2S_DMASR   0x04UL
#define S2MM_DMACR   0x30UL
#define S2MM_DMASR   0x34UL

#define DMACR_RESET      (1u << 2)
#define DMASR_ERR_MASK   ((1u << 4) | (1u << 5) | (1u << 6) | (1u << 8) | (1u << 9) | (1u << 10) | (1u << 14))
#define DMASR_IRQ_MASK   ((1u << 12) | (1u << 13) | (1u << 14))
#define DMASR_CLEAR_MASK (DMASR_ERR_MASK | DMASR_IRQ_MASK)

static inline void dma_write32(uintptr_t offset, uint32_t value)
{
  volatile uint32_t *ptr = (volatile uint32_t *)(DMA_BASE_ADDR + offset);
  *ptr = value;
}

static inline uint32_t dma_read32(uintptr_t offset)
{
  volatile uint32_t *ptr = (volatile uint32_t *)(DMA_BASE_ADDR + offset);
  return *ptr;
}

static void dump_channel(const char *name, uintptr_t cr_off, uintptr_t sr_off)
{
  uint32_t dmacr = dma_read32(cr_off);
  uint32_t dmasr = dma_read32(sr_off);
  printf("%s DMACR=0x%08x DMASR=0x%08x\n", name, dmacr, dmasr);
}

static int poll_reset_clear(const char *name, uintptr_t cr_off, uintptr_t sr_off)
{
  unsigned long timeout = DMA_TIMEOUT_CYCLES;

  while ((dma_read32(cr_off) & DMACR_RESET) != 0u) {
    if (timeout-- == 0UL) {
      printf("%s reset timeout: DMACR=0x%08x DMASR=0x%08x\n",
             name, dma_read32(cr_off), dma_read32(sr_off));
      return -1;
    }
  }

  return 0;
}

static int reset_channel(const char *name, uintptr_t cr_off, uintptr_t sr_off)
{
  printf("%s before reset\n", name);
  dump_channel(name, cr_off, sr_off);

  dma_write32(sr_off, DMASR_CLEAR_MASK);
  dma_write32(cr_off, DMACR_RESET);

  if (poll_reset_clear(name, cr_off, sr_off) != 0) {
    return -1;
  }

  printf("%s after reset\n", name);
  dump_channel(name, cr_off, sr_off);
  return 0;
}

int main(void)
{
  uint32_t mm2s_status_0;
  uint32_t mm2s_status_1;
  uint32_t s2mm_status_0;
  uint32_t s2mm_status_1;

  printf("Radar AXI DMA CSR smoke test start\n");
  printf("DMA_BASE_ADDR=0x%08lx\n", (unsigned long)DMA_BASE_ADDR);

  mm2s_status_0 = dma_read32(MM2S_DMASR);
  mm2s_status_1 = dma_read32(MM2S_DMASR);
  s2mm_status_0 = dma_read32(S2MM_DMASR);
  s2mm_status_1 = dma_read32(S2MM_DMASR);

  printf("MM2S_DMASR first=0x%08x second=0x%08x\n", mm2s_status_0, mm2s_status_1);
  printf("S2MM_DMASR first=0x%08x second=0x%08x\n", s2mm_status_0, s2mm_status_1);

  if (reset_channel("MM2S", MM2S_DMACR, MM2S_DMASR) != 0) {
    printf("Radar AXI DMA CSR smoke test FAILED\n");
    return 1;
  }

  if (reset_channel("S2MM", S2MM_DMACR, S2MM_DMASR) != 0) {
    printf("Radar AXI DMA CSR smoke test FAILED\n");
    return 1;
  }

  printf("Radar AXI DMA CSR smoke test PASSED\n");
  return 0;
}
