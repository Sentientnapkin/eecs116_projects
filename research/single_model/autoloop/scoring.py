"""Metrics, constraints, promotion tests, ledger helpers (pure functions; shared by loop.py and status.py)."""
import json
from pathlib import Path
import numpy as np
from research.single_model.run_variant import paired
from research.single_model.autoloop import params as P

HERE = Path(__file__).resolve().parent
RES = HERE / 'results'; LEDGER = HERE / 'ledger.jsonl'
_cats = None


def cats():
    global _cats
    if _cats is None:
        _cats = json.loads((HERE / 'categories.json').read_text())
    return _cats


def load_res(h, stage='search'):
    p = RES / f'{h}.{stage}.json'
    return json.loads(p.read_text()) if p.exists() else None


def metrics(res):
    """Absolute metrics of a search-stage result (visible selected flights: search folds 0-2, val fold 3)."""
    C = cats(); vis = C['visible']
    fl = {e: np.asarray(v, float) for e, v in res['flights'].items()}
    nrep = min(len(v) for v in fl.values()); fm = {e: float(v[:nrep].mean()) for e, v in fl.items()}
    srch = [e for e in fl if vis[e]['fold'] <= 2]; val = [e for e in fl if vis[e]['fold'] == 3]
    m = dict(nrep=nrep, n_flights=len(fl))
    m['search_reps'] = [float(np.mean([fl[e][i] for e in srch])) for i in range(nrep)]
    m['val_reps'] = [float(np.mean([fl[e][i] for e in val])) for i in range(nrep)]
    m['search'] = float(np.mean(m['search_reps'])); m['val'] = float(np.mean(m['val_reps']))
    for nm, st in (('static', 'static'), ('mid', 'mid')):
        m[nm] = float(np.mean([fm[e] for e in srch if vis[e]['start'] == st]))
        m['val_' + nm] = float(np.mean([fm[e] for e in val if vis[e]['start'] == st]))
    m['all'] = float(np.mean([fm[e] for e in fl]))
    for t in (3, 5, 10):
        m[f'n{t}'] = int(sum(fm[e] > t for e in srch)); m[f'val_n{t}'] = int(sum(fm[e] > t for e in val))
    m['over10'] = sorted(e for e in srch + val if fm[e] > 10)
    m['over10_any_rep'] = int(sum((fl[e][:nrep] > 10).any() for e in srch))
    m['cats'] = {}
    for c, eps in C['cats'].items():
        eps = [e for e in eps if e in fm]
        if not eps: continue
        w = max(eps, key=lambda e: fm[e])
        m['cats'][c] = dict(n=len(eps), mean=float(np.mean([fm[e] for e in eps])), worst=[w, float(fm[w])])
    pk = np.array([[x for x in res['fuel'][e][:nrep]] for e in fl], float)   # flights x reps
    m['fuel_peak'] = float(pk.max(0).mean())
    m['fuel_p95'] = float(max(np.mean(res['p95'][e][:nrep]) for e in fl)); m['fuel_med'] = float(np.mean([np.mean(res['med'][e][:nrep]) for e in fl]))
    m['wasm_size'] = int(np.mean(res['wasm_size'])) if res['wasm_size'] else None
    m['errors'] = len(res['errors']); m['valid'] = bool(not res['errors'] and nrep >= 1 and len(fl) == len(vis))
    return m


def fresh_metrics(res):
    C = cats(); stage = res['stage'][-1]; fc = C['fresh_cats'][stage]
    fm = {e: float(np.mean(v)) for e, v in res['flights'].items()}
    m = dict(n=len(fm), mean=float(np.mean(list(fm.values()))))
    for c, eps in fc.items():
        eps = [e for e in eps if e in fm]
        if eps: m[c] = float(np.mean([fm[e] for e in eps]))
    for t in (3, 5, 10): m[f'n{t}'] = int(sum(v > t for v in fm.values()))
    m['fuel_peak'] = float(max(v[0] for v in res['fuel'].values()))
    m['valid'] = not res['errors']
    return m


def flights_mean(res):
    return {e: float(np.mean(v)) for e, v in res['flights'].items()}


def judge(cm, cres, rm, rres):
    """Candidate vs reference. Returns dict(feasible, screen, improvement, reasons...)."""
    j = dict(reasons=[])
    if not cm['valid']:
        j.update(feasible=False, screen=False, improvement=float('-inf'), reasons=['invalid']); return j
    j['improvement'] = rm['search'] - cm['search']
    if cm['static'] > rm['static'] + 0.05: j['reasons'].append(f"static {cm['static']:.3f}>ref+0.05")
    new10 = [e for e in cm['over10'] if e not in rm['over10']]
    if new10: j['reasons'].append('new >10m: ' + ','.join(new10))
    for c, v in cm['cats'].items():
        if c == 'all' or c not in rm['cats']: continue
        r = rm['cats'][c]['mean']
        if v['mean'] > r + max(0.15, 0.15 * r): j['reasons'].append(f"cat {c} {v['mean']:.2f} vs {r:.2f}")
    if cm['fuel_peak'] > rm['fuel_peak'] * 1.05: j['reasons'].append(f"fuel {cm['fuel_peak']/1e6:.2f}M")
    j['feasible'] = not j['reasons']
    j['val_ok'] = cm['val'] <= rm['val'] + 0.15
    j['screen'] = bool(j['feasible'] and j['improvement'] >= 0.03 and j['val_ok'])
    return j


def key(cm, feasible):
    return (0 if feasible else 1, cm['search'], cm['n3'], cm['fuel_peak'])


def bootstrap(cres, rres):
    """paired scene bootstrap (candidate - reference) on replicate-mean flights, search and val."""
    vis = cats()['visible']; cf, rf = flights_mean(cres), flights_mean(rres); out = {}
    for nm, sel in (('search', lambda f: f <= 2), ('val', lambda f: f == 3)):
        ks = [e for e in cf if sel(vis[e]['fold'])]
        d, lo, hi = paired([rf[e] for e in ks], [cf[e] for e in ks], [vis[e]['scene'] for e in ks])
        out[nm] = [round(d, 3), round(lo, 3), round(hi, 3)]
    return out


def fresh_ok(fa, rfa):
    return fa['valid'] and fa['mean'] <= rfa['mean'] + 0.02 and fa['n5'] <= rfa['n5'] and fa['n10'] <= rfa['n10']


def read_ledger():
    rows = []
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            if line.strip():
                try: rows.append(json.loads(line))
                except Exception: pass
    return rows


def pareto(points):
    """points: list of (search, fuel, id); returns non-dominated ids (both minimised)."""
    front = []
    for a in points:
        if not any((b[0] <= a[0] and b[1] <= a[1]) and (b[0] < a[0] or b[1] < a[1]) for b in points): front.append(a)
    return sorted(front)
