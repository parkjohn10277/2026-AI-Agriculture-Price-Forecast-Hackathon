"""Confirm that model/ and tracks/ are byte-identical to the submitted packages.

Each tracks/<track>/reproducibility.json lists the SHA-256 of every file in that
track's submitted model.zip. Shared code lives once in model/; per-track files
(config.json, weights.joblib) live in tracks/<track>/.

    python scripts/check_hashes.py
"""
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PER_TRACK = {"config.json", "weights.joblib"}
RENAMED = {"README.md": "PACKAGE_README.md", "REPRODUCE.md": "PACKAGE_REPRODUCE.md"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


bad = 0
for track in ("short", "long1", "long2"):
    record = json.loads((ROOT / "tracks" / track / "reproducibility.json").read_text(encoding="utf-8"))
    ok = 0
    for f in record["files"]:
        name = f["path"]
        if name in PER_TRACK:
            path = ROOT / "tracks" / track / name
        elif name in RENAMED:
            path = ROOT / "tracks" / track / RENAMED[name]
        else:
            path = ROOT / "model" / name
        if path.exists() and sha(path) == f["sha256"]:
            ok += 1
        else:
            bad += 1
            print(f"  MISMATCH {track}: {name} -> {path.relative_to(ROOT)}")
    print(f"{track:6s}  {ok}/{len(record['files'])} files match the submitted model.zip")
sys.exit(1 if bad else 0)
