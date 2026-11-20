"""Variance-aware scoring of a candidate on the 711 fresh flights (and optionally the 171 selected, folds 0-3 only).

  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B \
     -m research.single_model.robust.score_robust <src.c | wasm> --name rb_x --reps 5 [--rep0 scores.json] [--defines "A=1 B=2"]

Replicates: rep 0 = unnudged build (or --rep0 existing scores.json of the same build); reps 1..R-1 = 0.5-1% nudges of
PIXEL_STD / DETECT_MIN_SCORE / ACCEL_NOISE / KLT_MIN_EIG (NUDGES below; distinct from tails/rep.sh's +-1% pixel/detect pair).
The source gets #ifndef guards around those four #defines (bit-identical at default values, verified by wasm sha on B7).
A wasm argument is only accepted if its sha is a known build (KNOWN) since nudging needs the source.
Outputs (robust/out/<name>/): replicates.json, replicates.csv, summary.txt  (per flight: mean/std/min/max, flags
high_variance = range>1 m or std>0.5 m; consistently_bad = all replicates >3 m; plus tags, dev/confirm split).
Run dirs: research/results/single_model/rb_<name>_r<k>/. At most 2 replicates run concurrently (--par)."""
import argparse, csv, hashlib, json, os, re, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
os.environ['VIOBENCH_PNG_CACHE'] = '0'
import numpy as np
from research.single_model import run_variant as RV

HERE = Path(__file__).resolve().parent
SM = HERE.parent
FRESH_POOL = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')
RES = RV.OUT
# (PIXEL_STD, DETECT_MIN_SCORE, ACCEL_NOISE, KLT_MIN_EIG) multiplicative nudges per replicate k (k=0 is the unnudged build)
NUDGES = {1: dict(ACCEL_NOISE=1.010, KLT_MIN_EIG=1.005),
          2: dict(ACCEL_NOISE=0.990, KLT_MIN_EIG=0.995),
          3: dict(PIXEL_STD=1.005, ACCEL_NOISE=1.005),
          4: dict(DETECT_MIN_SCORE=0.995, KLT_MIN_EIG=1.010, PIXEL_STD=0.995),
          5: dict(PIXEL_STD=1.008, DETECT_MIN_SCORE=1.006, ACCEL_NOISE=0.992),
          6: dict(KLT_MIN_EIG=0.990, DETECT_MIN_SCORE=1.004)}
BASE_VAL = dict(PIXEL_STD=1.5, DETECT_MIN_SCORE=1000.0, ACCEL_NOISE=0.28, KLT_MIN_EIG=2.0)
KNOWN = {'31137e4fb26f73249d6ededffd71669df307886a3f929ffe2bc5d28204ff0137': SM / 'fuel/c1fbh/adopted_c1_fbh_exact.c',
         'c8dc91de': SM / 'frontend/adopted_fbh.c'}
B7_BASE_SCORES = RV.ROOT / 'research/results/single_model/fuel_fresh_fbx/eval/fbx-31137e4f/scores.json'


def fresh_tags():
    return json.loads((SM / 'fresh/tags.json').read_text())


def fold(tag):
    return int(hashlib.sha256(f"{tag['catalog']}:{tag['scene']}".encode()).hexdigest()[:8], 16) % 5


def guard_defines(text):
    """wrap '#define NAME val' for the nudged names in #ifndef NAME ... #endif unless already guarded"""
    for n in BASE_VAL:
        if re.search(r'#ifndef\s+%s\b' % n, text):
            continue
        text = re.sub(r'^(#define\s+%s\b[^\n]*)$' % n, r'#ifndef %s\n\1\n#endif' % n, text, count=1, flags=re.M)
    return text


def resolve_src(target):
    target = Path(target)
    if target.suffix == '.c':
        return target
    sha = RV.sha if hasattr(RV, 'sha') else None
    h = hashlib.sha256(target.read_bytes()).hexdigest()
    for k, v in KNOWN.items():
        if h.startswith(k):
            return v
    raise SystemExit('wasm sha not in KNOWN; pass the .c source')


def build_rep(src, name, k, extra_defines):
    d = dict(BASE_VAL)
    nud = NUDGES.get(k, {}) if k else {}
    defs = [x for x in extra_defines.split() if x]
    given = {x.split('=')[0] for x in defs}
    for n, m in nud.items():
        if n not in given:
            defs.append(f'{n}={BASE_VAL[n] * m:.6g}')
    gsrc = HERE / 'out' / name / 'src'; gsrc.mkdir(parents=True, exist_ok=True)
    p = gsrc / (src.stem + '_guarded.c'); p.write_text(guard_defines(src.read_text()))
    cm = src.parent / 'CMakeLists.txt'
    wasm = RV.build(p, cm if cm.exists() else RV.CMAKE_DEFAULT, ' '.join(defs), f'rb_{name}_r{k}')
    return wasm, defs


def run_rep(src, name, k, defs, workers, which):
    wasm, dd = build_rep(src, name, k, defs)
    out = {}
    if 'fresh' in which:
        sc = RV.run_guest_fast(wasm, FRESH_POOL, RES / f'rb_{name}_r{k}' / 'fresh_eval', workers=workers, name=f'rb{k}')
        out['fresh'] = sc
    if 'sel' in which:
        sc = RV.run_guest_fast(wasm, RV.EPISODES, RES / f'rb_{name}_r{k}' / 'eval', workers=workers, name=f'rb{k}s')
        out['sel'] = sc
    return k, out, dd


def read_scores(p, which):
    d = json.loads(Path(p).read_text()); out = {}
    tg = fresh_tags() if which == 'fresh' else RV.tags()
    for r in d['rows']:
        if which == 'sel' and RV.slice_of(RV.fold(tg[r['episode']])) == 'sealed':
            continue                      # fold 4 dropped immediately
        if r.get('ate_full') is not None and r.get('error') is None:
            out[r['episode']] = r['ate_full']
    return out


def table(reps, which):
    tg = fresh_tags() if which == 'fresh' else RV.tags()
    eps = sorted(set.intersection(*[set(r) for r in reps]))
    A = np.array([[r[e] for r in reps] for e in eps])
    rows = []
    for i, e in enumerate(eps):
        a = A[i]; t = tg[e]; f = fold(t) if which == 'fresh' else RV.fold(t)
        rows.append(dict(episode=e, start=t['start'], scene=t['scene'], catalog=t['catalog'], fold=f,
                         split='dev' if f <= 2 else 'confirm', mean=float(a.mean()), std=float(a.std(ddof=1)) if len(a) > 1 else 0.0,
                         min=float(a.min()), max=float(a.max()), reps=[float(x) for x in a],
                         high_variance=bool(a.max() - a.min() > 1.0 or (a.std(ddof=1) > 0.5 if len(a) > 1 else False)),
                         consistently_bad=bool((a > 3).all())))
    return rows, A


def summarize(rows, A, label):
    R = A.shape[1]; m = A.mean(0)
    L = [f'== {label}: n={A.shape[0]} flights, R={R} replicates']
    L.append('per-replicate mean: ' + ' '.join(f'{x:.3f}' for x in m))
    L.append(f'mean of replicate means {m.mean():.3f}  | spread of the mean across replicates: std {m.std(ddof=1) if R > 1 else 0:.3f} range {m.max() - m.min():.3f}')
    L.append(f'mean per-flight std {np.mean([r["std"] for r in rows]):.3f} | median per-flight std {np.median([r["std"] for r in rows]):.3f}')
    hv = [r for r in rows if r['high_variance']]; cb = [r for r in rows if r['consistently_bad']]
    tot = sum(r['mean'] for r in rows)
    L.append(f'high-variance flights {len(hv)} (carry {sum(r["mean"] for r in hv) / tot * 100:.1f}% of the mean)  consistently bad {len(cb)} (carry {sum(r["mean"] for r in cb) / tot * 100:.1f}%)')
    for t in (3, 5, 10):
        c = (A > t).sum(0); L.append(f'  flights >{t} m per replicate: {" ".join(map(str, c))} (avg {c.mean():.1f})')
    L.append(f'  replicate median ' + ' '.join(f'{np.median(A[:, j]):.2f}' for j in range(R)) + '  p90 ' + ' '.join(f'{np.percentile(A[:, j], 90):.2f}' for j in range(R)))
    for sp in ('dev', 'confirm'):
        idx = [i for i, r in enumerate(rows) if r['split'] == sp]
        if idx:
            mm = A[idx].mean(0)
            L.append(f'  {sp} (n={len(idx)}): rep means ' + ' '.join(f'{x:.3f}' for x in mm) + f' | avg {mm.mean():.3f} std {mm.std(ddof=1) if R > 1 else 0:.3f} | mean flight std {np.mean([rows[i]["std"] for i in idx]):.3f} | hv {sum(rows[i]["high_variance"] for i in idx)}')
    for st in ('static', 'mid'):
        idx = [i for i, r in enumerate(rows) if r['start'] == st]
        if idx:
            L.append(f'  {st} (n={len(idx)}): avg of rep means {A[idx].mean():.3f}  mean flight std {np.mean([rows[i]["std"] for i in idx]):.3f}  hv {sum(rows[i]["high_variance"] for i in idx)}')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target'); ap.add_argument('--name', required=True)
    ap.add_argument('--reps', type=int, default=5); ap.add_argument('--workers', type=int, default=24)
    ap.add_argument('--par', type=int, default=1, help='replicates run concurrently (max 2)')
    ap.add_argument('--defines', default='', help='extra -D flags applied to every replicate')
    ap.add_argument('--rep0', help='existing fresh scores.json to reuse as replicate 0 (same build, unnudged)')
    ap.add_argument('--sets', default='fresh', help='fresh | fresh,sel | sel')
    ap.add_argument('--table-only', action='store_true', help='re-summarize from finished run dirs')
    a = ap.parse_args()
    which = a.sets.split(',')
    src = resolve_src(a.target)
    name = a.name.removeprefix('rb_')
    (HERE / 'out' / name).mkdir(parents=True, exist_ok=True)
    scores = {w: {} for w in which}
    todo = list(range(a.reps))
    if a.rep0 and 'fresh' in which:
        scores['fresh'][0] = Path(a.rep0); todo.remove(0)
    if a.table_only:
        for k in todo:
            for w in which:
                g = sorted((RES / f'rb_{name}_r{k}' / ('fresh_eval' if w == 'fresh' else 'eval')).glob('*/scores.json'))
                if g:
                    scores[w][k] = g[-1]
    else:
        # rep0 reuse only applies to fresh; if 'sel' requested, rep 0 still runs for it
        t0 = time.time()
        with ThreadPoolExecutor(min(a.par, 2)) as ex:
            futs = []
            for k in range(a.reps):
                w = [x for x in which if not (k == 0 and a.rep0 and x == 'fresh')]
                if w:
                    futs.append(ex.submit(run_rep, src, name, k, a.defines, a.workers, w))
            for f in futs:
                k, out, dd = f.result()
                for w, p in out.items():
                    scores[w][k] = p
                print(f'rep {k} done ({dd}) {time.time() - t0:.0f}s', flush=True)
    meta = {'src': str(src), 'nudges': {k: NUDGES.get(k, {}) for k in range(a.reps)}}
    txt = []
    for w in which:
        ks = sorted(scores[w]); reps = [read_scores(scores[w][k], w) for k in ks]
        if len(reps) < 1:
            continue
        rows, A = table(reps, w)
        (HERE / 'out' / name / f'replicates_{w}.json').write_text(json.dumps(dict(meta=meta, reps=ks, rows=rows), indent=0))
        with open(HERE / 'out' / name / f'replicates_{w}.csv', 'w', newline='') as f:
            wr = csv.writer(f); wr.writerow(['episode', 'start', 'scene', 'split', 'mean', 'std', 'min', 'max', 'high_variance', 'consistently_bad'] + [f'r{k}' for k in ks])
            for r in rows:
                wr.writerow([r['episode'], r['start'], r['scene'], r['split'], f"{r['mean']:.4f}", f"{r['std']:.4f}", f"{r['min']:.4f}", f"{r['max']:.4f}", int(r['high_variance']), int(r['consistently_bad'])] + [f'{x:.4f}' for x in r['reps']])
        txt.append(summarize(rows, A, f'{name} [{w}]'))
    s = '\n'.join(txt); (HERE / 'out' / name / 'summary.txt').write_text(s + '\n'); print(s)


if __name__ == '__main__':
    main()
