#include "radar_axi_dma_common.h"

typedef struct {
  unsigned long words;
  uint32_t pattern_base;
} dma_case_t;

static const dma_case_t dma_cases[] = {
  { 4UL,  0x11000000u },
  { 8UL,  0x22000000u },
  { 15UL, 0x33000000u },
  { 16UL, 0x44000000u },
  { 31UL, 0x55000000u },
  { 32UL, 0x66000000u },
  { 33UL, 0x77000000u },
  { 63UL, 0x88000000u },
  { 64UL, 0x99000000u }
};

static int run_case(unsigned long iteration, const dma_case_t *test_case)
{
  uint32_t length_bytes = (uint32_t)(test_case->words * sizeof(uint32_t));

  printf("CASE[%lu] words=%lu bytes=%u pattern=0x%08x\n",
         iteration,
         test_case->words,
         length_bytes,
         test_case->pattern_base);

  fill_tx_pattern_words(test_case->words, test_case->pattern_base);
  clear_rx_words(test_case->words);
  dma_prepare_cpu_to_device("Pre-DMA");

  if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, length_bytes) != 0) {
    printf("CASE[%lu] DMA run failed\n", iteration);
    return -1;
  }

  dma_prepare_device_to_cpu("Post-DMA");

  if (compare_buffers_words(test_case->words, "Consistency") >= 0) {
    printf("CASE[%lu] compare failed\n", iteration);
    return -1;
  }

  return 0;
}

int main(void)
{
  unsigned long i;

  printf("AXI DMA consistency regression start\n");
  radar_describe_buffer_protocol();
  preproc_disable();
  preproc_clear_counters();
  printf("TX_BUFFER_ADDR=0x%08lx RX_BUFFER_ADDR=0x%08lx EVICT_BUFFER_ADDR=0x%08lx\n",
         (unsigned long)TX_BUFFER_ADDR,
         (unsigned long)RX_BUFFER_ADDR,
         (unsigned long)EVICT_BUFFER_ADDR);

  for (i = 0; i < (sizeof(dma_cases) / sizeof(dma_cases[0])); ++i) {
    if (run_case(i, &dma_cases[i]) != 0) {
      printf("DMA_CONSISTENCY_FAILED\n");
      return 1;
    }
  }

  printf("DMA_CONSISTENCY_PASSED\n");
  return 0;
}
