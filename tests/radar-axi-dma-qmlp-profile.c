#include "radar_axi_dma_common.h"
#include "radar_qmlp_test_common.h"
#include "radar_qmlp_validation_data.h"

#define PROFILE_CLOCK_HZ 50000000ull
#define PROFILE_BATCH_CASES 6u
#define PROFILE_RX_REGION RADAR_BUF_REGION_MID0
#define PROFILE_RX_DMA_ADDR RADAR_BUF_MID0_BASE

static const unsigned int profile_batch_sizes[PROFILE_BATCH_CASES] = {
  1u, 8u, 32u, 64u, 256u, 511u
};

typedef struct {
  uint64_t prepare_cycles;
  uint64_t control_cycles;
  uint64_t dma_cycles;
  uint64_t verify_cycles;
  uint64_t hw_cycles;
  uint64_t samples;
} profile_totals_t;

static inline volatile int8_t *tx_buffer_u8_uncached(void)
{
  return (volatile int8_t *)radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
}

static inline volatile int32_t *rx_buffer_i32_uncached(void)
{
  return (volatile int32_t *)radar_buffer_cpu_addr(PROFILE_RX_REGION, RADAR_BUF_VIEW_UNCACHED, 0);
}

static inline uint64_t cycles_to_us_x100(uint64_t cycles)
{
  return (cycles * 100000000ull) / PROFILE_CLOCK_HZ;
}

static void prepare_qmlp_input_at(unsigned int sample_idx, const int8_t sample[RADAR_MLP_INPUT_DIM])
{
  volatile int8_t *tx = tx_buffer_u8_uncached();
  unsigned int base = sample_idx * RADAR_QMLP_TEST_INPUT_BYTES;
  unsigned int i;

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
    printf("[QMLP-PROFILE] counter mismatch samples=%u in=%u out=%u frames=%u keep=0x%08x sample=%u output=%u\n",
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
    printf("[QMLP-PROFILE] mismatch sample=%u hw={%d,%d} golden={%d,%d}\n",
           global_idx,
           rx[base + 0u], rx[base + 1u],
           golden_logits[0], golden_logits[1]);
    return -1;
  }
  return 0;
}

static void print_profile_result(unsigned int batch_size, const profile_totals_t *totals)
{
  uint64_t samples = totals->samples == 0u ? 1u : totals->samples;
  uint64_t prepare_avg = totals->prepare_cycles / samples;
  uint64_t control_avg = totals->control_cycles / samples;
  uint64_t dma_avg = totals->dma_cycles / samples;
  uint64_t verify_avg = totals->verify_cycles / samples;
  uint64_t hw_avg = totals->hw_cycles / samples;

  printf("[QMLP-PROFILE] batch=%u samples=%lu prep_avg=%lu ctrl_avg=%lu dma_avg=%lu verify_avg=%lu hw_avg=%lu dma_us_x100=%lu hw_us_x100=%lu\n",
         batch_size,
         (unsigned long)totals->samples,
         (unsigned long)prepare_avg,
         (unsigned long)control_avg,
         (unsigned long)dma_avg,
         (unsigned long)verify_avg,
         (unsigned long)hw_avg,
         (unsigned long)cycles_to_us_x100(dma_avg),
         (unsigned long)cycles_to_us_x100(hw_avg));
}

static int run_large_golden_profile(unsigned int batch_size)
{
  profile_totals_t totals = {0, 0, 0, 0, 0, 0};
  unsigned int batch_start;

  uint64_t init_start = radar_read_cycle64();
  if (dma_stream_prepare_noreset() != 0) {
    return -1;
  }
  printf("[QMLP-PROFILE] batch=%u dma_init_cycles=%lu\n",
         batch_size,
         (unsigned long)(radar_read_cycle64() - init_start));

  for (batch_start = 0; batch_start < RADAR_QMLP_LARGE_GOLDEN_ROWS; batch_start += batch_size) {
    unsigned int remaining = RADAR_QMLP_LARGE_GOLDEN_ROWS - batch_start;
    unsigned int run_samples = remaining < batch_size ? remaining : batch_size;
    unsigned int input_bytes = run_samples * RADAR_QMLP_TEST_INPUT_BYTES;
    unsigned int output_bytes = run_samples * RADAR_QMLP_TEST_OUTPUT_BYTES;
    unsigned int local_idx;
    uint64_t t0;
    uint64_t t1;
    uint64_t t2;
    uint64_t t3;
    uint64_t t4;
    uint32_t hw_cycles;

    t0 = radar_read_cycle64();
    for (local_idx = 0; local_idx < run_samples; ++local_idx) {
      prepare_qmlp_input_at(local_idx, radar_qmlp_large_input_row(batch_start + local_idx));
    }
    clear_qmlp_output_words(run_samples * 2u);
    riscv_fence_rw_rw();
    t1 = radar_read_cycle64();

    if (qmlp_wait_idle() != 0) {
      qmlp_enable(0);
      return -1;
    }
    qmlp_clear_counters();
    qmlp_enable(1);
    t2 = radar_read_cycle64();

    if (dma_run_stream_once_noreset(TX_BUFFER_ADDR, input_bytes,
                                    PROFILE_RX_DMA_ADDR, output_bytes) != 0) {
      qmlp_enable(0);
      return -1;
    }
    t3 = radar_read_cycle64();

    if (check_qmlp_batch_counters(run_samples) != 0) {
      qmlp_enable(0);
      return -1;
    }
    for (local_idx = 0; local_idx < run_samples; ++local_idx) {
      if (compare_qmlp_output_at(local_idx,
                                 batch_start + local_idx,
                                 radar_qmlp_large_logits_row(batch_start + local_idx)) != 0) {
        qmlp_enable(0);
        return -1;
      }
    }
    hw_cycles = qmlp_read32(QMLP_RUN_CYCLES);
    qmlp_enable(0);
    if (qmlp_wait_idle() != 0) {
      return -1;
    }
    t4 = radar_read_cycle64();

    totals.prepare_cycles += t1 - t0;
    totals.control_cycles += t2 - t1;
    totals.dma_cycles += t3 - t2;
    totals.verify_cycles += t4 - t3;
    totals.hw_cycles += hw_cycles;
    totals.samples += run_samples;
  }

  print_profile_result(batch_size, &totals);
  return 0;
}

int main(void)
{
  unsigned int i;

  printf("AXI DMA qmlp profile start\n");
  radar_describe_buffer_protocol();

  preproc_disable();
  qmlp_clear_counters();
  qmlp_enable(0);

  for (i = 0; i < PROFILE_BATCH_CASES; ++i) {
    if (run_large_golden_profile(profile_batch_sizes[i]) != 0) {
      printf("AXI DMA qmlp profile FAILED\n");
      return 1;
    }
  }

  printf("AXI DMA qmlp profile PASSED\n");
  return 0;
}
