#include "radar_axi_dma_common.h"

static inline volatile uint32_t *tx_buffer_uncached(void)
{
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
}

static inline volatile uint32_t *rx_buffer_uncached(void)
{
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_RX_OFFSET);
}

static void fill_tx_pattern_uncached(unsigned long word_count, uint32_t base)
{
  volatile uint32_t *tx = tx_buffer_uncached();

  for (unsigned long i = 0; i < word_count; ++i) {
    tx[i] = base | (uint32_t)i;
  }
}

static void clear_rx_uncached(unsigned long word_count)
{
  volatile uint32_t *rx = rx_buffer_uncached();

  for (unsigned long i = 0; i < word_count; ++i) {
    rx[i] = 0u;
  }
}

static long compare_uncached_words(unsigned long word_count)
{
  volatile uint32_t *tx = tx_buffer_uncached();
  volatile uint32_t *rx = rx_buffer_uncached();

  for (unsigned long i = 0; i < word_count; ++i) {
    uint32_t tx_word = tx[i];
    uint32_t rx_word = rx[i];
    if (tx_word != rx_word) {
      printf("UNCACHED mismatch at word %lu: tx=0x%08x rx=0x%08x\n", i, tx_word, rx_word);
      return (long)i;
    }
  }

  printf("UNCACHED compare passed\n");
  return -1;
}

int main(void)
{
  const uintptr_t tx_cpu_addr = radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
  const uintptr_t rx_cpu_addr = radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_RX_OFFSET);

  printf("AXI DMA uncached-alias test start\n");
  radar_describe_buffer_protocol();
  preproc_disable();
  preproc_clear_counters();
  printf("TX_BUFFER_ADDR=0x%08lx RX_BUFFER_ADDR=0x%08lx\n",
         (unsigned long)TX_BUFFER_ADDR,
         (unsigned long)RX_BUFFER_ADDR);
  printf("TX_BUFFER_CPU_ADDR=0x%016lx RX_BUFFER_CPU_ADDR=0x%016lx\n",
         (unsigned long)tx_cpu_addr,
         (unsigned long)rx_cpu_addr);

  fill_tx_pattern_uncached(TEST_WORD_COUNT, 0xD4D40000u);
  clear_rx_uncached(TEST_WORD_COUNT);
  riscv_fence_rw_rw();

  if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT) != 0) {
    printf("AXI DMA uncached-alias FAILED\n");
    return 1;
  }

  riscv_fence_rw_rw();

  if (compare_uncached_words(TEST_WORD_COUNT) >= 0) {
    printf("AXI DMA uncached-alias FAILED\n");
    return 1;
  }

  printf("AXI DMA uncached-alias PASSED\n");
  return 0;
}
