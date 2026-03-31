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
           hello mt-hello symmetric radar-axi-mmio-smoke radar-axi-dma-loopback


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
bringup-binaries: hello.riscv radar-axi-mmio-smoke.riscv radar-axi-dma-loopback.riscv
