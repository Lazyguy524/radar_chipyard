#include "params.h"
static int32_t round_shift_even_i64(int64_t value, unsigned int shift)
{
  uint64_t abs_value;
  uint64_t q_abs;
  uint64_t rem;
  uint64_t half;
  uint64_t rounded_abs;

  if (shift == 0u) {
    return (int32_t)value;
  }

  abs_value = (value < 0) ? (uint64_t)(-value) : (uint64_t)value;
  q_abs = abs_value >> shift;
  rem = abs_value & (((uint64_t)1u << shift) - 1u);
  half = (uint64_t)1u << (shift - 1u);
  rounded_abs = q_abs + ((rem > half) || ((rem == half) && (q_abs & 1u)));

  return (value < 0) ? -(int32_t)rounded_abs : (int32_t)rounded_abs;
}

static int8_t requant_relu_clamp(int32_t acc, int32_t multiplier)
{
  int64_t product = (int64_t)acc * (int64_t)multiplier;
  int32_t rounded = round_shift_even_i64(product, RADAR_QMLP_REQUANT_SHIFT);
  if (rounded < 0) return 0;
  if (rounded > 127) return 127;
  return (int8_t)rounded;
}

static void qmlp_infer(const int8_t *input, int32_t *logits, int8_t *l1_out, int8_t *l2_out)
{
  int out_idx;
  int in_idx;

  for (out_idx = 0; out_idx < RADAR_MLP_L1_OUT; ++out_idx) {
    int32_t acc = radar_mlp_l1_bias[out_idx];
    for (in_idx = 0; in_idx < RADAR_MLP_L1_IN; ++in_idx) {
      acc += (int32_t)input[in_idx] *
             (int32_t)radar_mlp_l1_weight[out_idx * RADAR_MLP_L1_IN + in_idx];
    }
    l1_out[out_idx] = requant_relu_clamp(acc, RADAR_QMLP_L1_MULTIPLIER);
  }

  for (out_idx = 0; out_idx < RADAR_MLP_L2_OUT; ++out_idx) {
    int32_t acc = radar_mlp_l2_bias[out_idx];
    for (in_idx = 0; in_idx < RADAR_MLP_L2_IN; ++in_idx) {
      acc += (int32_t)l1_out[in_idx] *
             (int32_t)radar_mlp_l2_weight[out_idx * RADAR_MLP_L2_IN + in_idx];
    }
    l2_out[out_idx] = requant_relu_clamp(acc, RADAR_QMLP_L2_MULTIPLIER);
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


void trace_batch(const int8_t *x, uint32_t n, int8_t *h1, int8_t *h2, int32_t *y) {
  for(uint32_t i=0;i<n;i++) qmlp_infer(x+i*21,y+i*2,h1+i*64,h2+i*32);
}
void test_round(const int64_t *x,uint32_t n,int32_t *y) {
  for(uint32_t i=0;i<n;i++) y[i]=round_shift_even_i64(x[i],16);
}
