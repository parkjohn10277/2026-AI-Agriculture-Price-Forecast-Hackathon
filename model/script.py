"""Submission entry point: `python script.py [--output output.csv]` runs predict.py for this package's track.

Works from any working directory. Data are found next to this file (see REPRODUCE.md):
model/ (this folder), training/2020-2024/, input/<year>/ and input/cases.json.
Unknown arguments (e.g. the starter example's --history) are ignored with a warning."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", default="", choices=["", "short", "long1", "long2"], help="default: the track this package was built for")
    ap.add_argument("--output", default="output.csv")
    ap.add_argument("--cases", default="")
    ap.add_argument("--audit", default="prediction-audit.json")
    a, unknown = ap.parse_known_args()
    if unknown:
        print("warning: ignoring arguments", unknown, file=sys.stderr)
    track = a.track or json.loads((HERE / "config.json").read_text(encoding="utf-8")).get("package_track", "")
    if not track:
        raise SystemExit("config.json has no package_track; pass --track short|long1|long2")
    args = ["predict.py", "--track", track, "--output", str(Path(a.output).resolve())]
    if a.cases:
        args += ["--cases", str(Path(a.cases).resolve())]
    if a.audit:
        args += ["--audit", str(Path(a.audit).resolve())]
    sys.argv = args
    import predict
    predict.main()


if __name__ == "__main__":
    main()
