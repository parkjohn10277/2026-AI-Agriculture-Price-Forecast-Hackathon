"""Feature construction, model training and backtesting. Uses only observations strictly before each origin."""
import sys, math
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data as D
import extra_features2 as X2
import extra_features3 as X3
from sklearn.ensemble import HistGradientBoostingRegressor

ITEMS = D.ITEMS
UNIT_KG = D.UNIT_KG


def next_block(d):
    if d.day < 11:
        return d.replace(day=11)
    if d.day < 21:
        return d.replace(day=21)
    return (d.replace(day=1) + pd.offsets.MonthBegin(1))


def target_period(origin, track):
    if track == "block1":
        return origin + pd.Timedelta(days=1), origin + pd.Timedelta(days=10)
    start = origin
    for _ in range(2 if track == "long1" else 3):
        start = next_block(start)
    return start, next_block(start) - pd.Timedelta(days=1)


class Daily:
    """Daily-indexed series with fast window means over observed values only."""
    def __init__(self, s, start="2019-01-01", end="2027-12-31"):
        idx = pd.date_range(start, end, freq="D")
        s = s.reindex(idx)
        self.idx = idx
        self.v = s.to_numpy(dtype=float)
        self.obs = ~np.isnan(self.v)
        self.csum = np.concatenate([[0.0], np.nancumsum(self.v)])
        self.ccnt = np.concatenate([[0], np.cumsum(self.obs)])
        self.t0 = idx[0]

    def pos(self, d):
        return (d - self.t0).days

    def mean(self, a, b):
        """mean of observed values in [a, b] inclusive; (nan, 0) if none."""
        i, j = max(self.pos(a), 0), min(self.pos(b) + 1, len(self.v))
        if j <= i:
            return np.nan, 0
        c = self.ccnt[j] - self.ccnt[i]
        return ((self.csum[j] - self.csum[i]) / c if c else np.nan), int(c)

    def last(self, before):
        """last observed value strictly before date."""
        k = self.pos(before) - 1
        while k >= 0 and not self.obs[k]:
            k -= 1
        return (self.v[k], self.idx[k]) if k >= 0 else (np.nan, None)

    def std_logdiff(self, a, b):
        i, j = max(self.pos(a), 0), min(self.pos(b) + 1, len(self.v))
        x = self.v[i:j]
        x = x[~np.isnan(x)]
        if len(x) < 5:
            return np.nan
        return float(np.std(np.diff(np.log(x))))


class FeatureBuilder:
    def __init__(self, bundle, extras=None):
        self.extras = extras        # extra_features2.Extras (regional weather, national wholesale) or None
        self._cache2 = {}
        self.price = {i: Daily(bundle["prices"][i]) for i in ITEMS}
        self.vol = {i: Daily(bundle["volume"][i]) for i in ITEMS}
        self.oprice = {i: Daily(bundle["oprice"][i]) for i in ITEMS}
        self.oarr = {i: Daily(bundle["oarr"][i]) for i in ITEMS}
        self.gprice = {i: Daily(bundle["gprice"][i]) for i in ITEMS}
        self.gvol = {i: Daily(bundle["gvol"][i]) for i in ITEMS}
        w = bundle["weather"]
        self.ta = Daily(w["avgTa"])
        self.rn = Daily(w["sumRn"])
        self.tmin = Daily(w["minTa"])
        self._cache = {}
        # EWMA levels of log price over observed days only (value at day d uses obs <= d)
        self.ewma = {}
        for i in ITEMS:
            P = self.price[i]
            lv = {}
            for a in (0.5, 0.35, 0.2):
                arr = np.full(len(P.v), np.nan)
                cur = np.nan
                for k in range(len(P.v)):
                    if P.obs[k]:
                        lv_k = math.log(P.v[k])
                        cur = lv_k if np.isnan(cur) else a * lv_k + (1 - a) * cur
                    arr[k] = cur
                lv[a] = arr
            self.ewma[i] = lv
        self.x3 = X3.Extras3(self)    # v8 regime / range / volume / block features (strictly before origin)

    def origin_features(self, item, o):
        """Own features plus (if extras are attached) regional weather, national wholesale and cross-item state.
        Returns (dict, last_price) or None. Everything uses observations strictly before origin o."""
        key = (item, o)
        if key in self._cache2:
            return self._cache2[key]
        base = self._own_features(item, o)
        if base is None or self.extras is None:
            self._cache2[key] = base
            return base
        f, L = base
        f = dict(f)
        f.update(self.extras.weather(o))
        f.update(self.extras.natwholesale(item, o, L))
        others = {it: (self._own_features(it, o) or (None, None))[0] for it in X2.CROSS_ITEMS}
        f.update(X2.cross_from_features(others))
        f.update(self.x3.feats(item, o, L))
        self._cache2[key] = (f, L)
        return f, L

    def _own_features(self, item, o):
        """Features from the item's own price/volume/market series and national weather (v6 feature set)."""
        key = (item, o)
        if key in self._cache:
            return self._cache[key]
        P = self.price[item]
        L, Lday = P.last(o)
        if np.isnan(L):
            self._cache[key] = None
            return None
        f = {"logL": math.log(L), "stale": (o - Lday).days}
        d1 = o - pd.Timedelta(days=1)
        kpos = P.pos(Lday)
        for a in (0.5, 0.35, 0.2):
            f[f"e{int(a*100)}"] = self.ewma[item][a][kpos] - math.log(L)
        for w in (3, 7, 14, 30, 60, 90, 180, 365):
            m, c = P.mean(o - pd.Timedelta(days=w), d1)
            f[f"r{w}"] = math.log(m / L) if c else 0.0
        for lag in (7, 14, 30):
            m, c = P.mean(o - pd.Timedelta(days=lag + 3), o - pd.Timedelta(days=lag - 3))
            f[f"mom{lag}"] = math.log(L / m) if c else 0.0
        f["vol30"] = P.std_logdiff(o - pd.Timedelta(days=30), d1)
        f["vol90"] = P.std_logdiff(o - pd.Timedelta(days=90), d1)
        for y in (1, 2):
            m, c = P.mean(o - pd.DateOffset(years=y) - pd.Timedelta(days=7), o - pd.DateOffset(years=y))
            f[f"yoy{y}"] = math.log(L / m) if c else np.nan
        V = self.vol[item]
        v7, c7 = V.mean(o - pd.Timedelta(days=7), d1)
        v30, c30 = V.mean(o - pd.Timedelta(days=30), d1)
        v365, c365 = V.mean(o - pd.Timedelta(days=365), d1)
        vly, cly = V.mean(o - pd.DateOffset(years=1) - pd.Timedelta(days=7), o - pd.DateOffset(years=1))
        f["v7_30"] = math.log(v7 / v30) if c7 and c30 and v7 > 0 and v30 > 0 else np.nan
        f["v7_365"] = math.log(v7 / v365) if c7 and c365 and v7 > 0 and v365 > 0 else np.nan
        f["v7_ly"] = math.log(v7 / vly) if c7 and cly and v7 > 0 and vly > 0 else np.nan
        OP, OA = self.oprice[item], self.oarr[item]
        op7, c = OP.mean(o - pd.Timedelta(days=7), d1)
        f["op7_L"] = math.log(op7 * UNIT_KG[item] / L) if c else np.nan
        op30, c2 = OP.mean(o - pd.Timedelta(days=30), d1)
        f["op7_30"] = math.log(op7 / op30) if c and c2 else np.nan
        oa7, c = OA.mean(o - pd.Timedelta(days=7), d1)
        oa30, c2 = OA.mean(o - pd.Timedelta(days=30), d1)
        f["oa7_30"] = math.log((oa7 + 1) / (oa30 + 1)) if c and c2 else np.nan
        GP, GV = self.gprice[item], self.gvol[item]
        gp7, c = GP.mean(o - pd.Timedelta(days=7), d1)
        f["gp7_L"] = math.log(gp7 * UNIT_KG[item] / L) if c else np.nan
        gp3, c3 = GP.mean(o - pd.Timedelta(days=3), d1)
        f["gp3_7"] = math.log(gp3 / gp7) if c and c3 else np.nan
        gv7, c = GV.mean(o - pd.Timedelta(days=7), d1)
        gv30, c2 = GV.mean(o - pd.Timedelta(days=30), d1)
        f["gv7_30"] = math.log((gv7 + 1) / (gv30 + 1)) if c and c2 else np.nan
        ta14, _ = self.ta.mean(o - pd.Timedelta(days=14), d1)
        clim = [self.ta.mean(o - pd.DateOffset(years=y) - pd.Timedelta(days=14), o - pd.DateOffset(years=y) - pd.Timedelta(days=1))[0] for y in (1, 2, 3)]
        clim = [x for x in clim if not np.isnan(x)]
        f["ta14"] = ta14
        f["ta14_anom"] = ta14 - float(np.mean(clim)) if clim else np.nan
        f["rn30"] = self.rn.mean(o - pd.Timedelta(days=30), d1)[0]
        f["rn14"] = self.rn.mean(o - pd.Timedelta(days=14), d1)[0]
        f["tmin14"] = self.tmin.mean(o - pd.Timedelta(days=14), d1)[0]
        f["doy_s"] = math.sin(2 * math.pi * o.dayofyear / 365.25)
        f["doy_c"] = math.cos(2 * math.pi * o.dayofyear / 365.25)
        f["month"] = o.month
        # v2 features: seasonal anomaly (level vs same calendar window in previous 1-3 years), recent log-price slopes,
        # arrivals and Garak volume year-over-year
        vals = []
        for y in (1, 2, 3):
            m, c = P.mean(o - pd.DateOffset(years=y) - pd.Timedelta(days=10), o - pd.DateOffset(years=y) + pd.Timedelta(days=10))
            if c:
                vals.append(math.log(m))
        f["anom3"] = (math.log(L) - float(np.mean(vals))) if vals else np.nan
        m7, c7 = P.mean(o - pd.Timedelta(days=7), d1)
        f["anom3_m7"] = (math.log(m7) - float(np.mean(vals))) if (vals and c7) else np.nan
        for span in (14, 30):
            i, j = max(P.pos(o - pd.Timedelta(days=span)), 0), P.pos(o)
            xs = np.arange(i, j)[P.obs[i:j]]
            if len(xs) >= 5:
                ys = np.log(P.v[xs])
                xc = xs - xs.mean()
                yc = ys - ys[0]
                num = float((xc * yc).sum()) - float(yc.mean()) * float(xc.sum())
                f[f"slope{span}"] = num / float((xc * xc).sum()) * 30
            else:
                f[f"slope{span}"] = np.nan
        oaly, c = OA.mean(o - pd.DateOffset(years=1) - pd.Timedelta(days=7), o - pd.DateOffset(years=1))
        f["oa7_ly"] = math.log((oa7 + 1) / (oaly + 1)) if c and oa7 == oa7 else np.nan
        gvly, c = GV.mean(o - pd.DateOffset(years=1) - pd.Timedelta(days=7), o - pd.DateOffset(years=1))
        f["gv7_ly"] = math.log((gv7 + 1) / (gvly + 1)) if c and gv7 == gv7 else np.nan
        self._cache[key] = (f, L)
        return f, L

    def seasonal_change(self, item, o, start, end, years=(1, 2, 3, 4)):
        """Historical mean log change from the 7 days before origin to the target window, same calendar in past years."""
        P = self.price[item]
        vals = []
        for y in years:
            oy = o - pd.DateOffset(years=y)
            if oy < P.idx[0] + pd.Timedelta(days=10):
                continue
            base, cb = P.mean(oy - pd.Timedelta(days=7), oy - pd.Timedelta(days=1))
            tgt, ct = P.mean(start - pd.DateOffset(years=y), end - pd.DateOffset(years=y))
            if cb and ct:
                vals.append(math.log(tgt / base))
        if not vals:
            return np.nan, np.nan, 0
        return float(np.mean(vals)), float(np.median(vals)), len(vals)

    def rows(self, item, o, track, base):
        """Feature rows for one (item, origin). Returns (list of (dict, start, end), last_price)."""
        f, L = base
        out = []
        if track in ("short", "daily31"):
            for h in range(1, 11 if track == "short" else 32):
                t = o + pd.Timedelta(days=h)
                r = dict(f)
                r["h"] = h
                r["dow"] = t.dayofweek
                r["tdoy_s"] = math.sin(2 * math.pi * t.dayofyear / 365.25)
                r["tdoy_c"] = math.cos(2 * math.pi * t.dayofyear / 365.25)
                sm, smed, n = self.seasonal_change(item, o, t - pd.Timedelta(days=3), t + pd.Timedelta(days=3))
                r["seas"] = sm
                r["seas_med"] = smed
                out.append((r, t, t))
        else:
            s, e = target_period(o, track)
            r = dict(f)
            r["h"] = (s - o).days
            r["h_end"] = (e - o).days
            r["plen"] = (e - s).days + 1
            mid = s + (e - s) / 2
            r["tdoy_s"] = math.sin(2 * math.pi * mid.dayofyear / 365.25)
            r["tdoy_c"] = math.cos(2 * math.pi * mid.dayofyear / 365.25)
            sm, smed, n = self.seasonal_change(item, o, s, e)
            r["seas"] = sm
            r["seas_med"] = smed
            out.append((r, s, e))
        return out, L


def build_training(fb, item, track, origins, cutoff):
    """Rows for origins whose target window ends before cutoff (Timestamp)."""
    X, y, meta = [], [], []
    for o in origins:
        base = fb.origin_features(item, o)
        if base is None:
            continue
        rows, L = fb.rows(item, o, track, base)
        for r, s, e in rows:
            if e >= cutoff:
                continue
            m, c = fb.price[item].mean(s, e)
            if not c:
                continue
            X.append(r)
            y.append(math.log(m / L))
            meta.append((o, s, e, L))
    return pd.DataFrame(X), np.array(y), meta


def make_model(params=None):
    p = dict(loss="absolute_error", max_iter=400, learning_rate=0.04, max_leaf_nodes=15, min_samples_leaf=40,
             l2_regularization=1.0, random_state=0)
    if params:
        p.update(params)
    return HistGradientBoostingRegressor(**p)


def mape(pred, act):
    return float(np.mean(np.abs(np.asarray(pred) - np.asarray(act)) / np.asarray(act) * 100))
