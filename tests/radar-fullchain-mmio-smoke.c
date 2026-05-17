#include "radar_fullchain_common.h"

#define DMA_TIMEOUT_CYCLES 1000000UL

static int wait_dma_reset_clear(const char *name, uintptr_t cr_off)
{
  unsigned long timeout = DMA_TIMEOUT_CYCLES;
  while ((fullchain_read32(cr_off) & FULLCHAIN_DMACR_RESET) != 0u) {
    if (timeout-- == 0UL) {
      printf("%s reset timeout, DMACR=0x%08x\n", name, fullchain_read32(cr_off));
      return -1;
    }
  }
  return 0;
}

static int reset_dma_channel(const char *name, uintptr_t cr_off, uintptr_t sr_off)
{
  printf("%s before reset: DMACR=0x%08x DMASR=0x%08x\n",
         name, fullchain_read32(cr_off), fullchain_read32(sr_off));
  fullchain_write32(sr_off, FULLCHAIN_DMASR_CLEAR_MASK);
  fullchain_write32(cr_off, FULLCHAIN_DMACR_RESET);
  if (wait_dma_reset_clear(name, cr_off) != 0) {
    return -1;
  }
  printf("%s after reset:  DMACR=0x%08x DMASR=0x%08x\n",
         name, fullchain_read32(cr_off), fullchain_read32(sr_off));
  return 0;
}

int main(void)
{
  uint32_t version;
  uint32_t expected_in;
  uint32_t expected_out;
  uint32_t status;

  printf("FullChain AXI DMA/MMIO smoke test start\n");
  printf("FULLCHAIN_BASE_ADDR=0x%08lx\n", (unsigned long)FULLCHAIN_BASE_ADDR);

  if (reset_dma_channel("MM2S", FULLCHAIN_DMA_MM2S_DMACR, FULLCHAIN_DMA_MM2S_DMASR) != 0) {
    printf("FullChain smoke test FAILED\n");
    return 1;
  }

  if (reset_dma_channel("S2MM", FULLCHAIN_DMA_S2MM_DMACR, FULLCHAIN_DMA_S2MM_DMASR) != 0) {
    printf("FullChain smoke test FAILED\n");
    return 1;
  }

  version = fullchain_read32(FULLCHAIN_ACCEL_VERSION);
  printf("FullChain VERSION=0x%08x\n", version);
  if (version != 0x20260509u) {
    printf("Unexpected FullChain VERSION, expected 0x20260509\n");
    printf("FullChain smoke test FAILED\n");
    return 1;
  }

  fullchain_configure_128x64_default();
  fullchain_dump_core_status("after-config");

  expected_in = fullchain_read32(FULLCHAIN_ACCEL_EXPECTED_IN);
  expected_out = fullchain_read32(FULLCHAIN_ACCEL_EXPECTED_OUT);
  status = fullchain_read32(FULLCHAIN_ACCEL_STATUS);

  if (expected_in != 8192u || expected_out != 4096u) {
    printf("Unexpected expected word counts: in=%u out=%u\n", expected_in, expected_out);
    printf("FullChain smoke test FAILED\n");
    return 1;
  }

  if ((status & FULLCHAIN_STATUS_CFG_ILLEGAL) != 0u) {
    printf("FullChain config marked illegal: STATUS=0x%08x\n", status);
    printf("FullChain smoke test FAILED\n");
    return 1;
  }

  printf("FullChain AXI DMA/MMIO smoke test PASSED\n");
  return 0;
}
