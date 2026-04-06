#include "radar_axi_dma_common.h"
#include "radar_qmlp_test_common.h"

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
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
}

static inline volatile uint32_t *rx_buffer_uncached(void)
{
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_RX_OFFSET);
}

static inline volatile int8_t *tx_buffer_u8_uncached(void)
{
  return (volatile int8_t *)radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
}

static inline volatile int32_t *rx_buffer_i32_uncached(void)
{
  return (volatile int32_t *)radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_RX_OFFSET);
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
  const uintptr_t tx_cpu_addr = radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
  const uintptr_t rx_cpu_addr = radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_RX_OFFSET);

  printf("[UNCACHED] start\n");
  printf("[UNCACHED] TX_CPU=0x%016lx RX_CPU=0x%016lx\n",
         (unsigned long)tx_cpu_addr,
         (unsigned long)rx_cpu_addr);

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

static void prepare_qmlp_input(const int8_t sample[RADAR_MLP_INPUT_DIM])
{
  volatile int8_t *tx = tx_buffer_u8_uncached();
  volatile int32_t *rx = rx_buffer_i32_uncached();
  unsigned int i;

  for (i = 0; i < RADAR_QMLP_TEST_INPUT_BYTES; ++i) {
    tx[i] = 0;
  }
  for (i = 0; i < (unsigned int)RADAR_MLP_INPUT_DIM; ++i) {
    tx[i] = sample[i];
  }
  for (i = 0; i < 8u; ++i) {
    rx[i] = 0;
  }
}

static int check_qmlp_counters(void)
{
  uint32_t in_beats = qmlp_read32(QMLP_IN_BEATS);
  uint32_t out_beats = qmlp_read32(QMLP_OUT_BEATS);
  uint32_t frames = qmlp_read32(QMLP_FRAME_COUNT);
  uint32_t keep = qmlp_read32(QMLP_LAST_KEEP);
  uint32_t sample_bytes = qmlp_read32(QMLP_SAMPLE_BYTES);
  uint32_t output_bytes = qmlp_read32(QMLP_OUTPUT_BYTES);

  printf("[QMLP] counters: in=%u out=%u frames=%u keep=0x%08x sample=%u output=%u\n",
         in_beats, out_beats, frames, keep, sample_bytes, output_bytes);

  if (in_beats != 4u || out_beats != 1u || frames != 1u || keep != 0xffu ||
      sample_bytes != RADAR_QMLP_TEST_INPUT_BYTES || output_bytes != RADAR_QMLP_TEST_OUTPUT_BYTES) {
    printf("[QMLP] counter check failed\n");
    return -1;
  }
  return 0;
}

static int compare_qmlp_output(const int32_t golden_logits[2])
{
  volatile int32_t *rx = rx_buffer_i32_uncached();

  printf("[QMLP] output logits: hw={%d, %d} golden={%d, %d}\n",
         rx[0], rx[1],
         golden_logits[0],
         golden_logits[1]);

  if (rx[0] != golden_logits[0] || rx[1] != golden_logits[1]) {
    printf("[QMLP] logits mismatch\n");
    return -1;
  }

  if ((int32_t)qmlp_read32(QMLP_LAST_LOGIT0) != golden_logits[0] ||
      (int32_t)qmlp_read32(QMLP_LAST_LOGIT1) != golden_logits[1]) {
    printf("[QMLP] status logits mismatch\n");
    return -1;
  }

  printf("[QMLP] compare passed\n");
  return 0;
}

static int run_qmlp(void)
{
  uint64_t total_hw_cycles = 0;
  uint64_t total_e2e_cycles = 0;
  uint32_t min_hw_cycles = 0xffffffffu;
  uint32_t max_hw_cycles = 0u;
  int8_t sample[RADAR_MLP_INPUT_DIM];
  int32_t golden_logits[2];
  unsigned int case_idx;

  printf("[QMLP] start\n");

  preproc_disable();
  qmlp_clear_counters();
  qmlp_enable(0);
  qmlp_dump_status("[QMLP] boot");

  radar_qmlp_software_infer(radar_mlp_golden_input, golden_logits);
  if (golden_logits[0] != radar_mlp_golden_logits[0] ||
      golden_logits[1] != radar_mlp_golden_logits[1]) {
    printf("[QMLP] software golden self-check failed\n");
    return -1;
  }

  for (case_idx = 0; case_idx < RADAR_QMLP_MULTI_CASES; ++case_idx) {
    uint64_t start_cycles;
    uint64_t end_cycles;
    uint32_t hw_cycles;

    radar_qmlp_prepare_case(case_idx, sample);
    radar_qmlp_software_infer(sample, golden_logits);
    prepare_qmlp_input(sample);
    riscv_fence_rw_rw();

    qmlp_clear_counters();
    qmlp_enable(1);
    printf("[QMLP][case=%u][%s] configured\n", case_idx, radar_qmlp_case_label(case_idx));

    start_cycles = radar_read_cycle64();
    if (dma_run_stream_once(TX_BUFFER_ADDR, RADAR_QMLP_TEST_INPUT_BYTES,
                            RX_BUFFER_ADDR, RADAR_QMLP_TEST_OUTPUT_BYTES) != 0) {
      qmlp_enable(0);
      printf("[QMLP] DMA run failed\n");
      return -1;
    }
    end_cycles = radar_read_cycle64();

    riscv_fence_rw_rw();
    qmlp_dump_status("[QMLP] done");

    if (check_qmlp_counters() != 0) {
      qmlp_enable(0);
      return -1;
    }

    if (compare_qmlp_output(golden_logits) != 0) {
      qmlp_enable(0);
      return -1;
    }

    hw_cycles = qmlp_read32(QMLP_RUN_CYCLES);
    total_hw_cycles += hw_cycles;
    total_e2e_cycles += (end_cycles - start_cycles);
    if (hw_cycles < min_hw_cycles) min_hw_cycles = hw_cycles;
    if (hw_cycles > max_hw_cycles) max_hw_cycles = hw_cycles;

    printf("[QMLP][case=%u][%s] perf hw_cycles=%u e2e_cycles=%lu mac_per_cycle_x1000=%lu\n",
           case_idx,
           radar_qmlp_case_label(case_idx),
           hw_cycles,
           (unsigned long)(end_cycles - start_cycles),
           (unsigned long)((uint64_t)RADAR_QMLP_TOTAL_MACS * 1000ull / (uint64_t)hw_cycles));
  }

  qmlp_enable(0);
  printf("[QMLP] multi-sample summary cases=%u hw_cycles_avg=%lu hw_cycles_min=%u hw_cycles_max=%u e2e_cycles_avg=%lu inf_per_sec=%lu input_MBps_x100=%lu\n",
         RADAR_QMLP_MULTI_CASES,
         (unsigned long)(total_hw_cycles / RADAR_QMLP_MULTI_CASES),
         min_hw_cycles,
         max_hw_cycles,
         (unsigned long)(total_e2e_cycles / RADAR_QMLP_MULTI_CASES),
         (unsigned long)(50000000ull * RADAR_QMLP_MULTI_CASES / total_hw_cycles),
         (unsigned long)((uint64_t)RADAR_QMLP_MULTI_CASES * RADAR_QMLP_TEST_INPUT_BYTES * 5000000000ull / total_hw_cycles));
  printf("[QMLP] passed\n");
  return 0;
}

int main(void)
{
  printf("AXI DMA integrated regression start\n");
  radar_describe_buffer_protocol();
  preproc_disable();
  preproc_clear_counters();
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

  if (run_qmlp() != 0) {
    printf("AXI_DMA_REGRESSION_FAILED\n");
    return 1;
  }

  printf("AXI_DMA_REGRESSION_PASSED\n");
  return 0;
}
