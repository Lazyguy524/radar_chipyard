#include "radar_axi_dma_common.h"
#include "radar_qmlp_test_common.h"
#include "radar_feature21_golden_subset.h"

#define FEATURE21_OUTPUT_BYTES 32u
#define FEATURE21_OUTPUT_BEATS 4u

static inline volatile uint32_t *golden_tx32(void)
{
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
}

static inline volatile int8_t *golden_rx8(void)
{
  return (volatile int8_t *)radar_buffer_cpu_addr(RADAR_BUF_REGION_MID0, RADAR_BUF_VIEW_UNCACHED, 0);
}

static uint32_t golden_sample_point_count(unsigned int sample)
{
  return radar_feature21_golden_offsets[sample + 1u] - radar_feature21_golden_offsets[sample];
}

static void fill_golden_stream(unsigned int sample)
{
  volatile uint32_t *tx = golden_tx32();
  uint32_t start = radar_feature21_golden_offsets[sample];
  uint32_t count = golden_sample_point_count(sample);
  uint32_t i;

  tx[0] = count;
  tx[1] = 0u;

  for (i = 0; i < count; ++i) {
    const radar_feature21_golden_point_t *pt = &radar_feature21_golden_points[start + i];
    uint32_t lo = ((uint32_t)(uint16_t)pt->y << 16) | (uint16_t)pt->x;
    uint32_t hi = ((uint32_t)(uint16_t)pt->rcs << 16) | (uint16_t)pt->doppler;

    tx[2u + i * 2u] = lo;
    tx[3u + i * 2u] = hi;
  }
}

static void clear_golden_rx(void)
{
  volatile int8_t *rx = golden_rx8();
  unsigned int i;

  for (i = 0; i < FEATURE21_OUTPUT_BYTES; ++i) {
    rx[i] = 0;
  }
}

static void print_feature21_dump(unsigned int sample, uint64_t cycles, const volatile int8_t *values)
{
  unsigned int i;

  printf("[F21-DUMP] s=%u c=%lu hw=", sample, (unsigned long)cycles);
  for (i = 0; i < RADAR_FEATURE21_GOLDEN_FEATURE_DIM; ++i) {
    printf("%02x", (unsigned int)((uint8_t)values[i]));
  }
  printf("\n");
}

static int run_golden_sample(unsigned int sample,
                             uint64_t *sample_cycles)
{
  volatile int8_t *rx = golden_rx8();
  uint32_t count = golden_sample_point_count(sample);
  uint32_t input_bytes = (count + 1u) * 8u;
  uint64_t t0;
  uint64_t t1;
  unsigned int i;

  preproc_clear_counters();
  preproc_configure(PREPROC_MODE_FEATURE21_Q8_8, 0u, 0u, 1);
  fill_golden_stream(sample);
  clear_golden_rx();
  riscv_fence_rw_rw();

  t0 = radar_read_cycle64();
  if (dma_run_stream_once_noreset(TX_BUFFER_ADDR, input_bytes,
                                  RADAR_BUF_MID0_BASE, FEATURE21_OUTPUT_BYTES) != 0) {
    return -1;
  }
  t1 = radar_read_cycle64();
  *sample_cycles = t1 - t0;

  if (preproc_read32(PREPROC_IN_BEATS) != (count + 1u) ||
      preproc_read32(PREPROC_OUT_BEATS) != FEATURE21_OUTPUT_BEATS ||
      preproc_read32(PREPROC_FRAME_COUNT) != 1u) {
    printf("[F21-GOLDEN] sample=%u counter failed in=%u out=%u frames=%u expected_in=%u\n",
           sample,
           preproc_read32(PREPROC_IN_BEATS),
           preproc_read32(PREPROC_OUT_BEATS),
           preproc_read32(PREPROC_FRAME_COUNT),
           count + 1u);
    return -1;
  }

  for (i = RADAR_FEATURE21_GOLDEN_FEATURE_DIM; i < FEATURE21_OUTPUT_BYTES; ++i) {
    if (rx[i] != 0) {
      printf("[F21-GOLDEN] sample=%u padding mismatch idx=%u hw=%d\n", sample, i, rx[i]);
      return -1;
    }
  }

  print_feature21_dump(sample, *sample_cycles, rx);
  return 0;
}

int main(void)
{
  uint32_t total_points = 0u;
  uint64_t total_cycles = 0u;
  uint64_t min_cycles = 0u;
  uint64_t max_cycles = 0u;
  unsigned int sample;

  printf("AXI DMA feature21 compact dump start\n");
  printf("[F21-DUMP] begin samples=%u input=q8.8_from_float32 format=hex21\n",
         RADAR_FEATURE21_GOLDEN_SAMPLE_COUNT);
  radar_describe_buffer_protocol();
  preproc_disable();
  qmlp_enable(0);

  if (dma_stream_prepare_noreset() != 0) {
    printf("AXI DMA feature21 golden FAILED\n");
    return 1;
  }

  for (sample = 0; sample < RADAR_FEATURE21_GOLDEN_SAMPLE_COUNT; ++sample) {
    uint64_t sample_cycles;
    uint32_t count = golden_sample_point_count(sample);

    if (run_golden_sample(sample, &sample_cycles) != 0) {
      printf("AXI DMA feature21 golden FAILED\n");
      return 1;
    }

    total_points += count;
    total_cycles += sample_cycles;
    if (sample == 0u || sample_cycles < min_cycles) {
      min_cycles = sample_cycles;
    }
    if (sample_cycles > max_cycles) {
      max_cycles = sample_cycles;
    }
  }

  {
    printf("[F21-DUMP] summary samples=%u points=%u cycles_avg=%lu cycles_min=%lu cycles_max=%lu\n",
           RADAR_FEATURE21_GOLDEN_SAMPLE_COUNT,
           total_points,
           (unsigned long)(total_cycles / RADAR_FEATURE21_GOLDEN_SAMPLE_COUNT),
           (unsigned long)min_cycles,
           (unsigned long)max_cycles);
  }

  preproc_disable();
  qmlp_enable(0);
  printf("AXI DMA feature21 compact dump COMPLETED\n");
  return 0;
}
