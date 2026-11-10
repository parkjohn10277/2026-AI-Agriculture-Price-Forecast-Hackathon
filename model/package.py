"""Build the four submission files for one track in the organiser's standard (model.zip / training.zip / input.zip /
output.xlsx, plus output.csv and manifest.json for checking), then replay the packaged model from the extracted ZIPs and
check that the replayed CSV is byte-identical.

Usage (from this folder):
  python package.py --track short --weights retrained.joblib --rules config.json --cases ../input/cases.json --destination ../rebuilt_short
  python package.py --track short --reuse-weights <packaged model/weights.joblib> --rules <packaged model/config.json> --cases <cases.json> --destination ...
    (--reuse-weights ships an already packaged one-track weights file byte for byte instead of re-dumping it)

Layout expected by the packaged model (data.py resolves it automatically): model/ (code, config.json, weights.joblib),
training/2020-2024/... (training.zip), input/by_case/... and input/cases.json (input.zip) extracted next to each other; run
from model/. predict.py takes origins and targets from input/cases.json. Training uses 2020-2024 only; later files are
inference inputs and every feature uses observations strictly before the origin.
"""
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, tempfile, time
from pathlib import Path
import joblib
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data as D
from workbook import write_workbook, write_zip

CODE_FILES = ["script.py", "split_slim.py", "data.py", "harness.py", "extra_features2.py", "extra_features3.py", "train.py", "predict.py",
              "workbook.py", "package.py", "requirements.txt", "validate_2020_2024.py", "validation_2020_2024.json", "official_short_template.xlsx"]
TRAIN_FILES = [
    "가격_일별_2020_2024.csv",
    "Supplementary/물량_일별_2020_2024.csv",
    "Supplementary/날씨와공휴일_2020_2024/weather_daily.csv",
    "Supplementary/날씨와공휴일_2020_2024/public_holidays.csv",
    "Supplementary/날씨와공휴일_2020_2024/README.md",
    "Supplementary/날씨와공휴일_2020_2024/DATA_DICTIONARY.json",
    "Supplementary/날씨와공휴일_2020_2024/TRAINING_MANIFEST.json",
    "Supplementary/시장별_경락정보_2020_2024/origin_daily.csv",
    "Supplementary/시장별_경락정보_2020_2024/garak_daily.csv",
    "Supplementary/시장별_경락정보_2020_2024/wholesale_daily.csv",
    "Supplementary/시장별_경락정보_2020_2024/README.md",
    "Supplementary/시장별_경락정보_2020_2024/DATA_DICTIONARY.json",
    "Supplementary/시장별_경락정보_2020_2024/TRAINING_MANIFEST.json",
]
RULE_KEYS = ("rules", "chuseok_short", "chuseok_block", "holiday_short", "holiday_block", "holiday_guard")
TRACK_KO = {"short": "10일 예측", "long1": "2순 후 예측", "long2": "3순 후 예측"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def run_predict(model_dir, track, out_csv, audit):
    env = {k: v for k, v in os.environ.items() if not k.startswith("NONGNET_")}
    cmd = [sys.executable, "predict.py", "--track", track, "--output", str(out_csv), "--audit", str(audit)]
    subprocess.run(cmd, cwd=model_dir, check=True, env=env, capture_output=True, text=True)


def check_output(raw, track, cases):
    """Format check against the official cases: identities, 5 positive prices per row."""
    import csv, io
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    identity = 3 if track == "short" else 4
    expected = []
    for case in cases:
        if track == "short":
            dates = sorted({t["date"] for t in case["targets"]})
            expected += [[case["caseId"], case["origin"], d] for d in dates]
        else:
            t = case["targets"][0]
            expected.append([case["caseId"], case["origin"], t.get("period_start", t.get("start")), t.get("period_end", t.get("end"))])
    body = rows[1:]
    if [r[:identity] for r in body] != expected:
        raise ValueError("출력의 사례·날짜 식별자가 공식 cases.json과 다릅니다.")
    n_prices = 0
    for r in body:
        vals = [float(x) for x in r[identity:identity + 5]]
        if len(vals) != 5 or any(not (v > 0) for v in vals):
            raise ValueError("가격 열은 5개의 양수여야 합니다.")
        n_prices += 5
    return {"rows": len(body), "prices": n_prices, "sha256": digest(raw)}


def stage_layout(root, model_files, weights_bytes, cases_bytes, input_files):
    (root / "model").mkdir(parents=True)
    for name, content in model_files.items():
        (root / "model" / name).write_bytes(content)
    (root / "model" / "weights.joblib").write_bytes(weights_bytes)
    for rel in TRAIN_FILES:
        dst = root / "training" / "2020-2024" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(D.TRAIN_DIR / rel, dst)
    for rel, content in input_files.items():
        dst = root / "input" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(content)
    (root / "input" / "cases.json").write_bytes(cases_bytes)



def build(track, weights_path, rules_path, cases_path, destination, verify=True, reuse=False):
    t0 = time.time()
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    source_input = Path(cases_path).resolve().parent
    input_files = {str(p.relative_to(source_input)): p.read_bytes()
                   for p in sorted(source_input.rglob("*"))
                   if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith(".")}
    full = joblib.load(weights_path)
    rules = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    cfg = dict(rules)
    for k in RULE_KEYS:
        cfg[k] = rules.get(k, {})
    if not reuse:
        cfg["version"] = f'{full["version"].split("+rules:")[0]}+rules:{Path(rules_path).stem}'
    if reuse:              # already a packaged one-track file: keep its bytes (and hash) unchanged
        assert set(full["banks"]) == {track}, "--reuse-weights needs a one-track packaged weights file"
        sub = full
        weights_bytes = Path(weights_path).read_bytes()
    else:
        sub = {"version": cfg["version"], "config": cfg, "banks": {track: full["banks"][track]}}
        del full
        tmp_w = destination / "_weights_tmp.joblib"
        joblib.dump(sub, tmp_w, compress=3)
        weights_bytes = tmp_w.read_bytes()
        tmp_w.unlink()
    model_files = {name: (HERE / name).read_bytes() for name in CODE_FILES
                   if name != "official_short_template.xlsx" or track == "short"}
    model_files["config.json"] = json_bytes(dict(cfg, package_track=track))   # default track for script.py
    predict_command = "python script.py --output reproduced.csv"
    train_command = "python train.py --out retrained.joblib"
    model_files["REPRODUCE.md"] = (HERE / "REPRODUCE.md").read_bytes()
    model_files["README.md"] = (HERE / "README.md").read_bytes()
    with tempfile.TemporaryDirectory(prefix="nongnet-pack-") as temp:
        root = Path(temp)
        stage_layout(root, model_files, weights_bytes, Path(cases_path).read_bytes(), input_files)
        run_predict(root / "model", track, root / "output.csv", root / "prediction-audit.json")
        output = (root / "output.csv").read_bytes()
        audit = json.loads((root / "prediction-audit.json").read_text(encoding="utf-8"))
    checked = check_output(output, track, cases)
    cutoff_a = next(v["cutoff_end"] for k, v in sub["banks"][track].items() if k.startswith("A:"))
    cutoff_b = next(v["cutoff_end"] for k, v in sub["banks"][track].items() if k.startswith("B:"))
    reproducibility = {
        "schema": "nongnet-reproduction-v1", "track": track, "model_version": cfg["version"],
        "python": sys.version.split()[0], "platform": platform.platform(),
        "dependencies": (HERE / "requirements.txt").read_text(encoding="utf-8").strip().splitlines(),
        "randomness": "ExtraTrees / HistGradientBoosting with random_state=0; ExtraTrees n_jobs=4.",
        "training": {"data": "training/2020-2024 (price, settled volume, origin-market grade price/arrivals, Garak and national settlement, weather, holidays)",
                     "origins": f'{cfg["origins_start"]} .. 2024-12-30', "bank_cutoffs": {"A (origins <= 2024-12-31)": cutoff_a, "B (later origins)": cutoff_b},
                     "command_from_model_directory": train_command,
                     "slope_implementation": "short: stabilized OLS; long banks: centered np.polyfit. Inference remains stabilized OLS for all tracks.",
                     "files": [{"path": f"training/2020-2024/{rel}", "sha256": digest((D.TRAIN_DIR / rel).read_bytes())} for rel in TRAIN_FILES]},
        "inference": {"data": "input/cases.json and case-specific observations selected by input/input-manifest.json",
                      "command_from_model_directory": predict_command, "strict_before_origin": True,
                      "output_rows": checked["rows"], "output_prices": checked["prices"], "output_csv_sha256": checked["sha256"],
                      "files": [{"path": f"input/{rel}", "sha256": digest(content)} for rel, content in sorted(input_files.items())]},
        "rules": cfg["rules"][track],
        "cases": [{"case_id": c["caseId"], "origin": c["origin"], "weights_cutoff": cutoff_a if c["origin"] <= "2024-12-31" else cutoff_b} for c in cases],
        "files": [{"path": name, "bytes": len(content), "sha256": digest(content)} for name, content in sorted(model_files.items())]
                 + [{"path": "weights.joblib", "bytes": len(weights_bytes), "sha256": digest(weights_bytes)}],
    }
    model_files["reproducibility.json"] = json_bytes(reproducibility)
    model_files["weights.joblib"] = weights_bytes
    write_zip(destination / "model.zip", model_files)
    write_zip(destination / "training.zip",
              {f"2020-2024/{rel}": (D.TRAIN_DIR / rel).read_bytes() for rel in TRAIN_FILES}
              | {"manifest.json": json_bytes({"period": "2020-01-01..2024-12-31", "training_allowed": True, "price_units": "as provided; no conversion",
                                              "files": reproducibility["training"]["files"], "bank_cutoffs": reproducibility["training"]["bank_cutoffs"]})})
    write_zip(destination / "input.zip", input_files)
    (destination / "output.csv").write_bytes(output)
    write_workbook(destination / "output.xlsx", output, track)
    files = [{"filename": name, "bytes": (destination / name).stat().st_size, "sha256": digest((destination / name).read_bytes())}
             for name in ["model.zip", "training.zip", "input.zip", "output.xlsx", "output.csv"]]
    (destination / "manifest.json").write_bytes(json_bytes({"track": track, "model_version": cfg["version"], "validation": checked, "files": files,
                                                            "submit": ["model.zip", "training.zip", "input.zip", "output.xlsx"]}))
    print(f"[{track}] four files written to {destination} ({time.time()-t0:.0f}s)", flush=True)
    if verify:
        verify_package(destination, track)


def verify_package(destination, track):
    """Extract the three ZIPs into a clean folder, replay the packaged model and compare with output.csv byte for byte."""
    import zipfile
    destination = Path(destination)
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="nongnet-verify-") as temp:
        root = Path(temp)
        for kind in ("model", "training", "input"):
            with zipfile.ZipFile(destination / f"{kind}.zip") as z:
                z.extractall(root / kind)
        # replay through the documented entry point, started from outside model/ (checks cwd independence)
        env = {k: v for k, v in os.environ.items() if not k.startswith("NONGNET_")}
        subprocess.run([sys.executable, str(root / "model" / "script.py"), "--output", str(root / "reproduced.csv")],
                       cwd=root, check=True, env=env, capture_output=True, text=True)
        (root / "model" / "reproduced.csv").write_bytes((root / "reproduced.csv").read_bytes())
        same = (root / "model" / "reproduced.csv").read_bytes() == (destination / "output.csv").read_bytes()
    print(f"[{track}] replay from extracted ZIPs {'IDENTICAL' if same else 'DIFFERENT'} ({time.time()-t0:.0f}s)", flush=True)
    if not same:
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True, choices=["short", "long1", "long2"])
    ap.add_argument("--weights", default=str(HERE / "weights.joblib"))
    ap.add_argument("--rules", default=str(HERE / "config.json"), help="rule file whose rules/chuseok_*/holiday_* keys are used")
    ap.add_argument("--cases", required=True, help="official cases.json for this track (from the starter example)")
    ap.add_argument("--destination", required=True)
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--reuse-weights", default="", help="packaged one-track weights.joblib to ship unchanged (instead of --weights)")
    a = ap.parse_args()
    build(a.track, a.reuse_weights or a.weights, a.rules, a.cases, a.destination, verify=not a.no_verify, reuse=bool(a.reuse_weights))


if __name__ == "__main__":
    main()
