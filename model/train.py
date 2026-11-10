"""Train all model banks for the three tracks on 2020-2024 data only.
Per track: cutoff A (targets end <= 2024-12-30, for the 2024-12-31 origin) and B (<= 2024-12-31, for 2025 origins),
each for every bank variant in config.json. A variant may be split by horizon group ("hgroups", short track) or by
origin month ("seasonal_window": each month's model trained only on origins within +-N days of year of that month).
Usage: python train.py [--out weights.joblib]"""
import sys, json, time, argparse, math
from pathlib import Path
import numpy as np, pandas as pd, joblib
from sklearn.ensemble import HistGradientBoostingRegressor, ExtraTreesRegressor
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data as D, harness as H, extra_features2 as X2

META = ["item", "origin", "start", "end", "L", "y", "y3", "n_obs"]


class LongTrainingFeatureBuilder(H.FeatureBuilder):
    """Reconstruct the numerical slope features used to fit the saved long banks.

    Those banks used centered np.polyfit, while the short banks and submitted
    inference use harness.py's stabilized OLS calculation. They implement the
    same slope mathematically, but floating-point differences near zero alter
    histogram binning. Keep the inference implementation unchanged.
    """

    def _own_features(self, item, origin):
        cached = (item, origin) in self._cache
        result = super()._own_features(item, origin)
        if result is None or cached:
            return result
        features, _ = result
        prices = self.price[item]
        for span in (14, 30):
            i = max(prices.pos(origin - pd.Timedelta(days=span)), 0)
            j = prices.pos(origin)
            x = np.arange(i, j)[prices.obs[i:j]]
            if len(x) >= 5:
                y = np.log(prices.v[x])
                features[f"slope{span}"] = float(np.polyfit(x - x.mean(), y, 1)[0]) * 30
        return result


def build_table(fb, track, origins, items):
    recs = []
    for item in items:
        P = fb.price[item]
        for o in origins:
            base = fb.origin_features(item, o)
            if base is None:
                continue
            rows, L = fb.rows(item, o, track, base)
            for r, s, e in rows:
                m, c = P.mean(s, e)
                if not c:
                    continue
                r = dict(r)
                y3 = np.nan
                if track in ("short", "daily31"):
                    m3, c3 = P.mean(s - pd.Timedelta(days=1), s + pd.Timedelta(days=1))
                    y3 = math.log(m3 / L) if c3 else np.nan
                r.update(item=item, origin=o, start=s, end=e, L=L, y=np.log(m / L), y3=y3, n_obs=c)
                recs.append(r)
    df = pd.DataFrame(recs)
    for it in D.ITEMS:
        df[f"is_{it}"] = (df.item == it).astype(float)
    return df


SPLIT_KEYS = ("kind", "mape_weight", "label", "tracks", "base", "hgroups", "seasonal_window", "clip", "table", "feature_set", "items")


def make_model(track, cfg, variant):
    v = dict(cfg["bank_variants"][variant])
    kind = v["kind"]
    v = {k: (val[track] if isinstance(val, dict) else val) for k, val in v.items() if k not in SPLIT_KEYS}
    if kind == "gbm":
        p = dict(cfg["gbm_params"])
        p["min_samples_leaf"] = p["min_samples_leaf"][track]
        p.update(v)
        return HistGradientBoostingRegressor(**p)
    if kind == "et":
        return make_pipeline(SimpleImputer(strategy="median"), ExtraTreesRegressor(n_jobs=4, random_state=0, **v))
    raise ValueError(kind)


def fit_one(tr, track, cfg, variant, feats):
    v = cfg["bank_variants"][variant]
    label = v.get("label", "y")
    base_col = v.get("base", "e50")
    X = tr[feats].copy()
    allnan = [c for c in feats if X[c].notna().sum() < 2]
    X[allnan] = 0.0
    y = tr[label].to_numpy()
    if "clip" in v:
        y = np.clip(y, -v["clip"][0], v["clip"][1])
    y = y - tr[base_col].to_numpy()
    model = make_model(track, cfg, variant)
    if v.get("mape_weight"):
        sw = np.exp(-tr.y.to_numpy())
        if v["kind"] == "gbm":
            model.fit(X, y, sample_weight=sw)
        else:
            model.fit(X, y, **{model.steps[-1][0] + "__sample_weight": sw})
    else:
        model.fit(X, y)
    return model, allnan


def fit_bank(df, cutoff_end, track, cfg, variant, feats):
    v = cfg["bank_variants"][variant]
    label = v.get("label", "y")
    tr = df[(df.end <= (cutoff_end - pd.Timedelta(days=1) if label == "y3" else cutoff_end)) & df[label].notna()]
    if v.get("items"):                       # bank trained on a subset of items only (e.g. radish-only)
        tr = tr[tr.item.isin(v["items"])]
    bank = {"features": feats, "cutoff_end": str(cutoff_end.date()), "rows": int(len(tr)), "variant": variant,
            "base": v.get("base", "e50"), "split": None, "models": {}}
    if v.get("hgroups") and v.get("seasonal_window"):
        bank["split"] = "month_h"            # one model per (target month, horizon group)
        W = v["seasonal_window"]
        doy = tr.origin.dt.dayofyear
        for mth in range(1, 13):
            center = pd.Timestamp(2001, mth, 15).dayofyear
            dd = (doy - center).abs()
            dd = np.minimum(dd, 365 - dd)
            sub_m = tr[dd <= W]
            for grp in v["hgroups"]:
                lo, hi = grp
                sub = sub_m[(sub_m.h >= lo) & (sub_m.h <= hi)]
                bank["models"][f"{mth}:{lo}-{hi}"] = fit_one(sub, track, cfg, variant, feats)
    elif v.get("hgroups"):
        bank["split"] = "h"
        for grp in v["hgroups"]:
            lo, hi = grp
            sub = tr[(tr.h >= lo) & (tr.h <= hi)]
            bank["models"][f"{lo}-{hi}"] = fit_one(sub, track, cfg, variant, feats)
    elif v.get("seasonal_window"):
        bank["split"] = "month"
        W = v["seasonal_window"]
        doy = tr.origin.dt.dayofyear
        for mth in range(1, 13):
            center = pd.Timestamp(2001, mth, 15).dayofyear
            dd = (doy - center).abs()
            dd = np.minimum(dd, 365 - dd)
            bank["models"][str(mth)] = fit_one(tr[dd <= W], track, cfg, variant, feats)
    else:
        bank["models"]["all"] = fit_one(tr, track, cfg, variant, feats)
    return bank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "weights.joblib"))
    a = ap.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    t = time.time()
    bundle = D.bundle(infer=False)          # 2020-2024 only
    assert bundle["prices"].index.max() <= pd.Timestamp("2024-12-31")
    builders = {
        "short": H.FeatureBuilder(bundle, extras=X2.Extras(train=True, infer=False)),
        "long": LongTrainingFeatureBuilder(bundle, extras=X2.Extras(train=True, infer=False)),
    }  # regional weather / national wholesale, 2020-2024 only
    origins = pd.date_range(cfg["origins_start"], "2024-12-30", freq="D")
    weights = {"version": cfg["version"], "config": cfg, "banks": {}}
    tables = {}
    for track in ("short", "long1", "long2"):
        fb = builders["short" if track == "short" else "long"]
        df = build_table(fb, track, origins, cfg["train_items"])
        feats = [c for c in df.columns if c not in META]
        banks = {}
        for name, cutoff in (("A", pd.Timestamp("2024-12-30")), ("B", pd.Timestamp("2024-12-31"))):
            for variant, v in cfg["bank_variants"].items():
                if "tracks" in v and track not in v["tracks"]:
                    continue
                if v.get("table"):                       # e.g. daily31: daily targets h=1..31, shared by the long tracks
                    tname = v["table"]
                    if tname not in tables:
                        tables[tname] = build_table(fb, tname, origins, cfg["train_items"])
                    dft = tables[tname]
                    ft = X2.select_features([c for c in dft.columns if c not in META], v.get("feature_set", "base"))
                    banks[f"{name}:{variant}"] = fit_bank(dft, cutoff, track, cfg, variant, ft)
                else:
                    fv = X2.select_features(feats, v.get("feature_set", "base"))
                    banks[f"{name}:{variant}"] = fit_bank(df, cutoff, track, cfg, variant, fv)
                print(f"{track} bank {name}:{variant}: rows={banks[f'{name}:{variant}']['rows']} ({time.time()-t:.0f}s)", flush=True)
        weights["banks"][track] = banks
    joblib.dump(weights, a.out, compress=3)
    print("saved", a.out)


if __name__ == "__main__":
    main()
