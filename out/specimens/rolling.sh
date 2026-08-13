#!/usr/bin/env bash
# rolling.sh -- stream an exponential moving average
set -euo pipefail

DECAY="${DECAY:-0.92}"

rolling_mean() {
  local acc=0
  while read -r x; do
    acc=$(awk -v d="$DECAY" -v a="$acc" -v x="$x" 'BEGIN{print d*a+(1-d)*x}')
  done
  printf '%.4f\n' "$acc"
}

rolling_mean < samples.txt
