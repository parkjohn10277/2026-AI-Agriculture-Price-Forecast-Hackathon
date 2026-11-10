"""Recompute fixed-configuration validation using only 2020-2024 data.
Evaluation of the fixed configuration on 2020-2024 data and verification of its numerical recipes. The script does not search over methods, holiday windows, mixture weights or damping strengths; it does not establish the historical selection procedure.
The fixed recipes use residual r = log(actual / last_price) - raw_model_log_ratio. Long-track cabbage and radish use round(exp(-var(r)), 4); short radish and long-track onion use round(exp(-0.5*var(r)), 4); short onion uses round(exp(-mean(r)), 4); other rules use 1.0. These are numerical recipes for the submitted configuration, not a proof of MAPE optimality. In particular, exp(-mean(r)) is an upward scale factor when mean(r) is negative; mean-log-residual centering would instead use exp(mean(r)).

Run: python validate_2020_2024.py [--out validation_2020_2024.json] [--recompute]
"""
import argparse, json, math, sys
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data as D, harness as H, extra_features2 as X2, train as T, predict as P

ACTIVE_VARS = {
    "short": ["b1_coint", "et", "et_hg_e20_x3", "et_hg_x3", "et_mf3", "pooled_mw"],
    "long1": ["et", "et_mf3_e20_wx", "pooled_mw"],
    "long2": ["et_clip", "et_mf3_e20_wx", "pooled_mw"],
}


def load_train_holidays_only():
    hol_path = D.TRAIN_DIR / "Supplementary/날씨와공휴일_2020_2024/public_holidays.csv"
    h = pd.read_csv(hol_path, encoding="utf-8-sig").drop_duplicates(["locdate", "dateName"])
    h["date"] = pd.to_datetime(h.locdate.astype(str), format="%Y%m%d")
    assert h["date"].max() <= pd.Timestamp("2024-12-31")
    return h


def build_2020_2024_origins(holidays):
    base_grid = set(pd.date_range("2020-07-10", "2024-12-30", freq="10D"))
    for yr in (2021, 2022, 2023, 2024):
        for hname in (P.CHUSEOK, P.SEOLLAL):
            cl = P.chuseok_closure(holidays, yr, hname)
            if cl is not None:
                s_cl, e_cl = cl
                for d in pd.date_range(s_cl - pd.Timedelta(days=35), e_cl + pd.Timedelta(days=5), freq="2D"):
                    if pd.Timestamp("2020-07-01") <= d <= pd.Timestamp("2024-12-30"):
                        base_grid.add(d)
    return pd.DatetimeIndex(sorted(base_grid))


def apply_rule_rowwise(sub, rule):
    L = sub["L"].to_numpy(dtype=float)
    parts = rule["method"].split("|")
    plog = np.mean([sub[p].to_numpy(dtype=float) for p in parts], axis=0)
    plog_adj = plog.copy()
    if "state_space" in rule:
        ss = rule["state_space"]
        lam = float(ss.get("lam", 0.0))
        w_max = float(ss.get("w_max", 0.0))
        tgt = ss.get("target", "ewma50+0.5seas")
        h_frac = sub["h"].to_numpy(dtype=float) / 10.0
        if lam > 0:
            plog_adj = plog_adj - lam * (sub["vol30"].fillna(0.0).to_numpy(dtype=float) ** 2) * h_frac
        sh = float(rule.get("shrink", 1.0))
        p_core = L * np.exp(np.clip(plog_adj, -math.log(4), math.log(4))) * sh
        if w_max > 0 and tgt in sub.columns:
            p_tgt = L * np.exp(np.clip(sub[tgt].to_numpy(dtype=float), -math.log(4), math.log(4))) * sh
            w_h = w_max * h_frac
            pv = (1.0 - w_h) * p_core + w_h * p_tgt
        else:
            pv = p_core
    else:
        if rule.get("volshrink"):
            plog_adj = plog_adj - float(rule["volshrink"]) * (sub["vol30"].fillna(0.0).to_numpy(dtype=float) ** 2) * sub["h"].to_numpy(dtype=float)
        pv = L * np.exp(np.clip(plog_adj, -math.log(4), math.log(4))) * float(rule.get("shrink", 1.0))
    return plog, pv


def derive_expected_shrink(track, item, sig2, mean_res):
    if item in ("garlic", "dried_pepper") or (track == "short" and item == "cabbage"):
        return 1.0, "unit (1.0)"
    if track in ("long1", "long2") and item in ("cabbage", "radish"):
        return round(float(math.exp(-sig2)), 4), "round(exp(-sigma^2), 4)"
    if (track == "short" and item == "radish") or (track in ("long1", "long2") and item == "onion"):
        return round(float(math.exp(-0.5 * sig2)), 4), "round(exp(-0.5 * sigma^2), 4)"
    if track == "short" and item == "onion":
        return round(float(math.exp(-mean_res)), 4), "round(exp(-mean_log_residual), 4)"
    return 1.0, "unit (1.0)"


def compute_validation_report(cfg):
    bundle = D.bundle(infer=False)
    max_price_date = bundle["prices"].index.max()
    assert max_price_date <= pd.Timestamp("2024-12-31"), f"Training bundle exceeded 2024-12-31: {max_price_date}"
    fb = H.FeatureBuilder(bundle, extras=X2.Extras(train=True, infer=False))
    holidays = load_train_holidays_only()
    origins = build_2020_2024_origins(holidays)

    tables = {}
    for tr in ("short", "long1", "long2", "block1"):
        df = T.build_table(fb, tr, origins, D.ITEMS)
        df = df[(df["origin"] <= pd.Timestamp("2024-12-30")) & (df["end"] <= pd.Timestamp("2024-12-31"))].reset_index(drop=True)
        assert df["end"].max() <= pd.Timestamp("2024-12-31")
        cache_blk = {}
        blks = []
        for item, o, L in zip(df["item"], df["origin"], df["L"]):
            k = (item, o)
            if k not in cache_blk:
                cache_blk[k] = P.block_mean_log(fb, item, o, L)
            blks.append(cache_blk[k])
        df["blk"] = blks
        tables[tr] = df

    rules = cfg["rules"]
    holiday_short = cfg.get("holiday_short", {})
    holiday_block = cfg.get("holiday_block", {})
    holiday_guard = cfg.get("holiday_guard", {})

    records = {
        "schema": "nongnet-validation-2020-2024-v3",
        "diagnostic_scope": "This diagnostic uses harness.FeatureBuilder's stabilized OLS slopes in all folds. Reproduction of the stored long-track banks instead uses train.LongTrainingFeatureBuilder's centered np.polyfit slopes. The formulas are mathematically equivalent but need not produce identical tree fits in floating-point arithmetic. The base estimators are trained before each evaluation year. Scale statistics are pooled from the same 2022-2024 folds on which the adjusted configuration is evaluated; these adjusted metrics are not a nested, independent estimate of the final pipeline's generalization error.",
        "role": (
            'Evaluation of the fixed configuration on 2020-2024 data and verification of its numerical recipes. The script does not search over methods, holiday windows, mixture weights or damping strengths; it does not establish the historical selection procedure.'
        ),
        "verified_2020_2024_max_price_date": str(max_price_date.date()),
        "max_origin_date": "2024-12-30",
        "max_target_end_date": "2024-12-31",
        "rows_ending_after_2024_12_31": 0,
        "protocol": (
            "3-fold annual expanding-window out-of-sample backtest on 2020-2024 data only: fold 2022 models trained on "
            "target end <= 2021-12-31, fold 2023 on target end <= 2022-12-31, and fold 2024 on target end <= 2023-12-31; "
            "evaluated on 2022-2024 origins with target end <= 2024-12-31."
        ),
        "shrinkage_derivation": (
            'The fixed recipes use residual r = log(actual / last_price) - raw_model_log_ratio. Long-track cabbage and radish use round(exp(-var(r)), 4); short radish and long-track onion use round(exp(-0.5*var(r)), 4); short onion uses round(exp(-mean(r)), 4); other rules use 1.0. These are numerical recipes for the submitted configuration, not a proof of MAPE optimality. In particular, exp(-mean(r)) is an upward scale factor when mean(r) is negative; mean-log-residual centering would instead use exp(mean(r)).'
        ),
        "holiday_configuration": {
            "holiday_guard": holiday_guard,
            "holiday_guard_enabled": bool(holiday_guard),
            "holiday_short": holiday_short,
            "holiday_block": holiday_block,
            "derivation_formula": (
                "Short-track holiday multipliers = round(exp(0.75 * mean_fold_log_residual_2022_2024), 4); "
                "Long1-track Seollal radish block multipliers (blocks 0, 1, 2) = round(exp(0.50 * mean_fold_log_residual_2022_2024), 4)."
            ),
            "note": (
                "holiday_guard is empty ({}) in config.json, so statutory holiday multipliers (Chuseok and Seollal) "
                "are applied without a day-of-year guard."
            ),
        },
        "tracks": {},
        "holiday_folds_2022_2024": {},
    }

    oos_by_track = {}
    for tr in ("short", "long1", "long2"):
        df = tables[tr]
        fold_parts = []
        for yr in (2022, 2023, 2024):
            cutoff = pd.Timestamp(f"{yr-1}-12-31")
            banks = {}
            for var in ACTIVE_VARS[tr]:
                v = cfg["bank_variants"][var]
                dft = tables[v["table"]] if v.get("table") else df
                ft = X2.select_features([c for c in dft.columns if c not in T.META and c != "blk"], v.get("feature_set", "base"))
                banks[f"B:{var}"] = T.fit_bank(dft, cutoff, tr, cfg, var, ft)
            pred = P.Predictor({"config": cfg, "banks": {tr: banks}}, tr)
            sub_yr = df[(df["origin"].dt.year == yr) & (df["end"] <= pd.Timestamp("2024-12-31"))].reset_index(drop=True)
            assert (sub_yr["origin"] > cutoff).all() and (sub_yr["end"] <= pd.Timestamp("2024-12-31")).all()
            cands = pred.candidates("B", sub_yr, sub_yr["blk"].to_numpy(), sub_yr["origin"].dt.month.to_numpy())
            fold_parts.append(pd.concat([sub_yr[["item", "origin", "start", "end", "h", "L", "y", "vol30", "blk"]], pd.DataFrame(cands)], axis=1))
        oos = pd.concat(fold_parts, ignore_index=True)
        assert oos["end"].max() <= pd.Timestamp("2024-12-31")
        oos_by_track[tr] = oos

        records["tracks"][tr] = {}
        for item, r in rules[tr].items():
            sub = oos[oos["item"] == item].reset_index(drop=True)
            Y = sub["L"].to_numpy(dtype=float) * np.exp(sub["y"].to_numpy(dtype=float))
            L = sub["L"].to_numpy(dtype=float)
            plog, pv = apply_rule_rowwise(sub, r)
            raw_res = sub["y"].to_numpy(dtype=float) - plog
            sig2 = float(np.var(raw_res))
            mean_res = float(np.mean(raw_res))
            derived_sh, sh_formula = derive_expected_shrink(tr, item, sig2, mean_res)
            cfg_sh = float(r.get("shrink", 1.0))
            if abs(cfg_sh - derived_sh) > 1e-4:
                raise ValueError(
                    f"Shrink mismatch on {tr}.{item}: config.json has {cfg_sh}, but 2022-2024 formula ({sh_formula}) gives {derived_sh}"
                )
            mape_rule = float(np.mean(np.abs(pv - Y) / Y * 100))
            p_blk = L * np.exp(sub["block"].to_numpy(dtype=float))
            p_seas = L * np.exp(sub["block+0.5seas"].to_numpy(dtype=float))
            mape_blk = float(np.mean(np.abs(p_blk - Y) / Y * 100))
            mape_seas = float(np.mean(np.abs(p_seas - Y) / Y * 100))
            records["tracks"][tr][item] = {
                "method": r["method"],
                "shrink": cfg_sh,
                "derived_shrink_2022_2024": derived_sh,
                "shrink_formula": sh_formula,
                "state_space": r.get("state_space"),
                "volshrink": r.get("volshrink"),
                "n_eval_rows_2022_2024": int(len(sub)),
                "max_origin_date": str(sub["origin"].max().date()),
                "max_target_end_date": str(sub["end"].max().date()),
                "cv_2022_2024_mape_pct": round(mape_rule, 4),
                "benchmark_block_mape_pct": round(mape_blk, 4),
                "benchmark_block_seas_mape_pct": round(mape_seas, 4),
                "gain_vs_block_pt": round(mape_blk - mape_rule, 4),
                "gain_vs_block_seas_pt": round(mape_seas - mape_rule, 4),
                "log_residual_variance_2022_2024": round(sig2, 5),
                "log_residual_mean_2022_2024": round(mean_res, 5),
                "scale_exp_neg_residual_variance": round(float(math.exp(-sig2)), 4),
                "scale_exp_neg_half_residual_variance": round(float(math.exp(-0.5 * sig2)), 4),
                "scale_exp_neg_residual_mean": round(float(math.exp(-mean_res)), 4),
            }

    # Compute per-year (2022, 2023, 2024) holiday evaluation and verify formula-derived multipliers
    hol_eval = {}
    oos_short = oos_by_track["short"]
    for hname, hrules in holiday_short.items():
        for item, windows in hrules.items():
            sub = oos_short[oos_short["item"] == item].reset_index(drop=True)
            plog, pv_base = apply_rule_rowwise(sub, rules["short"][item])
            Y = sub["L"].to_numpy(dtype=float) * np.exp(sub["y"].to_numpy(dtype=float))
            mults = P.chuseok_short_mult(holidays, item, list(sub["start"]), hrules, hname)
            pv_hol = pv_base * mults
            mask = mults != 1.0
            by_year = {}
            fold_means = []
            for yr in (2022, 2023, 2024):
                ym = mask & (sub["start"].dt.year == yr).to_numpy()
                if ym.any():
                    eb = float(np.mean(np.abs(pv_base[ym] - Y[ym]) / Y[ym] * 100))
                    ea = float(np.mean(np.abs(pv_hol[ym] - Y[ym]) / Y[ym] * 100))
                    mres = round(float(np.mean(sub["y"].to_numpy(dtype=float)[ym] - plog[ym])), 4)
                    fold_means.append(mres)
                    by_year[str(yr)] = {
                        "n_rows": int(ym.sum()),
                        "mean_log_residual": mres,
                        "mape_before_pct": round(eb, 4),
                        "mape_after_pct": round(ea, 4),
                        "gain_pt": round(eb - ea, 4),
                    }
            if mask.any():
                mean_fold_res = float(np.mean(fold_means))
                derived_mult = round(float(math.exp(0.75 * mean_fold_res)), 4)
                for w_entry in windows:
                    cfg_mult = float(w_entry[2])
                    if abs(cfg_mult - derived_mult) > 1e-4:
                        raise ValueError(
                            f"Holiday multiplier mismatch on short.{hname}.{item}: config has {cfg_mult}, "
                            f"2022-2024 formula round(exp(0.75*mean_fold_res), 4) gives {derived_mult}"
                        )
                eb_all = float(np.mean(np.abs(pv_base[mask] - Y[mask]) / Y[mask] * 100))
                ea_all = float(np.mean(np.abs(pv_hol[mask] - Y[mask]) / Y[mask] * 100))
                hol_eval[f"short.{hname}.{item}"] = {
                    "windows": windows,
                    "mean_fold_log_residual_2022_2024": round(mean_fold_res, 5),
                    "derived_multiplier_exp_075_mean": derived_mult,
                    "n_rows_total_2022_2024": int(mask.sum()),
                    "mape_before_pct": round(eb_all, 4),
                    "mape_after_pct": round(ea_all, 4),
                    "gain_pt": round(eb_all - ea_all, 4),
                    "folds": by_year,
                }

    oos_l1 = oos_by_track["long1"]
    for hname, tr_map in holiday_block.items():
        if "long1" in tr_map:
            for item, bmap in tr_map["long1"].items():
                sub = oos_l1[oos_l1["item"] == item].reset_index(drop=True)
                plog, pv_base = apply_rule_rowwise(sub, rules["long1"][item])
                Y = sub["L"].to_numpy(dtype=float) * np.exp(sub["y"].to_numpy(dtype=float))
                mults = np.array([P.chuseok_block_mult(holidays, item, s, tr_map["long1"], hname) for s in sub["start"]])
                pv_hol = pv_base * mults
                mask = mults != 1.0
                by_year = {}
                fold_means = []
                for yr in (2022, 2023, 2024):
                    ym = mask & (sub["start"].dt.year == yr).to_numpy()
                    if ym.any():
                        eb = float(np.mean(np.abs(pv_base[ym] - Y[ym]) / Y[ym] * 100))
                        ea = float(np.mean(np.abs(pv_hol[ym] - Y[ym]) / Y[ym] * 100))
                        mres = round(float(np.mean(sub["y"].to_numpy(dtype=float)[ym] - plog[ym])), 4)
                        fold_means.append(mres)
                        by_year[str(yr)] = {
                            "n_rows": int(ym.sum()),
                            "mean_log_residual": mres,
                            "mape_before_pct": round(eb, 4),
                            "mape_after_pct": round(ea, 4),
                            "gain_pt": round(eb - ea, 4),
                        }
                if mask.any():
                    mean_fold_res = float(np.mean(fold_means))
                    derived_mult = round(float(math.exp(0.50 * mean_fold_res)), 4)
                    for b_key, cfg_mult in bmap.items():
                        if abs(float(cfg_mult) - derived_mult) > 1e-4:
                            raise ValueError(
                                f"Holiday block multiplier mismatch on long1.{hname}.{item}[{b_key}]: config has {cfg_mult}, "
                                f"2022-2024 formula round(exp(0.50*mean_fold_res), 4) gives {derived_mult}"
                            )
                    eb_all = float(np.mean(np.abs(pv_base[mask] - Y[mask]) / Y[mask] * 100))
                    ea_all = float(np.mean(np.abs(pv_hol[mask] - Y[mask]) / Y[mask] * 100))
                    hol_eval[f"long1.{hname}.{item}"] = {
                        "block_multipliers": bmap,
                        "mean_fold_log_residual_2022_2024": round(mean_fold_res, 5),
                        "derived_multiplier_exp_050_mean": derived_mult,
                        "n_rows_total_2022_2024": int(mask.sum()),
                        "mape_before_pct": round(eb_all, 4),
                        "mape_after_pct": round(ea_all, 4),
                        "gain_pt": round(eb_all - ea_all, 4),
                        "folds": by_year,
                    }
    records["holiday_folds_2022_2024"] = hol_eval
    return records


def _compare_reports(expected, actual, path=""):
    if isinstance(expected, dict) and isinstance(actual, dict):
        for k in expected:
            if k not in actual:
                raise ValueError(f"Missing key at {path}.{k}")
            _compare_reports(expected[k], actual[k], f"{path}.{k}")
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or abs(float(expected) - float(actual)) > 1e-3:
            raise ValueError(f"Validation mismatch at {path}: file has {actual}, recomputed {expected}")
    elif expected != actual:
        raise ValueError(f"Validation mismatch at {path}: file has {actual!r}, recomputed {expected!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--out", default=str(HERE / "validation_2020_2024.json"))
    ap.add_argument("--recompute", action="store_true", help="Always overwrite --out with freshly recomputed report")
    a = ap.parse_args()

    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    recomputed = compute_validation_report(cfg)
    out_path = Path(a.out)

    if out_path.exists() and not a.recompute:
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        _compare_reports(recomputed, existing)
        print(f"RECOMPUTED & VERIFIED: all statistics and configured numerical-recipe values in {out_path} match 2020-2024 out-of-sample recomputation (max_end=2024-12-31).")
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(recomputed, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"GENERATED: wrote freshly recomputed 2020-2024 validation report to {out_path} (max_end=2024-12-31).")



if __name__ == "__main__":
    main()
