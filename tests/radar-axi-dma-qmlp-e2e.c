#include "radar_axi_dma_common.h"
#include "radar_qmlp_test_common.h"

#define RADAR_QMLP_BATCH_INPUT_BYTES   (RADAR_QMLP_MULTI_CASES * RADAR_QMLP_TEST_INPUT_BYTES)
#define RADAR_QMLP_BATCH_OUTPUT_BYTES  (RADAR_QMLP_MULTI_CASES * RADAR_QMLP_TEST_OUTPUT_BYTES)

static inline volatile int8_t *tx_buffer_u8_uncached(void)
{
  return (volatile int8_t *)radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
}

static inline volatile int32_t *rx_buffer_i32_uncached(void)
{
  return (volatile int32_t *)radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_RX_OFFSET);
}

static void prepare_qmlp_input_at(unsigned int sample_idx, const int8_t sample[RADAR_MLP_INPUT_DIM])
{
  volatile int8_t *tx = tx_buffer_u8_uncached();
  unsigned int i;
  unsigned int base = sample_idx * RADAR_QMLP_TEST_INPUT_BYTES;

  for (i = 0; i < RADAR_QMLP_TEST_INPUT_BYTES; ++i) {
    tx[base + i] = 0;
  }
  for (i = 0; i < (unsigned int)RADAR_MLP_INPUT_DIM; ++i) {
    tx[base + i] = sample[i];
  }
}

static void clear_qmlp_output_words(unsigned int word_count)
{
  volatile int32_t *rx = rx_buffer_i32_uncached();
  unsigned int i;

  for (i = 0; i < word_count; ++i) {
    rx[i] = 0;
  }
}

static int compare_qmlp_output_at(unsigned int sample_idx, const int32_t golden_logits[2])
{
  volatile int32_t *rx = rx_buffer_i32_uncached();
  unsigned int base = sample_idx * 2u;

  if (rx[base + 0u] != golden_logits[0] || rx[base + 1u] != golden_logits[1]) {
    printf("[QMLP][case=%u] logits mismatch hw={%d,%d} golden={%d,%d}\n",
           sample_idx,
           rx[base + 0u], rx[base + 1u],
           golden_logits[0], golden_logits[1]);
    return -1;
  }
  return 0;
}

static void dump_qmlp_batch_outputs(unsigned int sample_count)
{
  volatile int32_t *rx = rx_buffer_i32_uncached();
  unsigned int i;
  unsigned int limit = sample_count < 4u ? sample_count : 4u;

  printf("[QMLP-E2E][batch-debug] counters in=%u out=%u frames=%u keep=0x%08x sample=%u output=%u cycles=%u\n",
         qmlp_read32(QMLP_IN_BEATS),
         qmlp_read32(QMLP_OUT_BEATS),
         qmlp_read32(QMLP_FRAME_COUNT),
         qmlp_read32(QMLP_LAST_KEEP),
         qmlp_read32(QMLP_SAMPLE_BYTES),
         qmlp_read32(QMLP_OUTPUT_BYTES),
         qmlp_read32(QMLP_RUN_CYCLES));

  for (i = 0; i < limit; ++i) {
    printf("[QMLP-E2E][batch-debug] out[%u]={%d,%d}\n",
           i, rx[i * 2u], rx[i * 2u + 1u]);
  }
}

static int run_legacy_single(unsigned int *avg_hw_cycles, uint64_t *avg_e2e_cycles)
{
  uint64_t total_hw_cycles = 0;
  uint64_t total_e2e_cycles = 0;
  unsigned int case_idx;
  int8_t sample[RADAR_MLP_INPUT_DIM];
  int32_t golden_logits[2];

  for (case_idx = 0; case_idx < RADAR_QMLP_MULTI_CASES; ++case_idx) {
    radar_qmlp_prepare_case(case_idx, sample);
    radar_qmlp_software_infer(sample, golden_logits);
    prepare_qmlp_input_at(0u, sample);
    clear_qmlp_output_words(2u);
    riscv_fence_rw_rw();

    if (qmlp_wait_idle() != 0) {
      qmlp_enable(0);
      return -1;
    }
    qmlp_clear_counters();
    qmlp_enable(1);

    {
      uint64_t start_cycles = radar_read_cycle64();
      if (dma_run_stream_once(TX_BUFFER_ADDR, RADAR_QMLP_TEST_INPUT_BYTES,
                              RX_BUFFER_ADDR, RADAR_QMLP_TEST_OUTPUT_BYTES) != 0) {
        qmlp_enable(0);
        return -1;
      }
      total_e2e_cycles += radar_read_cycle64() - start_cycles;
    }

    if (compare_qmlp_output_at(0u, golden_logits) != 0) {
      qmlp_enable(0);
      return -1;
    }

    total_hw_cycles += qmlp_read32(QMLP_RUN_CYCLES);
    qmlp_enable(0);
    riscv_fence_rw_rw();
    if (qmlp_wait_idle() != 0) {
      return -1;
    }
  }

  *avg_hw_cycles = (unsigned int)(total_hw_cycles / RADAR_QMLP_MULTI_CASES);
  *avg_e2e_cycles = total_e2e_cycles / RADAR_QMLP_MULTI_CASES;
  return 0;
}

static int run_noreset_single(unsigned int *avg_hw_cycles, uint64_t *avg_e2e_cycles)
{
  uint64_t total_hw_cycles = 0;
  uint64_t total_e2e_cycles = 0;
  unsigned int case_idx;
  int8_t sample[RADAR_MLP_INPUT_DIM];
  int32_t golden_logits[2];

  if (dma_stream_prepare_noreset() != 0) {
    return -1;
  }

  for (case_idx = 0; case_idx < RADAR_QMLP_MULTI_CASES; ++case_idx) {
    radar_qmlp_prepare_case(case_idx, sample);
    radar_qmlp_software_infer(sample, golden_logits);
    prepare_qmlp_input_at(0u, sample);
    clear_qmlp_output_words(2u);
    riscv_fence_rw_rw();

    if (qmlp_wait_idle() != 0) {
      qmlp_enable(0);
      return -1;
    }
    qmlp_clear_counters();
    qmlp_enable(1);

    {
      uint64_t start_cycles = radar_read_cycle64();
      if (dma_run_stream_once_noreset(TX_BUFFER_ADDR, RADAR_QMLP_TEST_INPUT_BYTES,
                                      RX_BUFFER_ADDR, RADAR_QMLP_TEST_OUTPUT_BYTES) != 0) {
        qmlp_enable(0);
        return -1;
      }
      total_e2e_cycles += radar_read_cycle64() - start_cycles;
    }

    if (compare_qmlp_output_at(0u, golden_logits) != 0) {
      qmlp_enable(0);
      return -1;
    }

    total_hw_cycles += qmlp_read32(QMLP_RUN_CYCLES);
    qmlp_enable(0);
    riscv_fence_rw_rw();
    if (qmlp_wait_idle() != 0) {
      return -1;
    }
  }

  *avg_hw_cycles = (unsigned int)(total_hw_cycles / RADAR_QMLP_MULTI_CASES);
  *avg_e2e_cycles = total_e2e_cycles / RADAR_QMLP_MULTI_CASES;
  return 0;
}

static int run_reset_batch(unsigned int *avg_hw_cycles, uint64_t *avg_e2e_cycles)
{
  int8_t sample[RADAR_MLP_INPUT_DIM];
  int32_t golden_logits[RADAR_QMLP_MULTI_CASES][2];
  unsigned int case_idx;
  uint32_t hw_cycles;
  uint64_t e2e_cycles;

  for (case_idx = 0; case_idx < RADAR_QMLP_MULTI_CASES; ++case_idx) {
    radar_qmlp_prepare_case(case_idx, sample);
    radar_qmlp_software_infer(sample, golden_logits[case_idx]);
    prepare_qmlp_input_at(case_idx, sample);
  }
  clear_qmlp_output_words(RADAR_QMLP_MULTI_CASES * 2u);
  riscv_fence_rw_rw();

  if (qmlp_wait_idle() != 0) {
    return -1;
  }
  qmlp_clear_counters();
  qmlp_enable(1);

  {
    uint64_t start_cycles = radar_read_cycle64();
    if (dma_run_stream_once(TX_BUFFER_ADDR, RADAR_QMLP_BATCH_INPUT_BYTES,
                            RX_BUFFER_ADDR, RADAR_QMLP_BATCH_OUTPUT_BYTES) != 0) {
      qmlp_enable(0);
      return -1;
    }
    e2e_cycles = radar_read_cycle64() - start_cycles;
  }

  dump_qmlp_batch_outputs(RADAR_QMLP_MULTI_CASES);

  for (case_idx = 0; case_idx < RADAR_QMLP_MULTI_CASES; ++case_idx) {
    if (compare_qmlp_output_at(case_idx, golden_logits[case_idx]) != 0) {
      qmlp_enable(0);
      return -1;
    }
  }

  hw_cycles = qmlp_read32(QMLP_RUN_CYCLES);
  qmlp_enable(0);
  *avg_hw_cycles = hw_cycles / RADAR_QMLP_MULTI_CASES;
  *avg_e2e_cycles = e2e_cycles / RADAR_QMLP_MULTI_CASES;
  return 0;
}

int main(void)
{
  unsigned int batch_hw_cycles = 0u;
  uint64_t batch_e2e_cycles = 0u;

  printf("AXI DMA qmlp e2e benchmark start\n");
  radar_describe_buffer_protocol();

  preproc_disable();
  qmlp_clear_counters();
  qmlp_enable(0);

  if (run_reset_batch(&batch_hw_cycles, &batch_e2e_cycles) != 0) {
    printf("AXI DMA qmlp e2e FAILED\n");
    return 1;
  }

  printf("[QMLP-E2E] reset_batch_per_sample hw_cycles_avg=%u e2e_cycles_avg=%lu latency_us_x100=%lu\n",
         batch_hw_cycles,
         (unsigned long)batch_e2e_cycles,
         (unsigned long)(batch_e2e_cycles * 100000000ull / 50000000ull));
  printf("AXI DMA qmlp e2e PASSED\n");
  return 0;
}
