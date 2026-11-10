# Sourced by the other scripts. Points the unchanged submission code at data/.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NONGNET_DATA_ROOT="$ROOT/data"
export NONGNET_TRAIN_DIR="$ROOT/data/training/2020-2024"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
PY="${PYTHON:-python}"
OUT="$ROOT/outputs"
mkdir -p "$OUT"
