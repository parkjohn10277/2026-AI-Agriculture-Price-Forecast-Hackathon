"""Second batch of extra features merged onto the cached tables by (item, origin):
 - regional weather for the main production areas (highland Gangwon, south Jeonnam, west Chungcheong, Jeonbuk,
   Gyeongnam onion belt, Jeju) and national extreme-weather counts,
 - national wholesale settled price/volume (all markets, not only Garak),
 - cross-item price state (cabbage/radish/onion momentum visible to every item).
All features use observations strictly before the origin. Training builds use 2020-2024 data only."""
import sys, math
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data as D

ROOT = D.ROOT
GROUPS = {
    "high": [100, 216, 217, 121, 212],          # Daegwallyeong, Taebaek, Jeongseon, Yeongwol, Hongcheon
    "jn": [261, 268, 170, 165, 259, 260, 262],  # Haenam, Jindo, Wando, Mokpo, Gangjin, Jangheung, Goheung
    "cc": [129, 177, 235, 232, 127],            # Seosan, Hongseong, Boryeong, Cheonan, Chungju
    "jb": [172, 243, 245, 140, 146],            # Gochang, Buan, Jeongeup, Gunsan, Jeonju
    "gn": [288, 285, 263, 192, 155],            # Miryang, Hapcheon, Uiryeong, Jinju, Changwon
    "jeju": [184, 189, 188, 185],
}
IDX = pd.date_range("2019-01-01", "2027-12-31", freq="D")    # covers 2026 기준일 and their 3순 targets
T0 = IDX[0]
W_TRAIN = D.TRAIN_DIR / "Supplementary" / "날씨와공휴일_2020_2024" / "weather_daily.csv"
M_TRAIN = D.TRAIN_DIR / "Supplementary" / "시장별_경락정보_2020_2024"


def load_weather_raw(train=True, infer=False):
    cols = ["stnId", "tm", "avgTa", "minTa", "maxTa", "sumRn", "sumSsHr", "avgRhm"]
    frames = []
    if train:
        frames.append(pd.read_csv(W_TRAIN, encoding="utf-8-sig", usecols=cols))
    if infer:
        for f in D.infer_files("Supplementary/날씨와공휴일_*/weather_daily*.csv"):
            frames.append(pd.read_csv(f, encoding="utf-8-sig", usecols=cols))
    w = pd.concat(frames, ignore_index=True)
    w["tm"] = pd.to_datetime(w.tm)
    for c in ("avgTa", "minTa", "maxTa", "sumRn", "sumSsHr", "avgRhm"):
        w[c] = pd.to_numeric(w[c], errors="coerce")
    w["sumRn"] = w.sumRn.fillna(0.0)
    return w


def load_national_wholesale(train=True, infer=False):
    frames = []
    if train:
        t = pd.read_csv(M_TRAIN / "wholesale_daily.csv", encoding="utf-8-sig", parse_dates=["date"])
        t["price"] = pd.to_numeric(t.amount_krw, errors="coerce") / pd.to_numeric(t.volume_kg, errors="coerce")
        t["vol"] = pd.to_numeric(t.volume_kg, errors="coerce")
        frames.append(t[["date", "item", "price", "vol"]])
    if infer:
        for f in D.infer_files("Supplementary/시장별_경락정보_*/settlement_daily*.csv"):
            s = pd.read_csv(f, encoding="utf-8-sig", parse_dates=["date"], low_memory=False)
            s = s[(s.market_scope == "national_wholesale") & (s.measure == "settled_volume")].copy()
            s["price"] = pd.to_numeric(s.amount_krw, errors="coerce") / pd.to_numeric(s.value, errors="coerce")
            s["vol"] = pd.to_numeric(s.value, errors="coerce")
            frames.append(s[["date", "item", "price", "vol"]])
    t = pd.concat(frames, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    t = t[t.price > 0]
    price = t.pivot_table(index="date", columns="item", values="price", aggfunc="mean").sort_index()
    vol = t.pivot_table(index="date", columns="item", values="vol", aggfunc="sum").sort_index()
    return price, vol


def _arr(s):
    return s.reindex(IDX).to_numpy(dtype=float)


def _pos(d):
    return (d - T0).days


def _slice(a, d_from, d_to):
    i, j = max(_pos(d_from), 0), min(_pos(d_to) + 1, len(a))
    if j <= i:
        return np.empty(0)
    x = a[i:j]
    return x[~np.isnan(x)]


def wmean(a, d_from, d_to):
    x = _slice(a, d_from, d_to)
    return float(x.mean()) if len(x) else np.nan


def wmax(a, d_from, d_to):
    x = _slice(a, d_from, d_to)
    return float(x.max()) if len(x) else np.nan


def wmin(a, d_from, d_to):
    x = _slice(a, d_from, d_to)
    return float(x.min()) if len(x) else np.nan


def _anom(a, o, days, fn=lambda cur, clim: cur - clim):
    d1 = o - pd.Timedelta(days=1)
    cur = wmean(a, o - pd.Timedelta(days=days), d1)
    clim = [wmean(a, o - pd.DateOffset(years=y) - pd.Timedelta(days=days), o - pd.DateOffset(years=y) - pd.Timedelta(days=1)) for y in (1, 2, 3)]
    clim = [x for x in clim if not np.isnan(x)]
    if not clim or np.isnan(cur):
        return cur, np.nan
    return cur, fn(cur, float(np.mean(clim)))


class Extras:
    def __init__(self, train=True, infer=False):
        w = load_weather_raw(train, infer)
        self.g = {}
        for name, ids in GROUPS.items():
            sub = w[w.stnId.isin(ids)]
            d = sub.groupby("tm").agg(ta=("avgTa", "mean"), rn=("sumRn", "mean"), tmax=("maxTa", "max"),
                                      tmin=("minTa", "min"), ss=("sumSsHr", "mean"))
            self.g[name] = {k: _arr(d[k]) for k in d.columns}
        nat = w.groupby("tm").agg(ss=("sumSsHr", "mean"), rh=("avgRhm", "mean"),
                                  heavy=("sumRn", lambda x: float((x >= 50).mean())),
                                  heat=("maxTa", lambda x: float((x >= 33).mean())),
                                  frost=("minTa", lambda x: float((x <= -5).mean())))
        self.n = {k: _arr(nat[k]) for k in nat.columns}
        np_, nv = load_national_wholesale(train, infer)
        self.np = {i: _arr(np_[i]) if i in np_ else np.full(len(IDX), np.nan) for i in D.ITEMS}
        self.nv = {i: _arr(nv[i]) if i in nv else np.full(len(IDX), np.nan) for i in D.ITEMS}
        self._wcache = {}

    def weather(self, o):
        if o in self._wcache:
            return self._wcache[o]
        d1 = o - pd.Timedelta(days=1)
        f = {}
        for name, a in self.g.items():
            _, f[f"{name}_ta14a"] = _anom(a["ta"], o, 14)
            rn14, f[f"{name}_rn14a"] = _anom(a["rn"], o, 14, lambda c, k: math.log((c + 1) / (k + 1)))
            f[f"{name}_rn14"] = rn14
            f[f"{name}_rn30"] = wmean(a["rn"], o - pd.Timedelta(days=30), d1)
            f[f"{name}_tmax14"] = wmax(a["tmax"], o - pd.Timedelta(days=14), d1)
            f[f"{name}_tmin14"] = wmin(a["tmin"], o - pd.Timedelta(days=14), d1)
            f[f"{name}_ss30"] = wmean(a["ss"], o - pd.Timedelta(days=30), d1)
        f["n_heavy14"] = wmean(self.n["heavy"], o - pd.Timedelta(days=14), d1)
        f["n_heat14"] = wmean(self.n["heat"], o - pd.Timedelta(days=14), d1)
        f["n_frost14"] = wmean(self.n["frost"], o - pd.Timedelta(days=14), d1)
        f["n_rh14"] = wmean(self.n["rh"], o - pd.Timedelta(days=14), d1)
        f["n_ss30"], f["n_ss30a"] = _anom(self.n["ss"], o, 30)
        self._wcache[o] = f
        return f

    def natwholesale(self, item, o, L):
        d1 = o - pd.Timedelta(days=1)
        p, v = self.np[item], self.nv[item]
        f = {}
        np7 = wmean(p, o - pd.Timedelta(days=7), d1)
        np30 = wmean(p, o - pd.Timedelta(days=30), d1)
        np3 = wmean(p, o - pd.Timedelta(days=3), d1)
        f["np7_L"] = math.log(np7 * D.UNIT_KG[item] / L) if np7 == np7 and np7 > 0 else np.nan
        f["np7_30"] = math.log(np7 / np30) if np7 == np7 and np30 == np30 and np30 > 0 else np.nan
        f["np3_7"] = math.log(np3 / np7) if np3 == np3 and np7 == np7 and np7 > 0 else np.nan
        nv7 = wmean(v, o - pd.Timedelta(days=7), d1)
        nv30 = wmean(v, o - pd.Timedelta(days=30), d1)
        nvly = wmean(v, o - pd.DateOffset(years=1) - pd.Timedelta(days=7), o - pd.DateOffset(years=1))
        f["nv7_30"] = math.log((nv7 + 1) / (nv30 + 1)) if nv7 == nv7 and nv30 == nv30 else np.nan
        f["nv7_ly"] = math.log((nv7 + 1) / (nvly + 1)) if nv7 == nv7 and nvly == nvly else np.nan
        return f


CROSS_FEATS = ["r7", "r30", "mom14", "anom3", "slope14"]
CROSS_ITEMS = {"cabbage": "xc", "radish": "xr", "onion": "xo"}
WEATHER_PREFIXES = tuple(GROUPS) + ("n_",)
NATW_FEATS = ["np7_L", "np7_30", "np3_7", "nv7_30", "nv7_ly"]


V2_OWN = ["anom3", "anom3_m7", "slope14", "slope30", "oa7_ly", "gv7_ly"]
X3_FEATS = ["ma_run", "above60", "dd60", "du60", "dd180", "du180", "nup7", "v30_ly", "v30_365", "v14_ly", "v30_ly2",
            "blk_L", "blk_mom", "blk2_L", "yoy_mom30", "r7_ly", "r30_ly"]
COINT_FEATS = ["cr_spread", "cr_mom_diff", "co_spread", "ro_spread"]


def select_features(allfeats, name):
    """Feature subset for a bank variant: base (v6 features), wxcr (base + national extremes + cabbage/radish
    production-area weather), wxon (onion areas), wx (all weather), nc (base + national wholesale + cross-item), coint, all."""
    wx = [c for c in allfeats if c.startswith(WEATHER_PREFIXES)]
    natw = [c for c in allfeats if c in NATW_FEATS]
    cross = [c for c in allfeats if c[:3] in ("xc_", "xr_", "xo_")]
    x3 = [c for c in allfeats if c in X3_FEATS]                 # v8 regime / range / volume / block extras
    coint = [c for c in allfeats if c in COINT_FEATS]           # v9 cross-item cointegration spreads
    extras = set(wx) | set(natw) | set(cross) | set(x3) | set(coint)
    base = [c for c in allfeats if c not in extras]            # own features incl. the v2 additions (anom3, slopes, ...)
    nov2 = [c for c in base if c not in V2_OWN]                # own features without the v2 additions
    nat = [c for c in wx if c.startswith("n_")]
    reg = {g: [c for c in wx if c.startswith(g + "_")] for g in GROUPS}
    if name == "base":
        return base
    if name == "coint":
        return base + coint
    if name == "nov2":
        return nov2
    if name == "x3":
        return base + x3
    if name == "wxcr_nov2":
        return nov2 + nat + reg["high"] + reg["jn"] + reg["cc"] + reg["jb"]
    if name == "all":
        return list(allfeats)
    if name == "wx":
        return base + wx
    if name == "wxcr":
        return base + nat + reg["high"] + reg["jn"] + reg["cc"] + reg["jb"]
    if name == "wxon":
        return base + nat + reg["gn"] + reg["jn"] + reg["jeju"]
    if name == "nc":
        return base + natw + cross
    raise ValueError(name)


def cross_table(short_df):
    """Cross-item state by origin, derived from the cached short table (h==1 rows)."""
    base = short_df[short_df.h == 1]
    parts = []
    for item, pre in CROSS_ITEMS.items():
        t = base[base.item == item].set_index("origin")[CROSS_FEATS]
        t.columns = [f"{pre}_{c}" for c in CROSS_FEATS]
        parts.append(t)
    return pd.concat(parts, axis=1)


def cross_from_features(feat_by_item):
    """Same cross-item features from origin_features dicts {item: f} (inference path)."""
    out = {}
    for item, pre in CROSS_ITEMS.items():
        f = feat_by_item.get(item)
        for c in CROSS_FEATS:
            out[f"{pre}_{c}"] = f[c] if f is not None else np.nan
    out["cr_spread"] = out["xc_anom3"] - out["xr_anom3"]
    out["cr_mom_diff"] = out["xc_r7"] - out["xr_r7"]
    out["co_spread"] = out["xc_anom3"] - out["xo_anom3"]
    out["ro_spread"] = out["xr_anom3"] - out["xo_anom3"]
    return out


def build_extras_table(origins, items, L_lookup):
    """L_lookup: dict (item, origin) -> last price. Returns DataFrame with item, origin and the extra features."""
    ex = Extras(train=True, infer=False)
    recs = []
    for o in origins:
        wf = ex.weather(o)
        for item in items:
            L = L_lookup.get((item, o))
            if L is None:
                continue
            r = dict(item=item, origin=o)
            r.update(wf)
            r.update(ex.natwholesale(item, o, L))
            recs.append(r)
    return pd.DataFrame(recs)
