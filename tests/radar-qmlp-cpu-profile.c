#include <stdint.h>
#include <stdio.h>

#include "radar_qmlp_test_common.h"

#define RADAR_QMLP_CPU_PROFILE_REPEATS 200u

typedef struct {
  uint64_t infer_cycles;
  uint64_t prep_cycles;
  uint64_t dot_mac_cycles;
  uint64_t quant_cycles;
  uint64_t instret;
  uint64_t infer_count;
} radar_qmlp_cpu_profile_totals_t;

static volatile int32_t radar_qmlp_cpu_profile_sink0;
static volatile int32_t radar_qmlp_cpu_profile_sink1;

static inline uint64_t radar_read_instret64(void)
{
  uint64_t value;
  asm volatile ("rdinstret %0" : "=r"(value));
  return value;
}

static void radar_qmlp_profiled_infer(const int8_t input[RADAR_MLP_INPUT_DIM],
                                      int32_t logits[2],
                                      radar_qmlp_cpu_profile_totals_t *totals)
{
  int out_idx;
  int in_idx;
  int8_t l1_out[RADAR_MLP_L1_OUT];
  int8_t l2_out[RADAR_MLP_L2_OUT];

  for (out_idx = 0; out_idx < RADAR_MLP_L1_OUT; ++out_idx) {
    uint64_t t0;
    uint64_t t1;
    int32_t acc = radar_mlp_l1_bias[out_idx];

    t0 = radar_read_cycle64();
    for (in_idx = 0; in_idx < RADAR_MLP_L1_IN; ++in_idx) {
      acc += (int32_t)input[in_idx] *
             (int32_t)radar_mlp_l1_weight[out_idx * RADAR_MLP_L1_IN + in_idx];
    }
    t1 = radar_read_cycle64();
    totals->dot_mac_cycles += t1 - t0;

    t0 = radar_read_cycle64();
    l1_out[out_idx] = radar_qmlp_requant_relu_clamp(acc, RADAR_QMLP_L1_MULTIPLIER);
    t1 = radar_read_cycle64();
    totals->quant_cycles += t1 - t0;
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L2_OUT; ++out_idx) {
    uint64_t t0;
    uint64_t t1;
    int32_t acc = radar_mlp_l2_bias[out_idx];

    t0 = radar_read_cycle64();
    for (in_idx = 0; in_idx < RADAR_MLP_L2_IN; ++in_idx) {
      acc += (int32_t)l1_out[in_idx] *
             (int32_t)radar_mlp_l2_weight[out_idx * RADAR_MLP_L2_IN + in_idx];
    }
    t1 = radar_read_cycle64();
    totals->dot_mac_cycles += t1 - t0;

    t0 = radar_read_cycle64();
    l2_out[out_idx] = radar_qmlp_requant_relu_clamp(acc, RADAR_QMLP_L2_MULTIPLIER);
    t1 = radar_read_cycle64();
    totals->quant_cycles += t1 - t0;
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L3_OUT; ++out_idx) {
    uint64_t t0;
    uint64_t t1;
    int32_t acc = radar_mlp_l3_bias[out_idx];

    t0 = radar_read_cycle64();
    for (in_idx = 0; in_idx < RADAR_MLP_L3_IN; ++in_idx) {
      acc += (int32_t)l2_out[in_idx] *
             (int32_t)radar_mlp_l3_weight[out_idx * RADAR_MLP_L3_IN + in_idx];
    }
    t1 = radar_read_cycle64();
    totals->dot_mac_cycles += t1 - t0;
    logits[out_idx] = acc;
  }
}

static void print_share(const char *name, uint64_t part, uint64_t total)
{
  uint64_t pct_x100 = total == 0u ? 0u : (part * 10000ull) / total;
  printf("[CPU-QMLP-PROFILE] share %-16s cycles_avg=%lu pct_x100=%lu\n",
         name,
         (unsigned long)(part / (RADAR_QMLP_CPU_PROFILE_REPEATS * RADAR_QMLP_MULTI_CASES)),
         (unsigned long)pct_x100);
}

int main(void)
{
  radar_qmlp_cpu_profile_totals_t totals = {0, 0, 0, 0, 0, 0};
  int8_t sample[RADAR_MLP_INPUT_DIM];
  int32_t logits[2];
  uint32_t repeat_idx;
  uint32_t case_idx;
  uint64_t total_infers =
    (uint64_t)RADAR_QMLP_CPU_PROFILE_REPEATS * (uint64_t)RADAR_QMLP_MULTI_CASES;
  uint64_t residual_cycles;

  printf("QMLP CPU-only profiled forward test start\n");
  printf("[CPU-QMLP-PROFILE] dims input=%u l1=%u l2=%u l3=%u total_macs=%u repeats=%u cases=%u\n",
         (unsigned int)RADAR_MLP_INPUT_DIM,
         (unsigned int)RADAR_MLP_L1_OUT,
         (unsigned int)RADAR_MLP_L2_OUT,
         (unsigned int)RADAR_MLP_L3_OUT,
         (unsigned int)RADAR_QMLP_TOTAL_MACS,
         RADAR_QMLP_CPU_PROFILE_REPEATS,
         RADAR_QMLP_MULTI_CASES);

  radar_qmlp_software_infer(radar_mlp_golden_input, logits);
  if (logits[0] != radar_mlp_golden_logits[0] ||
      logits[1] != radar_mlp_golden_logits[1]) {
    printf("QMLP CPU-only profile FAILED\n");
    return 1;
  }

  for (repeat_idx = 0; repeat_idx < RADAR_QMLP_CPU_PROFILE_REPEATS; ++repeat_idx) {
    for (case_idx = 0; case_idx < RADAR_QMLP_MULTI_CASES; ++case_idx) {
      uint64_t t0;
      uint64_t t1;
      uint64_t i0;
      uint64_t i1;

      t0 = radar_read_cycle64();
      radar_qmlp_prepare_case(case_idx, sample);
      t1 = radar_read_cycle64();
      totals.prep_cycles += t1 - t0;

      i0 = radar_read_instret64();
      t0 = radar_read_cycle64();
      radar_qmlp_profiled_infer(sample, logits, &totals);
      t1 = radar_read_cycle64();
      i1 = radar_read_instret64();

      radar_qmlp_cpu_profile_sink0 = logits[0];
      radar_qmlp_cpu_profile_sink1 = logits[1];
      totals.infer_cycles += t1 - t0;
      totals.instret += i1 - i0;
      totals.infer_count++;
    }
  }

  residual_cycles = totals.infer_cycles -
    (totals.dot_mac_cycles + totals.quant_cycles);

  printf("[CPU-QMLP-PROFILE] summary infers=%lu infer_avg=%lu prep_avg=%lu instret_avg=%lu sink={%d,%d}\n",
         (unsigned long)totals.infer_count,
         (unsigned long)(totals.infer_cycles / total_infers),
         (unsigned long)(totals.prep_cycles / total_infers),
         (unsigned long)(totals.instret / total_infers),
         radar_qmlp_cpu_profile_sink0,
         radar_qmlp_cpu_profile_sink1);
  print_share("dot_mac_upper", totals.dot_mac_cycles, totals.infer_cycles);
  print_share("quant_relu", totals.quant_cycles, totals.infer_cycles);
  print_share("control_resid", residual_cycles, totals.infer_cycles);
  printf("[CPU-QMLP-PROFILE] note dot_mac_upper includes activation/weight loads and loop control; activation lookup is not a separate table in this QMLP path.\n");
  printf("QMLP CPU-only profiled forward PASSED\n");
  return 0;
}
