"""Unified evaluation matrix for all candidate builds of the single gp_msckf-family estimator. Idempotent and cached.

  cd /data/backups/rganapa/Sebastian/eecs116_projects
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.matrix.matrix [--score] [--holdout] [--only B6,B7]

Without flags it only (re)builds RESULTS.md / results.json / results.csv from the per-build store (matrix/store/<id>.json).
--score    : for every build whose wasm exists and whose store entry is missing/stale (sha differs): score the 171 selected flights
             (run_variant, search/val per flight, sealed AGGREGATE only) and the 711 fresh flights (reuse an existing scores.json with the same
             wasm SHA, otherwise rescore). At most 2 evaluations at a time, 24 workers each, backs off when load > 150.
--holdout  : once the holdout set is ready (holdout/tags.json + gen/raw-holdout/final), score missing builds with holdout/score_build.sh
             (one-shot per name: mx_<id>) and read holdout/table_mx_<id>.json.
Sealed (fold 4) per-flight rows are never stored or analysed: they are dropped at load time; only run_variant's sealed_aggregate.json is read, REPORTING ONLY.
Writes only inside research/single_model/matrix/ and research/results/single_model/mx_*.
"""
import argparse, csv, glob, hashlib, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1'); os.environ.setdefault('OMP_NUM_THREADS', '1')
from research.single_model import run_variant as RV

ROOT = RV.ROOT; SM = ROOT / 'research/single_model'; MX = SM / 'matrix'; STORE = MX / 'store'; RES = RV.OUT
GEN = Path('/data/backups/rganapa/Sebastian/gen')
FRESH_POOL = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')
HOLD_FINAL = GEN / 'raw-holdout/final'
SUB = SM / 'final/submit'
GP = ROOT / 'Final Project/classical_vio/gp_msckf'
TEACHER = '/data/backups/rganapa/Sebastian/venv-teacher/bin/python'

# ---------------------------------------------------------------------------------------------------------------- builds
# sel_use: which sets were used for selecting/tuning the build (honesty column)
B = [
 dict(id='B0', name='baseline gp_msckf', wasm=[GP / 'gp_msckf.wasm'], src=GP / 'solution.c',
      sel_use='originally tuned on its own pool; submitted (server 3.22 m)'),
 dict(id='B1', name='f0 (startup prior)', wasm=[SUB / 'gp_msckf_startup_f0.wasm'], src=SUB / 'f0.c',
      sel_use='171 selected (search/val); sealed fold 4 read once earlier (1.146 m) at integration, not used for a decision'),
 dict(id='B2', name='G = f0 + vision movement gate (SUBMITTED)', wasm=[SUB / 'gp_msckf_startup_gate.wasm'], src=SUB / 'gate.c',
      sel_use='171 selected (search/val); fresh 711 used as confirmation only; sealed not read for selection'),
 dict(id='B3', name='gate + tails merged (REJECTED)', wasm=[SUB / 'gp_msckf_startup_gate_tails.wasm'], src=SUB / 'gate_tails.c',
      sel_use='171 selected (search/val); sealed fold 4 read once earlier (0.981 m); rejected after fresh 711 showed new >10 m tails'),
 dict(id='B4', name='G + C1 (hover hold + vz/lat priors)', wasm=[SUB / 'gp_msckf_startup_gate_c1.wasm'], src=SUB / 'gate_c1.c',
      sel_use='search/val of the 171 (ideas screened + 3-replicate means); fresh 711 for adoption (confirmation)'),
 dict(id='B5', name='G + C1 + exact fuel rewrite', wasm=[SUB / 'gp_msckf_startup_gate_c1_exact.wasm'], src=SUB / 'gate_c1_exact.c',
      cmake=SM / 'fuel/c1/CMakeLists.txt', sel_use='same as B4 (bit-identical estimates; only fuel changed)'),
 dict(id='B6', name='G + C1 + forward-backward KLT (FB)', wasm=[SM / 'fuel/publish/gp_msckf_startup_gate_c1_fbh.wasm', SUB / 'gp_msckf_startup_gate_c1_fbh.wasm'], src=SM / 'frontend/adopted_fbh.c',
      sel_use='search/val of the 171 (3 replicates) + fresh 711 for adoption (confirmation); fresh partly used for the decision'),
 dict(id='B7', name='G + C1 + FB + exact fuel', wasm=[SM / 'fuel/publish/gp_msckf_startup_gate_c1_fbh_exact.wasm', SUB / 'gp_msckf_startup_gate_c1_fbh_exact.wasm'], src=SM / 'fuel/c1fbh/adopted_c1_fbh_exact.c',
      cmake=SM / 'fuel/c1fbh/CMakeLists.txt', sel_use='same as B6 (exact port; estimates should be bit-identical to B6)'),
 dict(id='B8', name='G + C1 + FB + CMBX (evaluated, not adopted)', wasm=[SUB / 'gp_msckf_startup_gate_c1_fbh_cmbx.wasm'], src=SM / 'cmbx/b8.c', provisional_build=True,
      sel_use='CMBX arm selected on search/val of the 171 and the 582 non-fold-4 fresh flights (edge work) -> fresh is NOT a clean confirmation for B8'),
 dict(id='B9', name='G + C1 + autoloop vector ba7c9bb8d93e (not adopted)', wasm=[], src=SM / 'autoloop/best/ba7c9bb8d93e.c',
      sel_use='tuned on search (192 vectors, 3-replicate means, fresh-A confirmation); held-out fresh-B (236) showed no gain; NOT adopted'),
 dict(id='B10', name='learned startup net (learned_c)', wasm=[], src=None,
      sel_use='partial port; no wasm'),
]
BID = {b['id']: b for b in B}
NOISE = dict(search=0.2, val=0.2, fresh=0.04, holdout=0.04)   # replicate-noise of the same build under 1% nudges (task statement)


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load():
    return os.getloadavg()[0]


def wait_load(limit=150):
    while load() > limit:
        time.sleep(60)


# ------------------------------------------------------------------------------------------------------------ wasm / build
def find_wasm(b):
    """Return (path, how). Published wasm if it exists, else (if source known and not B8/B10) build as run_variant.build()."""
    for p in b['wasm']:
        if Path(p).exists():
            return Path(p), 'published'
    extra = []
    if b['id'] == 'B10':
        extra = [Path(p) for p in glob.glob(str(SM / 'learned_c/**/*.wasm'), recursive=True)]
        if extra:
            return extra[0], 'learned_c wasm'
    if b.get('src') and (b.get('provisional_build') or b['id'] == 'B9') and Path(b['src']).exists():
        out = RES / f"mx_{b['id']}" / 'solution.wasm'
        stamp = RES / f"mx_{b['id']}" / 'src_sha.txt'
        s = sha_file(b['src'])
        if out.exists() and stamp.exists() and stamp.read_text().strip() == s:
            return out, 'matrix-built'
        (RES / f"mx_{b['id']}").mkdir(parents=True, exist_ok=True)
        cm = b.get('cmake') or (Path(b['src']).parent / 'CMakeLists.txt' if (Path(b['src']).parent / 'CMakeLists.txt').exists() else RV.CMAKE_DEFAULT)
        w = RV.build(Path(b['src']), Path(cm), '', f"mx_{b['id']}")
        stamp.write_text(s)
        return w, 'matrix-built'
    return None, 'not built'


# ------------------------------------------------------------------------------------------------------------------ store
def sidecars():
    tg = RV.tags()
    return tg


def fresh_tags():
    return json.loads((SM / 'fresh/tags.json').read_text())


def row_of(r):
    return dict(ate=r.get('ate_full'), peak=r.get('peak_fuel_per_frame'), med=r.get('median_fuel_per_frame'), p95=r.get('p95_fuel_per_frame'),
                ok=bool(r.get('completed')) and r.get('error') is None and r.get('ate_full') is not None, filled=r.get('filled_full'))


def read_sel(scores):
    """per-flight rows of folds 0-3 only; fold 4 rows are dropped immediately (never stored)."""
    tg = RV.tags(); d = json.loads(Path(scores).read_text()); out = {}
    for r in d['rows']:
        if RV.slice_of(RV.fold(tg[r['episode']])) == 'sealed':
            continue
        out[r['episode']] = row_of(r)
    return out


def read_fresh(scores):
    d = json.loads(Path(scores).read_text()); return {r['episode']: row_of(r) for r in d['rows']}


_SHA_INDEX = None
def sha_index():
    global _SHA_INDEX
    if _SHA_INDEX is None:
        _SHA_INDEX = {}
        for g in glob.glob(str(RES / '*/eval/*/guest.json')) + glob.glob(str(RES / '*/*/eval/*/guest.json')):
            try:
                _SHA_INDEX.setdefault(json.loads(Path(g).read_text())['sha256'], []).append(Path(g).parent / 'scores.json')
            except Exception:
                pass
    return _SHA_INDEX


def find_existing_fresh(sha):
    want = set(fresh_tags())
    for p in sha_index().get(sha, []):
        if not p.exists():
            continue
        try:
            rows = read_fresh(p)
        except Exception:
            continue
        if set(rows) == want and all(v['ok'] for v in rows.values()):
            return rows, str(p.relative_to(ROOT))
    return None, None


def entry_path(bid):
    return STORE / f'{bid}.json'


def load_entry(bid):
    p = entry_path(bid)
    return json.loads(p.read_text()) if p.exists() else None


def save_entry(bid, e):
    STORE.mkdir(parents=True, exist_ok=True)
    tmp = entry_path(bid).with_suffix('.tmp'); tmp.write_text(json.dumps(e)); tmp.replace(entry_path(bid))


def score_build(b, workers=24):
    wasm, how = find_wasm(b)
    if wasm is None:
        return
    sha = sha_file(wasm)
    e = load_entry(b['id']) or {}
    if e.get('sha') != sha:
        e = dict(id=b['id'], sha=sha, wasm=str(wasm.relative_to(ROOT)) if str(wasm).startswith(str(ROOT)) else str(wasm), how=how)
    e['wasm_how'] = how; e['wasm'] = str(wasm.relative_to(ROOT)) if str(wasm).startswith(str(ROOT)) else str(wasm)
    save_entry(b['id'], e)
    name = f"mx_{b['id']}"
    if 'sel' not in e or 'sealed' not in e:
        wait_load()
        t0 = time.time()
        p = subprocess.run([sys.executable, '-B', '-m', 'research.single_model.run_variant', '--name', name, '--wasm', str(wasm), '--workers', str(workers)],
                           cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
        (MX / 'logs').mkdir(exist_ok=True); (MX / 'logs' / f'{name}_171.log').write_text(p.stdout + p.stderr)
        if p.returncode:
            print(b['id'], '171 failed', p.stderr[-500:]); return
        folder = next((RES / name / 'eval').glob(name + '-' + sha[:8]))
        e['sel'] = read_sel(folder / 'scores.json')
        e['sealed'] = json.loads((RES / name / 'sealed_aggregate.json').read_text())
        e['sealed_note'] = 'reported once, not used for selection (aggregate from run_variant sealed_aggregate.json)'
        print(b['id'], '171 done', round(time.time() - t0), 's', flush=True)
        save_entry(b['id'], e)
    if 'fresh' not in e:
        rows, src = find_existing_fresh(sha)
        if rows is None:
            wait_load(); t0 = time.time()
            os.environ['VIOBENCH_PNG_CACHE'] = '0'
            sc = RV.run_guest_fast(wasm, FRESH_POOL, RES / name / 'fresh_eval', workers=workers, name=name + '_fresh')
            rows = read_fresh(sc); src = f'rescored {sc.relative_to(ROOT)} ({round(time.time() - t0)} s)'
        e['fresh'] = rows; e['fresh_src'] = src
        print(b['id'], 'fresh done:', src, flush=True)
        save_entry(b['id'], e)


def holdout_ready():
    t = SM / 'holdout/tags.json'
    return t.exists() and HOLD_FINAL.exists() and len(list(HOLD_FINAL.glob('*.zip'))) >= 100


def score_holdout(b):
    e = load_entry(b['id'])
    if not e or 'holdout' in e:
        return
    name = f"mx_{b['id']}"; tab = SM / f'holdout/table_{name}.json'
    if not tab.exists():
        wait_load()
        env = dict(os.environ, WORKERS='24')
        p = subprocess.run(['bash', str(SM / 'holdout/score_build.sh'), str(ROOT / e['wasm']) if not Path(e['wasm']).is_absolute() else e['wasm'], name],
                           cwd=ROOT, capture_output=True, text=True, env=env)
        (MX / 'logs').mkdir(exist_ok=True); (MX / 'logs' / f'{name}_holdout.log').write_text(p.stdout + p.stderr)
        if not tab.exists():
            print(b['id'], 'holdout failed', p.stderr[-300:]); return
    rows = json.loads(tab.read_text())
    e['holdout'] = {r['episode']: dict(ate=r['ate'], peak=r.get('peak_fuel'), med=None, p95=None, ok=r['ate'] is not None and r.get('error') is None, filled=r.get('filled')) for r in rows}
    save_entry(b['id'], e)


# ----------------------------------------------------------------------------------------------------------------- metrics
def ctx():
    """flight metadata per set."""
    tg = RV.tags(); ft = fresh_tags(); tf = {r['episode']: r for r in json.load(open(SM / 'fresh/truth_feats.json'))}
    audit = json.load(open(SM / 'edge/audit.json'))
    pf = {}
    for line in open(RV.PERFLIGHT):
        r = json.loads(line); pf[r['episode']] = r
    meta = {'sel': {}, 'fresh': {}, 'holdout': {}}
    for ep, t in tg.items():
        f = RV.fold(t)
        if f == 4:
            continue
        a = audit.get(ep, {})
        meta['sel'][ep] = dict(start=t['start'], scene=t['catalog'] + ':' + t['scene'], clean=(pf[ep].get('group') == 'clean'), fold=f,
                               slice=RV.slice_of(f), flat=a.get('flat'), dark=a.get('dark'), travel=a.get('travel'))
    for ep, t in ft.items():
        a = audit.get(ep, {}); x = tf[ep]
        meta['fresh'][ep] = dict(start=t['start'], scene=t['catalog'] + ':' + t['scene'], clean=(t['group'] == 'clean'), group=t['group'],
                                 angle=x['angle'] if t['start'] == 'mid' else None, speed0=x['speed0'], flat=a.get('flat'), dark=a.get('dark'),
                                 fold=a.get('fold'), travel=a.get('travel'))
    ht = SM / 'holdout/tags.json'
    if ht.exists():
        h = json.loads(ht.read_text()); hb = {}
        for p in glob.glob(str(GEN / 'raw-holdout/bench/*.json')):
            try:
                d = json.load(open(p)); hb[d['id']] = d['audit']
            except Exception:
                pass
        for ep, t in h.items():
            a = hb.get(ep, {})
            meta['holdout'][ep] = dict(start=t['start'], scene=t['catalog'] + ':' + t['scene'], clean=(t.get('group') == 'clean'), group=t.get('group'),
                                       flat=a.get('flat_fraction'), dark=a.get('dark_fraction'), travel=a.get('travel_m'))
    return meta


def subset(meta, setname):
    """episode lists for 'search','val','fresh','holdout'."""
    if setname in ('search', 'val'):
        return [e for e, m in meta['sel'].items() if m['slice'] == setname]
    return list(meta[setname])


def vec(entry, setname, eps):
    src = entry['sel'] if setname in ('search', 'val') else entry[setname]
    return np.array([src[e]['ate'] if e in src and src[e]['ok'] else np.nan for e in eps], float)


def boot(d, scenes, n=4000, seed=20261120):
    u, inv = np.unique(scenes, return_inverse=True)
    sm = np.bincount(inv, weights=d); k = np.bincount(inv)
    rng = np.random.default_rng(seed); ix = rng.integers(0, len(u), (n, len(u)))
    b = sm[ix].sum(1) / k[ix].sum(1)
    return float(d.mean()), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def stats(x):
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return {}
    return dict(n=int(len(x)), mean=float(x.mean()), median=float(np.median(x)), p90=float(np.percentile(x, 90)), max=float(x.max()),
                gt3=int((x > 3).sum()), gt5=int((x > 5).sum()), gt10=int((x > 10).sum()))


def fuel(entry, setname, eps):
    src = entry['sel'] if setname in ('search', 'val') else entry[setname]
    pk = [src[e]['peak'] for e in eps if e in src and src[e].get('peak') is not None]
    p95 = [src[e]['p95'] for e in eps if e in src and src[e].get('p95') is not None]
    md = [src[e]['med'] for e in eps if e in src and src[e].get('med') is not None]
    f = {}
    if pk: f['peak_max'] = max(pk) / 1e6
    if p95: f['p95_max'] = max(p95) / 1e6; f['p95_mean'] = float(np.mean(p95)) / 1e6
    if md: f['median_mean'] = float(np.mean(md)) / 1e6
    return f


# ------------------------------------------------------------------------------------------------------- 12-episode proxy
def proxy(entries, N=30000):
    """edge/proxy.py method: 12 server slots (path lengths sd), each slot draws one of the 60 pool flights nearest in travel distance, mid with prob pm,
    pool = non-fold-4 selected (144) + non-fold-4 fresh (582) = the 726 flights of edge/sig.json. Same draws (seed 11) for all builds."""
    E = SM / 'edge'
    a = json.load(open(E / 'audit.json')); s = json.load(open(E / 'sig.json'))
    eps = [e for e in s if all(c in s[e] for c in ('base', 'f0', 'G', 'T', 'M'))]
    mid = np.array([a[e]['start'] == 'mid' for e in eps]); trav = np.array([a[e]['travel'] for e in eps])
    sd = np.array([72.70, 56.89, 80.38, 48.19, 58.52, 39.49, 63.23, 59.53, 58.93, 61.71, 74.03, 41.54])
    K = 60; idx = [np.argsort(np.abs(trav - d))[:K] for d in sd]
    rng = np.random.default_rng(11)
    draws = {}
    for pm in (0.0, 0.5, 1.0):
        res = np.zeros((N, 12), int)
        for j, i in enumerate(idx):
            im = i[mid[i]]; ist = i[~mid[i]]; ism = rng.random(N) < pm
            res[:, j] = np.where(ism, rng.choice(im, N), rng.choice(ist, N))
        draws[pm] = res
    out = {}
    for bid, e in entries.items():
        A = np.array([(e['sel'].get(x, {}).get('ate') if a[x]['pool'] == 'sel' else e['fresh'].get(x, {}).get('ate')) for x in eps], float)
        if np.isnan(A).any():
            continue
        o = {}
        for pm, r in draws.items():
            x = A[r]; m = x.mean(1); n5 = (x > 5).sum(1)
            o[str(pm)] = dict(mean=float(m.mean()), p5=float(np.percentile(m, 5)), p50=float(np.percentile(m, 50)), p95=float(np.percentile(m, 95)),
                              p_any5=float((n5 >= 1).mean()), p_ge2_5=float((n5 >= 2).mean()), p_ge_1244=float((m >= 1.244).mean()))
        out[bid] = o
    return out, len(eps)


# ------------------------------------------------------------------------------------------------------------------- report
def build_results():
    meta = ctx(); entries = {b['id']: load_entry(b['id']) for b in B}
    entries = {k: v for k, v in entries.items() if v and 'sel' in v and 'fresh' in v}
    R = dict(generated=time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()), builds={}, sets={}, classes={}, proxy={}, noise=NOISE)
    sets = ['search', 'val', 'fresh'] + (['holdout'] if any('holdout' in e for e in entries.values()) else [])
    eps_of = {s: subset(meta, s) for s in sets}
    mkey = lambda s: 'sel' if s in ('search', 'val') else s
    for bid, e in entries.items():
        bd = dict(sha=e['sha'], wasm=e['wasm'], how=e.get('wasm_how'), fresh_src=e.get('fresh_src'), sealed=e.get('sealed'), sets={})
        for s in sets:
            if s == 'holdout' and 'holdout' not in e:
                continue
            eps = eps_of[s]; x = vec(e, s, eps); m = meta[mkey(s)]
            st = np.array([m[k]['start'] == 'static' for k in eps]); cl = np.array([m[k]['clean'] for k in eps])
            d = stats(x); d['static'] = stats(x[st]).get('mean'); d['mid'] = stats(x[~st]).get('mean'); d['clean'] = stats(x[cl]).get('mean') if cl.any() else None
            d['fuel'] = fuel(e, s, eps)
            sc = [m[k]['scene'] for k in eps]
            for ref in ('B0', 'B2'):
                if ref in entries and (s != 'holdout' or 'holdout' in entries[ref]):
                    y = vec(entries[ref], s, eps); ok = ~np.isnan(x) & ~np.isnan(y)
                    if ref != bid and ok.any():
                        d['d_' + ref] = boot((x - y)[ok], np.array(sc)[ok])
            bd['sets'][s] = d
        R['builds'][bid] = bd
    # per-class tables on fresh (truth feature classes) and holdout (static/mid/flat/dark/clean only)
    fm = meta['fresh']; feps = eps_of['fresh']
    def cls_masks(setname):
        m = meta[setname]; eps = eps_of[setname]; g = lambda k: np.array([(m[x].get(k) if m[x].get(k) is not None else np.nan) for x in eps], float)
        mid = np.array([m[x]['start'] == 'mid' for x in eps]); C = {}
        C['all'] = np.ones(len(eps), bool); C['static'] = ~mid; C['mid'] = mid
        C['clean scenes'] = np.array([m[x]['clean'] for x in eps])
        C['flat fraction >0.2'] = g('flat') > 0.2; C['dark fraction >0.2'] = g('dark') > 0.2
        if setname == 'fresh':
            ang = g('angle'); sp = g('speed0')
            for lo, hi in ((0, 45), (45, 90), (90, 135), (135, 181)):
                C[f'mid, start-velocity angle {lo}-{min(hi,180)} deg (camera axis)'] = mid & (ang >= lo) & (ang < hi)
            for lo, hi, nm in ((0, 0.3, '<0.3'), (0.3, 0.6, '0.3-0.6'), (0.6, 1.2, '0.6-1.2'), (1.2, 1.8, '1.2-1.8'), (1.8, 99, '>=1.8')):
                C[f'mid, start speed {nm} m/s'] = mid & (sp >= lo) & (sp < hi)
            if 'B0' in entries and 'B2' in entries:
                d = vec(entries['B2'], 'fresh', eps) - vec(entries['B0'], 'fresh', eps)
                C['regression class (fresh, B2 > B0 + 1.5 m)'] = d > 1.5
        return eps, C
    for setname in [s for s in ('fresh', 'holdout') if s in sets]:
        eps, C = cls_masks(setname); T = {}
        for cname, mask in C.items():
            if mask.sum() == 0:
                continue
            T[cname] = dict(n=int(mask.sum()), builds={bid: dict(mean=float(np.nanmean(vec(e, setname, eps)[mask])), gt3=int((vec(e, setname, eps)[mask] > 3).sum()),
                                                                  gt5=int((vec(e, setname, eps)[mask] > 5).sum()))
                                                      for bid, e in entries.items() if setname != 'holdout' or 'holdout' in e})
        R['classes'][setname] = T
    R['proxy'], R['proxy_n'] = proxy(entries)
    return R, entries


def fmt_d(t):
    if not t: return '-'
    return f'{t[0]:+.3f} [{t[1]:+.3f},{t[2]:+.3f}]'


def noise_tag(t, s):
    if not t: return ''
    return ' (noise)' if abs(t[0]) < NOISE[s] else ''


def status():
    p = MX / 'status.json'
    return json.loads(p.read_text()) if p.exists() else {}


def write_md(R, entries):
    ST = status(); L = []
    A = L.append
    A('# Unified evaluation matrix: all candidate builds of the single estimator')
    A(f"Generated {R['generated']} by `research/single_model/matrix/matrix.py` (re-runnable; per-flight store `matrix/store/<id>.json`). Metric: mean unaligned ATE (m), never Sim(3). Pinned evaluator via run_variant / run_guest_fast.\n")
    A('Replicate noise: the SAME build under 1% parameter nudges moves search means by ~0.2 m and fresh means by ~0.02-0.04 m. Paired differences smaller than 0.2 (search/val) or 0.04 (fresh/holdout) are marked `(noise)`; paired CIs are scene-bootstrap (4000 resamples). Builds are deterministic, so the numbers below are single draws of a chaotic estimator (esp. mid starts).\n')
    A('## 1. Builds, hashes, selection use, preflight, submission')
    A('| id | build | wasm SHA-256 | wasm source | sets used for selecting/tuning | preflight | submission |')
    A('|--|--|--|--|--|--|--|')
    for b in B:
        bid = b['id']; e = entries.get(bid); st = ST.get(bid, {})
        sha = e['sha'] if e else '-'
        how = (e.get('wasm_how') + ': ' + e['wasm']) if e else 'not built / not scored yet'
        A(f"| {bid} | {b['name']} | `{sha}` | {how} | {b['sel_use']} | {st.get('preflight', 'pending')} | {st.get('submission', 'not submitted')} |")
    A('\nSealed fold 4 (n=27) numbers below are aggregates from each build\'s own sealed_aggregate.json, **reported once, not used for selection**. Per-flight sealed rows are never read or stored.\n')
    A('## 2. Headline: mean unaligned ATE (m) per set (paired difference vs B0 and vs B2 in brackets)')
    sets = [s for s in ('search', 'val', 'fresh', 'holdout') if any(s in v['sets'] for v in R['builds'].values())]
    hdr = '| id | ' + ' | '.join({'search': 'search n=119', 'val': 'val n=25', 'fresh': 'fresh n=711', 'holdout': 'holdout'}[s] for s in sets) + ' | sealed n=27 (report only) |'
    A(hdr); A('|--|' + '--|' * (len(sets) + 1))
    for bid, bd in R['builds'].items():
        cells = []
        for s in sets:
            d = bd['sets'].get(s)
            cells.append('(empty)' if not d else f"{d['mean']:.3f}")
        sl = bd['sealed']; cells.append(f"{sl['mean']:.3f}" if sl else '-')
        A(f'| {bid} | ' + ' | '.join(cells) + ' |')
    if 'holdout' not in sets:
        A('\nHoldout column: **empty** (holdout set not ready when this was generated; re-run `matrix.py --score --holdout` when `holdout/README.md` says it is final).')
    for s in sets:
        A(f"\n## 3.{sets.index(s)+1} Set `{s}` in detail")
        A('| id | n | mean | median | p90 | max | >3 | >5 | >10 | static | mid | clean | d vs B0 | d vs B2 | peak fuel (M) | p95 max / mean (M) | median fuel (M) |')
        A('|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|')
        for bid, bd in R['builds'].items():
            d = bd['sets'].get(s)
            if not d: continue
            f = d['fuel']; g = lambda v: '-' if v is None else f'{v:.3f}'
            A(f"| {bid} | {d['n']} | {d['mean']:.3f} | {d['median']:.3f} | {d['p90']:.2f} | {d['max']:.2f} | {d['gt3']} | {d['gt5']} | {d['gt10']} | {g(d['static'])} | {g(d['mid'])} | {g(d['clean'])} | "
              f"{fmt_d(d.get('d_B0'))}{noise_tag(d.get('d_B0'), s)} | {fmt_d(d.get('d_B2'))}{noise_tag(d.get('d_B2'), s)} | "
              f"{f.get('peak_max', float('nan')):.2f} | {f.get('p95_max', float('nan')):.2f} / {f.get('p95_mean', float('nan')):.2f} | {f.get('median_mean', float('nan')):.2f} |")
    A('\n## 4. Sealed fold 4 aggregates (n=27, reporting only, not used for selection)')
    A('| id | mean | median | p90 | max | >5 | >10 | baseline mean on these 27 |'); A('|--|--|--|--|--|--|--|--|')
    for bid, bd in R['builds'].items():
        s = bd['sealed']
        if s: A(f"| {bid} | {s['mean']:.3f} | {s['median']:.3f} | {s['p90']:.2f} | {s['max']:.2f} | {s['above5']} | {s['above10']} | {s['base']['mean']:.3f} |")
    for setname, T in R['classes'].items():
        A(f'\n## 5. Per-class tables on `{setname}` (mean ATE m; in brackets >3 m / >5 m flight counts)')
        ids = [b for b in R['builds'] if setname != 'holdout' or 'holdout' in entries[b]]
        A('| class | n | ' + ' | '.join(ids) + ' |'); A('|--|--|' + '--|' * len(ids))
        for c, v in T.items():
            A(f'| {c} | {v["n"]} | ' + ' | '.join(f"{v['builds'][i]['mean']:.2f} ({v['builds'][i]['gt3']}/{v['builds'][i]['gt5']})" for i in ids) + ' |')
        if setname == 'fresh':
            A('\nClass notes: angle = angle between the TRUE start velocity and the optical axis (+z of the camera-frame truth velocity; fresh/truth_feats.json, corrected convention) on mid flights with any speed (very slow starts have a poorly defined angle). Speed = true start speed. Flat/dark = sidecar audit fraction >0.2 (edge/audit.json). The regression class is defined by B2 vs B0 on the same flights, i.e. selected on the outcome: other builds regress to the mean there, so read it as a stress list, not an unbiased estimate.')
    A('\n## 6. 12-episode server proxy (edge/NOTES.md method)')
    A(f"Pool = non-fold-4 selected (144) + non-fold-4 fresh (582) = {R.get('proxy_n')} flights; each of the 12 server slots (server path lengths) draws one of the 60 nearest-by-travel pool flights; a draw is mid with probability pm; 30000 draws, identical draws for every build. Reported: mean of the 12-flight mean, 5th/50th/95th percentile, P(any of the 12 > 5 m). Server anchors: B0 3.22, B2 1.244 (G sits at the 59-74th percentile of its own distribution).")
    for pm in ('0.5', '0.0', '1.0'):
        A(f'\n### pm = {pm} (probability a draw is a mid-flight start)')
        A('| id | mean | p5 | median | p95 | P(any >5 m) | P(>=2 >5 m) | P(12-mean >= 1.244) |'); A('|--|--|--|--|--|--|--|--|')
        for bid, o in R['proxy'].items():
            x = o[pm]; A(f"| {bid} | {x['mean']:.3f} | {x['p5']:.2f} | {x['p50']:.2f} | {x['p95']:.2f} | {x['p_any5']:.2f} | {x['p_ge2_5']:.2f} | {x['p_ge_1244']:.2f} |")
    A('\n## 7. Preflight / submission status')
    for b in B:
        st = ST.get(b['id'], {}); A(f"* {b['id']}: preflight {st.get('preflight', 'pending')}; evidence {st.get('evidence', '-')}; submission {st.get('submission', 'not submitted')}")
    if ST.get('_notes'):
        A('\n' + ST['_notes'])
    A('\n## 8. Ranked recommendation')
    A(ST.get('_recommendation', '(generated by the coordinator once builds have landed; see below for the automatic ranking)'))
    rk = sorted(R['builds'].items(), key=lambda kv: kv[1]['sets']['fresh']['mean'])
    A('\nAutomatic ranking by fresh mean (holdout mean where present), tails and peak fuel:')
    A('| rank | id | fresh mean | fresh >5 / >10 | holdout mean | peak fuel (M) | preflight |'); A('|--|--|--|--|--|--|--|')
    for i, (bid, bd) in enumerate(rk, 1):
        f = bd['sets']['fresh']; h = bd['sets'].get('holdout')
        A(f"| {i} | {bid} | {f['mean']:.3f} | {f['gt5']}/{f['gt10']} | {('%.3f' % h['mean']) if h else '(empty)'} | {f['fuel'].get('peak_max', float('nan')):.1f} | {ST.get(bid, {}).get('preflight', 'pending')} |")
    (MX / 'RESULTS.md').write_text('\n'.join(L) + '\n')


def write_json_csv(R):
    (MX / 'results.json').write_text(json.dumps(R, indent=1))
    with open(MX / 'results.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['build', 'set', 'n', 'mean', 'median', 'p90', 'max', 'gt3', 'gt5', 'gt10', 'static', 'mid', 'clean', 'd_B0', 'd_B0_lo', 'd_B0_hi', 'd_B2', 'd_B2_lo', 'd_B2_hi',
                    'peak_fuel_M', 'p95_max_M', 'median_fuel_M'])
        for bid, bd in R['builds'].items():
            for s, d in bd['sets'].items():
                z = lambda k: d.get(k) or ['', '', '']
                w.writerow([bid, s, d['n'], d['mean'], d['median'], d['p90'], d['max'], d['gt3'], d['gt5'], d['gt10'], d['static'], d['mid'], d['clean'],
                            *z('d_B0'), *z('d_B2'), d['fuel'].get('peak_max'), d['fuel'].get('p95_max'), d['fuel'].get('median_mean')])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--score', action='store_true'); ap.add_argument('--holdout', action='store_true'); ap.add_argument('--only', default='')
    a = ap.parse_args()
    MX.mkdir(exist_ok=True); STORE.mkdir(exist_ok=True)
    sel = [b for b in B if not a.only or b['id'] in a.only.split(',')]
    if a.score:
        with ThreadPoolExecutor(2) as ex:
            list(ex.map(score_build, sel))
    if a.holdout:
        if holdout_ready():
            for b in sel:
                score_holdout(b)
        else:
            print('holdout not ready (holdout/tags.json or gen/raw-holdout/final missing)')
    R, entries = build_results()
    write_json_csv(R); write_md(R, entries)
    print('wrote RESULTS.md with builds:', list(entries))


if __name__ == '__main__':
    main()
