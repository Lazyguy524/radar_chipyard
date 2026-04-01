#include "radar_axi_dma_common.h"

static int dma_wait_done_verbose(const char *name, uintptr_t sr_off)
{
  unsigned long timeout = DMA_TIMEOUT_CYCLES;

  while (timeout-- > 0UL) {
    uint32_t status = mmio_read32(DMA_BASE_ADDR + sr_off);

    if ((status & DMASR_ERR_MASK) != 0u) {
      printf("%s error: DMASR=0x%08x\n", name, status);
      if (sr_off == MM2S_DMASR) {
        dma_dump_channel_regs(name, MM2S_DMACR, MM2S_DMASR, MM2S_SA, MM2S_SA_MSB, MM2S_LENGTH);
      } else {
        dma_dump_channel_regs(name, S2MM_DMACR, S2MM_DMASR, S2MM_DA, S2MM_DA_MSB, S2MM_LENGTH);
      }
      dma_dump_buffers_preview();
      mmio_write32(DMA_BASE_ADDR + sr_off, DMASR_CLEAR_MASK);
      return -1;
    }

    if ((status & DMASR_IRQ_MASK) != 0u) {
      mmio_write32(DMA_BASE_ADDR + sr_off, DMASR_IRQ_MASK);
      return 0;
    }

    if ((status & DMASR_IDLE) != 0u && (status & DMASR_HALTED) == 0u) {
      return 0;
    }
  }

  printf("%s timeout: DMASR=0x%08x\n", name, mmio_read32(DMA_BASE_ADDR + sr_off));
  if (sr_off == MM2S_DMASR) {
    dma_dump_channel_regs(name, MM2S_DMACR, MM2S_DMASR, MM2S_SA, MM2S_SA_MSB, MM2S_LENGTH);
  } else {
    dma_dump_channel_regs(name, S2MM_DMACR, S2MM_DMASR, S2MM_DA, S2MM_DA_MSB, S2MM_LENGTH);
  }
  dma_dump_buffers_preview();
  return -1;
}

static int dma_reset_channel_verbose(const char *name, uintptr_t cr_off, uintptr_t sr_off)
{
  printf("%s reset begin\n", name);
  if (cr_off == MM2S_DMACR) {
    dma_dump_channel_regs(name, cr_off, sr_off, MM2S_SA, MM2S_SA_MSB, MM2S_LENGTH);
  } else {
    dma_dump_channel_regs(name, cr_off, sr_off, S2MM_DA, S2MM_DA_MSB, S2MM_LENGTH);
  }

  if (dma_reset_channel(name, cr_off, sr_off) != 0) {
    return -1;
  }

  printf("%s reset done\n", name);
  if (cr_off == MM2S_DMACR) {
    dma_dump_channel_regs(name, cr_off, sr_off, MM2S_SA, MM2S_SA_MSB, MM2S_LENGTH);
  } else {
    dma_dump_channel_regs(name, cr_off, sr_off, S2MM_DA, S2MM_DA_MSB, S2MM_LENGTH);
  }
  return 0;
}

static void dma_start_simple_s2mm_verbose(uintptr_t dst_addr, uint32_t length)
{
  mmio_write32(DMA_BASE_ADDR + S2MM_DMASR, DMASR_CLEAR_MASK);
  dma_dump_channel_regs("S2MM after clear", S2MM_DMACR, S2MM_DMASR, S2MM_DA, S2MM_DA_MSB, S2MM_LENGTH);
  mmio_write32(DMA_BASE_ADDR + S2MM_DMACR, DMACR_RUN_MASK);
  dma_dump_channel_regs("S2MM after RS", S2MM_DMACR, S2MM_DMASR, S2MM_DA, S2MM_DA_MSB, S2MM_LENGTH);
  if (dma_wait_running("S2MM", S2MM_DMASR) != 0) {
    return;
  }
  mmio_write32(DMA_BASE_ADDR + S2MM_DA, (uint32_t)dst_addr);
  dma_dump_channel_regs("S2MM after DA", S2MM_DMACR, S2MM_DMASR, S2MM_DA, S2MM_DA_MSB, S2MM_LENGTH);
  mmio_write32(DMA_BASE_ADDR + S2MM_DA_MSB, 0u);
  dma_dump_channel_regs("S2MM after DA_MSB", S2MM_DMACR, S2MM_DMASR, S2MM_DA, S2MM_DA_MSB, S2MM_LENGTH);
  mmio_write32(DMA_BASE_ADDR + S2MM_LENGTH, length);
  dma_dump_channel_regs("S2MM after start", S2MM_DMACR, S2MM_DMASR, S2MM_DA, S2MM_DA_MSB, S2MM_LENGTH);
}

static void dma_start_simple_mm2s_verbose(uintptr_t src_addr, uint32_t length)
{
  mmio_write32(DMA_BASE_ADDR + MM2S_DMASR, DMASR_CLEAR_MASK);
  dma_dump_channel_regs("MM2S after clear", MM2S_DMACR, MM2S_DMASR, MM2S_SA, MM2S_SA_MSB, MM2S_LENGTH);
  mmio_write32(DMA_BASE_ADDR + MM2S_DMACR, DMACR_RUN_MASK);
  dma_dump_channel_regs("MM2S after RS", MM2S_DMACR, MM2S_DMASR, MM2S_SA, MM2S_SA_MSB, MM2S_LENGTH);
  if (dma_wait_running("MM2S", MM2S_DMASR) != 0) {
    return;
  }
  mmio_write32(DMA_BASE_ADDR + MM2S_SA, (uint32_t)src_addr);
  dma_dump_channel_regs("MM2S after SA", MM2S_DMACR, MM2S_DMASR, MM2S_SA, MM2S_SA_MSB, MM2S_LENGTH);
  mmio_write32(DMA_BASE_ADDR + MM2S_SA_MSB, 0u);
  dma_dump_channel_regs("MM2S after SA_MSB", MM2S_DMACR, MM2S_DMASR, MM2S_SA, MM2S_SA_MSB, MM2S_LENGTH);
  mmio_write32(DMA_BASE_ADDR + MM2S_LENGTH, length);
  dma_dump_channel_regs("MM2S after start", MM2S_DMACR, MM2S_DMASR, MM2S_SA, MM2S_SA_MSB, MM2S_LENGTH);
}

int main(void)
{
  printf("AXI DMA loopback test start\n");
  printf("TX_BUFFER_ADDR=0x%08lx RX_BUFFER_ADDR=0x%08lx EVICT_BUFFER_ADDR=0x%08lx\n",
         (unsigned long)TX_BUFFER_ADDR,
         (unsigned long)RX_BUFFER_ADDR,
         (unsigned long)EVICT_BUFFER_ADDR);

  fill_tx_pattern_words(TEST_WORD_COUNT, 0xA5A50000u);
  clear_rx_words(TEST_WORD_COUNT);
  dma_prepare_cpu_to_device("Pre-DMA");

  if (dma_reset_channel_verbose("MM2S", MM2S_DMACR, MM2S_DMASR) != 0) return 1;
  if (dma_reset_channel_verbose("S2MM", S2MM_DMACR, S2MM_DMASR) != 0) return 1;

  dma_start_simple_s2mm_verbose(RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT);
  dma_start_simple_mm2s_verbose(TX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT);

  if (dma_wait_done_verbose("MM2S", MM2S_DMASR) != 0) return 1;
  if (dma_wait_done_verbose("S2MM", S2MM_DMASR) != 0) return 1;

  dma_prepare_device_to_cpu("Post-DMA");

  if (compare_buffers_words(TEST_WORD_COUNT, "Loopback") >= 0) {
    printf("AXI DMA loopback FAILED\n");
    return 1;
  }

  printf("AXI DMA loopback PASSED\n");
  return 0;
}
