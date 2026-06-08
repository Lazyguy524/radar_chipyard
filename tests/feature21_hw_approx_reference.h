#ifndef FEATURE21_HW_APPROX_REFERENCE_H
#define FEATURE21_HW_APPROX_REFERENCE_H

#include <stdint.h>

#define FEATURE21_HW_APPROX_DIM 21u
#define FEATURE21_HW_APPROX_MAX_POINTS 511u

typedef struct {
  int16_t x;
  int16_t y;
  int16_t doppler;
  int16_t rcs;
} feature21_hw_point_t;

static inline int32_t feature21_hw_bank_round_shift(int64_t value, unsigned int shift)
{
  uint64_t abs_value = (value < 0) ? (uint64_t)(-value) : (uint64_t)value;
  uint64_t q_abs = abs_value >> shift;
  uint64_t rem = abs_value & (((uint64_t)1u << shift) - 1u);
  uint64_t half = (uint64_t)1u << (shift - 1u);
  uint64_t rounded_abs = q_abs + ((rem > half) || ((rem == half) && (q_abs & 1u)));
  return (value < 0) ? -(int32_t)rounded_abs : (int32_t)rounded_abs;
}

static inline int8_t feature21_hw_clamp_s8_symmetric(int32_t value)
{
  if (value > 127) return 127;
  if (value < -127) return -127;
  return (int8_t)value;
}

static inline int8_t feature21_hw_quant_q8p8(int32_t value)
{
  return feature21_hw_clamp_s8_symmetric(
      feature21_hw_bank_round_shift((int64_t)value * 105ll, 16u));
}

static inline int8_t feature21_hw_quant_raw_count(uint32_t value)
{
  return feature21_hw_quant_q8p8((int32_t)(value << 8));
}

static inline int32_t feature21_hw_abs_i32(int32_t value)
{
  return value < 0 ? -value : value;
}

static inline int32_t feature21_hw_range_v1p3_q8p8(int32_t x, int32_t y)
{
  int32_t ax = feature21_hw_abs_i32(x);
  int32_t ay = feature21_hw_abs_i32(y);
  int32_t hi = ax > ay ? ax : ay;
  int32_t lo = ax > ay ? ay : ax;
  return hi + (lo >> 1);
}

static inline int32_t feature21_hw_mean_v1p3_q8p8(int64_t sum, uint32_t count)
{
  unsigned int shift = 0u;
  if (count == 2u) shift = 1u;
  else if (count >= 3u && count <= 4u) shift = 2u;
  else if (count >= 5u && count <= 8u) shift = 3u;
  else if (count >= 9u && count <= 16u) shift = 4u;
  else if (count >= 17u && count <= 32u) shift = 5u;
  else if (count >= 33u && count <= 64u) shift = 6u;
  else if (count >= 65u && count <= 128u) shift = 7u;
  else if (count >= 129u && count <= 256u) shift = 8u;
  else if (count > 256u) shift = 9u;
  return (int32_t)(sum >> shift);
}

static inline void feature21_hw_approx_v1p3(const feature21_hw_point_t *points,
                                            uint32_t point_count,
                                            int8_t out[FEATURE21_HW_APPROX_DIM])
{
  uint32_t count = point_count > FEATURE21_HW_APPROX_MAX_POINTS
      ? FEATURE21_HW_APPROX_MAX_POINTS
      : point_count;
  int64_t sum_x = 0, sum_y = 0, sum_d = 0, sum_r = 0;
  int32_t min_x = 0, max_x = 0, min_y = 0, max_y = 0;
  int32_t min_d = 0, max_d = 0, min_r = 0, max_r = 0;
  int32_t min_range = 0, max_range = 0;
  uint32_t i;

  for (i = 0; i < count; ++i) {
    int32_t x = points[i].x;
    int32_t y = points[i].y;
    int32_t d = points[i].doppler;
    int32_t r = points[i].rcs;
    int32_t range = feature21_hw_range_v1p3_q8p8(x, y);
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
    int32_t mean_x = feature21_hw_mean_v1p3_q8p8(sum_x, count);
    int32_t mean_y = feature21_hw_mean_v1p3_q8p8(sum_y, count);
    int32_t mean_d = feature21_hw_mean_v1p3_q8p8(sum_d, count);
    int32_t mean_r = feature21_hw_mean_v1p3_q8p8(sum_r, count);
    int32_t span_x = max_x - min_x;
    int32_t span_y = max_y - min_y;
    int32_t span_d = max_d - min_d;
    int32_t span_r = max_r - min_r;
    int32_t std_x = span_x >> 2;
    int32_t std_y = span_y >> 2;
    int32_t eig_major = std_x > std_y ? std_x : std_y;
    int32_t eig_minor = std_x > std_y ? std_y : std_x;

    out[0] = feature21_hw_quant_raw_count(count);
    out[1] = feature21_hw_quant_q8p8(mean_x);
    out[2] = feature21_hw_quant_q8p8(mean_y);
    out[3] = feature21_hw_quant_q8p8(std_x);
    out[4] = feature21_hw_quant_q8p8(std_y);
    out[5] = feature21_hw_quant_q8p8(span_x);
    out[6] = feature21_hw_quant_q8p8(span_y);
    out[7] = feature21_hw_quant_q8p8(min_range);
    out[8] = feature21_hw_quant_q8p8(max_range);
    out[9] = feature21_hw_quant_q8p8(feature21_hw_range_v1p3_q8p8(mean_x, mean_y));
    out[10] = feature21_hw_quant_q8p8(span_y);
    out[11] = feature21_hw_quant_q8p8(eig_major);
    out[12] = feature21_hw_quant_q8p8(eig_minor);
    out[13] = feature21_hw_quant_raw_count(count);
    out[14] = feature21_hw_quant_q8p8(mean_d);
    out[15] = feature21_hw_quant_q8p8(span_d >> 2);
    out[16] = feature21_hw_quant_q8p8(min_d);
    out[17] = feature21_hw_quant_q8p8(max_d);
    out[18] = feature21_hw_quant_q8p8(mean_r);
    out[19] = feature21_hw_quant_q8p8(span_r >> 2);
    out[20] = feature21_hw_quant_q8p8(max_r);
  }
}

#endif
