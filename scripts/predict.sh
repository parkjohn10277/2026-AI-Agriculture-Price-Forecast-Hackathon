#!/usr/bin/env bash
# Replay the submitted weights:  scripts/predict.sh [short|long1|long2|all]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
tracks=("${1:-all}"); [[ "${tracks[0]}" == all ]] && tracks=(short long1 long2)
for t in "${tracks[@]}"; do
  "$PY" "$ROOT/model/predict.py" --track "$t" \
    --weights "$ROOT/tracks/$t/weights.joblib" --config "$ROOT/tracks/$t/config.json" \
    --cases "$ROOT/data/input/$t/cases.json" \
    --output "$OUT/$t.csv" --audit "$OUT/${t}_audit.json"
done
