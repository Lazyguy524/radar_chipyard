#include "radar_axi_dma_common.h"

int main(void)
{
  printf("AXI DMA loopback cache-maint probe start\n");
  printf("TX_BUFFER_ADDR=0x%08lx RX_BUFFER_ADDR=0x%08lx EVICT_BUFFER_ADDR=0x%08lx\n",
         (unsigned long)TX_BUFFER_ADDR,
         (unsigned long)RX_BUFFER_ADDR,
         (unsigned long)EVICT_BUFFER_ADDR);

  fill_tx_pattern_words(TEST_WORD_COUNT, 0xC3C30000u);
  clear_rx_words(TEST_WORD_COUNT);
  dma_prepare_cpu_to_device("Pre-DMA");

  if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT) != 0) {
    return 1;
  }

  dma_prepare_device_to_cpu("Post-DMA");

  if (compare_buffers_words(TEST_WORD_COUNT, "Cache-maint") >= 0) {
    printf("CACHE_MAINT_PROBE_FAILED\n");
    return 1;
  }

  printf("CACHE_MAINT_PROBE_PASSED\n");
  return 0;
}
