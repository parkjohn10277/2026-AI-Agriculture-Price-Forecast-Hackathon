"""Compare outputs/ against the submitted predictions.

    python scripts/verify.py              # saved-weight replay (outputs/<track>.csv)
    python scripts/verify.py --retrained  # fresh retraining  (outputs/<track>_retrained.csv)

Exact text comparison of every price; reports the CSV SHA-256 against tracks/<track>/reproducibility.json.
"""
import argparse, csv, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ["배추", "무", "양파", "깐마늘", "건고추"]


def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrained", action="store_true")
    a = ap.parse_args()
    ok = True
    for t in ("short", "long1", "long2"):
        out = ROOT / "outputs" / (f"{t}_retrained.csv" if a.retrained else f"{t}.csv")
        ref = ROOT / "predictions" / f"{t}_predictions.csv"
        if not out.exists():
            print(f"{t:6s}  missing {out.relative_to(ROOT)}"); ok = False; continue
        got, exp = rows(out), rows(ref)
        n = same = 0; worst = 0.0
        for g, e in zip(got, exp):
            for it in ITEMS:
                n += 1
                if g[it] == e[it]:
                    same += 1
                else:
                    worst = max(worst, abs(float(g[it]) - float(e[it])) / float(e[it]) * 100)
        recorded = json.loads((ROOT / "tracks" / t / "reproducibility.json").read_text(encoding="utf-8"))["inference"]["output_csv_sha256"]
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        match = "sha256 match" if digest == recorded else "sha256 differs"
        print(f"{t:6s}  {same}/{n} prices identical  max diff {worst:.3f}%  {match}")
        ok &= (same == n and len(got) == len(exp))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
