"""Third batch of extra features (v8): price-regime persistence, range position, 30-day volume vs last year,
last complete 10-day block means and year-over-year anomaly momentum. All use observations strictly before the origin.
Works for training (2020-2024) and inference (2025 inputs) through the FeatureBuilder's Daily series."""
import sys, math
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data as D


def next_block(d):
    """Start of the next 10-day block (1st / 11th / 21st) strictly after day d (same rule as harness.next_block)."""
    if d.day < 11:
        return d.replace(day=11)
    if d.day < 21:
        return d.replace(day=21)
    return d.replace(day=1) + pd.offsets.MonthBegin(1)

X3_FEATS = ["ma_run", "above60", "dd60", "du60", "dd180", "du180", "nup7", "v30_ly", "v30_365", "v14_ly", "v30_ly2",
            "blk_L", "blk_mom", "blk2_L", "yoy_mom30", "r7_ly", "r30_ly"]


def _wmean_all(P, w):
    """array m[d] = mean of observed values in [d-w, d-1] for every day index d."""
    n = len(P.v)
    d = np.arange(n)
    i = np.clip(d - w, 0, n); j = d
    c = P.ccnt[j] - P.ccnt[i]
    with np.errstate(invalid="ignore", divide="ignore"):
        m = (P.csum[j] - P.csum[i]) / c
    m[c == 0] = np.nan
    return m


class Extras3:
    def __init__(self, fb):
        self.fb = fb
        self._c = {}
        self.pre = {}
        for item in D.ITEMS:
            P = fb.price[item]
            m7 = _wmean_all(P, 7); m365 = _wmean_all(P, 365)
            above = np.where(np.isnan(m7) | np.isnan(m365), np.nan, (m7 > m365).astype(float))
            run = np.zeros(len(P.v))
            for k in range(1, len(P.v)):
                if np.isnan(above[k]):
                    run[k] = 0.0
                elif above[k] == 1:
                    run[k] = run[k - 1] + 1 if run[k - 1] > 0 else 1
                else:
                    run[k] = run[k - 1] - 1 if run[k - 1] < 0 else -1
            s = pd.Series(P.v, index=P.idx)
            ind = pd.Series(np.where(P.obs, (P.v > m365).astype(float), np.nan), index=P.idx)
            self.pre[item] = dict(
                run=np.clip(run, -200, 200),
                above60=ind.rolling(60, min_periods=10).mean().to_numpy(),
                max60=s.rolling(60, min_periods=5).max().to_numpy(), min60=s.rolling(60, min_periods=5).min().to_numpy(),
                max180=s.rolling(180, min_periods=5).max().to_numpy(), min180=s.rolling(180, min_periods=5).min().to_numpy(),
                nup7=pd.Series(np.sign(np.diff(np.log(s.dropna()))), index=s.dropna().index[1:]).gt(0).astype(float)
                .rolling(7, min_periods=4).mean().reindex(P.idx).ffill().to_numpy(),
            )

    def feats(self, item, o, L):
        key = (item, o)
        if key in self._c:
            return self._c[key]
        P, V = self.fb.price[item], self.fb.vol[item]
        pre = self.pre[item]
        k = P.pos(o)              # day index of origin; arrays indexed by day use obs < o at index o (rolling uses <= o-1 at o-1)
        k1 = k - 1
        d1 = o - pd.Timedelta(days=1)
        f = {}
        f["ma_run"] = float(pre["run"][k]) if k < len(pre["run"]) else np.nan
        f["above60"] = float(pre["above60"][k1]) if k1 >= 0 else np.nan
        for w in (60, 180):
            mx, mn = pre[f"max{w}"][k1], pre[f"min{w}"][k1]
            f[f"dd{w}"] = math.log(L / mx) if mx == mx and mx > 0 else np.nan
            f[f"du{w}"] = math.log(L / mn) if mn == mn and mn > 0 else np.nan
        f["nup7"] = float(pre["nup7"][k1]) if k1 >= 0 else np.nan
        v30, c30 = V.mean(o - pd.Timedelta(days=30), d1)
        v14, c14 = V.mean(o - pd.Timedelta(days=14), d1)
        v365, c365 = V.mean(o - pd.Timedelta(days=365), d1)
        oy = o - pd.DateOffset(years=1); oy2 = o - pd.DateOffset(years=2)
        vly30, cl30 = V.mean(oy - pd.Timedelta(days=30), oy - pd.Timedelta(days=1))
        vly14, cl14 = V.mean(oy - pd.Timedelta(days=14), oy - pd.Timedelta(days=1))
        vly2, cl2 = V.mean(oy2 - pd.Timedelta(days=30), oy2 - pd.Timedelta(days=1))
        lr = lambda a, b, ca, cb: math.log(a / b) if ca and cb and a > 0 and b > 0 else np.nan
        f["v30_ly"] = lr(v30, vly30, c30, cl30)
        f["v30_365"] = lr(v30, v365, c30, c365)
        f["v14_ly"] = lr(v14, vly14, c14, cl14)
        f["v30_ly2"] = lr(v30, vly2, c30, cl2)
        # last two complete 10-day blocks before the origin
        blocks = []
        s = next_block(o - pd.Timedelta(days=45))
        while True:
            e = next_block(s) - pd.Timedelta(days=1)
            if e >= o:
                break
            m, c = P.mean(s, e)
            if c:
                blocks.append(m)
            s = next_block(s)
        f["blk_L"] = math.log(blocks[-1] / L) if blocks else np.nan
        f["blk2_L"] = math.log(blocks[-2] / L) if len(blocks) >= 2 else np.nan
        f["blk_mom"] = math.log(blocks[-1] / blocks[-2]) if len(blocks) >= 2 else np.nan
        m7, c7 = P.mean(o - pd.Timedelta(days=7), d1)
        ly7, cy7 = P.mean(oy - pd.Timedelta(days=7), oy - pd.Timedelta(days=1))
        o30 = o - pd.Timedelta(days=30); oy30 = oy - pd.Timedelta(days=30)
        m7b, c7b = P.mean(o30 - pd.Timedelta(days=7), o30 - pd.Timedelta(days=1))
        ly7b, cy7b = P.mean(oy30 - pd.Timedelta(days=7), oy30 - pd.Timedelta(days=1))
        a_now = lr(m7, ly7, c7, cy7); a_bef = lr(m7b, ly7b, c7b, cy7b)
        f["yoy_mom30"] = a_now - a_bef if a_now == a_now and a_bef == a_bef else np.nan
        f["r7_ly"] = a_now
        m30, c30p = P.mean(o - pd.Timedelta(days=30), d1)
        ly30, cy30 = P.mean(oy - pd.Timedelta(days=30), oy - pd.Timedelta(days=1))
        f["r30_ly"] = lr(m30, ly30, c30p, cy30)
        self._c[key] = f
        return f

