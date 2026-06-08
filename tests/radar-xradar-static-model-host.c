#include <stdint.h>
#include <stdio.h>

#include "radar_xradar_fallback.h"

static void print_layer(const char *name, unsigned int out_dim, unsigned int in_dim)
{
  unsigned int macs = out_dim * in_dim;
  unsigned int rqdot4_groups = out_dim * (in_dim / 4u);
  unsigned int tail_macs = out_dim * (in_dim % 4u);
  unsigned int scalar_loads = macs * 2u;
  unsigned int packed_loads = rqdot4_groups * 2u + tail_macs * 2u;

  printf("[XRADAR-STATIC] layer=%s shape=%ux%u macs=%u rqdot4=%u tail_macs=%u scalar_loads=%u packed_loads=%u packed_load_reduction_x100=%u\n",
         name,
         out_dim,
         in_dim,
         macs,
         rqdot4_groups,
         tail_macs,
         scalar_loads,
         packed_loads,
         scalar_loads == 0u ? 0u : ((scalar_loads - packed_loads) * 10000u) / scalar_loads);
}

static unsigned int speedup_x1000(unsigned int f_pct, unsigned int sk_x)
{
  uint64_t denom = (uint64_t)(100u - f_pct) * (uint64_t)sk_x + (uint64_t)f_pct;
  return (unsigned int)(((uint64_t)100000u * (uint64_t)sk_x + (denom / 2u)) / denom);
}

int main(void)
{
  unsigned int total_rqdot4 =
    RADAR_MLP_L1_OUT * (RADAR_MLP_L1_IN / 4u) +
    RADAR_MLP_L2_OUT * (RADAR_MLP_L2_IN / 4u) +
    RADAR_MLP_L3_OUT * (RADAR_MLP_L3_IN / 4u);
  unsigned int total_tail =
    RADAR_MLP_L1_OUT * (RADAR_MLP_L1_IN % 4u) +
    RADAR_MLP_L2_OUT * (RADAR_MLP_L2_IN % 4u) +
    RADAR_MLP_L3_OUT * (RADAR_MLP_L3_IN % 4u);
  unsigned int packed_terms = total_rqdot4 * 4u;
  static const unsigned int f_values[] = {20u, 40u, 50u, 60u, 70u, 80u};
  static const unsigned int sk_values[] = {2u, 4u, 6u, 8u};
  unsigned int i;
  unsigned int j;

  print_layer("L1", RADAR_MLP_L1_OUT, RADAR_MLP_L1_IN);
  print_layer("L2", RADAR_MLP_L2_OUT, RADAR_MLP_L2_IN);
  print_layer("L3", RADAR_MLP_L3_OUT, RADAR_MLP_L3_IN);

  printf("[XRADAR-STATIC] total_macs=%u rqdot4=%u packed_terms=%u tail_macs=%u packed_coverage_x100=%u rqscale8=%u\n",
         XRADAR_QMLP_TOTAL_MACS,
         total_rqdot4,
         packed_terms,
         total_tail,
         (unsigned int)(((uint64_t)packed_terms * 10000ull) / XRADAR_QMLP_TOTAL_MACS),
         RADAR_MLP_L1_OUT + RADAR_MLP_L2_OUT);

  for (i = 0; i < sizeof(f_values) / sizeof(f_values[0]); ++i) {
    printf("[XRADAR-AMDAHL] f_pct=%u", f_values[i]);
    for (j = 0; j < sizeof(sk_values) / sizeof(sk_values[0]); ++j) {
      printf(" sk%ux_x1000=%u", sk_values[j], speedup_x1000(f_values[i], sk_values[j]));
    }
    printf("\n");
  }

  return 0;
}
