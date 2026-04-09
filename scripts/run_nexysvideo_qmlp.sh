#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec "$repo_root/scripts/run_nexysvideo_uart_tsi.sh" \
  --bin "$repo_root/tests/radar-axi-dma-qmlp.riscv" \
  --log-name "run-qmlp-manual" \
  "$@"
