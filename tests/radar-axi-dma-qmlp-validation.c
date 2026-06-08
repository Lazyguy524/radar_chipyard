#include "radar_axi_dma_common.h"
#include "radar_qmlp_test_common.h"
#include "radar_qmlp_validation_data.h"

#ifndef RADAR_QMLP_CHAIN_MODE
#define RADAR_QMLP_CHAIN_MODE 0
#endif

#if RADAR_QMLP_CHAIN_MODE
#define RADAR_QMLP_VALIDATION_START_MSG "AXI DMA qmlp preproc-chain validation start"
#define RADAR_QMLP_VALIDATION_PASS_MSG  "AXI DMA qmlp preproc-chain validation PASSED"
#define RADAR_QMLP_VALIDATION_FAIL_MSG  "AXI DMA qmlp preproc-chain validation FAILED"
#else
#define RADAR_QMLP_VALIDATION_START_MSG "AXI DMA qmlp validation start"
#define RADAR_QMLP_VALIDATION_PASS_MSG  "AXI DMA qmlp validation PASSED"
#define RADAR_QMLP_VALIDATION_FAIL_MSG  "AXI DMA qmlp validation FAILED"
#endif

#define RADAR_QMLP_MAX_BATCH  RADAR_QMLP_VALIDATION_BATCH_SAMPLES

static inline void qmlp_validation_configure_frontend(void)
{
#if RADAR_QMLP_CHAIN_MODE
  preproc_configure(PREPROC_MODE_BYPASS, 0u, 0u, 1);
#else
  preproc_disable();
#endif
}

static inline void qmlp_validation_enable(int enable)
{
#if RADAR_QMLP_CHAIN_MODE
  qmlp_enable_preproc_chain(enable);
#else
  qmlp_enable(enable);
#endif
}

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

static int check_qmlp_batch_counters(unsigned int sample_count)
{
  uint32_t in_beats = qmlp_read32(QMLP_IN_BEATS);
  uint32_t out_beats = qmlp_read32(QMLP_OUT_BEATS);
  uint32_t frames = qmlp_read32(QMLP_FRAME_COUNT);
  uint32_t keep = qmlp_read32(QMLP_LAST_KEEP);
  uint32_t sample_bytes = qmlp_read32(QMLP_SAMPLE_BYTES);
  uint32_t output_bytes = qmlp_read32(QMLP_OUTPUT_BYTES);

  if (in_beats != (sample_count * 4u) || out_beats != sample_count || frames != 1u ||
      keep != 0xffu || sample_bytes != RADAR_QMLP_TEST_INPUT_BYTES ||
      output_bytes != RADAR_QMLP_TEST_OUTPUT_BYTES) {
    printf("[QMLP-VAL] counter mismatch samples=%u in=%u out=%u frames=%u keep=0x%08x sample=%u output=%u\n",
           sample_count, in_beats, out_beats, frames, keep, sample_bytes, output_bytes);
    return -1;
  }
  return 0;
}

static int compare_qmlp_output_at(unsigned int local_idx,
                                  unsigned int global_idx,
                                  const int32_t golden_logits[2])
{
  volatile int32_t *rx = rx_buffer_i32_uncached();
  unsigned int base = local_idx * 2u;

  if (rx[base + 0u] != golden_logits[0] || rx[base + 1u] != golden_logits[1]) {
    printf("[QMLP-VAL] mismatch sample=%u hw={%d,%d} golden={%d,%d}\n",
           global_idx,
           rx[base + 0u], rx[base + 1u],
           golden_logits[0], golden_logits[1]);
    return -1;
  }
  return 0;
}

static int run_dataset_batches(const char *tag,
                               unsigned int sample_rows,
                               const int8_t *(*input_row)(unsigned int),
                               const int32_t *(*logits_row)(unsigned int),
                               unsigned int batch_size,
                               unsigned int *avg_hw_cycles,
                               uint64_t *avg_e2e_cycles)
{
  uint64_t total_hw_cycles = 0;
  uint64_t total_e2e_cycles = 0;
  unsigned int batch_start;

  for (batch_start = 0; batch_start < sample_rows; batch_start += batch_size) {
    unsigned int remaining = sample_rows - batch_start;
    unsigned int run_samples = remaining < batch_size ? remaining : batch_size;
    unsigned int input_bytes = run_samples * RADAR_QMLP_TEST_INPUT_BYTES;
    unsigned int output_bytes = run_samples * RADAR_QMLP_TEST_OUTPUT_BYTES;
    unsigned int local_idx;
    uint64_t start_cycles;
    uint64_t end_cycles;
    uint32_t hw_cycles;

    for (local_idx = 0; local_idx < run_samples; ++local_idx) {
      prepare_qmlp_input_at(local_idx, input_row(batch_start + local_idx));
    }
    clear_qmlp_output_words(run_samples * 2u);
    riscv_fence_rw_rw();

    if (qmlp_wait_idle() != 0) {
      qmlp_validation_enable(0);
      return -1;
    }
    qmlp_clear_counters();
    qmlp_validation_enable(1);

    start_cycles = radar_read_cycle64();
    if (dma_run_stream_once(TX_BUFFER_ADDR, input_bytes,
                            RX_BUFFER_ADDR, output_bytes) != 0) {
      qmlp_validation_enable(0);
      return -1;
    }
    end_cycles = radar_read_cycle64();

    if (check_qmlp_batch_counters(run_samples) != 0) {
      qmlp_validation_enable(0);
      return -1;
    }

    for (local_idx = 0; local_idx < run_samples; ++local_idx) {
      if (compare_qmlp_output_at(local_idx,
                                 batch_start + local_idx,
                                 logits_row(batch_start + local_idx)) != 0) {
        qmlp_validation_enable(0);
        return -1;
      }
    }

    hw_cycles = qmlp_read32(QMLP_RUN_CYCLES);
    total_hw_cycles += hw_cycles;
    total_e2e_cycles += (end_cycles - start_cycles);
    qmlp_validation_enable(0);

    if (((batch_start + run_samples) % 128u) == 0u || (batch_start + run_samples) == sample_rows) {
      printf("[QMLP-VAL][%s] progress %u/%u hw_cycles_total=%lu e2e_cycles_total=%lu\n",
             tag,
             batch_start + run_samples,
             sample_rows,
             (unsigned long)total_hw_cycles,
             (unsigned long)total_e2e_cycles);
    }
  }

  *avg_hw_cycles = (unsigned int)(total_hw_cycles / sample_rows);
  *avg_e2e_cycles = total_e2e_cycles / sample_rows;
  return 0;
}

int main(void)
{
  unsigned int large_hw_cycles = 0u;
  uint64_t large_e2e_cycles = 0u;
  unsigned int boundary_hw_cycles = 0u;
  uint64_t boundary_e2e_cycles = 0u;

  printf("%s\n", RADAR_QMLP_VALIDATION_START_MSG);
  radar_describe_buffer_protocol();

  qmlp_validation_configure_frontend();
  qmlp_clear_counters();
  qmlp_validation_enable(0);

  if (run_dataset_batches("large_golden",
                          RADAR_QMLP_LARGE_GOLDEN_ROWS,
                          radar_qmlp_large_input_row,
                          radar_qmlp_large_logits_row,
                          RADAR_QMLP_VALIDATION_BATCH_SAMPLES,
                          &large_hw_cycles,
                          &large_e2e_cycles) != 0) {
    printf("%s\n", RADAR_QMLP_VALIDATION_FAIL_MSG);
    return 1;
  }

  if (run_dataset_batches("boundary_cases",
                          RADAR_QMLP_BOUNDARY_ROWS,
                          radar_qmlp_boundary_input_row,
                          radar_qmlp_boundary_logits_row,
                          1u,
                          &boundary_hw_cycles,
                          &boundary_e2e_cycles) != 0) {
    printf("%s\n", RADAR_QMLP_VALIDATION_FAIL_MSG);
    return 1;
  }

  printf("[QMLP-VAL] large_golden samples=%u hw_cycles_avg=%u e2e_cycles_avg=%lu\n",
         RADAR_QMLP_LARGE_GOLDEN_ROWS,
         large_hw_cycles,
         (unsigned long)large_e2e_cycles);
  printf("[QMLP-VAL] boundary_cases samples=%u hw_cycles_avg=%u e2e_cycles_avg=%lu\n",
         RADAR_QMLP_BOUNDARY_ROWS,
         boundary_hw_cycles,
         (unsigned long)boundary_e2e_cycles);
  printf("%s\n", RADAR_QMLP_VALIDATION_PASS_MSG);
  return 0;
}
