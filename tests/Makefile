#################################
# RISCV Toolchain
#################################

TARGET = riscv64-unknown-elf

GCC = $(TARGET)-gcc
CXX = $(TARGET)-g++
CP = $(TARGET)-objcopy
OBJDUMP = $(TARGET)-objdump
DG = $(TARGET)-gdb
SIZE = $(TARGET)-size
HOSTCC ?= gcc


#################################
# Flags
#################################

# SoC Settings
# Keep the historical default ABI for the general test suite. The current
# bundled riscv-tools install only provides a single hard-float newlib/libgloss
# variant, so the no-FPU Nexys Video bring-up binaries are built separately
# with a freestanding runtime below.
ARCH ?= rv64imafdc
ABI ?= lp64d
ARCHFLAGS = -march=$(ARCH) -mabi=$(ABI)

BRINGUP_ARCH ?= rv64imac_zicsr_zifencei
BRINGUP_ABI ?= lp64
BRINGUP_ARCHFLAGS = -march=$(BRINGUP_ARCH) -mabi=$(BRINGUP_ABI)
BRINGUP_CMODEL = -mcmodel=medany
BRINGUP_CFLAGS = -std=gnu99 -O2 -fno-common -fno-builtin-printf -Wall -ffreestanding $(BRINGUP_ARCHFLAGS) $(BRINGUP_CMODEL)
BRINGUP_LDFLAGS = -static -nostdlib -nostartfiles $(BRINGUP_ARCHFLAGS) $(BRINGUP_CMODEL)

CFLAGS  = -std=gnu99 -O2 -fno-common -fno-builtin-printf -Wall
CFLAGS += $(ARCHFLAGS)
LDFLAGS = -static
LDFLAGS += $(ARCHFLAGS)

include libgloss.mk

PROGRAMS = pwm blkdev accum charcount nic-loopback big-blkdev pingd \
           streaming-passthrough streaming-fir nvdla spiflashread spiflashwrite fft gcd \
           hello mt-hello symmetric radar-axi-mmio-smoke radar-axi-dma-loopback \
           radar-axi-dma-consistency radar-axi-dma-regression radar-axi-dma-uncached-alias \
           radar-axi-dma-preproc radar-axi-dma-qmlp radar-qmlp-cpu-only radar-qmlp-cpu-profile radar-axi-dma-qmlp-e2e \
           radar-axi-dma-qmlp-validation radar-axi-dma-qmlp-chain-validation radar-axi-dma-qmlp-profile radar-axi-dma-qmlp-mmio-profile \
           radar-axi-dma-feature21 radar-axi-dma-feature21-golden


.DEFAULT_GOAL := default


#################################
# Build
#################################

spiflash.img: spiflash.py
	python3 $<

%.o: %.S
	$(GCC) $(CFLAGS) -D__ASSEMBLY__=1 -c $< -o $@

%.o: %.c mmio.h spiflash.h
	$(GCC) $(CFLAGS) -c $< -o $@

%.riscv: %.o $(libgloss)
	$(GCC) $(LDFLAGS) $< -o $@

%.dump: %.riscv
	$(OBJDUMP) -D $< > $@

%.bringup.o: %.c
	$(GCC) $(BRINGUP_CFLAGS) -c $< -o $@

%.bringup.o: %.S
	$(GCC) $(BRINGUP_CFLAGS) -D__ASSEMBLY__=1 -c $< -o $@

BRINGUP_RUNTIME = htif_nolib.bringup.o htif_crt0.bringup.o
BRINGUP_LDS = ../toolchains/libgloss/util/htif.ld
RADAR_QMLP_CPU_PROFILE_USE_XRADAR_FALLBACK ?= 0
QMLP_VALIDATION_HEADERS = radar_qmlp_validation_data.h \
	../releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/hardware_validation_20260414/large_golden/test_inputs_int8.h \
	../releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/hardware_validation_20260414/large_golden/test_logits_int32.h \
	../releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/hardware_validation_20260414/boundary_cases/boundary_inputs_int8.h \
	../releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/hardware_validation_20260414/boundary_cases/boundary_logits_int32.h

hello.riscv: hello.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-mmio-smoke.riscv: radar-axi-mmio-smoke.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-loopback.riscv: radar-axi-dma-loopback.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-loopback-cacheprobe.riscv: radar-axi-dma-loopback-cacheprobe.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-loopback-cachemaint.riscv: radar-axi-dma-loopback-cachemaint.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-consistency.riscv: radar-axi-dma-consistency.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-regression.riscv: radar-axi-dma-regression.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-uncached-alias.riscv: radar-axi-dma-uncached-alias.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-preproc.riscv: radar-axi-dma-preproc.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-feature21.riscv: radar-axi-dma-feature21.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-feature21-golden.riscv: radar-axi-dma-feature21-golden.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-feature21-golden.bringup.o: radar-axi-dma-feature21-golden.c radar_feature21_golden_subset.h
	$(GCC) $(BRINGUP_CFLAGS) -c $< -o $@

radar-axi-dma-qmlp.riscv: radar-axi-dma-qmlp.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-qmlp-e2e.riscv: radar-axi-dma-qmlp-e2e.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-qmlp-validation.riscv: radar-axi-dma-qmlp-validation.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-qmlp-validation.bringup.o: radar-axi-dma-qmlp-validation.c $(QMLP_VALIDATION_HEADERS)
	$(GCC) $(BRINGUP_CFLAGS) -c $< -o $@

radar-axi-dma-qmlp-chain-validation.riscv: radar-axi-dma-qmlp-chain-validation.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-qmlp-chain-validation.bringup.o: radar-axi-dma-qmlp-chain-validation.c radar-axi-dma-qmlp-validation.c $(QMLP_VALIDATION_HEADERS)
	$(GCC) $(BRINGUP_CFLAGS) -c $< -o $@

radar-axi-dma-qmlp-profile.riscv: radar-axi-dma-qmlp-profile.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-qmlp-profile.bringup.o: radar-axi-dma-qmlp-profile.c $(QMLP_VALIDATION_HEADERS)
	$(GCC) $(BRINGUP_CFLAGS) -c $< -o $@

radar-axi-dma-qmlp-mmio-profile.riscv: radar-axi-dma-qmlp-mmio-profile.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-axi-dma-qmlp-mmio-profile.bringup.o: radar-axi-dma-qmlp-mmio-profile.c $(QMLP_VALIDATION_HEADERS)
	$(GCC) $(BRINGUP_CFLAGS) -c $< -o $@

radar-qmlp-cpu-only.riscv: radar-qmlp-cpu-only.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-qmlp-cpu-profile.riscv: radar-qmlp-cpu-profile.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-qmlp-cpu-profile.bringup.o: radar-qmlp-cpu-profile.c radar_xradar_fallback.h
	$(GCC) $(BRINGUP_CFLAGS) -DRADAR_QMLP_CPU_PROFILE_USE_XRADAR_FALLBACK=$(RADAR_QMLP_CPU_PROFILE_USE_XRADAR_FALLBACK) -c $< -o $@

radar-xradar-rocc-smoke.riscv: radar-xradar-rocc-smoke.bringup.o $(BRINGUP_RUNTIME)
	$(GCC) $(BRINGUP_LDFLAGS) -T $(BRINGUP_LDS) $^ -lgcc -o $@

radar-xradar-rocc-smoke.bringup.o: radar-xradar-rocc-smoke.c radar_xradar_fallback.h
	$(GCC) $(BRINGUP_CFLAGS) -c $< -o $@


#################################
# Recipes
#################################

.PHONY: clean
clean:
	rm -f *.riscv *.o *.dump *.bringup.o
	$(if $(libgloss),rm -rf $(libgloss_builddir)/)

.PHONY: default
default: $(addsuffix .riscv, $(PROGRAMS)) spiflash.img

.PHONY: dumps
dumps: $(addsuffix .dump, $(PROGRAMS))

.PHONY: bringup-binaries
bringup-binaries: hello.riscv radar-axi-mmio-smoke.riscv radar-axi-dma-loopback.riscv radar-axi-dma-consistency.riscv radar-axi-dma-regression.riscv radar-axi-dma-uncached-alias.riscv radar-axi-dma-preproc.riscv radar-axi-dma-feature21.riscv radar-axi-dma-feature21-golden.riscv radar-axi-dma-qmlp.riscv radar-qmlp-cpu-only.riscv radar-qmlp-cpu-profile.riscv radar-axi-dma-qmlp-e2e.riscv radar-axi-dma-qmlp-validation.riscv radar-axi-dma-qmlp-chain-validation.riscv radar-axi-dma-qmlp-profile.riscv radar-axi-dma-qmlp-mmio-profile.riscv

.PHONY: xradar-host-test
xradar-host-test:
	$(HOSTCC) -std=gnu99 -O2 -Wall -Wextra -I. radar-xradar-fallback-host.c -o /tmp/radar-xradar-fallback-host
	/tmp/radar-xradar-fallback-host

.PHONY: xradar-static-model
xradar-static-model:
	$(HOSTCC) -std=gnu99 -O2 -Wall -Wextra -I. radar-xradar-static-model-host.c -o /tmp/radar-xradar-static-model-host
	/tmp/radar-xradar-static-model-host
