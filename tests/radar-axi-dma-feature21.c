#include "radar_axi_dma_common.h"
#include "radar_qmlp_test_common.h"

#define FEATURE21_POINT_COUNT 4u
#define FEATURE21_INPUT_BYTES ((FEATURE21_POINT_COUNT + 1u) * 8u)
#define FEATURE21_OUTPUT_BYTES 32u
#define FEATURE21_QMLP_OUTPUT_BYTES 8u
#define FEATURE21_CLOCK_HZ 50000000ull

typedef struct {
  int16_t x;
  int16_t y;
  int16_t doppler;
  int16_t rcs;
} feature21_point_t;

static const feature21_point_t feature21_points[FEATURE21_POINT_COUNT] = {
  { 256,  512,  256,  2560},
  { 512,  512,  256,  5120},
  { 768,  512,  256,  7680},
  {1024,  512,  256, 10240}
};

static inline volatile uint32_t *feature21_tx32(void)
{
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
}

static inline volatile int8_t *feature21_rx8(void)
{
  return (volatile int8_t *)radar_buffer_cpu_addr(RADAR_BUF_REGION_MID0, RADAR_BUF_VIEW_UNCACHED, 0);
}

static inline volatile int32_t *feature21_rx32(void)
{
  return (volatile int32_t *)radar_buffer_cpu_addr(RADAR_BUF_REGION_MID0, RADAR_BUF_VIEW_UNCACHED, 0);
}

static int32_t bankers_round_shift_i64(int64_t value, unsigned int shift)
{
  uint64_t abs_value = (value < 0) ? (uint64_t)(-value) : (uint64_t)value;
  uint64_t q_abs = abs_value >> shift;
  uint64_t rem = abs_value & (((uint64_t)1u << shift) - 1u);
  uint64_t half = (uint64_t)1u << (shift - 1u);
  uint64_t rounded_abs = q_abs + ((rem > half) || ((rem == half) && (q_abs & 1u)));
  return (value < 0) ? -(int32_t)rounded_abs : (int32_t)rounded_abs;
}

static int8_t clamp_s8_symmetric(int32_t value)
{
  if (value > 127) return 127;
  if (value < -127) return -127;
  return (int8_t)value;
}

static int8_t quant_q8p8(int32_t value)
{
  return clamp_s8_symmetric(bankers_round_shift_i64((int64_t)value * 105ll, 16u));
}

static int8_t quant_raw(uint32_t value)
{
  return clamp_s8_symmetric(bankers_round_shift_i64((int64_t)value * 26911ll, 16u));
}

static int32_t mean_q8p8(int64_t sum, uint32_t count)
{
  if (count == 0u) return 0;
  return bankers_round_shift_i64(sum * ((1ll << 16) / (int64_t)count), 16u);
}

static int32_t abs16_i32(int32_t value)
{
  return value < 0 ? -value : value;
}

static int32_t range_approx_q8p8(int32_t x, int32_t y)
{
  int32_t ax = abs16_i32(x);
  int32_t ay = abs16_i32(y);
  int32_t hi = ax > ay ? ax : ay;
  int32_t lo = ax > ay ? ay : ax;
  return hi + (lo >> 1);
}

static void build_feature21_expected(int8_t out[21])
{
  int64_t sum_x = 0;
  int64_t sum_y = 0;
  int64_t sum_d = 0;
  int64_t sum_r = 0;
  int32_t min_x = 0, max_x = 0;
  int32_t min_y = 0, max_y = 0;
  int32_t min_d = 0, max_d = 0;
  int32_t min_r = 0, max_r = 0;
  int32_t min_range = 0, max_range = 0;
  unsigned int i;

  for (i = 0; i < FEATURE21_POINT_COUNT; ++i) {
    int32_t x = feature21_points[i].x;
    int32_t y = feature21_points[i].y;
    int32_t d = feature21_points[i].doppler;
    int32_t r = feature21_points[i].rcs;
    int32_t range = range_approx_q8p8(x, y);
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
    int32_t mean_x = mean_q8p8(sum_x, FEATURE21_POINT_COUNT);
    int32_t mean_y = mean_q8p8(sum_y, FEATURE21_POINT_COUNT);
    int32_t mean_d = mean_q8p8(sum_d, FEATURE21_POINT_COUNT);
    int32_t mean_r = mean_q8p8(sum_r, FEATURE21_POINT_COUNT);
    int32_t span_x = max_x - min_x;
    int32_t span_y = max_y - min_y;
    int32_t span_d = max_d - min_d;
    int32_t span_r = max_r - min_r;
    int32_t std_x = span_x >> 2;
    int32_t std_y = span_y >> 2;
    int32_t eig_major = std_x > std_y ? std_x : std_y;
    int32_t eig_minor = std_x > std_y ? std_y : std_x;

    out[0] = quant_raw(FEATURE21_POINT_COUNT);
    out[1] = quant_q8p8(mean_x);
    out[2] = quant_q8p8(mean_y);
    out[3] = quant_q8p8(std_x);
    out[4] = quant_q8p8(std_y);
    out[5] = quant_q8p8(span_x);
    out[6] = quant_q8p8(span_y);
    out[7] = quant_q8p8(min_range);
    out[8] = quant_q8p8(max_range);
    out[9] = quant_q8p8(range_approx_q8p8(mean_x, mean_y));
    out[10] = quant_q8p8(span_y);
    out[11] = quant_q8p8(eig_major);
    out[12] = quant_q8p8(eig_minor);
    out[13] = quant_raw(FEATURE21_POINT_COUNT);
    out[14] = quant_q8p8(mean_d);
    out[15] = quant_q8p8(span_d >> 2);
    out[16] = quant_q8p8(min_d);
    out[17] = quant_q8p8(max_d);
    out[18] = quant_q8p8(mean_r);
    out[19] = quant_q8p8(span_r >> 2);
    out[20] = quant_q8p8(max_r);
  }
}

static void fill_feature21_stream(void)
{
  volatile uint32_t *tx = feature21_tx32();
  unsigned int i;

  tx[0] = FEATURE21_POINT_COUNT;
  tx[1] = 0u;

  for (i = 0; i < FEATURE21_POINT_COUNT; ++i) {
    uint32_t lo = ((uint32_t)(uint16_t)feature21_points[i].y << 16) |
                  (uint16_t)feature21_points[i].x;
    uint32_t hi = ((uint32_t)(uint16_t)feature21_points[i].rcs << 16) |
                  (uint16_t)feature21_points[i].doppler;
    tx[2u + i * 2u] = lo;
    tx[3u + i * 2u] = hi;
  }
}

static void clear_feature21_rx(unsigned int bytes)
{
  volatile int8_t *rx = feature21_rx8();
  unsigned int i;

  for (i = 0; i < bytes; ++i) {
    rx[i] = 0;
  }
}

static int compare_feature21_output(void)
{
  int8_t expected[21];
  volatile int8_t *rx = feature21_rx8();
  unsigned int i;

  build_feature21_expected(expected);

  for (i = 0; i < 21u; ++i) {
    if (rx[i] != expected[i]) {
      printf("[FEATURE21] mismatch idx=%u hw=%d expected=%d\n",
             i, rx[i], expected[i]);
      return -1;
    }
  }

  for (i = 21u; i < FEATURE21_OUTPUT_BYTES; ++i) {
    if (rx[i] != 0) {
      printf("[FEATURE21] padding mismatch idx=%u hw=%d\n", i, rx[i]);
      return -1;
    }
  }

  printf("[FEATURE21] preproc compare passed\n");
  return 0;
}

static int run_feature21_preproc_only(void)
{
  uint64_t t0;
  uint64_t t1;

  printf("[FEATURE21] preproc-only start\n");
  preproc_clear_counters();
  preproc_configure(PREPROC_MODE_FEATURE21_Q8_8, 0u, 0u, 1);
  fill_feature21_stream();
  clear_feature21_rx(FEATURE21_OUTPUT_BYTES);
  riscv_fence_rw_rw();

  t0 = radar_read_cycle64();
  if (dma_run_stream_once(TX_BUFFER_ADDR, FEATURE21_INPUT_BYTES,
                          RADAR_BUF_MID0_BASE, FEATURE21_OUTPUT_BYTES) != 0) {
    return -1;
  }
  t1 = radar_read_cycle64();

  if (compare_feature21_output() != 0) {
    return -1;
  }

  printf("[FEATURE21] preproc cycles=%lu us_x100=%lu in=%u out=%u frames=%u\n",
         (unsigned long)(t1 - t0),
         (unsigned long)(((t1 - t0) * 100000000ull) / FEATURE21_CLOCK_HZ),
         preproc_read32(PREPROC_IN_BEATS),
         preproc_read32(PREPROC_OUT_BEATS),
         preproc_read32(PREPROC_FRAME_COUNT));

  if (preproc_read32(PREPROC_IN_BEATS) != (FEATURE21_POINT_COUNT + 1u) ||
      preproc_read32(PREPROC_OUT_BEATS) != 4u ||
      preproc_read32(PREPROC_FRAME_COUNT) != 1u) {
    printf("[FEATURE21] preproc counter check failed\n");
    return -1;
  }

  return 0;
}

static int run_feature21_qmlp_chain(void)
{
  volatile int32_t *rx = feature21_rx32();
  uint64_t t0;
  uint64_t t1;

  printf("[FEATURE21] qmlp-chain start\n");
  preproc_clear_counters();
  qmlp_clear_counters();
  preproc_configure(PREPROC_MODE_FEATURE21_Q8_8, 0u, 0u, 1);
  qmlp_enable_preproc_chain(1);
  fill_feature21_stream();
  clear_feature21_rx(FEATURE21_QMLP_OUTPUT_BYTES);
  riscv_fence_rw_rw();

  t0 = radar_read_cycle64();
  if (dma_run_stream_once(TX_BUFFER_ADDR, FEATURE21_INPUT_BYTES,
                          RADAR_BUF_MID0_BASE, FEATURE21_QMLP_OUTPUT_BYTES) != 0) {
    qmlp_enable_preproc_chain(0);
    return -1;
  }
  t1 = radar_read_cycle64();

  printf("[FEATURE21] chain cycles=%lu us_x100=%lu logits={%d,%d} pre_in=%u pre_out=%u q_in=%u q_out=%u q_cyc=%u\n",
         (unsigned long)(t1 - t0),
         (unsigned long)(((t1 - t0) * 100000000ull) / FEATURE21_CLOCK_HZ),
         rx[0], rx[1],
         preproc_read32(PREPROC_IN_BEATS),
         preproc_read32(PREPROC_OUT_BEATS),
         qmlp_read32(QMLP_IN_BEATS),
         qmlp_read32(QMLP_OUT_BEATS),
         qmlp_read32(QMLP_RUN_CYCLES));

  if (preproc_read32(PREPROC_IN_BEATS) != (FEATURE21_POINT_COUNT + 1u) ||
      preproc_read32(PREPROC_OUT_BEATS) != 4u ||
      qmlp_read32(QMLP_IN_BEATS) != 4u ||
      qmlp_read32(QMLP_OUT_BEATS) != 1u) {
    printf("[FEATURE21] chain counter check failed\n");
    qmlp_enable_preproc_chain(0);
    return -1;
  }

  qmlp_enable_preproc_chain(0);
  return 0;
}

int main(void)
{
  printf("AXI DMA feature21 fixed-point preprocessor test start\n");
  radar_describe_buffer_protocol();
  preproc_disable();
  qmlp_enable(0);

  if (run_feature21_preproc_only() != 0) {
    printf("AXI DMA feature21 FAILED\n");
    return 1;
  }

  if (run_feature21_qmlp_chain() != 0) {
    printf("AXI DMA feature21 FAILED\n");
    return 1;
  }

  preproc_disable();
  qmlp_enable(0);
  printf("AXI DMA feature21 PASSED\n");
  return 0;
}
