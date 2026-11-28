#!/bin/bash
# evalcand.sh CKPT.pt [SCALE] : score a cheap-model checkpoint with the exact server metrics on the 19 proxy flights,
# the tuning conf sets and holdout 240; compares per flight with outputting zero and with the submitted model.
# SCALE (default 1) multiplies the predicted velocity (a global shrink; folded into the exported weights).
set -e
C=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/cheap
CK=$1; SC=${2:-1}; TAG=$(basename $CK .pt)_x$SC
~/.venv_gru/bin/python - "$CK" "$SC" "$HOME/data/cand_$TAG.npz" <<'PY'
import sys, numpy as np, torch
sys.path.insert(0, "/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/cheap")
import export_mlp as em
m = em.load(sys.argv[1]); s = float(sys.argv[2]); c = torch.load(sys.argv[1], weights_only=False)
np.savez(sys.argv[3], Wv=s * m["Wv"], W1=m["W1"], B1=m["B1"], W2=s * m["W2"], act=m["act"], grows=np.array(c.get("grows", [2, 7])))
PY
source ~/.venv/bin/activate
[ -f ~/data/fp_cand_$TAG.json ] || J=12 python $C/fingerprint.py ~/data/cand_$TAG.npz ~/data/fp_cand_$TAG.json \
  "proxy=$HOME/data/proxy19/*.zip" "ho=$HOME/data/ho240/*.zip" "tune_fconf=$HOME/data/tune/fconf/*.zip" \
  "tune_st1conf=$HOME/data/tune/st1conf/*.zip" "tune_st2conf=$HOME/data/tune/st2conf/*.zip" > /dev/null
python - "$HOME/data/fp_cand_$TAG.json" "$TAG" <<'PY'
import json, sys, os, numpy as np
H = os.path.expanduser("~/data")
c = {(r["pool"] if r["pool"] == "proxy" else "x", r["name"]): r["metrics"] for r in json.load(open(sys.argv[1])) if "metrics" in r}
sub = {r["name"]: r["metrics"] for r in json.load(open(f"{H}/fp_submitted.json")) if "metrics" in r}
pools = {}
for r in json.load(open(sys.argv[1])):
    if "metrics" in r: pools.setdefault(r["pool"], []).append(r["name"])
print(f"== {sys.argv[2]}")
for p in ["proxy", "ho", "tune_fconf", "tune_st1conf", "tune_st2conf"]:
    k = "proxy" if p == "proxy" else "x"
    n = [x for x in pools.get(p, []) if x in sub]
    a = np.array([c[(k, x)]["ate_rmse"] for x in n]); z = np.array([c[(k, x)]["zero_ate"] for x in n]); s = np.array([sub[x]["ate_rmse"] for x in n])
    print(f"  {p:13s} n={len(n):3d}  cand {a.mean():.3f}  submitted {s.mean():.3f}  zero {z.mean():.3f} | cand<zero {np.mean(a<z):4.0%}  "
          f"cand<submitted {np.mean(a<s):4.0%}  worst cand/zero {np.max(a/z):.2f}")
PY
