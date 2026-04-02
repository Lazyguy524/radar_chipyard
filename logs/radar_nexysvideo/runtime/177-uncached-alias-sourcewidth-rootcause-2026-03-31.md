# uncached alias 当前最强根因

- `ExtTLMem` alias 接入后，`MemoryBus` 导出的 `tl_mem` A/D source 宽度从原先的 4-bit 级别抬升到了 7-bit
- 生成文件 `MemoryBus.sv` 中可见：
  - `auto_coupler_to_memory_controller_port_named_tl_mem_buffer_out_a_bits_source` 为 `[6:0]`
- 但板级 harness 到 Nexys MIG 的 TL 接口仍然只接收 4-bit source：
  - `NexysVideoHarness.sv` 将 `_chiptop0_tl_slave_0_a_bits_source[3:0]` 接到 MIG wrapper
  - `XilinxNexysVideoMIG.sv` 中 `auto_buffer_in_a_bits_source` 也是 `[3:0]`
- 因此 alias 版 bitstream 的基础 DDR selfcheck 很可能不是 alias 地址解码本身坏掉，而是 `tl_mem source` 在顶层被截断，导致返回路由失配
- 当前修正方向：把 `TLSourceShrinker` 挪到 alias/normal 两路合流后的 `mem_bypass_xbar` 之后，先把导出的 `tl_mem source` 压回原有可承受范围，再重新验证
