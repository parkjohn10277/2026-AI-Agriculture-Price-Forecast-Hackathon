#!/usr/bin/env bash
# Place the competition data next to the code.
#
#   scripts/setup_data.sh <submission folder or v11_zero_linux.zip>
#
# The organizer's data are NOT redistributed in this repository. This script
# unpacks them from the original submission bundle (전체 학습 데이터.zip and the
# three 입력 자료.zip files) into data/, which is git-ignored:
#
#   data/training/2020-2024/...   2020–2024 training bundle (shared by all tracks)
#   data/input/{short,long1,long2}/cases.json, input-manifest.json, by_case/C01..C12/
set -euo pipefail

SRC="${1:?usage: scripts/setup_data.sh <v11_zero_linux folder or .zip>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$ROOT/data"
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT

if [[ -f "$SRC" && "$SRC" == *.zip ]]; then
  unzip -q "$SRC" -d "$TMP/bundle"
  SRC="$(find "$TMP/bundle" -maxdepth 2 -type d -name '10일 예측 모델' -exec dirname {} \; | head -1)"
fi
[[ -d "$SRC/10일 예측 모델" ]] || { echo "error: '$SRC' does not contain '10일 예측 모델/'" >&2; exit 1; }

mkdir -p "$DATA/training" "$DATA/input"
unzip -q -o "$SRC/10일 예측 모델/전체 학습 데이터.zip" -d "$DATA/training"
for pair in "short:10일 예측 모델" "long1:2순 후 모델" "long2:3순 후 모델"; do
  track="${pair%%:*}"; folder="${pair#*:}"
  mkdir -p "$DATA/input/$track"
  unzip -q -o "$SRC/$folder/입력 자료.zip" -d "$DATA/input/$track"
done

echo "training: $(find "$DATA/training/2020-2024" -type f | wc -l | tr -d ' ') files"
for t in short long1 long2; do
  echo "input/$t: $(find "$DATA/input/$t" -type f | wc -l | tr -d ' ') files"
done
