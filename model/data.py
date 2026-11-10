"""Training data loading (2020-2024 only) and case-specific inference inputs.
predict.py selects the physical case directory through inference_case.
Legacy input/<year>/ folders and explicit NONGNET_INFER_DIR overrides remain supported.
Observed features use dates strictly before each origin.
"""
import os, sys
from contextlib import contextmanager
from pathlib import Path
import numpy as np, pandas as pd

def _find_root():
    """Folder holding the training data: next to model/ (separate ZIP folders) or this folder (all ZIPs in one folder)."""
    here = Path(__file__).resolve().parent
    for cand in (here.parent, here):
        if (cand / "2020-2024").exists() or (cand / "training" / "2020-2024").exists():
            return cand
    return here.parent


ROOT = Path(os.environ["NONGNET_DATA_ROOT"]) if os.environ.get("NONGNET_DATA_ROOT") else _find_root()
# training data (2020-2024) and inference inputs: project layout ROOT/2020-2024, ROOT/<year> or the
# submission layout model/, training/2020-2024, input/<year> next to each other; env vars override
TRAIN_DIR = Path(os.environ["NONGNET_TRAIN_DIR"]) if os.environ.get("NONGNET_TRAIN_DIR") else (
    ROOT / "2020-2024" if (ROOT / "2020-2024").exists() else ROOT / "training" / "2020-2024")


def _infer_dirs():
    if os.environ.get("NONGNET_INFER_DIR"):
        return [Path(p) for p in os.environ["NONGNET_INFER_DIR"].split(os.pathsep) if p]
    base = ROOT / "input" if (ROOT / "input").exists() else ROOT
    dirs = [base] + sorted(d for d in base.iterdir() if d.is_dir())
    return [d for d in dirs if d.resolve() != TRAIN_DIR.resolve() and any(d.glob("가격_일별_*.csv"))]


INFER_DIRS = _infer_dirs()
INFER_DIR = INFER_DIRS[-1] if INFER_DIRS else ROOT / "input"
ITEMS = ["cabbage", "radish", "onion", "garlic", "dried_pepper"]
UNIT_KG = {"cabbage": 10, "radish": 20, "onion": 1, "garlic": 1, "dried_pepper": 0.6}


def infer_files(pattern, required=False):
    """Inference files matching a glob pattern in every inference folder (sorted, deduplicated)."""
    found = sorted({p.resolve() for d in INFER_DIRS for p in d.glob(pattern)})
    if not found:
        msg = f"inference input not found: {pattern} in {[str(d) for d in INFER_DIRS]}"
        if required:
            raise FileNotFoundError(msg)
        print("warning:", msg, "(features from it are missing for inference origins)", file=sys.stderr)
    return found


def load_prices(paths):
    frames = [pd.read_csv(p, encoding="utf-8-sig", parse_dates=["date"]) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df = df[pd.to_numeric(df.price, errors="coerce") > 0]
    df["price"] = df.price.astype(float)
    df = df.drop_duplicates(["date", "item"], keep="last")      # overlapping files (e.g. a combined history)
    return df.pivot(index="date", columns="item", values="price").sort_index()


def load_volume(paths):
    df = pd.concat([pd.read_csv(p, encoding="utf-8-sig", parse_dates=["date"]) for p in paths], ignore_index=True)
    df["volume_kg"] = pd.to_numeric(df.volume_kg, errors="coerce")
    df = df.drop_duplicates(["date", "item"], keep="last")
    return df.pivot_table(index="date", columns="item", values="volume_kg", aggfunc="sum").sort_index()


def load_origin(train=True, infer=False):
    """Nonghyup origin market grade-sang price (won/kg) and arrivals (t)."""
    frames = []
    if train:
        o = pd.read_csv(TRAIN_DIR / "Supplementary/시장별_경락정보_2020_2024/origin_daily.csv",
                        encoding="utf-8-sig", parse_dates=["date"], low_memory=False)
        o = o[(o.grade == "상") & (o.variety.isin(["전체", "깐마늘"]))]
        frames.append(o[["date", "item", "price_krw_per_kg", "arrival_volume_tonnes"]])
    if infer:
        for f in infer_files("Supplementary/시장별_경락정보_*/origin_daily_*grade12*.csv"):
            o = pd.read_csv(f, encoding="utf-8-sig", parse_dates=["date"], low_memory=False)
            frames.append(o[["date", "item", "price_krw_per_kg", "arrival_volume_tonnes"]])
    o = pd.concat(frames, ignore_index=True)
    for c in ("price_krw_per_kg", "arrival_volume_tonnes"):
        o[c] = pd.to_numeric(o[c], errors="coerce")
    o = o[o.price_krw_per_kg > 0]
    price = o.pivot_table(index="date", columns="item", values="price_krw_per_kg", aggfunc="mean")
    arr = o.pivot_table(index="date", columns="item", values="arrival_volume_tonnes", aggfunc="sum")
    return price.sort_index(), arr.sort_index()


def load_weather(train=True, infer=False):
    cols = ["stnNm", "tm", "avgTa", "minTa", "maxTa", "sumRn"]
    frames = []
    if train:
        frames.append(pd.read_csv(TRAIN_DIR / "Supplementary/날씨와공휴일_2020_2024/weather_daily.csv",
                                  encoding="utf-8-sig", usecols=cols))
    if infer:
        for f in infer_files("Supplementary/날씨와공휴일_*/weather_daily*.csv"):
            frames.append(pd.read_csv(f, encoding="utf-8-sig", usecols=cols))
    w = pd.concat(frames, ignore_index=True).drop_duplicates(["stnNm", "tm"], keep="last")
    w["tm"] = pd.to_datetime(w.tm)
    for c in ("avgTa", "minTa", "maxTa", "sumRn"):
        w[c] = pd.to_numeric(w[c], errors="coerce")
    w["sumRn"] = w.sumRn.fillna(0)
    nat = w.groupby("tm").agg(avgTa=("avgTa", "mean"), minTa=("minTa", "mean"), maxTa=("maxTa", "mean"),
                              sumRn=("sumRn", "mean"))
    return nat.sort_index()


def load_garak(train=True, infer=False):
    """Garak market all-grade settled price (won/kg) derived as amount/volume, plus settled volume."""
    frames = []
    if train:
        g = pd.read_csv(TRAIN_DIR / "Supplementary/시장별_경락정보_2020_2024/garak_daily.csv",
                        encoding="utf-8-sig", parse_dates=["date"], low_memory=False)
        g = g[g.variety.isin(["전체", "깐마늘"])].copy()
        g["price"] = pd.to_numeric(g.settled_amount_krw, errors="coerce") / pd.to_numeric(g.settled_volume_kg, errors="coerce")
        g["vol"] = pd.to_numeric(g.settled_volume_kg, errors="coerce")
        frames.append(g[["date", "item", "price", "vol"]])
    if infer:
        for f in infer_files("Supplementary/시장별_경락정보_*/settlement_daily*.csv"):
            s = pd.read_csv(f, encoding="utf-8-sig", parse_dates=["date"], low_memory=False)
            s = s[(s.market_scope == "garak") & (s.measure == "settled_volume")].copy()
            s["price"] = pd.to_numeric(s.amount_krw, errors="coerce") / pd.to_numeric(s.value, errors="coerce")
            s["vol"] = pd.to_numeric(s.value, errors="coerce")
            frames.append(s[["date", "item", "price", "vol"]])
    g = pd.concat(frames, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    g = g[g.price > 0]
    price = g.pivot_table(index="date", columns="item", values="price", aggfunc="mean").sort_index()
    vol = g.pivot_table(index="date", columns="item", values="vol", aggfunc="sum").sort_index()
    return price, vol


def bundle(infer=False):
    if infer:
        prices = load_prices([TRAIN_DIR / "가격_일별_2020_2024.csv"] + infer_files("가격_일별_*.csv", required=True))
        volume = load_volume([TRAIN_DIR / "Supplementary/물량_일별_2020_2024.csv"]
                             + infer_files("Supplementary/물량_일별_*.csv"))
    else:
        prices = load_prices([TRAIN_DIR / "가격_일별_2020_2024.csv"])
        volume = load_volume([TRAIN_DIR / "Supplementary/물량_일별_2020_2024.csv"])
    oprice, oarr = load_origin(train=True, infer=infer)
    weather = load_weather(train=True, infer=infer)
    gprice, gvol = load_garak(train=True, infer=infer)
    return dict(prices=prices, volume=volume, oprice=oprice, oarr=oarr, weather=weather, gprice=gprice, gvol=gvol)


def _case_manifest(cases_path):
    path = Path(cases_path).resolve().parent / "input-manifest.json"
    if not path.exists():
        return None
    import json
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return manifest if manifest.get("schema") == "nongnet-case-input-v1" else None


def has_case_inputs(cases_path):
    return _case_manifest(cases_path) is not None


@contextmanager
def inference_case(cases_path, case_id, origin):
    """Select only this case's physically truncated observation files.

    The public-holiday calendar is a known-calendar input, not an observation
    series. Legacy year-folder inputs remain supported by predict.py.
    """
    global INFER_DIRS, INFER_DIR
    manifest = _case_manifest(cases_path)
    if manifest is None:
        raise ValueError("A case-input manifest is required")
    entries = [r for r in manifest["cases"] if str(r["case_id"]) == str(case_id)]
    if len(entries) != 1 or entries[0]["origin"] != str(pd.Timestamp(origin).date()):
        raise ValueError(f"Input case/origin mismatch: {case_id} {origin}")
    base = Path(cases_path).resolve().parent
    case_root = (base / entries[0]["input_directory"]).resolve()
    if not case_root.is_relative_to(base):
        raise ValueError("Case input directory must be inside the input package")
    dirs = [case_root] + sorted(p for p in case_root.iterdir() if p.is_dir())
    dirs = [p for p in dirs if any(p.glob("가격_일별_*.csv"))]
    if not dirs:
        raise FileNotFoundError(f"No price input for case {case_id}")
    previous = INFER_DIRS, INFER_DIR
    INFER_DIRS, INFER_DIR = dirs, dirs[-1]
    try:
        yield
    finally:
        INFER_DIRS, INFER_DIR = previous
