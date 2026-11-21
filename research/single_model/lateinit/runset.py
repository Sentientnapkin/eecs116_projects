"""Build a tailcap source (with -D defines) and score it on sel144 (visible selected, never fold 4) + fresh711 (+ chaos replicates).
  PYTHONPATH=. python -B research/single_model/tailcap/runset.py NAME SRC.c ["DEFINES"] [--reps 1] [--sets sel,fresh] [--workers 24]
Results: research/results/single_model/tc_<NAME>_r<k>/ ; table tailcap/tables/<NAME>_r<k>.json (episode, ate, peak_fuel, set)."""
import argparse, json, os, re, sys
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
HERE = Path(__file__).resolve().parent
CMAKE = RV.ROOT / 'research/single_model/bulk/exact/CMakeLists.txt'
POOLS = {'sel': HERE.parent / 'tailcap/pool_sel144', 'fresh': Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')}
NUDGE = {0: (1.0, 1.0), 1: (1.01, 1.01), 2: (0.99, 0.99)}

def nudge(defs, k):
    # replicate chaos: PIXEL_STD / DETECT_MIN_SCORE scaling, as evalrep (appended defines)
    if k == 0: return defs
    f = NUDGE[k][0]
    return (defs + f' PIXEL_STD={1.5*f:.6g} DETECT_MIN_SCORE={1000.0*f:.6g}').strip()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('src'); ap.add_argument('defs', nargs='?', default='')
    ap.add_argument('--reps', type=int, default=1); ap.add_argument('--sets', default='sel,fresh'); ap.add_argument('--workers', type=int, default=24)
    ap.add_argument('--first', type=int, default=0); ap.add_argument('--cmake', default='')
    a = ap.parse_args()
    global CMAKE
    if a.cmake: CMAKE = RV.ROOT / a.cmake
    (HERE / 'tables').mkdir(exist_ok=True)
    for k in range(a.first, a.first + a.reps):
        nm = f'li_{a.name}_r{k}'
        wasm = RV.build(Path(a.src), CMAKE, nudge(a.defs, k), nm)
        rows = []
        for st in a.sets.split(','):
            sc = RV.run_guest_fast(wasm, POOLS[st], RV.OUT / nm / ('eval_' + st), workers=a.workers, name=nm)
            for r in json.loads(Path(sc).read_text())['rows']:
                rows.append(dict(episode=r['episode'], set=st, ate=r.get('ate_full'), peak_fuel=r.get('peak_fuel_per_frame'), filled=r.get('filled_full'), completed=r.get('completed')))
        (HERE / 'tables' / f'{a.name}_r{k}.json').write_text(json.dumps(rows))
        print(a.name, k, 'done', flush=True)
main()
