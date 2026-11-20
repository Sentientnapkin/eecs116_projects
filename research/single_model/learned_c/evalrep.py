"""3 chaos replicates (r0 = as is; r1/r2 multiply PIXEL_STD and DETECT_MIN_SCORE by 1.01 / 0.99, as autoloop) of a C source on the visible selected flights (s171: folds 0-3,
fold 4 rows dropped immediately) and/or the 107 unselected fold-3 flights (f3). Tables: learned_c/tables/<set>_<name>_r<k>.json ; prints replicate-mean search / val / f3 and peak fuel.
  PYTHONPATH=. python -B research/single_model/learned_c/evalrep.py NAME SRC.c [--set s171,f3] [--reps 3] [--workers 24]"""
import argparse, json, os, re, sys
from pathlib import Path
import numpy as np
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
HERE = Path(__file__).resolve().parent
F = json.load(open(HERE / 'feats.json'))
F3 = Path('/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool')


def nudge(text, k):
    if k == 0:
        return text
    f = {1: 1.01, 2: 0.99}[k]
    for n in ('PIXEL_STD', 'DETECT_MIN_SCORE'):
        pat = re.compile(r'^(\s*#define\s+' + n + r'\s+)(\S+)(.*)$', re.M)
        text = pat.sub(lambda m: m.group(1) + ('%.6g' % (float(m.group(2)) * f)) + m.group(3), text, count=1)
    return text


def run(name, src, sets, reps, workers):
    for k in range(reps):
        nm = f'{name}_r{k}'
        d = RV.OUT / ('lc_' + nm)
        d.mkdir(parents=True, exist_ok=True)
        (d / 'in.c').write_text(nudge(Path(src).read_text(), k))
        wasm = RV.build(d / 'in.c', RV.CMAKE_DEFAULT, '', 'lc_' + nm)
        for st in sets:
            pool = RV.EPISODES if st == 's171' else F3
            sc = RV.run_guest_fast(wasm, pool, d / ('eval' if st == 's171' else 'eval_f3'), workers=workers, name=nm)
            rows = [dict(episode=r['episode'], ate=r.get('ate_full'), peak_fuel=r.get('peak_fuel_per_frame'), filled=r.get('filled_full'), completed=r.get('completed'))
                    for r in json.loads(Path(sc).read_text())['rows'] if r['episode'] in F]   # fold-4 rows never kept
            (HERE / 'tables').mkdir(exist_ok=True)
            (HERE / 'tables' / f'{st}_{nm}.json').write_text(json.dumps(rows))


def load_rep(st, name, reps):
    T = [{r['episode']: r for r in json.load(open(HERE / 'tables' / f'{st}_{name}_r{k}.json'))} for k in range(reps)]
    eps = sorted(T[0])
    return eps, {e: float(np.mean([t[e]['ate'] for t in T])) for e in eps}, T


def summarize(name, reps, sets):
    for st in sets:
        eps, ate, T = load_rep(st, name, reps)
        fuel = max((r['peak_fuel'] or 0) for t in T for r in t.values())
        if st == 's171':
            for lab, folds in (('search', (0, 1, 2)), ('val', (3,))):
                m = [e for e in eps if F[e]['fold'] in folds]
                print(f'{name} {lab:6s} n={len(m)} rep-mean {np.mean([ate[e] for e in m]):.3f}  per-rep ' + ' '.join('%.3f' % np.mean([t[e]['ate'] for e in m]) for t in T) + f'  max peak fuel {fuel/1e6:.2f} M')
        else:
            print(f'{name} f3 n={len(eps)} rep-mean {np.mean(list(ate.values())):.3f}  per-rep ' + ' '.join('%.3f' % np.mean([t[e]['ate'] for e in eps]) for t in T) + f'  max peak fuel {fuel/1e6:.2f} M')
    # replicate-mean tables for cmp.py
    for st in sets:
        eps, ate, T = load_rep(st, name, reps)
        (HERE / 'tables' / f'{st}_{name}.json').write_text(json.dumps([dict(episode=e, ate=ate[e], peak_fuel=max((t[e]['peak_fuel'] or 0) for t in T)) for e in eps]))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('name'); ap.add_argument('src'); ap.add_argument('--set', default='s171'); ap.add_argument('--reps', type=int, default=3); ap.add_argument('--workers', type=int, default=24)
    ap.add_argument('--summ_only', action='store_true')
    a = ap.parse_args(); sets = a.set.split(',')
    if not a.summ_only:
        run(a.name, a.src, sets, a.reps, a.workers)
    summarize(a.name, a.reps, sets)
