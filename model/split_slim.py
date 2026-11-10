"""Make the one-track weights file shipped in a model.zip from train.py's output, without changing any prediction:
keep only this track's banks, drop banks the track's rules never read (prune_weights logic), blank tree statistics
predict() never reads (impurity, node sample counts) and save with lzma.

  python split_slim.py <weights.joblib from train.py> <rules config.json> <track> <out.joblib>"""
import sys, json, joblib
from sklearn.tree._tree import Tree

src, rules_path, track, out = sys.argv[1:5]
w = joblib.load(src)
rules = json.loads(open(rules_path, encoding="utf-8").read())["rules"][track]
banks = w["banks"][track]
variants = sorted({k.split(":", 1)[1] for k in banks})
names = []
for r in rules.values():
    names += r["method"].split("|") + [r.get("fallback", "")]
keep = [v for v in variants if any(n == v or n.startswith(v + "+") or n == "h1last_" + v for n in names)]
banks = {k: b for k, b in banks.items() if k.split(":", 1)[1] in keep}

seen = set()
def strip(o):
    if id(o) in seen:
        return
    seen.add(id(o))
    if hasattr(o, "tree_") and isinstance(o.tree_, Tree):
        st = o.tree_.__getstate__(); n = st["nodes"].copy()
        for f in ("impurity", "n_node_samples", "weighted_n_node_samples"):
            n[f] = 0
        st["nodes"] = n; o.tree_.__setstate__(st); return
    for a in (getattr(o, "estimators_", None), getattr(o, "steps", None)):
        if a is not None:
            for e in a:
                strip(e[1] if isinstance(e, tuple) else e)
    if isinstance(o, dict):
        for v in o.values(): strip(v)
    elif isinstance(o, (list, tuple)):
        for v in o: strip(v)
strip(banks)

cfg = json.loads(open(rules_path, encoding="utf-8").read())
if keep != variants:
    cfg["pruned_banks"] = {"kept": keep, "reason": "only banks read by this track's rules; train.py still trains all"}
joblib.dump({"version": cfg["version"], "config": cfg, "banks": {track: banks}}, out, compress=("lzma", 6))
print(track, "banks kept:", len(keep), "of", len(variants), "->", out)
