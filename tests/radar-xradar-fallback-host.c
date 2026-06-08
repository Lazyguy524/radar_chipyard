#include <stdint.h>
#include <stdio.h>

#include "radar_xradar_fallback.h"

static int check_basic_ops(void)
{
  uint32_t a = xradar_pack_i8x4(1, -2, 3, -4);
  uint32_t b = xradar_pack_i8x4(-5, 6, -7, 8);
  int32_t dot = xradar_rqdot4_sw(a, b);

  if (dot != -70) {
    printf("[XRADAR-FALLBACK] rqdot4 basic mismatch: got=%d expected=-70\n", dot);
    return -1;
  }

  if (xradar_rqscale8_relu_sw(-100, XRADAR_QMLP_L1_MULTIPLIER) != 0) {
    printf("[XRADAR-FALLBACK] rqscale8 negative relu mismatch\n");
    return -1;
  }

  if (xradar_rqscale8_relu_sw(100000000, XRADAR_QMLP_L1_MULTIPLIER) != 127) {
    printf("[XRADAR-FALLBACK] rqscale8 positive clamp mismatch\n");
    return -1;
  }

  return 0;
}

int main(void)
{
  int8_t sample[RADAR_MLP_INPUT_DIM];
  int32_t scalar_logits[2];
  int32_t xradar_logits[2];
  xradar_qmlp_op_counts_t counts;
  unsigned int case_idx;

  if (check_basic_ops() != 0) {
    return 1;
  }

  xradar_qmlp_scalar_infer(radar_mlp_golden_input, scalar_logits);
  xradar_qmlp_fallback_infer(radar_mlp_golden_input, xradar_logits, &counts);
  if (scalar_logits[0] != radar_mlp_golden_logits[0] ||
      scalar_logits[1] != radar_mlp_golden_logits[1] ||
      xradar_logits[0] != scalar_logits[0] ||
      xradar_logits[1] != scalar_logits[1]) {
    printf("[XRADAR-FALLBACK] golden mismatch scalar={%d,%d} xradar={%d,%d} pkg={%d,%d}\n",
           scalar_logits[0], scalar_logits[1],
           xradar_logits[0], xradar_logits[1],
           radar_mlp_golden_logits[0], radar_mlp_golden_logits[1]);
    return 1;
  }

  for (case_idx = 0; case_idx < XRADAR_QMLP_MULTI_CASES; ++case_idx) {
    xradar_qmlp_prepare_case(case_idx, sample);
    xradar_qmlp_scalar_infer(sample, scalar_logits);
    xradar_qmlp_fallback_infer(sample, xradar_logits, &counts);
    if (xradar_logits[0] != scalar_logits[0] ||
        xradar_logits[1] != scalar_logits[1]) {
      printf("[XRADAR-FALLBACK] case=%u %s mismatch scalar={%d,%d} xradar={%d,%d}\n",
             case_idx,
             xradar_qmlp_case_label(case_idx),
             scalar_logits[0], scalar_logits[1],
             xradar_logits[0], xradar_logits[1]);
      return 1;
    }
    printf("[XRADAR-FALLBACK] case=%u %-20s logits={%d,%d}\n",
           case_idx,
           xradar_qmlp_case_label(case_idx),
           xradar_logits[0],
           xradar_logits[1]);
  }

  printf("[XRADAR-FALLBACK] counts rqdot4=%u scalar_tail_macs=%u rqscale8=%u total_macs=%u packed_mac_coverage_x100=%u\n",
         counts.rqdot4_ops,
         counts.scalar_tail_macs,
         counts.rqscale8_ops,
         XRADAR_QMLP_TOTAL_MACS,
         (unsigned int)(((uint64_t)counts.rqdot4_ops * 4ull * 10000ull) /
                        (uint64_t)XRADAR_QMLP_TOTAL_MACS));
  printf("[XRADAR-FALLBACK] PASSED\n");
  return 0;
}
