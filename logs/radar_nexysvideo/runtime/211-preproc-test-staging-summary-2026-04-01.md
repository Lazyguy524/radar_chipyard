# Preproc board-test staging summary

- Bitstream under test: `207-fpga-bitstream-dma-preproc-2026-04-01.log`
- Regression run: `209-run-integrated-regression-on-preproc-bitstream-2026-04-01.log`
- Regression result: `PASSED`
- Follow-up preproc run: `210-run-dma-preproc-on-preproc-bitstream-2026-04-01.log`
- Preproc result in same power-on session: stuck after `Connection succeeded`, did not enter `selfcheck`
- Interpretation: this matches the known multi-ELF `uart_tsi` session issue; next action is a fresh `CPU_RESET` and then rerun `radar-axi-dma-preproc.riscv`
