#ifndef RADAR_XRADAR_FALLBACK_H
#define RADAR_XRADAR_FALLBACK_H

#include <stdint.h>

#include "../releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_input.h"
#include "../releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_logits.h"
#include "../releases/input_convergence_k3_rcs21_20260406/radar_mlp_binary_k3_rcs21_params.h"

#define XRADAR_QMLP_TEST_INPUT_BYTES   32u
#define XRADAR_QMLP_TEST_OUTPUT_BYTES  8u
#define XRADAR_QMLP_MULTI_CASES        8u
#define XRADAR_QMLP_REQUANT_SHIFT      16u
#define XRADAR_QMLP_L1_MULTIPLIER      1516
#define XRADAR_QMLP_L2_MULTIPLIER      608
#define XRADAR_QMLP_TOTAL_MACS         ((RADAR_MLP_L1_IN * RADAR_MLP_L1_OUT) + \
                                        (RADAR_MLP_L2_IN * RADAR_MLP_L2_OUT) + \
                                        (RADAR_MLP_L3_IN * RADAR_MLP_L3_OUT))

typedef struct {
  uint32_t rqdot4_ops;
  uint32_t scalar_tail_macs;
  uint32_t rqscale8_ops;
  uint32_t rqpack_ops;
} xradar_qmlp_op_counts_t;

static inline int8_t xradar_clamp_i8(int value)
{
  if (value > 127) return 127;
  if (value < -128) return -128;
  return (int8_t)value;
}

static inline uint32_t xradar_pack_i8x4(int8_t lane0, int8_t lane1, int8_t lane2, int8_t lane3)
{
  return ((uint32_t)(uint8_t)lane0) |
         ((uint32_t)(uint8_t)lane1 << 8) |
         ((uint32_t)(uint8_t)lane2 << 16) |
         ((uint32_t)(uint8_t)lane3 << 24);
}

static inline int8_t xradar_lane_i8(uint32_t packed, unsigned int lane)
{
  return (int8_t)((packed >> (lane * 8u)) & 0xffu);
}

static inline int32_t xradar_rqdot4_sw(uint32_t rs1, uint32_t rs2)
{
  int32_t sum = 0;
  unsigned int lane;

  for (lane = 0; lane < 4u; ++lane) {
    sum += (int32_t)xradar_lane_i8(rs1, lane) *
           (int32_t)xradar_lane_i8(rs2, lane);
  }
  return sum;
}

static inline int32_t xradar_rqmac4_sw(int32_t acc, uint32_t rs1, uint32_t rs2)
{
  return acc + xradar_rqdot4_sw(rs1, rs2);
}

static inline int32_t xradar_round_shift_even_i64(int64_t value, unsigned int shift)
{
  uint64_t abs_value;
  uint64_t q_abs;
  uint64_t rem_mask;
  uint64_t rem;
  uint64_t half;
  uint64_t rounded_abs;

  if (shift == 0u) {
    return (int32_t)value;
  }

  abs_value = (value < 0) ? (uint64_t)(-value) : (uint64_t)value;
  q_abs = abs_value >> shift;
  rem_mask = ((uint64_t)1u << shift) - 1u;
  rem = abs_value & rem_mask;
  half = (uint64_t)1u << (shift - 1u);
  rounded_abs = q_abs + ((rem > half) || ((rem == half) && (q_abs & 1u)));

  return (value < 0) ? -(int32_t)rounded_abs : (int32_t)rounded_abs;
}

static inline int32_t xradar_rqscale8_relu_sw(int32_t acc, int32_t multiplier)
{
  int64_t product = (int64_t)acc * (int64_t)multiplier;
  int32_t rounded = xradar_round_shift_even_i64(product, XRADAR_QMLP_REQUANT_SHIFT);

  if (rounded < 0) rounded = 0;
  if (rounded > 127) rounded = 127;
  return rounded;
}

static inline int32_t xradar_dot_i8_packed_tail(const int8_t *lhs,
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
    acc = xradar_rqmac4_sw(acc, lhs_pack, rhs_pack);
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

static inline const char *xradar_qmlp_case_label(unsigned int case_idx)
{
  switch (case_idx) {
    case 0u: return "golden_base";
    case 1u: return "zero";
    case 2u: return "alternating_perturb";
    case 3u: return "sparse_keep3";
    case 4u: return "sign_flip_even";
    case 5u: return "half_scale";
    case 6u: return "offset_plus";
    case 7u: return "offset_minus";
    default: return "unknown";
  }
}

static inline void xradar_qmlp_prepare_case(unsigned int case_idx, int8_t sample[RADAR_MLP_INPUT_DIM])
{
  unsigned int i;

  for (i = 0; i < (unsigned int)RADAR_MLP_INPUT_DIM; ++i) {
    int base = radar_mlp_golden_input[i];
    int value = base;

    switch (case_idx) {
      case 0u: value = base; break;
      case 1u: value = 0; break;
      case 2u: value = base + ((i & 1u) ? -3 : 4); break;
      case 3u: value = ((i % 3u) == 0u) ? base : 0; break;
      case 4u: value = ((i & 1u) == 0u) ? -base : base; break;
      case 5u: value = base / 2; break;
      case 6u: value = base + 6; break;
      case 7u: value = base - 6; break;
      default: value = base; break;
    }

    sample[i] = xradar_clamp_i8(value);
  }
}

static inline void xradar_qmlp_scalar_infer(const int8_t input[RADAR_MLP_INPUT_DIM],
                                            int32_t logits[2])
{
  int out_idx;
  int in_idx;
  int8_t l1_out[RADAR_MLP_L1_OUT];
  int8_t l2_out[RADAR_MLP_L2_OUT];

  for (out_idx = 0; out_idx < RADAR_MLP_L1_OUT; ++out_idx) {
    int32_t acc = radar_mlp_l1_bias[out_idx];
    for (in_idx = 0; in_idx < RADAR_MLP_L1_IN; ++in_idx) {
      acc += (int32_t)input[in_idx] *
             (int32_t)radar_mlp_l1_weight[out_idx * RADAR_MLP_L1_IN + in_idx];
    }
    l1_out[out_idx] = (int8_t)xradar_rqscale8_relu_sw(acc, XRADAR_QMLP_L1_MULTIPLIER);
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L2_OUT; ++out_idx) {
    int32_t acc = radar_mlp_l2_bias[out_idx];
    for (in_idx = 0; in_idx < RADAR_MLP_L2_IN; ++in_idx) {
      acc += (int32_t)l1_out[in_idx] *
             (int32_t)radar_mlp_l2_weight[out_idx * RADAR_MLP_L2_IN + in_idx];
    }
    l2_out[out_idx] = (int8_t)xradar_rqscale8_relu_sw(acc, XRADAR_QMLP_L2_MULTIPLIER);
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L3_OUT; ++out_idx) {
    int32_t acc = radar_mlp_l3_bias[out_idx];
    for (in_idx = 0; in_idx < RADAR_MLP_L3_IN; ++in_idx) {
      acc += (int32_t)l2_out[in_idx] *
             (int32_t)radar_mlp_l3_weight[out_idx * RADAR_MLP_L3_IN + in_idx];
    }
    logits[out_idx] = acc;
  }
}

static inline void xradar_qmlp_fallback_infer(const int8_t input[RADAR_MLP_INPUT_DIM],
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
      xradar_dot_i8_packed_tail(input, weights, RADAR_MLP_L1_IN, counts);
    l1_out[out_idx] = (int8_t)xradar_rqscale8_relu_sw(acc, XRADAR_QMLP_L1_MULTIPLIER);
    if (counts != 0) counts->rqscale8_ops++;
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L2_OUT; ++out_idx) {
    const int8_t *weights = &radar_mlp_l2_weight[out_idx * RADAR_MLP_L2_IN];
    int32_t acc = radar_mlp_l2_bias[out_idx] +
      xradar_dot_i8_packed_tail(l1_out, weights, RADAR_MLP_L2_IN, counts);
    l2_out[out_idx] = (int8_t)xradar_rqscale8_relu_sw(acc, XRADAR_QMLP_L2_MULTIPLIER);
    if (counts != 0) counts->rqscale8_ops++;
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L3_OUT; ++out_idx) {
    const int8_t *weights = &radar_mlp_l3_weight[out_idx * RADAR_MLP_L3_IN];
    logits[out_idx] = radar_mlp_l3_bias[out_idx] +
      xradar_dot_i8_packed_tail(l2_out, weights, RADAR_MLP_L3_IN, counts);
  }
}

#endif
