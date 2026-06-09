#include <stdint.h>
#include <stdio.h>

#include "radar_xradar_fallback.h"

static inline int32_t xradar_rocc_rqdot4(uint32_t lhs, uint32_t rhs)
{
  long result;
  asm volatile (".insn r CUSTOM_0, 7, 0, %0, %1, %2"
                : "=r"(result)
                : "r"((unsigned long)lhs), "r"((unsigned long)rhs));
  return (int32_t)result;
}

int main(void)
{
  const uint32_t lhs = xradar_pack_i8x4(1, -2, 3, -4);
  const uint32_t rhs = xradar_pack_i8x4(-5, 6, -7, 8);
  int32_t got;
  int32_t expected;

  printf("[XRADAR-HTIF] before rqdot4\n");
  got = xradar_rocc_rqdot4(lhs, rhs);
  expected = xradar_rqdot4_sw(lhs, rhs);
  printf("[XRADAR-HTIF] after rqdot4 got=%d expected=%d\n", got, expected);

  if (got != expected) {
    printf("[XRADAR-HTIF] FAILED\n");
    return 1;
  }

  printf("[XRADAR-HTIF] PASSED\n");
  return 0;
}
