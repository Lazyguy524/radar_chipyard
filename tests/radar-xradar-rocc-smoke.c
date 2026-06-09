#include <stdint.h>
#include <stdio.h>

#include "radar_xradar_fallback.h"

static inline int32_t xradar_rocc_rqdot4(uint32_t lhs, uint32_t rhs)
{
  long result;
  /* RoCC custom funct3 encodes xd/xs1/xs2; rqdot4 reads both sources and writes rd. */
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

static int check_basic_ops(void)
{
  static const int8_t lanes[][8] = {
    {1, -2, 3, -4, -5, 6, -7, 8},
    {127, -128, 1, -1, 1, 1, -128, 127},
    {0, 0, 0, 0, 99, -99, 7, -7},
    {-12, 34, -56, 78, -9, -8, 7, 6},
  };
  unsigned int i;

  for (i = 0; i < sizeof(lanes) / sizeof(lanes[0]); ++i) {
    uint32_t lhs = xradar_pack_i8x4(lanes[i][0], lanes[i][1], lanes[i][2], lanes[i][3]);
    uint32_t rhs = xradar_pack_i8x4(lanes[i][4], lanes[i][5], lanes[i][6], lanes[i][7]);
    int32_t got = xradar_rocc_rqdot4(lhs, rhs);
    int32_t expected = xradar_rqdot4_sw(lhs, rhs);

    if (got != expected) {
      printf("[XRADAR-ROCC] rqdot4 basic mismatch case=%u got=%d expected=%d\n",
             i, got, expected);
      return -1;
    }
  }

  return 0;
}

int main(void)
{
  int8_t sample[RADAR_MLP_INPUT_DIM];
  int32_t scalar_logits[2];
  int32_t rocc_logits[2];
  xradar_qmlp_op_counts_t counts;
  unsigned int case_idx;

  printf("[XRADAR-ROCC] rqdot4 smoke start\n");

  if (check_basic_ops() != 0) {
    return 1;
  }

  for (case_idx = 0; case_idx < XRADAR_QMLP_MULTI_CASES; ++case_idx) {
    xradar_qmlp_prepare_case(case_idx, sample);
    xradar_qmlp_scalar_infer(sample, scalar_logits);
    xradar_qmlp_rocc_infer(sample, rocc_logits, &counts);
    if (rocc_logits[0] != scalar_logits[0] ||
        rocc_logits[1] != scalar_logits[1]) {
      printf("[XRADAR-ROCC] case=%u %s mismatch scalar={%d,%d} rocc={%d,%d}\n",
             case_idx,
             xradar_qmlp_case_label(case_idx),
             scalar_logits[0], scalar_logits[1],
             rocc_logits[0], rocc_logits[1]);
      return 1;
    }
    printf("[XRADAR-ROCC] case=%u %s logits={%d,%d}\n",
           case_idx,
           xradar_qmlp_case_label(case_idx),
           rocc_logits[0],
           rocc_logits[1]);
  }

  printf("[XRADAR-ROCC] counts rqdot4=%u scalar_tail_macs=%u rqscale8=%u total_macs=%u packed_mac_coverage_x100=%u\n",
         counts.rqdot4_ops,
         counts.scalar_tail_macs,
         counts.rqscale8_ops,
         XRADAR_QMLP_TOTAL_MACS,
         (unsigned int)(((uint64_t)counts.rqdot4_ops * 4ull * 10000ull) /
                        (uint64_t)XRADAR_QMLP_TOTAL_MACS));
  printf("[XRADAR-ROCC] PASSED\n");

  return 0;
}
