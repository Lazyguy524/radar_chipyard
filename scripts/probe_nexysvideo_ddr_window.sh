#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
uart_tsi_bin="$repo_root/generators/testchipip/uart_tsi/uart_tsi"
log_dir="$repo_root/logs/radar_nexysvideo/runtime"

tty_dev="/dev/ttyUSB0"
baudrate="115200"
prefix="ddr-window-probe"
sleep_s="1"

usage() {
  cat <<'EOF'
Usage:
  scripts/probe_nexysvideo_ddr_window.sh [options]

Options:
  --tty <dev>          UART device, default /dev/ttyUSB0
  --baudrate <rate>    UART baudrate, default 115200
  --prefix <name>      Log filename prefix
  --sleep <sec>        Seconds between write/read operations, default 1
  -h, --help           Show this help

This script performs a deterministic DDR window write/readback probe
around the currently observed bad region near 0x80000980 and a control
window near 0x80000a80.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tty)
      tty_dev="$2"
      shift 2
      ;;
    --baudrate)
      baudrate="$2"
      shift 2
      ;;
    --prefix)
      prefix="$2"
      shift 2
      ;;
    --sleep)
      sleep_s="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

mkdir -p "$log_dir"

if [[ ! -x "$uart_tsi_bin" ]]; then
  echo "uart_tsi binary not found: $uart_tsi_bin" >&2
  exit 1
fi

if [[ ! -e "$tty_dev" ]]; then
  echo "UART device not found: $tty_dev" >&2
  exit 1
fi

stamp="$(date +%Y-%m-%d-%H%M%S)"
log_path="$log_dir/${prefix}-${stamp}.log"

run_uart() {
  timeout 8s "$uart_tsi_bin" "+tty=${tty_dev}" "+baudrate=${baudrate}" +no_hart0_msip "$@" none
}

probe_pair() {
  local addr="$1"
  local value="$2"
  echo "=== WRITE ${addr} ${value} ===" | tee -a "$log_path"
  run_uart "+init_write=${addr}:${value}" 2>&1 | tee -a "$log_path" || true
  sleep "$sleep_s"
  echo "=== READ ${addr} ===" | tee -a "$log_path"
  run_uart "+init_read=${addr}" 2>&1 | tee -a "$log_path" || true
  sleep "$sleep_s"
}

{
  echo "[probe] repo_root=${repo_root}"
  echo "[probe] tty=${tty_dev} baudrate=${baudrate}"
  echo "[probe] log=${log_path}"
  echo "[probe] 提示: 最好在 fresh CPU_RESET 后运行，且不要并行占用同一串口。"
} | tee "$log_path"

# Suspected bad window.
probe_pair 0x8000097c 0x11223344
probe_pair 0x80000980 0xA5A5A5A5
probe_pair 0x80000984 0x99AABBCC
probe_pair 0x80000988 0x13579BDF
probe_pair 0x8000098c 0x2468ACE0
probe_pair 0x80000990 0x0BADF00D
probe_pair 0x80000994 0x55AA55AA

# Control window.
probe_pair 0x80000a7c 0xCAFEBABE
probe_pair 0x80000a80 0x01020304
probe_pair 0x80000a84 0x11121314
probe_pair 0x80000a88 0x21222324
probe_pair 0x80000a8c 0x31323334
probe_pair 0x80000a90 0x41424344

echo "[probe] completed, log saved to ${log_path}" | tee -a "$log_path"
