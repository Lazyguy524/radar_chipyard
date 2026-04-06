#include "radar_axi_dma_common.h"
#include "radar_qmlp_test_common.h"

static inline volatile int8_t *tx_buffer_u8_uncached(void)
{
  return (volatile int8_t *)radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
}

static inline volatile int32_t *rx_buffer_i32_uncached(void)
{
  return (volatile int32_t *)radar_buffer_cpu_addr(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_RX_OFFSET);
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

int main(void)
{
  uint64_t total_hw_cycles = 0;
  uint64_t total_e2e_cycles = 0;
  uint32_t min_hw_cycles = 0xffffffffu;
  uint32_t max_hw_cycles = 0u;
  uint64_t start_cycles;
  uint64_t end_cycles;
  int8_t sample[RADAR_MLP_INPUT_DIM];
  int32_t golden_logits[2];
  unsigned int case_idx;

  printf("AXI DMA qmlp test start\n");
  radar_describe_buffer_protocol();

  preproc_disable();
  qmlp_clear_counters();
  qmlp_enable(0);
  qmlp_dump_status("[BOOT]");

  radar_qmlp_software_infer(radar_mlp_golden_input, golden_logits);
  printf("[QMLP] golden self-check sw={%d, %d} pkg={%d, %d}\n",
         golden_logits[0], golden_logits[1],
         radar_mlp_golden_logits[0], radar_mlp_golden_logits[1]);
  if (golden_logits[0] != radar_mlp_golden_logits[0] ||
      golden_logits[1] != radar_mlp_golden_logits[1]) {
    printf("AXI DMA qmlp FAILED\n");
    return 1;
  }

  for (case_idx = 0; case_idx < RADAR_QMLP_MULTI_CASES; ++case_idx) {
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
      printf("AXI DMA qmlp FAILED\n");
      return 1;
    }
    end_cycles = radar_read_cycle64();

    riscv_fence_rw_rw();
    qmlp_dump_status("[QMLP] done");

    if (check_qmlp_counters() != 0) {
      qmlp_enable(0);
      printf("AXI DMA qmlp FAILED\n");
      return 1;
    }

    if (compare_qmlp_output(golden_logits) != 0) {
      qmlp_enable(0);
      printf("AXI DMA qmlp FAILED\n");
      return 1;
    }

    {
      uint32_t hw_cycles = qmlp_read32(QMLP_RUN_CYCLES);
      uint64_t e2e_cycles = end_cycles - start_cycles;
      total_hw_cycles += hw_cycles;
      total_e2e_cycles += e2e_cycles;
      if (hw_cycles < min_hw_cycles) min_hw_cycles = hw_cycles;
      if (hw_cycles > max_hw_cycles) max_hw_cycles = hw_cycles;
      printf("[QMLP][case=%u][%s] perf hw_cycles=%u e2e_cycles=%lu mac_per_cycle_x1000=%lu\n",
             case_idx,
             radar_qmlp_case_label(case_idx),
             hw_cycles,
             (unsigned long)e2e_cycles,
             (unsigned long)((uint64_t)RADAR_QMLP_TOTAL_MACS * 1000ull / (uint64_t)hw_cycles));
    }
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
  printf("AXI DMA qmlp PASSED\n");
  return 0;
}
