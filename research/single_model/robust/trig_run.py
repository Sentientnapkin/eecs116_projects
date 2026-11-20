"""Run the RB_DEBUG build (b6r.c) under the 5 B7 nudge sets on the high-variance flights of out/B7. usage: trig_run.py"""
import json, os, sys
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
from research.single_model.robust import score_robust as S
HERE = S.HERE
rows = json.loads((HERE / 'out/B7/replicates_fresh.json').read_text())['rows']
hv = [r['episode'] for r in rows if r['high_variance']]
pool = RV.OUT / 'rb_hvpool'; pool.mkdir(exist_ok=True)
for e in hv:
    for ext in ('zip', 'json'):
        d = pool / f'{e}.{ext}'
        if not d.exists(): d.symlink_to(S.FRESH_POOL / f'{e}.{ext}')
src = HERE / 'b6r.c'
for k in range(5):
    wasm, dd = S.build_rep(src, 'dbg', k, '-DRB_DEBUG'.lstrip('-') if False else 'RB_DEBUG=1')
    sc = RV.run_guest_fast(wasm, pool, RV.OUT / f'rb_dbg_r{k}' / 'eval', workers=24, name=f'dbg{k}')
    print(k, dd, flush=True)
