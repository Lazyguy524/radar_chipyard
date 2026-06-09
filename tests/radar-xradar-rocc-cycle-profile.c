#include <stdint.h>
#include <stdio.h>

#include "radar_xradar_fallback.h"

#define XRADAR_ROCC_PROFILE_REPEATS 200u

typedef struct {
  uint64_t cycles;
  uint64_t instret;
  uint64_t count;
  uint64_t rqdot4_ops;
  uint64_t scalar_tail_macs;
  uint64_t rqscale8_ops;
} xradar_profile_totals_t;

static volatile int32_t xradar_profile_sink0;
static volatile int32_t xradar_profile_sink1;

static inline uint64_t xradar_read_cycle64(void)
{
  uint64_t value;
  asm volatile ("rdcycle %0" : "=r"(value));
  return value;
}

static inline uint64_t xradar_read_instret64(void)
{
  uint64_t value;
  asm volatile ("rdinstret %0" : "=r"(value));
  return value;
}

static inline int32_t xradar_rocc_rqdot4(uint32_t lhs, uint32_t rhs)
{
  long result;
  asm volatile (".insn r CUSTOM_0, 7, 0, %0, %1, %2"
                : "=r"(result)
                : "r"((unsigned long)lhs), "r"((unsigned long)rhs));
  return (int32_t)result;
}

static int32_t xradar_dot_i8_rocc_tail(const int8_t *lhs,
                                       const int8_t *rhs,
                                       unsigned int count,
                                       xradar_qmlp_op_counts_t *counts)
{
  int32_t acc = 0;
  unsigned int idx = 0;

  while ((idx + 4u) <= count) {
    uint32_t lhs_pack = xradar_pack_i8x4(lhs[idx + 0u], lhs[idx + 1u],
                                         lhs[idx + 2u], lhs[idx + 3u]);
    uint32_t rhs_pack = xradar_pack_i8x4(rhs[idx + 0u], rhs[idx + 1u],
                                         rhs[idx + 2u], rhs[idx + 3u]);
    acc += xradar_rocc_rqdot4(lhs_pack, rhs_pack);
    if (counts != 0) counts->rqdot4_ops++;
    idx += 4u;
  }

  while (idx < count) {
    acc += (int32_t)lhs[idx] * (int32_t)rhs[idx];
    if (counts != 0) counts->scalar_tail_macs++;
    idx++;
  }

  return acc;
}

static void xradar_qmlp_rocc_infer(const int8_t input[RADAR_MLP_INPUT_DIM],
                                   int32_t logits[2],
                                   xradar_qmlp_op_counts_t *counts)
{
  int out_idx;
  int8_t l1_out[RADAR_MLP_L1_OUT];
  int8_t l2_out[RADAR_MLP_L2_OUT];

  if (counts != 0) {
    counts->rqdot4_ops = 0;
    counts->scalar_tail_macs = 0;
    counts->rqscale8_ops = 0;
    counts->rqpack_ops = 0;
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L1_OUT; ++out_idx) {
    const int8_t *weights = &radar_mlp_l1_weight[out_idx * RADAR_MLP_L1_IN];
    int32_t acc = radar_mlp_l1_bias[out_idx] +
      xradar_dot_i8_rocc_tail(input, weights, RADAR_MLP_L1_IN, counts);
    l1_out[out_idx] = (int8_t)xradar_rqscale8_relu_sw(acc, XRADAR_QMLP_L1_MULTIPLIER);
    if (counts != 0) counts->rqscale8_ops++;
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L2_OUT; ++out_idx) {
    const int8_t *weights = &radar_mlp_l2_weight[out_idx * RADAR_MLP_L2_IN];
    int32_t acc = radar_mlp_l2_bias[out_idx] +
      xradar_dot_i8_rocc_tail(l1_out, weights, RADAR_MLP_L2_IN, counts);
    l2_out[out_idx] = (int8_t)xradar_rqscale8_relu_sw(acc, XRADAR_QMLP_L2_MULTIPLIER);
    if (counts != 0) counts->rqscale8_ops++;
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L3_OUT; ++out_idx) {
    const int8_t *weights = &radar_mlp_l3_weight[out_idx * RADAR_MLP_L3_IN];
    logits[out_idx] = radar_mlp_l3_bias[out_idx] +
      xradar_dot_i8_rocc_tail(l2_out, weights, RADAR_MLP_L3_IN, counts);
  }
}

static void add_scalar_profile(const int8_t input[RADAR_MLP_INPUT_DIM],
                               int32_t logits[2],
                               xradar_profile_totals_t *totals)
{
  uint64_t c0 = xradar_read_cycle64();
  uint64_t i0 = xradar_read_instret64();
  uint64_t i1;
  uint64_t c1;

  xradar_qmlp_scalar_infer(input, logits);

  i1 = xradar_read_instret64();
  c1 = xradar_read_cycle64();
  totals->cycles += c1 - c0;
  totals->instret += i1 - i0;
  totals->count++;
}

static void add_rocc_profile(const int8_t input[RADAR_MLP_INPUT_DIM],
                             int32_t logits[2],
                             xradar_profile_totals_t *totals)
{
  xradar_qmlp_op_counts_t counts;
  uint64_t c0 = xradar_read_cycle64();
  uint64_t i0 = xradar_read_instret64();
  uint64_t i1;
  uint64_t c1;

  xradar_qmlp_rocc_infer(input, logits, &counts);

  i1 = xradar_read_instret64();
  c1 = xradar_read_cycle64();
  totals->cycles += c1 - c0;
  totals->instret += i1 - i0;
  totals->count++;
  totals->rqdot4_ops += counts.rqdot4_ops;
  totals->scalar_tail_macs += counts.scalar_tail_macs;
  totals->rqscale8_ops += counts.rqscale8_ops;
}

static void print_totals(const char *name, const xradar_profile_totals_t *totals)
{
  printf("[XRADAR-PROFILE] %s count=%lu cycles_avg=%lu instret_avg=%lu sink={%d,%d}\n",
         name,
         (unsigned long)totals->count,
         (unsigned long)(totals->cycles / totals->count),
         (unsigned long)(totals->instret / totals->count),
         xradar_profile_sink0,
         xradar_profile_sink1);
}

int main(void)
{
  static int8_t samples[XRADAR_QMLP_MULTI_CASES][RADAR_MLP_INPUT_DIM];
  xradar_profile_totals_t scalar = {0, 0, 0, 0, 0, 0};
  xradar_profile_totals_t rocc = {0, 0, 0, 0, 0, 0};
  int32_t scalar_logits[2];
  int32_t rocc_logits[2];
  uint32_t repeat_idx;
  uint32_t case_idx;
  uint64_t scalar_avg;
  uint64_t rocc_avg;
  uint64_t speedup_x1000;

  printf("[XRADAR-PROFILE] scalar-vs-rocc start repeats=%u cases=%u\n",
         XRADAR_ROCC_PROFILE_REPEATS,
         XRADAR_QMLP_MULTI_CASES);

  for (case_idx = 0; case_idx < XRADAR_QMLP_MULTI_CASES; ++case_idx) {
    xradar_qmlp_prepare_case(case_idx, samples[case_idx]);
    xradar_qmlp_scalar_infer(samples[case_idx], scalar_logits);
    xradar_qmlp_rocc_infer(samples[case_idx], rocc_logits, 0);
    if (scalar_logits[0] != rocc_logits[0] || scalar_logits[1] != rocc_logits[1]) {
      printf("[XRADAR-PROFILE] mismatch case=%u scalar={%d,%d} rocc={%d,%d}\n",
             case_idx,
             scalar_logits[0],
             scalar_logits[1],
             rocc_logits[0],
             rocc_logits[1]);
      return 1;
    }
  }

  for (repeat_idx = 0; repeat_idx < XRADAR_ROCC_PROFILE_REPEATS; ++repeat_idx) {
    for (case_idx = 0; case_idx < XRADAR_QMLP_MULTI_CASES; ++case_idx) {
      add_scalar_profile(samples[case_idx], scalar_logits, &scalar);
      xradar_profile_sink0 = scalar_logits[0];
      xradar_profile_sink1 = scalar_logits[1];
    }
  }

  for (repeat_idx = 0; repeat_idx < XRADAR_ROCC_PROFILE_REPEATS; ++repeat_idx) {
    for (case_idx = 0; case_idx < XRADAR_QMLP_MULTI_CASES; ++case_idx) {
      add_rocc_profile(samples[case_idx], rocc_logits, &rocc);
      xradar_profile_sink0 = rocc_logits[0];
      xradar_profile_sink1 = rocc_logits[1];
    }
  }

  scalar_avg = scalar.cycles / scalar.count;
  rocc_avg = rocc.cycles / rocc.count;
  speedup_x1000 = rocc_avg == 0u ? 0u : (scalar_avg * 1000ull) / rocc_avg;

  print_totals("scalar", &scalar);
  print_totals("rocc", &rocc);
  printf("[XRADAR-PROFILE] rocc_ops rqdot4_avg=%lu scalar_tail_macs_avg=%lu rqscale8_avg=%lu packed_mac_coverage_x100=%lu\n",
         (unsigned long)(rocc.rqdot4_ops / rocc.count),
         (unsigned long)(rocc.scalar_tail_macs / rocc.count),
         (unsigned long)(rocc.rqscale8_ops / rocc.count),
         (unsigned long)(((rocc.rqdot4_ops * 4ull) * 10000ull) /
                         (rocc.rqdot4_ops * 4ull + rocc.scalar_tail_macs)));
  printf("[XRADAR-PROFILE] speedup_x1000=%lu scalar_avg=%lu rocc_avg=%lu\n",
         (unsigned long)speedup_x1000,
         (unsigned long)scalar_avg,
         (unsigned long)rocc_avg);
  printf("[XRADAR-PROFILE] PASSED\n");
  return 0;
}
