"""Score a wasm on the 107 unselected fold-3 flights (honest set for the learned net: fold 3 never trained on). Table -> learned_c/tables/f3_<name>.json
  python -B -m research.single_model.learned_c.runfold3 --name X --wasm path.wasm [--workers 24]"""
import argparse, json, os
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
POOL = Path('/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool'); HERE = Path(__file__).resolve().parent
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--name', required=True); ap.add_argument('--wasm', type=Path, required=True); ap.add_argument('--workers', type=int, default=24)
    a = ap.parse_args()
    out = RV.OUT / ('lc_f3_' + a.name)
    sc = RV.run_guest_fast(a.wasm, POOL, out / 'eval', workers=a.workers, name=a.name)
    d = json.loads(Path(sc).read_text()); (HERE / 'tables').mkdir(exist_ok=True)
    rows = [dict(episode=r['episode'], ate=r.get('ate_full'), completed=r.get('completed'), filled=r.get('filled_full'), peak_fuel=r.get('peak_fuel_per_frame')) for r in d['rows']]
    (HERE / 'tables' / f'f3_{a.name}.json').write_text(json.dumps(rows))
    ok = [r['ate'] for r in rows if r['ate'] is not None]; print(a.name, 'n', len(ok), 'mean %.4f' % (sum(ok) / len(ok)))
if __name__ == '__main__': main()
