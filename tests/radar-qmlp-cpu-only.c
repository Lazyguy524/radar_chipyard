#include <stdint.h>
#include <stdio.h>

#include "radar_qmlp_test_common.h"

#define RADAR_QMLP_CPU_ONLY_REPEATS 1000u

static volatile int32_t radar_qmlp_cpu_only_sink0;
static volatile int32_t radar_qmlp_cpu_only_sink1;

int main(void)
{
  int8_t sample[RADAR_MLP_INPUT_DIM];
  int32_t logits[2];
  uint64_t total_cycles = 0;
  uint32_t min_cycles = 0xffffffffu;
  uint32_t max_cycles = 0u;
  uint64_t start_cycles;
  uint64_t end_cycles;
  uint32_t repeat_idx;
  uint32_t case_idx;
  uint64_t total_infers = (uint64_t)RADAR_QMLP_CPU_ONLY_REPEATS * (uint64_t)RADAR_QMLP_MULTI_CASES;
  uint64_t avg_cycles;
  uint64_t avg_us_x100;

  printf("QMLP CPU-only pure forward test start\n");

  radar_qmlp_software_infer(radar_mlp_golden_input, logits);
  printf("[CPU-QMLP] golden self-check sw={%d, %d} pkg={%d, %d}\n",
         logits[0], logits[1],
         radar_mlp_golden_logits[0], radar_mlp_golden_logits[1]);
  if (logits[0] != radar_mlp_golden_logits[0] ||
      logits[1] != radar_mlp_golden_logits[1]) {
    printf("QMLP CPU-only FAILED\n");
    return 1;
  }

  for (case_idx = 0; case_idx < RADAR_QMLP_MULTI_CASES; ++case_idx) {
    radar_qmlp_prepare_case(case_idx, sample);
    radar_qmlp_software_infer(sample, logits);
    printf("[CPU-QMLP][case=%u][%s] logits={%d, %d}\n",
           case_idx,
           radar_qmlp_case_label(case_idx),
           logits[0],
           logits[1]);
  }

  for (case_idx = 0; case_idx < RADAR_QMLP_MULTI_CASES; ++case_idx) {
    radar_qmlp_prepare_case(case_idx, sample);
    radar_qmlp_software_infer(sample, logits);
    radar_qmlp_cpu_only_sink0 = logits[0];
    radar_qmlp_cpu_only_sink1 = logits[1];
  }

  for (repeat_idx = 0; repeat_idx < RADAR_QMLP_CPU_ONLY_REPEATS; ++repeat_idx) {
    for (case_idx = 0; case_idx < RADAR_QMLP_MULTI_CASES; ++case_idx) {
      uint32_t delta_cycles;

      radar_qmlp_prepare_case(case_idx, sample);
      start_cycles = radar_read_cycle64();
      radar_qmlp_software_infer(sample, logits);
      end_cycles = radar_read_cycle64();

      radar_qmlp_cpu_only_sink0 = logits[0];
      radar_qmlp_cpu_only_sink1 = logits[1];

      delta_cycles = (uint32_t)(end_cycles - start_cycles);
      total_cycles += delta_cycles;
      if (delta_cycles < min_cycles) min_cycles = delta_cycles;
      if (delta_cycles > max_cycles) max_cycles = delta_cycles;
    }
  }

  avg_cycles = total_cycles / total_infers;
  avg_us_x100 = (avg_cycles * 100000000ull) / 50000000ull;

  printf("[CPU-QMLP] summary repeats=%u cases=%u total_infers=%lu avg_cycles=%lu min_cycles=%u max_cycles=%u avg_latency_us_x100=%lu inf_per_sec=%lu sink={%d,%d}\n",
         RADAR_QMLP_CPU_ONLY_REPEATS,
         RADAR_QMLP_MULTI_CASES,
         (unsigned long)total_infers,
         (unsigned long)avg_cycles,
         min_cycles,
         max_cycles,
         (unsigned long)avg_us_x100,
         (unsigned long)(50000000ull / avg_cycles),
         radar_qmlp_cpu_only_sink0,
         radar_qmlp_cpu_only_sink1);

  printf("QMLP CPU-only PASSED\n");
  return 0;
}
