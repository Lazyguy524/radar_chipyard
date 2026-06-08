#include "radar_axi_dma_common.h"
#include "radar_qmlp_test_common.h"
#include "radar_qmlp_validation_data.h"

#define PROFILE_CLOCK_HZ 50000000ull
#define PROFILE_BATCH_CASES 4u
#define PROFILE_RX_REGION RADAR_BUF_REGION_MID0
#define PROFILE_RX_DMA_ADDR RADAR_BUF_MID0_BASE

static const unsigned int profile_batch_sizes[PROFILE_BATCH_CASES] = {
  1u, 8u, 64u, 511u
};

typedef struct {
  uint64_t mmio_reads;
  uint64_t mmio_writes;
  uint64_t qmlp_idle_poll_iters;
  uint64_t dma_ready_checks;
  uint64_t dma_running_poll_iters;
  uint64_t dma_done_poll_iters;
  uint64_t dma_setup_cycles;
  uint64_t dma_poll_cycles;
  uint64_t qmlp_control_cycles;
  uint64_t prepare_cycles;
  uint64_t verify_cycles;
  uint64_t hw_cycles;
  uint64_t samples;
} mmio_profile_totals_t;

typedef struct {
  uint64_t mmio_reads;
  uint64_t mmio_writes;
  uint64_t qmlp_idle_poll_iters;
  uint64_t dma_ready_checks;
  uint64_t dma_running_poll_iters;
  uint64_t dma_done_poll_iters;
  uint64_t dma_setup_cycles;
  uint64_t dma_poll_cycles;
  uint64_t qmlp_control_cycles;
} mmio_profile_run_t;

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

static inline void prof_write32(mmio_profile_run_t *run, uintptr_t reg_off, uint32_t value)
{
  run->mmio_writes++;
  mmio_write32(DMA_BASE_ADDR + reg_off, value);
}

static inline uint32_t prof_read32(mmio_profile_run_t *run, uintptr_t reg_off)
{
  run->mmio_reads++;
  return mmio_read32(DMA_BASE_ADDR + reg_off);
}

static void profile_accum(mmio_profile_totals_t *totals, const mmio_profile_run_t *run)
{
  totals->mmio_reads += run->mmio_reads;
  totals->mmio_writes += run->mmio_writes;
  totals->qmlp_idle_poll_iters += run->qmlp_idle_poll_iters;
  totals->dma_ready_checks += run->dma_ready_checks;
  totals->dma_running_poll_iters += run->dma_running_poll_iters;
  totals->dma_done_poll_iters += run->dma_done_poll_iters;
  totals->dma_setup_cycles += run->dma_setup_cycles;
  totals->dma_poll_cycles += run->dma_poll_cycles;
  totals->qmlp_control_cycles += run->qmlp_control_cycles;
}

static uint64_t subtract_saturating_u64(uint64_t value, uint64_t subtract)
{
  return value > subtract ? value - subtract : 0u;
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

static int prof_qmlp_wait_idle(mmio_profile_run_t *run)
{
  unsigned long timeout = DMA_TIMEOUT_CYCLES;

  while (timeout-- > 0UL) {
    uint32_t status;
    run->qmlp_idle_poll_iters++;
    status = prof_read32(run, QMLP_STATUS);
    if ((status & 0x1fu) == 0u) {
      return 0;
    }
  }

  printf("[QMLP-MMIO-PROFILE] QMLP idle timeout STATUS=0x%08x\n",
         prof_read32(run, QMLP_STATUS));
  return -1;
}

static void prof_qmlp_clear_enable(mmio_profile_run_t *run)
{
  uint64_t t0 = radar_read_cycle64();
  prof_write32(run, QMLP_CTRL, QMLP_CTRL_CLR_COUNTS);
  prof_write32(run, QMLP_CTRL, 0u);
  prof_write32(run, QMLP_CTRL, QMLP_CTRL_ENABLE);
  run->qmlp_control_cycles += radar_read_cycle64() - t0;
}

static void prof_qmlp_disable(mmio_profile_run_t *run)
{
  uint64_t t0 = radar_read_cycle64();
  prof_write32(run, QMLP_CTRL, 0u);
  run->qmlp_control_cycles += radar_read_cycle64() - t0;
}

static int prof_dma_ready_for_reuse(mmio_profile_run_t *run,
                                    const char *name,
                                    uintptr_t sr_off)
{
  uint32_t status;

  run->dma_ready_checks++;
  status = prof_read32(run, sr_off);
  if ((status & DMASR_ERR_MASK) != 0u) {
    printf("[QMLP-MMIO-PROFILE] %s reuse error DMASR=0x%08x\n", name, status);
    return -1;
  }
  if ((status & DMASR_HALTED) != 0u) {
    printf("[QMLP-MMIO-PROFILE] %s reuse halted DMASR=0x%08x\n", name, status);
    return -1;
  }
  return 0;
}

static int prof_dma_wait_running(mmio_profile_run_t *run,
                                 const char *name,
                                 uintptr_t sr_off)
{
  unsigned long timeout = DMA_TIMEOUT_CYCLES;

  while (timeout-- > 0UL) {
    uint32_t status;
    run->dma_running_poll_iters++;
    status = prof_read32(run, sr_off);
    if ((status & DMASR_HALTED) == 0u) {
      return 0;
    }
  }

  printf("[QMLP-MMIO-PROFILE] %s failed to leave HALTED DMASR=0x%08x\n",
         name, prof_read32(run, sr_off));
  return -1;
}

static int prof_dma_wait_done(mmio_profile_run_t *run,
                              const char *name,
                              uintptr_t sr_off)
{
  unsigned long timeout = DMA_TIMEOUT_CYCLES;

  while (timeout-- > 0UL) {
    uint32_t status;
    run->dma_done_poll_iters++;
    status = prof_read32(run, sr_off);
    if ((status & DMASR_ERR_MASK) != 0u) {
      printf("[QMLP-MMIO-PROFILE] %s error DMASR=0x%08x\n", name, status);
      return -1;
    }
    if ((status & DMASR_IRQ_MASK) != 0u) {
      prof_write32(run, sr_off, DMASR_IRQ_MASK);
      return 0;
    }
    if ((status & DMASR_IDLE) != 0u && (status & DMASR_HALTED) == 0u) {
      return 0;
    }
  }

  printf("[QMLP-MMIO-PROFILE] %s timeout DMASR=0x%08x\n",
         name, prof_read32(run, sr_off));
  return -1;
}

static int prof_dma_stream_prepare_noreset(mmio_profile_run_t *run)
{
  if (dma_stream_prepare_noreset() != 0) {
    return -1;
  }

  /* The one-time reset/init path is intentionally not counted in per-run totals. */
  run->mmio_reads = 0;
  run->mmio_writes = 0;
  run->qmlp_idle_poll_iters = 0;
  run->dma_ready_checks = 0;
  run->dma_running_poll_iters = 0;
  run->dma_done_poll_iters = 0;
  run->dma_setup_cycles = 0;
  run->dma_poll_cycles = 0;
  run->qmlp_control_cycles = 0;
  return 0;
}

static int prof_dma_run_stream_once_noreset(mmio_profile_run_t *run,
                                            uintptr_t src_addr,
                                            uint32_t mm2s_length,
                                            uintptr_t dst_addr,
                                            uint32_t s2mm_length)
{
  uint64_t setup_start;
  uint64_t poll_start;

  setup_start = radar_read_cycle64();
  if (prof_dma_ready_for_reuse(run, "MM2S", MM2S_DMASR) != 0) return -1;
  if (prof_dma_ready_for_reuse(run, "S2MM", S2MM_DMASR) != 0) return -1;

  prof_write32(run, MM2S_DMASR, DMASR_CLEAR_MASK);
  prof_write32(run, S2MM_DMASR, DMASR_CLEAR_MASK);
  prof_write32(run, MM2S_DMACR, DMACR_RUN_MASK);
  prof_write32(run, S2MM_DMACR, DMACR_RUN_MASK);

  if (prof_dma_wait_running(run, "MM2S", MM2S_DMASR) != 0) return -1;
  if (prof_dma_wait_running(run, "S2MM", S2MM_DMASR) != 0) return -1;

  prof_write32(run, S2MM_DA, (uint32_t)dst_addr);
  prof_write32(run, S2MM_DA_MSB, 0u);
  prof_write32(run, S2MM_LENGTH, s2mm_length);
  prof_write32(run, MM2S_SA, (uint32_t)src_addr);
  prof_write32(run, MM2S_SA_MSB, 0u);
  prof_write32(run, MM2S_LENGTH, mm2s_length);
  run->dma_setup_cycles += radar_read_cycle64() - setup_start;

  poll_start = radar_read_cycle64();
  if (prof_dma_wait_done(run, "MM2S", MM2S_DMASR) != 0) return -1;
  if (prof_dma_wait_done(run, "S2MM", S2MM_DMASR) != 0) return -1;
  run->dma_poll_cycles += radar_read_cycle64() - poll_start;
  return 0;
}

static int check_qmlp_batch_counters(mmio_profile_run_t *run, unsigned int sample_count)
{
  uint32_t in_beats = prof_read32(run, QMLP_IN_BEATS);
  uint32_t out_beats = prof_read32(run, QMLP_OUT_BEATS);
  uint32_t frames = prof_read32(run, QMLP_FRAME_COUNT);
  uint32_t keep = prof_read32(run, QMLP_LAST_KEEP);
  uint32_t sample_bytes = prof_read32(run, QMLP_SAMPLE_BYTES);
  uint32_t output_bytes = prof_read32(run, QMLP_OUTPUT_BYTES);

  if (in_beats != (sample_count * 4u) || out_beats != sample_count || frames != 1u ||
      keep != 0xffu || sample_bytes != RADAR_QMLP_TEST_INPUT_BYTES ||
      output_bytes != RADAR_QMLP_TEST_OUTPUT_BYTES) {
    printf("[QMLP-MMIO-PROFILE] counter mismatch samples=%u in=%u out=%u frames=%u keep=0x%08x sample=%u output=%u\n",
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
    printf("[QMLP-MMIO-PROFILE] mismatch sample=%u hw={%d,%d} golden={%d,%d}\n",
           global_idx,
           rx[base + 0u], rx[base + 1u],
           golden_logits[0], golden_logits[1]);
    return -1;
  }
  return 0;
}

static void print_profile_result(unsigned int batch_size, const mmio_profile_totals_t *totals)
{
  uint64_t samples = totals->samples == 0u ? 1u : totals->samples;
  uint64_t control_poll_cycles = totals->qmlp_control_cycles + totals->dma_setup_cycles + totals->dma_poll_cycles;

  printf("[QMLP-MMIO-PROFILE] batch=%u samples=%lu prep_avg=%lu qctrl_avg=%lu dma_setup_avg=%lu dma_poll_avg=%lu verify_avg=%lu hw_avg=%lu ctrl_poll_avg=%lu ctrl_poll_us_x100=%lu\n",
         batch_size,
         (unsigned long)totals->samples,
         (unsigned long)(totals->prepare_cycles / samples),
         (unsigned long)(totals->qmlp_control_cycles / samples),
         (unsigned long)(totals->dma_setup_cycles / samples),
         (unsigned long)(totals->dma_poll_cycles / samples),
         (unsigned long)(totals->verify_cycles / samples),
         (unsigned long)(totals->hw_cycles / samples),
         (unsigned long)(control_poll_cycles / samples),
         (unsigned long)cycles_to_us_x100(control_poll_cycles / samples));
  printf("[QMLP-MMIO-PROFILE] batch=%u mmio_reads_per_sample=%lu mmio_writes_per_sample=%lu qmlp_idle_poll_per_sample=%lu dma_ready_checks_per_sample=%lu dma_running_poll_per_sample=%lu dma_done_poll_per_sample=%lu\n",
         batch_size,
         (unsigned long)(totals->mmio_reads / samples),
         (unsigned long)(totals->mmio_writes / samples),
         (unsigned long)(totals->qmlp_idle_poll_iters / samples),
         (unsigned long)(totals->dma_ready_checks / samples),
         (unsigned long)(totals->dma_running_poll_iters / samples),
         (unsigned long)(totals->dma_done_poll_iters / samples));
}

static int run_large_golden_profile(unsigned int batch_size)
{
  mmio_profile_totals_t totals = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  mmio_profile_run_t init_run = {0, 0, 0, 0, 0, 0, 0, 0, 0};
  unsigned int batch_start;

  if (prof_dma_stream_prepare_noreset(&init_run) != 0) {
    return -1;
  }

  for (batch_start = 0; batch_start < RADAR_QMLP_LARGE_GOLDEN_ROWS; batch_start += batch_size) {
    unsigned int remaining = RADAR_QMLP_LARGE_GOLDEN_ROWS - batch_start;
    unsigned int run_samples = remaining < batch_size ? remaining : batch_size;
    unsigned int input_bytes = run_samples * RADAR_QMLP_TEST_INPUT_BYTES;
    unsigned int output_bytes = run_samples * RADAR_QMLP_TEST_OUTPUT_BYTES;
    unsigned int local_idx;
    mmio_profile_run_t run = {0, 0, 0, 0, 0, 0, 0, 0, 0};
    uint64_t t0;
    uint64_t t1;
    uint64_t t2;
    uint32_t hw_cycles;

    t0 = radar_read_cycle64();
    for (local_idx = 0; local_idx < run_samples; ++local_idx) {
      prepare_qmlp_input_at(local_idx, radar_qmlp_large_input_row(batch_start + local_idx));
    }
    clear_qmlp_output_words(run_samples * 2u);
    riscv_fence_rw_rw();
    t1 = radar_read_cycle64();

    if (prof_qmlp_wait_idle(&run) != 0) {
      prof_qmlp_disable(&run);
      return -1;
    }
    prof_qmlp_clear_enable(&run);

    if (prof_dma_run_stream_once_noreset(&run, TX_BUFFER_ADDR, input_bytes,
                                         PROFILE_RX_DMA_ADDR, output_bytes) != 0) {
      prof_qmlp_disable(&run);
      return -1;
    }

    if (check_qmlp_batch_counters(&run, run_samples) != 0) {
      prof_qmlp_disable(&run);
      return -1;
    }
    for (local_idx = 0; local_idx < run_samples; ++local_idx) {
      if (compare_qmlp_output_at(local_idx,
                                 batch_start + local_idx,
                                 radar_qmlp_large_logits_row(batch_start + local_idx)) != 0) {
        prof_qmlp_disable(&run);
        return -1;
      }
    }
    hw_cycles = prof_read32(&run, QMLP_RUN_CYCLES);
    prof_qmlp_disable(&run);
    if (prof_qmlp_wait_idle(&run) != 0) {
      return -1;
    }
    t2 = radar_read_cycle64();

    totals.prepare_cycles += t1 - t0;
    totals.verify_cycles += subtract_saturating_u64(t2 - t1,
      run.qmlp_control_cycles + run.dma_setup_cycles + run.dma_poll_cycles);
    totals.hw_cycles += hw_cycles;
    totals.samples += run_samples;
    profile_accum(&totals, &run);
  }

  print_profile_result(batch_size, &totals);
  return 0;
}

int main(void)
{
  unsigned int i;

  printf("AXI DMA qmlp MMIO/polling profile start\n");
  radar_describe_buffer_protocol();

  preproc_disable();
  qmlp_clear_counters();
  qmlp_enable(0);

  for (i = 0; i < PROFILE_BATCH_CASES; ++i) {
    if (run_large_golden_profile(profile_batch_sizes[i]) != 0) {
      printf("AXI DMA qmlp MMIO/polling profile FAILED\n");
      return 1;
    }
  }

  printf("AXI DMA qmlp MMIO/polling profile PASSED\n");
  return 0;
}
