#include "mmio.h"

#include <stdint.h>
#include <stdio.h>

#define PREPROC_BASE  0x60000000UL
#define CLUSTER_BASE  0x60001000UL
#define DETECT_BASE   0x60002000UL
#define RESERVED_BASE 0x60003000UL

static int check64(uintptr_t addr, uint64_t expected)
{
  reg_write64(addr, expected);
  uint64_t got = reg_read64(addr);
  if (got != expected) {
    printf("FAIL64 addr=0x%08lx got=0x%016lx expected=0x%016lx\n",
      (unsigned long)addr, (unsigned long)got, (unsigned long)expected);
    return 1;
  }
  printf("PASS64 addr=0x%08lx data=0x%016lx\n",
    (unsigned long)addr, (unsigned long)got);
  return 0;
}

static int check32(uintptr_t addr, uint32_t expected)
{
  reg_write32(addr, expected);
  uint32_t got = reg_read32(addr);
  if (got != expected) {
    printf("FAIL32 addr=0x%08lx got=0x%08x expected=0x%08x\n",
      (unsigned long)addr, got, expected);
    return 1;
  }
  printf("PASS32 addr=0x%08lx data=0x%08x\n",
    (unsigned long)addr, got);
  return 0;
}

int main(void)
{
  int failed = 0;

  printf("Radar AXI MMIO smoke test start\n");

  failed += check64(PREPROC_BASE,  0x1122334455667788ULL);
  failed += check64(CLUSTER_BASE,  0x8877665544332211ULL);
  failed += check64(DETECT_BASE,   0xCAFEBABE12345678ULL);
  failed += check64(RESERVED_BASE, 0x0BADF00DDEADBEEFULL);

  failed += check32(PREPROC_BASE + 0x8, 0xA5A55A5A);
  failed += check32(CLUSTER_BASE + 0x8, 0x55AA55AA);
  failed += check32(DETECT_BASE + 0x8, 0x13579BDF);
  failed += check32(RESERVED_BASE + 0x8, 0x2468ACE0);

  if (failed) {
    printf("Radar AXI MMIO smoke test FAILED (%d checks)\n", failed);
    return 1;
  }

  printf("Radar AXI MMIO smoke test PASSED\n");
  return 0;
}
