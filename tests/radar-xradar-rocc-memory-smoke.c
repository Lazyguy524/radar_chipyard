#include <stdint.h>

#include "radar_xradar_fallback.h"

#define XRADAR_MEMSMOKE_BASE 0x80010000UL

enum {
  XRADAR_STAGE_START = 0x11110000,
  XRADAR_STAGE_BASIC_DONE = 0x22220000,
  XRADAR_STAGE_QMLP_BASE = 0x33330000,
  XRADAR_STAGE_PASS = 0x7777aaaa,
  XRADAR_STAGE_FAIL = 0xdead0000,
};

static inline void probe_write(unsigned int index, uint64_t value)
{
  volatile uint64_t *probe = (volatile uint64_t *)XRADAR_MEMSMOKE_BASE;
  probe[index] = value;
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

static int run_basic_ops(void)
{
  static const int8_t lanes[][8] = {
    {1, -2, 3, -4, -5, 6, -7, 8},
    {127, -128, 1, -1, 1, 1, -128, 127},
    {0, 0, 0, 0, 99, -99, 7, -7},
    {-12, 34, -56, 78, -9, -8, 7, 6},
  };
  unsigned int i;
  uint32_t pass_mask = 0;

  for (i = 0; i < sizeof(lanes) / sizeof(lanes[0]); ++i) {
    uint32_t lhs = xradar_pack_i8x4(lanes[i][0], lanes[i][1], lanes[i][2], lanes[i][3]);
    uint32_t rhs = xradar_pack_i8x4(lanes[i][4], lanes[i][5], lanes[i][6], lanes[i][7]);
    int32_t got = xradar_rocc_rqdot4(lhs, rhs);
    int32_t expected = xradar_rqdot4_sw(lhs, rhs);
    unsigned int base = 32u + i * 4u;

    probe_write(base + 0u, lhs);
    probe_write(base + 1u, rhs);
    probe_write(base + 2u, (uint32_t)got);
    probe_write(base + 3u, (uint32_t)expected);
    probe_write(17u, (uint32_t)got);
    probe_write(18u, (uint32_t)expected);
    probe_write(19u, lhs);
    probe_write(20u, rhs);

    if (got != expected) {
      probe_write(2u, 0xb000u + i);
      probe_write(1u, XRADAR_STAGE_FAIL);
      return -1;
    }

    pass_mask |= 1u << i;
    probe_write(3u, pass_mask);
    probe_write(5u, i + 1u);
  }

  probe_write(1u, XRADAR_STAGE_BASIC_DONE);
  return 0;
}

int main(void)
{
  int8_t sample[RADAR_MLP_INPUT_DIM];
  int32_t scalar_logits[2];
  int32_t rocc_logits[2];
  xradar_qmlp_op_counts_t counts;
  unsigned int case_idx;
  uint32_t qmlp_mask = 0;

  probe_write(0u, 0x58524441524f4343ull);
  probe_write(1u, XRADAR_STAGE_START);
  probe_write(2u, 0u);
  probe_write(3u, 0u);
  probe_write(4u, 0u);
  probe_write(5u, 0u);
  probe_write(6u, 0u);
  probe_write(10u, XRADAR_QMLP_TOTAL_MACS);

  if (run_basic_ops() != 0) {
    for (;;) { asm volatile ("" ::: "memory"); }
  }

  for (case_idx = 0; case_idx < XRADAR_QMLP_MULTI_CASES; ++case_idx) {
    unsigned int base = 64u + case_idx * 6u;
    probe_write(1u, XRADAR_STAGE_QMLP_BASE | case_idx);
    probe_write(12u, case_idx);

    xradar_qmlp_prepare_case(case_idx, sample);
    xradar_qmlp_scalar_infer(sample, scalar_logits);
    xradar_qmlp_rocc_infer(sample, rocc_logits, &counts);

    probe_write(7u, counts.rqdot4_ops);
    probe_write(8u, counts.scalar_tail_macs);
    probe_write(9u, counts.rqscale8_ops);
    probe_write(11u, (uint32_t)(((uint64_t)counts.rqdot4_ops * 4ull * 10000ull) /
                                (uint64_t)XRADAR_QMLP_TOTAL_MACS));
    probe_write(13u, (uint32_t)rocc_logits[0]);
    probe_write(14u, (uint32_t)scalar_logits[0]);
    probe_write(15u, (uint32_t)rocc_logits[1]);
    probe_write(16u, (uint32_t)scalar_logits[1]);

    probe_write(base + 0u, (uint32_t)rocc_logits[0]);
    probe_write(base + 1u, (uint32_t)scalar_logits[0]);
    probe_write(base + 2u, (uint32_t)rocc_logits[1]);
    probe_write(base + 3u, (uint32_t)scalar_logits[1]);
    probe_write(base + 4u, counts.rqdot4_ops);
    probe_write(base + 5u, counts.scalar_tail_macs);

    if (rocc_logits[0] != scalar_logits[0] ||
        rocc_logits[1] != scalar_logits[1]) {
      probe_write(2u, 0xc000u + case_idx);
      probe_write(1u, XRADAR_STAGE_FAIL);
      for (;;) { asm volatile ("" ::: "memory"); }
    }

    qmlp_mask |= 1u << case_idx;
    probe_write(4u, qmlp_mask);
    probe_write(6u, case_idx + 1u);
  }

  probe_write(1u, XRADAR_STAGE_PASS);
  probe_write(2u, 0u);

  for (;;) {
    asm volatile ("" ::: "memory");
  }
}
