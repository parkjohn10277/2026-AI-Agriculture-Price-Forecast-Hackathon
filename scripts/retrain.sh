#!/usr/bin/env bash
# Retrain all banks from the 2020–2024 bundle, then predict every track with the new weights.
#   scripts/retrain.sh            (≈2–3 min on a 4-thread laptop CPU)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
"$PY" "$ROOT/model/train.py" --out "$OUT/retrained.joblib"
for t in short long1 long2; do
  "$PY" "$ROOT/model/predict.py" --track "$t" --weights "$OUT/retrained.joblib" \
    --config "$ROOT/tracks/$t/config.json" --cases "$ROOT/data/input/$t/cases.json" \
    --output "$OUT/${t}_retrained.csv"
  "$PY" "$ROOT/model/split_slim.py" "$OUT/retrained.joblib" "$ROOT/tracks/$t/config.json" "$t" "$OUT/${t}_weights.joblib"
done
