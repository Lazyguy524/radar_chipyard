#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
uart_tsi_bin="$repo_root/generators/testchipip/uart_tsi/uart_tsi"
default_bin="$repo_root/tests/radar-axi-dma-regression.riscv"
log_dir="$repo_root/logs/radar_nexysvideo/runtime"

tty_dev="/dev/ttyUSB0"
baudrate="921600"
bin_path="$default_bin"
enable_selfcheck=1
extra_plusargs=()
log_name=""

usage() {
  cat <<'EOF'
Usage:
  scripts/run_nexysvideo_uart_tsi.sh [options]

Options:
  --tty <dev>          UART device, default /dev/ttyUSB0
  --baudrate <rate>    UART baudrate, default 921600
  --bin <elf>          ELF/binary to load, default tests/radar-axi-dma-regression.riscv
  --log-name <name>    Log filename prefix, default derived from ELF name
  --no-selfcheck       Disable uart_tsi +selfcheck
  --plusarg <arg>      Extra uart_tsi plusarg, may be repeated
  -h, --help           Show this help

Examples:
  scripts/run_nexysvideo_uart_tsi.sh
  scripts/run_nexysvideo_uart_tsi.sh --bin tests/radar-axi-dma-qmlp.riscv
  scripts/run_nexysvideo_uart_tsi.sh --tty /dev/ttyUSB1 --plusarg +no_hart0_msip
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
    --bin)
      bin_path="$2"
      shift 2
      ;;
    --log-name)
      log_name="$2"
      shift 2
      ;;
    --no-selfcheck)
      enable_selfcheck=0
      shift
      ;;
    --plusarg)
      extra_plusargs+=("$2")
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

if [[ "$bin_path" != "none" ]]; then
  if [[ ! -f "$bin_path" ]]; then
    echo "ELF/binary not found: $bin_path" >&2
    exit 1
  fi
fi

stamp="$(date +%Y-%m-%d-%H%M%S)"
if [[ -z "$log_name" ]]; then
  base_name="$(basename "$bin_path")"
  log_name="${base_name%.*}"
fi
log_path="$log_dir/${log_name}-${stamp}.log"

cmd=("$uart_tsi_bin" "+tty=${tty_dev}" "+baudrate=${baudrate}")
if [[ "$enable_selfcheck" -eq 1 ]]; then
  cmd+=("+selfcheck")
fi
if [[ "${#extra_plusargs[@]}" -gt 0 ]]; then
  cmd+=("${extra_plusargs[@]}")
fi
cmd+=("$bin_path")

{
  echo "[nexysvideo] repo_root=${repo_root}"
  echo "[nexysvideo] tty=${tty_dev} baudrate=${baudrate}"
  echo "[nexysvideo] bin=${bin_path}"
  echo "[nexysvideo] log=${log_path}"
  echo "[nexysvideo] 提示: 如需 fresh 状态，请先按板上的 CPU_RESET。"
  echo "[nexysvideo] command=${cmd[*]}"
  stdbuf -oL -eL "${cmd[@]}"
} | tee "$log_path"

echo "[nexysvideo] completed, log saved to $log_path"
