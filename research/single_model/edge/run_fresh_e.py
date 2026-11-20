"""Score a prebuilt wasm on the 711 fresh flights (copy of fresh/run_fresh.py writing only under edge/ and results/single_model/edge_fresh_*).
Fold-4 scenes are scored by the harness (cannot be skipped cheaply) but dropped in all analysis (analysis only reads non-fold-4)."""
import argparse, json, os, sys
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
POOL = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')
HERE = Path(__file__).resolve().parent
OUT = RV.ROOT / 'research/results/single_model'
ap = argparse.ArgumentParser(); ap.add_argument('--name', required=True); ap.add_argument('--wasm', type=Path, required=True); ap.add_argument('--workers', type=int, default=24)
a = ap.parse_args()
sc = RV.run_guest_fast(a.wasm, POOL, OUT / ('edge_fresh_' + a.name) / 'eval', workers=a.workers, name=a.name)
d = json.loads(Path(sc).read_text())
rows = {r['episode']: r.get('ate_full') for r in d['rows']}
(HERE / f'ftable_{a.name}.json').write_text(json.dumps(rows))
print(a.name, len(rows))
