#include "radar_axi_dma_common.h"

#define DDR_UNCACHED_ALIAS_OFFSET 0x1000000000UL
#define TX_BUFFER_CPU_ADDR        (TX_BUFFER_ADDR + DDR_UNCACHED_ALIAS_OFFSET)
#define RX_BUFFER_CPU_ADDR        (RX_BUFFER_ADDR + DDR_UNCACHED_ALIAS_OFFSET)

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

static inline volatile uint32_t *tx_buffer_uncached(void)
{
  return (volatile uint32_t *)TX_BUFFER_CPU_ADDR;
}

static inline volatile uint32_t *rx_buffer_uncached(void)
{
  return (volatile uint32_t *)RX_BUFFER_CPU_ADDR;
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

static long compare_uncached_words(unsigned long word_count, const char *tag)
{
  volatile uint32_t *tx = tx_buffer_uncached();
  volatile uint32_t *rx = rx_buffer_uncached();

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

static int run_mmio_smoke(void)
{
  uint32_t mm2s_status_0;
  uint32_t mm2s_status_1;
  uint32_t s2mm_status_0;
  uint32_t s2mm_status_1;

  printf("[MMIO] start\n");

  mm2s_status_0 = mmio_read32(DMA_BASE_ADDR + MM2S_DMASR);
  mm2s_status_1 = mmio_read32(DMA_BASE_ADDR + MM2S_DMASR);
  s2mm_status_0 = mmio_read32(DMA_BASE_ADDR + S2MM_DMASR);
  s2mm_status_1 = mmio_read32(DMA_BASE_ADDR + S2MM_DMASR);

  printf("[MMIO] MM2S_DMASR=0x%08x/0x%08x S2MM_DMASR=0x%08x/0x%08x\n",
         mm2s_status_0, mm2s_status_1, s2mm_status_0, s2mm_status_1);

  if (dma_reset_channel("MM2S", MM2S_DMACR, MM2S_DMASR) != 0) return -1;
  if (dma_reset_channel("S2MM", S2MM_DMACR, S2MM_DMASR) != 0) return -1;

  printf("[MMIO] passed\n");
  return 0;
}

static int run_cache_probe(void)
{
  long no_maint_bad;
  long pre_only_bad;
  long full_maint_bad;

  printf("[CACHE] probe start\n");

  fill_tx_pattern_words(TEST_WORD_COUNT, 0xA5A50000u);
  clear_rx_words(TEST_WORD_COUNT);
  riscv_fence_rw_rw();

  if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT) != 0) {
    printf("[CACHE] no-maint DMA run failed\n");
    return -1;
  }
  no_maint_bad = compare_buffers_words(TEST_WORD_COUNT, "[CACHE] no-maint");

  fill_tx_pattern_words(TEST_WORD_COUNT, 0xB6B60000u);
  clear_rx_words(TEST_WORD_COUNT);
  dma_prepare_cpu_to_device("[CACHE] pre-only");

  if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT) != 0) {
    printf("[CACHE] pre-only DMA run failed\n");
    return -1;
  }
  pre_only_bad = compare_buffers_words(TEST_WORD_COUNT, "[CACHE] pre-only");

  fill_tx_pattern_words(TEST_WORD_COUNT, 0xC7C70000u);
  clear_rx_words(TEST_WORD_COUNT);
  dma_prepare_cpu_to_device("[CACHE] full-pre");

  if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT) != 0) {
    printf("[CACHE] full-maint DMA run failed\n");
    return -1;
  }
  dma_prepare_device_to_cpu("[CACHE] full-post");
  full_maint_bad = compare_buffers_words(TEST_WORD_COUNT, "[CACHE] full-maint");

  printf("[CACHE] summary no-maint=%ld pre-only=%ld full-maint=%ld\n",
         no_maint_bad, pre_only_bad, full_maint_bad);

  if (full_maint_bad >= 0) {
    printf("[CACHE] full maintenance still failed\n");
    return -1;
  }

  if (no_maint_bad < 0 && pre_only_bad < 0) {
    printf("[CACHE] no observable incoherence in this run\n");
  } else {
    printf("[CACHE] software cache maintenance remains required\n");
  }

  printf("[CACHE] passed\n");
  return 0;
}

static int run_uncached_alias(void)
{
  printf("[UNCACHED] start\n");
  printf("[UNCACHED] TX_CPU=0x%016lx RX_CPU=0x%016lx\n",
         (unsigned long)TX_BUFFER_CPU_ADDR,
         (unsigned long)RX_BUFFER_CPU_ADDR);

  fill_tx_pattern_uncached(TEST_WORD_COUNT, 0xD4D40000u);
  clear_rx_uncached(TEST_WORD_COUNT);
  riscv_fence_rw_rw();

  if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT) != 0) {
    printf("[UNCACHED] DMA run failed\n");
    return -1;
  }

  riscv_fence_rw_rw();

  if (compare_uncached_words(TEST_WORD_COUNT, "[UNCACHED]") >= 0) {
    printf("[UNCACHED] compare failed\n");
    return -1;
  }

  printf("[UNCACHED] passed\n");
  return 0;
}

static int run_consistency(void)
{
  unsigned long i;

  printf("[CONSISTENCY] start\n");

  for (i = 0; i < (sizeof(dma_cases) / sizeof(dma_cases[0])); ++i) {
    uint32_t length_bytes = (uint32_t)(dma_cases[i].words * sizeof(uint32_t));
    printf("[CONSISTENCY] case=%lu words=%lu bytes=%u pattern=0x%08x\n",
           i, dma_cases[i].words, length_bytes, dma_cases[i].pattern_base);

    fill_tx_pattern_words(dma_cases[i].words, dma_cases[i].pattern_base);
    clear_rx_words(dma_cases[i].words);
    dma_prepare_cpu_to_device("[CONSISTENCY] pre");

    if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, length_bytes) != 0) {
      printf("[CONSISTENCY] case=%lu DMA run failed\n", i);
      return -1;
    }

    dma_prepare_device_to_cpu("[CONSISTENCY] post");

    if (compare_buffers_words(dma_cases[i].words, "[CONSISTENCY] compare") >= 0) {
      printf("[CONSISTENCY] case=%lu compare failed\n", i);
      return -1;
    }
  }

  printf("[CONSISTENCY] passed\n");
  return 0;
}

int main(void)
{
  printf("AXI DMA integrated regression start\n");
  printf("TX_BUFFER_ADDR=0x%08lx RX_BUFFER_ADDR=0x%08lx EVICT_BUFFER_ADDR=0x%08lx\n",
         (unsigned long)TX_BUFFER_ADDR,
         (unsigned long)RX_BUFFER_ADDR,
         (unsigned long)EVICT_BUFFER_ADDR);

  if (run_mmio_smoke() != 0) {
    printf("AXI_DMA_REGRESSION_FAILED\n");
    return 1;
  }

  if (run_cache_probe() != 0) {
    printf("AXI_DMA_REGRESSION_FAILED\n");
    return 1;
  }

  if (run_uncached_alias() != 0) {
    printf("AXI_DMA_REGRESSION_FAILED\n");
    return 1;
  }

  if (run_consistency() != 0) {
    printf("AXI_DMA_REGRESSION_FAILED\n");
    return 1;
  }

  printf("AXI_DMA_REGRESSION_PASSED\n");
  return 0;
}
