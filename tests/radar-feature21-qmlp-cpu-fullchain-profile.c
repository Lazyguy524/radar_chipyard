#include <stdint.h>
#include <stdio.h>

#include "radar_feature21_golden_subset.h"
#include "../docs/feature_preproc_compare_20260420/feature21/qmlp_params_21.h"

#define CPU_FULLCHAIN_SAMPLES RADAR_FEATURE21_GOLDEN_SAMPLE_COUNT
#define CPU_FULLCHAIN_FEATURE_DIM RADAR_FEATURE21_GOLDEN_FEATURE_DIM
#define CPU_FULLCHAIN_MAX_POINTS 511u

__asm__(
  ".section .rodata\n"
  ".balign 8\n"
  ".global cpu_fullchain_golden_features_bin\n"
  "cpu_fullchain_golden_features_bin:\n"
  ".incbin \"../docs/feature_preproc_compare_20260420/feature21/golden/features_int8_21.bin\"\n"
  ".balign 8\n"
  ".global cpu_fullchain_board_logits_bin\n"
  "cpu_fullchain_board_logits_bin:\n"
  ".incbin \"../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-19/pc-replay-strict-oracle-board-s0-n1000-chunked/pc-replay-s0-n1000-expected.bin\"\n"
  ".balign 8\n"
);

extern const int8_t cpu_fullchain_golden_features_bin[];
extern const int32_t cpu_fullchain_board_logits_bin[];

static volatile int32_t cpu_fullchain_sink0;
static volatile int32_t cpu_fullchain_sink1;

static inline uint64_t read_cycle64(void)
{
  uint64_t value;
  asm volatile ("rdcycle %0" : "=r"(value));
  return value;
}

static inline uint64_t read_instret64(void)
{
  uint64_t value;
  asm volatile ("rdinstret %0" : "=r"(value));
  return value;
}

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

static uint64_t round_div_even_u64(uint64_t numer, uint64_t denom)
{
  uint64_t q = numer / denom;
  uint64_t rem = numer - q * denom;
  uint64_t twice_rem = rem << 1;
  return q + ((twice_rem > denom) || ((twice_rem == denom) && (q & 1u)));
}

static int8_t clamp_s8_symmetric(int32_t value)
{
  if (value > 127) return 127;
  if (value < -127) return -127;
  return (int8_t)value;
}

static int8_t quant_q8p8(int32_t value)
{
  return clamp_s8_symmetric(round_shift_even_i64((int64_t)value * 105ll, 16u));
}

static int8_t quant_raw_count(uint32_t count)
{
  return quant_q8p8((int32_t)(count << 8));
}

static int32_t abs16_i32(int32_t value)
{
  int32_t abs_value = (value < 0) ? -value : value;
  return abs_value & 0xffff;
}

static int32_t range_v1p3_q8p8(int32_t x, int32_t y)
{
  int32_t ax = abs16_i32(x);
  int32_t ay = abs16_i32(y);
  int32_t hi = ax > ay ? ax : ay;
  int32_t lo = ax > ay ? ay : ax;
  return hi + (lo >> 1);
}

static int32_t mean_shift_v1p3(int64_t sum, uint32_t count)
{
  unsigned int shift;
  if (count <= 1u) shift = 0u;
  else if (count == 2u) shift = 1u;
  else if (count <= 4u) shift = 2u;
  else if (count <= 8u) shift = 3u;
  else if (count <= 16u) shift = 4u;
  else if (count <= 32u) shift = 5u;
  else if (count <= 64u) shift = 6u;
  else if (count <= 128u) shift = 7u;
  else if (count <= 256u) shift = 8u;
  else shift = 9u;
  return (int32_t)(sum >> shift);
}

static unsigned int bit_length_u64(uint64_t value)
{
  unsigned int bits = 0u;
  while (value != 0u) {
    bits++;
    value >>= 1;
  }
  return bits;
}

static int8_t density_recip_exact_lut_quant(uint32_t count, int32_t span_x, int32_t span_y)
{
  uint64_t sx = span_x > 0 ? (uint64_t)span_x : 0u;
  uint64_t sy = span_y > 0 ? (uint64_t)span_y : 0u;
  uint64_t area_q16p16 = sx * sy;
  unsigned int exponent;
  uint64_t mant8;
  uint64_t recip_q0p23;
  uint64_t prod;
  uint64_t density_q8p8;
  int64_t density_i64;

  if (count == 0u) {
    return 0;
  }
  if (area_q16p16 == 0u) {
    return 127;
  }

  exponent = bit_length_u64(area_q16p16) - 1u;
  if (exponent >= 7u) {
    mant8 = area_q16p16 >> (exponent - 7u);
  } else {
    mant8 = area_q16p16 << (7u - exponent);
  }
  if (mant8 < 128u) mant8 = 128u;
  if (mant8 > 255u) mant8 = 255u;

  recip_q0p23 = round_div_even_u64((uint64_t)1u << 23, mant8);
  prod = (uint64_t)count * recip_q0p23;
  if (exponent >= 8u) {
    density_q8p8 = (uint64_t)round_shift_even_i64((int64_t)prod, exponent - 8u);
  } else {
    density_q8p8 = prod << (8u - exponent);
  }

  density_i64 = (int64_t)density_q8p8;
  if (density_i64 > 0x7fffffffll) {
    density_i64 = 0x7fffffffll;
  }
  {
    int8_t quant = quant_q8p8((int32_t)density_i64);
    return quant < 0 ? 0 : quant;
  }
}

static void feature21_density_exact_lut(uint32_t sample, int8_t out[CPU_FULLCHAIN_FEATURE_DIM])
{
  uint32_t start = radar_feature21_golden_offsets[sample];
  uint32_t raw_count = radar_feature21_golden_offsets[sample + 1u] - start;
  uint32_t count = raw_count > CPU_FULLCHAIN_MAX_POINTS ? CPU_FULLCHAIN_MAX_POINTS : raw_count;
  int64_t sum_x = 0, sum_y = 0, sum_d = 0, sum_r = 0;
  int32_t min_x = 0, max_x = 0, min_y = 0, max_y = 0;
  int32_t min_d = 0, max_d = 0, min_r = 0, max_r = 0;
  int32_t min_range = 0, max_range = 0;
  uint32_t i;

  for (i = 0u; i < count; ++i) {
    const radar_feature21_golden_point_t *pt = &radar_feature21_golden_points[start + i];
    int32_t x = pt->x;
    int32_t y = pt->y;
    int32_t d = pt->doppler;
    int32_t r = pt->rcs;
    int32_t range = range_v1p3_q8p8(x, y);
    int first = (i == 0u);

    sum_x += x;
    sum_y += y;
    sum_d += d;
    sum_r += r;

    if (first || x < min_x) min_x = x;
    if (first || x > max_x) max_x = x;
    if (first || y < min_y) min_y = y;
    if (first || y > max_y) max_y = y;
    if (first || d < min_d) min_d = d;
    if (first || d > max_d) max_d = d;
    if (first || r < min_r) min_r = r;
    if (first || r > max_r) max_r = r;
    if (first || range < min_range) min_range = range;
    if (first || range > max_range) max_range = range;
  }

  {
    int32_t mean_x = mean_shift_v1p3(sum_x, count);
    int32_t mean_y = mean_shift_v1p3(sum_y, count);
    int32_t mean_d = mean_shift_v1p3(sum_d, count);
    int32_t mean_r = mean_shift_v1p3(sum_r, count);
    int32_t span_x = max_x - min_x;
    int32_t span_y = max_y - min_y;
    int32_t span_d = max_d - min_d;
    int32_t span_r = max_r - min_r;
    int32_t std_x = span_x >> 2;
    int32_t std_y = span_y >> 2;
    int32_t eig_major = std_x > std_y ? std_x : std_y;
    int32_t eig_minor = std_x > std_y ? std_y : std_x;

    out[0] = quant_raw_count(count);
    out[1] = quant_q8p8(mean_x);
    out[2] = quant_q8p8(mean_y);
    out[3] = quant_q8p8(std_x);
    out[4] = quant_q8p8(std_y);
    out[5] = quant_q8p8(span_x);
    out[6] = quant_q8p8(span_y);
    out[7] = quant_q8p8(min_range);
    out[8] = quant_q8p8(max_range);
    out[9] = quant_q8p8(range_v1p3_q8p8(mean_x, mean_y));
    out[10] = quant_q8p8(span_y);
    out[11] = quant_q8p8(eig_major);
    out[12] = quant_q8p8(eig_minor);
    out[13] = density_recip_exact_lut_quant(count, span_x, span_y);
    out[14] = quant_q8p8(mean_d);
    out[15] = quant_q8p8(span_d >> 2);
    out[16] = quant_q8p8(min_d);
    out[17] = quant_q8p8(max_d);
    out[18] = quant_q8p8(mean_r);
    out[19] = quant_q8p8(span_r >> 2);
    out[20] = quant_q8p8(max_r);
  }
}

static int8_t requant_relu_clamp(int32_t acc, int32_t multiplier)
{
  int64_t product = (int64_t)acc * (int64_t)multiplier;
  int32_t rounded = round_shift_even_i64(product, RADAR_QMLP_REQUANT_SHIFT);
  if (rounded < 0) return 0;
  if (rounded > 127) return 127;
  return (int8_t)rounded;
}

static void qmlp_infer(const int8_t input[RADAR_MLP_INPUT_DIM], int32_t logits[2])
{
  int8_t l1_out[RADAR_MLP_L1_OUT];
  int8_t l2_out[RADAR_MLP_L2_OUT];
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

int main(void)
{
  uint64_t feature_cycles = 0u;
  uint64_t qmlp_cycles = 0u;
  uint64_t full_cycles = 0u;
  uint64_t full_instret = 0u;
  uint32_t feature_value_mismatches = 0u;
  uint32_t feature_exact_samples = 0u;
  uint32_t logit_mismatches = 0u;
  uint32_t pred_mismatches = 0u;
  uint32_t sample;

  printf("Feature21 + QMLP CPU full-chain profile start\n");
  printf("[CPU-FULLCHAIN] samples=%u points=%u feature_dim=%u mode=density_recip_exact_lut expected=board_reference\n",
         CPU_FULLCHAIN_SAMPLES,
         RADAR_FEATURE21_GOLDEN_POINT_TOTAL,
         CPU_FULLCHAIN_FEATURE_DIM);

  for (sample = 0u; sample < CPU_FULLCHAIN_SAMPLES; ++sample) {
    int8_t features[CPU_FULLCHAIN_FEATURE_DIM];
    int32_t logits[2];
    const int8_t *golden_features =
      cpu_fullchain_golden_features_bin + sample * CPU_FULLCHAIN_FEATURE_DIM;
    const int32_t *expected_logits = cpu_fullchain_board_logits_bin + sample * 2u;
    uint32_t sample_feature_mismatches = 0u;
    uint64_t c0, c1, c2;
    uint64_t i0, i2;
    unsigned int j;

    i0 = read_instret64();
    c0 = read_cycle64();
    feature21_density_exact_lut(sample, features);
    c1 = read_cycle64();
    qmlp_infer(features, logits);
    c2 = read_cycle64();
    i2 = read_instret64();

    feature_cycles += c1 - c0;
    qmlp_cycles += c2 - c1;
    full_cycles += c2 - c0;
    full_instret += i2 - i0;
    cpu_fullchain_sink0 = logits[0];
    cpu_fullchain_sink1 = logits[1];

    for (j = 0u; j < CPU_FULLCHAIN_FEATURE_DIM; ++j) {
      if (features[j] != golden_features[j]) {
        if (feature_value_mismatches < 8u) {
          printf("[CPU-FULLCHAIN] feature_diff sample=%u idx=%u mirror=%d golden=%d\n",
                 sample,
                 j,
                 features[j],
                 golden_features[j]);
        }
        feature_value_mismatches++;
        sample_feature_mismatches++;
      }
    }
    if (sample_feature_mismatches == 0u) {
      feature_exact_samples++;
    }

    if (logits[0] != expected_logits[0] || logits[1] != expected_logits[1]) {
      if (logit_mismatches < 8u) {
        printf("[CPU-FULLCHAIN] logit_mismatch sample=%u got={%d,%d} expected={%d,%d}\n",
               sample,
               logits[0],
               logits[1],
               expected_logits[0],
               expected_logits[1]);
      }
      logit_mismatches++;
    }
    if ((logits[1] > logits[0]) != (expected_logits[1] > expected_logits[0])) {
      pred_mismatches++;
    }
  }

  printf("[CPU-FULLCHAIN] summary samples=%u feature_avg=%lu qmlp_avg=%lu full_avg=%lu instret_avg=%lu feature_value_mismatches=%u feature_exact_samples=%u logit_mismatches=%u pred_mismatches=%u sink={%d,%d}\n",
         CPU_FULLCHAIN_SAMPLES,
         (unsigned long)(feature_cycles / CPU_FULLCHAIN_SAMPLES),
         (unsigned long)(qmlp_cycles / CPU_FULLCHAIN_SAMPLES),
         (unsigned long)(full_cycles / CPU_FULLCHAIN_SAMPLES),
         (unsigned long)(full_instret / CPU_FULLCHAIN_SAMPLES),
         feature_value_mismatches,
         feature_exact_samples,
         logit_mismatches,
         pred_mismatches,
         cpu_fullchain_sink0,
         cpu_fullchain_sink1);

  if (logit_mismatches != 0u || pred_mismatches != 0u) {
    printf("Feature21 + QMLP CPU full-chain profile FAILED\n");
    return 1;
  }

  printf("Feature21 + QMLP CPU full-chain profile PASSED\n");
  return 0;
}
