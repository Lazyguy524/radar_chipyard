#include "radar_axi_dma_common.h"

int main(void)
{
  long first_bad;
  long second_bad;

  printf("AXI DMA loopback cache probe start\n");
  printf("TX_BUFFER_ADDR=0x%08lx RX_BUFFER_ADDR=0x%08lx EVICT_BUFFER_ADDR=0x%08lx\n",
         (unsigned long)TX_BUFFER_ADDR,
         (unsigned long)RX_BUFFER_ADDR,
         (unsigned long)EVICT_BUFFER_ADDR);

  fill_tx_pattern_words(TEST_WORD_COUNT, 0xA5A50000u);
  clear_rx_words(TEST_WORD_COUNT);
  riscv_fence_rw_rw();

  if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT) != 0) {
    return 1;
  }

  riscv_fence_rw_rw();

  first_bad = compare_buffers_words(TEST_WORD_COUNT, "Before eviction");
  dma_prepare_device_to_cpu("Eviction sweep");
  second_bad = compare_buffers_words(TEST_WORD_COUNT, "After eviction");

  if (first_bad >= 0 && second_bad < 0) {
    printf("CACHE_COHERENCE_HYPOTHESIS_CONFIRMED\n");
    return 0;
  }

  if (second_bad >= 0) {
    printf("AXI DMA loopback cache probe FAILED\n");
    return 1;
  }

  printf("AXI DMA loopback cache probe PASSED\n");
  return 0;
}
