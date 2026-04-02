#include "radar_axi_dma_common.h"

static inline volatile uint32_t *tx_buffer_uncached(void)
{
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_TX_OFFSET);
}

static inline volatile uint32_t *rx_buffer_uncached(void)
{
  return radar_buffer_ptr32(RADAR_BUF_REGION_IN, RADAR_BUF_VIEW_UNCACHED, RADAR_STAGE_RX_OFFSET);
}

static void clear_rx_uncached(unsigned long word_count)
{
  volatile uint32_t *rx = rx_buffer_uncached();
  for (unsigned long i = 0; i < word_count; ++i) {
    rx[i] = 0u;
  }
}

static void fill_add32_pattern(unsigned long word_count, uint32_t base)
{
  volatile uint32_t *tx = tx_buffer_uncached();
  for (unsigned long i = 0; i < word_count; ++i) {
    tx[i] = base | (uint32_t)i;
  }
}

static long compare_add32_expected(unsigned long word_count, uint32_t add_lo, uint32_t add_hi)
{
  volatile uint32_t *tx = tx_buffer_uncached();
  volatile uint32_t *rx = rx_buffer_uncached();

  for (unsigned long i = 0; i < word_count; ++i) {
    uint32_t expected = tx[i] + ((i & 1UL) ? add_hi : add_lo);
    if (rx[i] != expected) {
      printf("[ADD32] mismatch at word %lu: tx=0x%08x expected=0x%08x rx=0x%08x\n",
             i, tx[i], expected, rx[i]);
      return (long)i;
    }
  }

  printf("[ADD32] compare passed\n");
  return -1;
}

static uint16_t relu_clip_lane(int16_t sample, uint16_t clip)
{
  if (sample < 0) return 0u;
  if (clip != 0u && (uint16_t)sample > clip) return clip;
  return (uint16_t)sample;
}

static void fill_relu16_pattern(unsigned long word_count)
{
  volatile uint32_t *tx = tx_buffer_uncached();

  for (unsigned long i = 0; i < word_count; ++i) {
    int16_t lo = (int16_t)((int)i * 73 - 900);
    int16_t hi = (int16_t)((int)i * 55 - 400);
    tx[i] = ((uint32_t)(uint16_t)hi << 16) | (uint16_t)lo;
  }
}

static long compare_relu16_expected(unsigned long word_count, uint16_t clip)
{
  volatile uint32_t *tx = tx_buffer_uncached();
  volatile uint32_t *rx = rx_buffer_uncached();

  for (unsigned long i = 0; i < word_count; ++i) {
    int16_t tx_lo = (int16_t)(tx[i] & 0xffffu);
    int16_t tx_hi = (int16_t)(tx[i] >> 16);
    uint32_t expected = ((uint32_t)relu_clip_lane(tx_hi, clip) << 16) |
                        relu_clip_lane(tx_lo, clip);
    if (rx[i] != expected) {
      printf("[RELU16] mismatch at word %lu: tx=0x%08x expected=0x%08x rx=0x%08x\n",
             i, tx[i], expected, rx[i]);
      return (long)i;
    }
  }

  printf("[RELU16] compare passed\n");
  return -1;
}

static int check_preproc_counters(const char *tag, uint32_t expected_beats, uint32_t expected_frames)
{
  uint32_t in_beats = preproc_read32(PREPROC_IN_BEATS);
  uint32_t out_beats = preproc_read32(PREPROC_OUT_BEATS);
  uint32_t frames = preproc_read32(PREPROC_FRAME_COUNT);

  printf("%s counters: in=%u out=%u frames=%u\n", tag, in_beats, out_beats, frames);

  if (in_beats != expected_beats || out_beats != expected_beats || frames != expected_frames) {
    printf("%s counter check failed\n", tag);
    return -1;
  }

  return 0;
}

static int run_add32_case(void)
{
  const uint32_t add_lo = 0x00000111u;
  const uint32_t add_hi = 0x00000222u;
  const uint32_t expected_beats = (uint32_t)(TEST_BYTE_COUNT / 8UL);

  printf("[ADD32] start\n");
  preproc_clear_counters();
  preproc_configure(PREPROC_MODE_ADD32, add_lo, add_hi, 1);
  preproc_dump_status("[ADD32] configured");

  fill_add32_pattern(TEST_WORD_COUNT, 0x21000000u);
  clear_rx_uncached(TEST_WORD_COUNT);
  riscv_fence_rw_rw();

  if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT) != 0) {
    printf("[ADD32] DMA run failed\n");
    return -1;
  }

  riscv_fence_rw_rw();

  if (compare_add32_expected(TEST_WORD_COUNT, add_lo, add_hi) >= 0) {
    return -1;
  }

  if (check_preproc_counters("[ADD32]", expected_beats, 1u) != 0) {
    return -1;
  }

  return 0;
}

static int run_relu16_case(void)
{
  const uint16_t clip = 0x3fffu;
  const uint32_t expected_beats = (uint32_t)(TEST_BYTE_COUNT / 8UL);

  printf("[RELU16] start\n");
  preproc_clear_counters();
  preproc_configure(PREPROC_MODE_RELU16, clip, 0u, 1);
  preproc_dump_status("[RELU16] configured");

  fill_relu16_pattern(TEST_WORD_COUNT);
  clear_rx_uncached(TEST_WORD_COUNT);
  riscv_fence_rw_rw();

  if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT) != 0) {
    printf("[RELU16] DMA run failed\n");
    return -1;
  }

  riscv_fence_rw_rw();

  if (compare_relu16_expected(TEST_WORD_COUNT, clip) >= 0) {
    return -1;
  }

  if (check_preproc_counters("[RELU16]", expected_beats, 1u) != 0) {
    return -1;
  }

  return 0;
}

int main(void)
{
  printf("AXI DMA preprocessor test start\n");
  radar_describe_buffer_protocol();
  preproc_disable();
  preproc_clear_counters();
  preproc_dump_status("[BOOT]");

  if (run_add32_case() != 0) {
    preproc_disable();
    printf("AXI DMA preprocessor FAILED\n");
    return 1;
  }

  if (run_relu16_case() != 0) {
    preproc_disable();
    printf("AXI DMA preprocessor FAILED\n");
    return 1;
  }

  preproc_disable();
  preproc_dump_status("[DONE]");
  printf("AXI DMA preprocessor PASSED\n");
  return 0;
}
