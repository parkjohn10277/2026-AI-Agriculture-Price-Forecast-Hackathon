"""Predict the cases in cases.json for one track. Uses observations strictly before each origin (post-2024 data for inference only).
Usage: python predict.py --track short [--cases ../input/cases.json] --weights weights.joblib --output out_short.csv [--audit audit.json]
Origins, case IDs and target dates come from cases.json (any 기준일, any year); the target windows the model computes
are checked against it."""
import sys, json, math, argparse, csv, io
from pathlib import Path
import numpy as np, pandas as pd, joblib
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data as D, harness as H, extra_features2 as X2

NAMES = {"cabbage": "배추", "radish": "무", "onion": "양파", "garlic": "깐마늘", "dried_pepper": "건고추"}
BANK_CUTOFF = pd.Timestamp("2024-12-31")   # bank A (targets <= 2024-12-30) for origins up to this day, bank B after


def find_cases():
    """cases.json next to the inference data (input/cases.json in the submission layout)."""
    cands = [D.ROOT / "input" / "cases.json", D.ROOT / "cases.json"]
    for d in D.INFER_DIRS:
        cands += [d / "cases.json", d.parent / "cases.json"]
    cands.append(HERE / "cases.json")
    for c in cands:
        if c.exists():
            return c
    raise FileNotFoundError("cases.json not found; pass --cases")


def load_cases(path, track):
    """[(case_id, origin, [(start, end), ...])] in file order; short targets are one day each."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = raw.get("cases", raw) if isinstance(raw, dict) else raw
    out = []
    for c in raw:
        wins = []
        for t in c["targets"]:
            if track == "short":
                d = pd.Timestamp(t["date"]); w = (d, d)
            else:
                w = (pd.Timestamp(t["period_start"]), pd.Timestamp(t["period_end"]))
            if w not in wins:
                wins.append(w)
        out.append((str(c["caseId"]), pd.Timestamp(c["origin"]), wins))
    return out


def columns(track):
    return ["사례번호", "기준일"] + (["예측일"] if track == "short" else ["예측시작일", "예측종료일"]) + [NAMES[i] for i in D.ITEMS]


def load_holidays():
    files = [D.TRAIN_DIR / "Supplementary/날씨와공휴일_2020_2024/public_holidays.csv"] +         D.infer_files("Supplementary/날씨와공휴일_*/public_holidays*.csv")
    h = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files if f.exists()], ignore_index=True)
    h = h.drop_duplicates(["locdate", "dateName"])
    h["date"] = pd.to_datetime(h.locdate.astype(str), format="%Y%m%d")
    return h


CHUSEOK, SEOLLAL = "추석", "설날"      # holiday names as they appear in public_holidays.csv


def chuseok_closure(holidays, year, name=CHUSEOK):
    """(start, end) of the holiday market closure: the holiday days plus adjacent public holidays and Sundays."""
    hol = set(holidays.date.dt.normalize())
    cs = holidays[(holidays.dateName.str.contains(name)) & (holidays.date.dt.year == year)].date.dt.normalize()
    if cs.empty:
        return None
    def closed(d):
        return d in hol or d.dayofweek == 6
    start, end = cs.min(), cs.max()
    while closed(start - pd.Timedelta(days=1)):
        start -= pd.Timedelta(days=1)
    while closed(end + pd.Timedelta(days=1)):
        end += pd.Timedelta(days=1)
    return start, end


def chuseok_short_mult(holidays, item, dates, rules, name=CHUSEOK):
    out = np.ones(len(dates))
    windows = rules.get(item)
    if not windows:
        return out
    for i, d in enumerate(dates):
        c = chuseok_closure(holidays, d.year, name)
        if c is None:
            continue
        s, e = c
        off = -((s - d).days) if d < s else ((d - e).days if d > e else 0)
        for a, b, m in windows:
            if a <= off <= b:
                out[i] *= m
    return out


def chuseok_block_mult(holidays, item, start, rules, name=CHUSEOK):
    r = rules.get(item)
    if not r:
        return 1.0
    cs = holidays[(holidays.dateName.str.contains(name)) & (holidays.date.dt.year == start.year)].date.dt.normalize()
    if cs.empty:
        return 1.0
    c0 = cs.min()
    bs = H.next_block(c0 - pd.Timedelta(days=11))
    while not (bs <= c0 < H.next_block(bs)):
        bs = H.next_block(bs)
    k, b = 0, bs
    while b < start:
        b = H.next_block(b); k += 1
    while b > start:
        b = H.next_block(b - pd.Timedelta(days=11)); k -= 1
        if k < -3:
            break
    return float(r.get(str(k), 1.0))


def holiday_allowed(holidays, name, year, rng):
    """Extrapolation guard (optional, config key holiday_guard): apply a holiday rule only when that year's holiday falls
    inside the configured day-of-year span [lo, hi]. This guard is disabled when holiday_guard is empty."""
    if not rng:
        return True
    cs = holidays[(holidays.dateName.str.contains(name)) & (holidays.date.dt.year == year)].date
    if cs.empty:
        return True
    return rng[0] <= int(cs.min().dayofyear) <= rng[1]


def block_mean_log(fb, item, o, L):
    P = fb.price[item]
    s = H.next_block(o - pd.Timedelta(days=40))
    best = np.nan
    while True:
        e = H.next_block(s) - pd.Timedelta(days=1)
        if e >= o:
            break
        m, c = P.mean(s, e)
        if c:
            best = m
        s = H.next_block(s)
    return math.log(best / L) if best == best else 0.0


class Predictor:
    def __init__(self, weights, track):
        self.w, self.track = weights, track
        self.variants = [k.split(":", 1)[1] for k in weights["banks"][track] if k.startswith("B:")]

    def _predict_bank(self, bank, X, origin):
        """origin: one Timestamp, or a per-row array of origin months for batched prediction."""
        Xb = X.reindex(columns=bank["features"]).copy()
        out = np.full(len(Xb), np.nan)
        if bank["split"] is None:
            model, allnan = bank["models"]["all"]
            Xb[allnan] = 0.0
            out[:] = model.predict(Xb)
        elif bank["split"] == "h":
            h = X["h"].to_numpy()
            for key, (model, allnan) in bank["models"].items():
                lo, hi = (int(x) for x in key.split("-"))
                m = (h >= lo) & (h <= hi)
                if m.any():
                    Xs = Xb[m].copy(); Xs[allnan] = 0.0
                    out[m] = model.predict(Xs)
        elif bank["split"] == "month":
            months = np.full(len(Xb), origin.month) if isinstance(origin, pd.Timestamp) else np.asarray(origin)
            for mth in np.unique(months):
                model, allnan = bank["models"][str(int(mth))]
                sel = months == mth
                Xs = Xb[sel].copy(); Xs[allnan] = 0.0
                out[sel] = model.predict(Xs)
        elif bank["split"] == "month_h":
            months = np.full(len(Xb), origin.month) if isinstance(origin, pd.Timestamp) else np.asarray(origin)
            h = X["h"].to_numpy()
            for key, (model, allnan) in bank["models"].items():
                mth, rng = key.split(":")
                lo, hi = (int(x) for x in rng.split("-"))
                m = (months == int(mth)) & (h >= lo) & (h <= hi)
                if m.any():
                    Xs = Xb[m].copy(); Xs[allnan] = 0.0
                    out[m] = model.predict(Xs)
        return out

    def model_plogs(self, bank_key, X, origin):
        """Each model's predicted log(target/L) (its own base level added back)."""
        out = {}
        for v in self.variants:
            bank = self.w["banks"][self.track][f"{bank_key}:{v}"]
            tbl = self.w["config"]["bank_variants"][v].get("table")
            if tbl == "daily31":
                continue                                   # daily-target banks are used through daily31agg
            if tbl == "block1":
                Xb = X.copy()
                Xb["h"] = 1; Xb["h_end"] = 10; Xb["plen"] = 10
                out[v] = Xb[bank["base"]].to_numpy() + self._predict_bank(bank, Xb, origin)
                continue
            out[v] = X[bank["base"]].to_numpy() + self._predict_bank(bank, X, origin)
        return out

    def daily31agg(self, bank_key, fb, item, origin, blocks, L):
        """Block-mean forecast from the daily (h=1..31) bank: mean of predicted prices over the block's non-Sunday days."""
        key = f"{bank_key}:daily31"
        if key not in self.w["banks"][self.track]:
            return None
        bank = self.w["banks"][self.track][key]
        base = fb.origin_features(item, origin)
        rows, _ = fb.rows(item, origin, "daily31", base)
        Xd = pd.DataFrame([r for r, _, _ in rows])
        for it in D.ITEMS:
            Xd[f"is_{it}"] = float(it == item)
        plog_d = Xd[bank["base"]].to_numpy() + self._predict_bank(bank, Xd, origin)
        price = {s: L * math.exp(p) for (r, s, e), p in zip(rows, plog_d)}
        out = []
        for s, e in blocks:
            vals = [price[d] for d in pd.date_range(s, e, freq="D") if d.dayofweek != 6 and d in price]
            out.append(math.log(np.mean(vals) / L) if vals else np.nan)
        return np.array(out)

    def candidates(self, bank_key, X, blk, origin, extra=None):
        g = self.model_plogs(bank_key, X, origin)
        e50, e35, e20 = X["e50"].to_numpy(), X["e35"].to_numpy(), X["e20"].to_numpy()
        seas = X["seas"].fillna(0.0).to_numpy()
        n = len(X)
        blk = np.broadcast_to(np.asarray(blk, dtype=float), (n,))       # scalar per origin, or per row (batched)
        c = {"last": np.zeros(n), "ewma50": e50, "ewma35": e35, "ewma20": e20, "block": np.full(n, blk),
             "ewma50+0.5seas": e50 + 0.5 * seas, "block+0.5seas": blk + 0.5 * seas}
        for v, core in g.items():
            c[v] = core
            c[v + "+ewma50"] = (core + e50) / 2
            c[v + "+block"] = (core + blk) / 2
            c[v + "+ewma+seas"] = 0.5 * core + 0.5 * (e50 + seas)
        base_vars = [v for v in g if not self.w["config"]["bank_variants"][v].get("table") and v != "gbm_coint"]
        mean_models = np.mean([g[v] for v in (base_vars or list(g))], axis=0)
        c["mean_models"] = mean_models
        c["mean_models+ewma50"] = (mean_models + e50) / 2
        if self.track == "short":
            h = X["h"].to_numpy()
            for v in g:
                c["h1last_" + v] = np.where(h == 1, 0.0, g[v])
        if extra:
            c.update(extra)
        return c


def resolve(cands, method):
    """'A|B' = equal log-space blend of candidates."""
    parts = method.split("|")
    return np.mean([cands[p] for p in parts], axis=0)



def case_inputs(pred, fb, track, cases):
    """Feature rows and model candidates for every (case, item). Without a daily31 bank the candidates of all cases
    are predicted in one batch per bank key (row-wise models: same values as one call per case, much faster)."""
    out = {}
    for item in D.ITEMS:
        recs = []
        for k, (case_id, o, wins) in enumerate(cases):
            base = fb.origin_features(item, o)
            if base is None:
                raise ValueError(f"{case_id} {o.date()} {item}: no price observed before the origin")
            rows, L = fb.rows(item, o, track, base)
            if [(s_, e_) for _, s_, e_ in rows] != wins:
                raise ValueError(f"{case_id} {o.date()}: cases.json targets {wins} differ from the model's windows "
                                 f"{[(s_, e_) for _, s_, e_ in rows]}")
            X = pd.DataFrame([r for r, _, _ in rows])
            for it in D.ITEMS:
                X[f"is_{it}"] = float(it == item)
            recs.append((k, o, rows, L, X, block_mean_log(fb, item, o, L), "A" if o <= BANK_CUTOFF else "B"))
        batched = not any(key.endswith(":daily31") for key in pred.w["banks"][track])
        for bk in ("A", "B"):
            sel = [r for r in recs if r[6] == bk]
            if not sel:
                continue
            if batched:
                Xall = pd.concat([r[4] for r in sel], ignore_index=True)
                blk = np.concatenate([np.full(len(r[4]), r[5]) for r in sel])
                months = np.concatenate([np.full(len(r[4]), r[1].month) for r in sel])
                cands = pred.candidates(bk, Xall, blk, months)
                pos = 0
                for k, o, rows, L, X, b, _ in sel:
                    n = len(X)
                    out[(item, k)] = (rows, L, X, {c: v[pos:pos + n] for c, v in cands.items()})
                    pos += n
            else:
                for k, o, rows, L, X, b, _ in sel:
                    extra = None
                    if track != "short":
                        agg = pred.daily31agg(bk, fb, item, o, [(s, e) for (_, s, e) in rows], L)
                        extra = {"daily31agg": agg} if agg is not None else None
                    out[(item, k)] = (rows, L, X, pred.candidates(bk, X, b, o, extra))
    return out


def predict_track(track, weights, fb, cfg, cases):
    rules = cfg["rules"][track]
    pred = Predictor(weights, track)
    # holiday rules: {holiday name: rules}; legacy keys chuseok_short / chuseok_block map to the Chuseok entry
    hs = dict(cfg.get("holiday_short", {})); hb = dict(cfg.get("holiday_block", {}))
    if cfg.get("chuseok_short"):
        hs[CHUSEOK] = cfg["chuseok_short"]
    if cfg.get("chuseok_block"):
        hb[CHUSEOK] = cfg["chuseok_block"]
    short_rules = {n: r for n, r in hs.items() if r} if track == "short" else {}
    block_rules = {n: r.get(track, {}) for n, r in hb.items() if r.get(track)} if track != "short" else {}
    holidays = load_holidays() if (short_rules or block_rules) else None
    guard = cfg.get("holiday_guard") or {}
    inputs = case_inputs(pred, fb, track, cases)
    rows_out, audit = [], []
    for k, (case_id, o, wins) in enumerate(cases):
        bank_key = "A" if o <= BANK_CUTOFF else "B"
        per_item = {}
        for item in D.ITEMS:
            rule = rules[item]
            m = rule["method"]
            rows, L, X, cands = inputs[(item, k)]
            info = {"method": m}
            plog = resolve(cands, m)
            if "state_space" in rule:
                ss = rule["state_space"]
                lam = float(ss.get("lam", 0.0))
                w_max = float(ss.get("w_max", 0.0))
                tgt_name = ss.get("target", "ewma50+0.5seas")
                h_frac = X["h"].to_numpy(dtype=float) / 10.0
                if lam > 0:
                    vol = X["vol30"].fillna(0.0).to_numpy(dtype=float)
                    plog = plog - lam * (vol ** 2) * h_frac
                shrink = rule.get("shrink", 1.0)
                p_core = L * np.exp(np.clip(plog, -math.log(4), math.log(4))) * shrink
                if w_max > 0 and tgt_name in cands:
                    p_tgt = L * np.exp(np.clip(cands[tgt_name], -math.log(4), math.log(4))) * shrink
                    w_h = w_max * h_frac
                    pv = (1.0 - w_h) * p_core + w_h * p_tgt
                else:
                    pv = p_core
                info["state_space"] = {"lam": lam, "w_max": w_max, "target": tgt_name}
            else:
                c_vs = rule.get("volshrink")
                if c_vs:
                    plog = plog - c_vs * X["vol30"].fillna(0.0).to_numpy() ** 2 * X["h"].to_numpy()
                pv = L * np.exp(np.clip(plog, -math.log(4), math.log(4))) * rule.get("shrink", 1.0)
            tyear = rows[0][1].year
            for hname, hr in short_rules.items():
                if item in hr and not holiday_allowed(holidays, hname, tyear, guard.get(hname)):
                    info[f"holiday_guard_{hname}"] = "skipped (holiday date outside derivation span)"
                elif item in hr:
                    mult = chuseok_short_mult(holidays, item, [s for (r, s, e) in rows], hr, hname)
                    pv = pv * mult
                    if (mult != 1).any():
                        info[f"holiday_mult_{hname}"] = [round(float(x), 3) for x in mult]
            for hname, hr in block_rules.items():
                if item in hr and not holiday_allowed(holidays, hname, tyear, guard.get(hname)):
                    info[f"holiday_guard_{hname}"] = "skipped (holiday date outside derivation span)"
                elif item in hr:
                    bm = chuseok_block_mult(holidays, item, rows[0][1], hr, hname)
                    pv = pv * bm
                    if bm != 1.0:
                        info[f"holiday_mult_{hname}"] = bm
            per_item[item] = [(s, e, float(max(0.0001, min(1e9, p)))) for (r, s, e), p in zip(rows, pv)]
            audit.append({"case": case_id, "origin": str(o.date()), "item": item, "last_price": L,
                          "last_obs": str(fb.price[item].last(o)[1].date()), "bank": bank_key, **info})
        n = len(per_item["cabbage"])
        for j in range(n):
            s, e, _ = per_item["cabbage"][j]
            ident = [case_id, str(o.date())] + ([str(s.date())] if track == "short" else [str(s.date()), str(e.date())])
            rows_out.append(ident + [f"{per_item[i][j][2]:.4f}" for i in D.ITEMS])
    return rows_out, audit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True, choices=["short", "long1", "long2"])
    ap.add_argument("--weights", default=str(HERE / "weights.joblib"))
    ap.add_argument("--output", required=True)
    ap.add_argument("--cases", default="", help="cases.json (default: input/cases.json next to the inference data)")
    ap.add_argument("--audit", default="")
    ap.add_argument("--config", default=str(HERE / "config.json"), help="rule file (rules / chuseok_*); banks come from --weights")
    a = ap.parse_args()
    weights = joblib.load(a.weights)
    cfg = dict(weights["config"])
    disk = json.loads(Path(a.config).read_text(encoding="utf-8"))   # prediction-time rules from disk
    for k in ("rules", "chuseok_short", "chuseok_block", "holiday_short", "holiday_block", "holiday_guard"):
        cfg[k] = disk.get(k, {})          # prediction-time rules come from the config file on disk only
    cases_path = a.cases or find_cases()
    cases = load_cases(cases_path, a.track)
    if D.has_case_inputs(cases_path):
        rows, audit = [], []
        for case in cases:
            case_id, origin, _ = case
            with D.inference_case(cases_path, case_id, origin):
                fb = H.FeatureBuilder(D.bundle(infer=True), extras=X2.Extras(train=True, infer=True))
                case_rows, case_audit = predict_track(a.track, weights, fb, cfg, [case])
                rows.extend(case_rows)
                audit.extend(case_audit)
    else:
        fb = H.FeatureBuilder(D.bundle(infer=True), extras=X2.Extras(train=True, infer=True))
        rows, audit = predict_track(a.track, weights, fb, cfg, cases)
    stream = io.StringIO(newline="")
    w = csv.writer(stream)
    w.writerow(columns(a.track))
    w.writerows(rows)
    Path(a.output).write_bytes(stream.getvalue().encode("utf-8-sig"))
    if a.audit:
        Path(a.audit).write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    print(a.track, "rows:", len(rows), "->", a.output)


if __name__ == "__main__":
    main()
