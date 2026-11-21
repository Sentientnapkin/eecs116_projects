"""score the B15 wasm: sel144 twice (determinism) + fresh 711 once. outputs under results/single_model/tc_pf15_*"""
import json, os, sys
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
W = Path('research/single_model/tailcap/gp_msckf_startup_b15_pv25.wasm')
P = Path('research/single_model/tailcap')
for tag, pool in (('sel_a', P / 'pool_sel144'), ('sel_b', P / 'pool_sel144'), ('fresh', Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool'))):
    sc = RV.run_guest_fast(W, pool, RV.OUT / ('tc_pf15_' + tag), workers=24, name='pf15' + tag)
    rows = json.loads(Path(sc).read_text())['rows']
    json.dump([dict(episode=r['episode'], ate=r.get('ate_full'), peak=r.get('peak_fuel_per_frame'), p95=r.get('p95_fuel_per_frame'), filled=r.get('filled_full'), completed=r.get('completed')) for r in rows], open(P / 'preflight_b15' / f'rows_{tag}.json', 'w'))
    print(tag, 'done', flush=True)
