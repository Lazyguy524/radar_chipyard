#include <stdint.h>

#define XRADAR_PROBE_BASE 0x80003000UL

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
  volatile uint64_t *probe = (volatile uint64_t *)XRADAR_PROBE_BASE;
  const uint32_t lhs = 0xfc03fe01u; /* {1, -2, 3, -4} */
  const uint32_t rhs = 0x08f906fbu; /* {-5, 6, -7, 8} */
  int32_t result;

  /* Expected dot product: 1*(-5) + (-2)*6 + 3*(-7) + (-4)*8 = -70. */
  probe[0] = 0x11110000u;
  probe[1] = lhs;
  probe[2] = rhs;
  result = xradar_rocc_rqdot4(lhs, rhs);
  probe[3] = (uint32_t)result;
  probe[4] = (result == -70) ? 0x2222aaaau : 0x2222eee0u;

  for (;;) {
    asm volatile ("" ::: "memory");
  }
}
