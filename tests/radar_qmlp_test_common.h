#ifndef RADAR_QMLP_TEST_COMMON_H
#define RADAR_QMLP_TEST_COMMON_H

#include <stdint.h>

#include "../releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_input.h"
#include "../releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_logits.h"
#include "../releases/input_convergence_k3_rcs21_20260406/radar_mlp_binary_k3_rcs21_params.h"

#define RADAR_QMLP_TEST_INPUT_BYTES   32u
#define RADAR_QMLP_TEST_OUTPUT_BYTES  8u
#define RADAR_QMLP_MULTI_CASES        8u
#define RADAR_QMLP_TOTAL_MACS         ((RADAR_MLP_L1_IN * RADAR_MLP_L1_OUT) + \
                                       (RADAR_MLP_L2_IN * RADAR_MLP_L2_OUT) + \
                                       (RADAR_MLP_L3_IN * RADAR_MLP_L3_OUT))
#define RADAR_QMLP_REQUANT_SHIFT      16
#define RADAR_QMLP_L1_MULTIPLIER      1516
#define RADAR_QMLP_L2_MULTIPLIER      608

static inline uint64_t radar_read_cycle64(void)
{
  uint64_t value;
  asm volatile ("rdcycle %0" : "=r"(value));
  return value;
}

static inline int8_t radar_qmlp_clamp_i8(int value)
{
  if (value > 127) return 127;
  if (value < -128) return -128;
  return (int8_t)value;
}

static inline int32_t radar_qmlp_bankers_round_shift(int64_t value, unsigned int shift)
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

  if (value < 0) {
    return -(int32_t)rounded_abs;
  }
  return (int32_t)rounded_abs;
}

static inline int8_t radar_qmlp_requant_relu_clamp(int32_t acc, int multiplier)
{
  int64_t product = (int64_t)acc * (int64_t)multiplier;
  int32_t rounded = radar_qmlp_bankers_round_shift(product, RADAR_QMLP_REQUANT_SHIFT);

  if (rounded < 0) {
    rounded = 0;
  }
  if (rounded > 127) {
    rounded = 127;
  }
  return (int8_t)rounded;
}

static inline const char *radar_qmlp_case_label(unsigned int case_idx)
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

static inline void radar_qmlp_prepare_case(unsigned int case_idx, int8_t sample[RADAR_MLP_INPUT_DIM])
{
  unsigned int i;

  for (i = 0; i < (unsigned int)RADAR_MLP_INPUT_DIM; ++i) {
    int base = radar_mlp_golden_input[i];
    int value = base;

    switch (case_idx) {
      case 0u:
        value = base;
        break;
      case 1u:
        value = 0;
        break;
      case 2u:
        value = base + ((i & 1u) ? -3 : 4);
        break;
      case 3u:
        value = ((i % 3u) == 0u) ? base : 0;
        break;
      case 4u:
        value = ((i & 1u) == 0u) ? -base : base;
        break;
      case 5u:
        value = base / 2;
        break;
      case 6u:
        value = base + 6;
        break;
      case 7u:
        value = base - 6;
        break;
      default:
        value = base;
        break;
    }

    sample[i] = radar_qmlp_clamp_i8(value);
  }
}

static inline void radar_qmlp_software_infer(const int8_t input[RADAR_MLP_INPUT_DIM], int32_t logits[2])
{
  int out_idx;
  int in_idx;
  int8_t l1_out[RADAR_MLP_L1_OUT];
  int8_t l2_out[RADAR_MLP_L2_OUT];

  for (out_idx = 0; out_idx < RADAR_MLP_L1_OUT; ++out_idx) {
    int32_t acc = radar_mlp_l1_bias[out_idx];
    for (in_idx = 0; in_idx < RADAR_MLP_L1_IN; ++in_idx) {
      acc += (int32_t)input[in_idx] * (int32_t)radar_mlp_l1_weight[out_idx * RADAR_MLP_L1_IN + in_idx];
    }
    l1_out[out_idx] = radar_qmlp_requant_relu_clamp(acc, RADAR_QMLP_L1_MULTIPLIER);
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L2_OUT; ++out_idx) {
    int32_t acc = radar_mlp_l2_bias[out_idx];
    for (in_idx = 0; in_idx < RADAR_MLP_L2_IN; ++in_idx) {
      acc += (int32_t)l1_out[in_idx] * (int32_t)radar_mlp_l2_weight[out_idx * RADAR_MLP_L2_IN + in_idx];
    }
    l2_out[out_idx] = radar_qmlp_requant_relu_clamp(acc, RADAR_QMLP_L2_MULTIPLIER);
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L3_OUT; ++out_idx) {
    int32_t acc = radar_mlp_l3_bias[out_idx];
    for (in_idx = 0; in_idx < RADAR_MLP_L3_IN; ++in_idx) {
      acc += (int32_t)l2_out[in_idx] * (int32_t)radar_mlp_l3_weight[out_idx * RADAR_MLP_L3_IN + in_idx];
    }
    logits[out_idx] = acc;
  }
}

#endif
