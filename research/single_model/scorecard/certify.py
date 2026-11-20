"""Certification scorecard: per-class >3 m / >5 m rates with CIs, P(all 12 server episodes <= 3 m) estimates, worst flights, mechanism tags.

Usage (numpy only):
  cd /data/backups/rganapa/Sebastian/eecs116_projects
  /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B research/single_model/scorecard/certify.py --all            # every existing build -> scorecard/out/
  ... certify.py --build B7                                                                                           # one registered build
  ... certify.py --name MYBUILD --fresh t_fresh.json --sel t_sel.json --holdout t_hold.json                           # a new candidate
A table file is a json list of {"episode":..,"ate":..} or a dict episode->ate (or episode->{"ate":..}). Any subset of the three sets may be given.
The holdout (240 clean flights) is only READ here (existing holdout/table_*.json or a table passed by the caller); this script never scores anything.

Sets: fresh = 711 never-tuned pool flights (partly used for confirmation decisions), sel = 144 visible selected flights (used for tuning, OPTIMISTIC),
holdout = 240 clean one-shot flights (the honest set, path 59.4 m ~ server).  Class features: scorecard/feats.json (make_feats.py).
"""
import argparse, json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; SM = HERE.parent
Z = 1.96
SERVER = [  # (episode, path m, ATE of gp_msckf (B0), ATE of gated build G (B2)) from final/SERVER_RESULT.md; extras only for e7aa5aee
    ('004c5894', 72.7, 2.94, 1.24), ('1c6e73f3', 56.9, 0.272, 0.288), ('21494468', 80.4, 2.74, 0.73), ('726458d9', 48.2, 0.271, 0.121),
    ('78ed493f', 58.5, 0.723, 0.973), ('8950399d', 39.5, 11.3, 0.307), ('89f8c99e', 63.2, 7.97, 0.299), ('a61ad08d', 59.5, 1.57, 0.407),
    ('cd6dc704', 58.9, 8.68, 1.09), ('dd7a737e', 61.7, 0.585, 0.291), ('e7aa5aee', 74.0, 0.918, 7.70), ('f7c2546f', 41.5, 0.742, 1.48)]
E7AA_SCALE = 0.572   # Sim(3) scale of G on e7aa5aee (SERVER_RESULT.md); other episodes: not available
CLASSES = ['static', 'mid slow (v0<0.3)', 'mid fwd (0.3<=v0<1.8, <90deg)', 'mid wrongdir (0.3<=v0<1.8, >=90deg)', 'mid fast (v0>=1.8)', 'flat/dark scene']
BUILDS = [('B0', 'baseline gp_msckf (server 3.22)'), ('B1', 'f0 startup prior'), ('B2', 'G gated (server 1.244)'), ('B3', 'gate+tails (rejected)'),
          ('B4', 'G+C1'), ('B5', 'G+C1 exact fuel'), ('B6', 'G+C1+FB'), ('B7', 'G+C1+FB exact'), ('B8', 'B6+CMBX (not adopted)'), ('B9', 'G+C1+autoloop vec (not adopted)'),
          ('B10', 'B6 + learned startup net'), ('B11', 'B7 exact + learned net (bit-identical to B10)')]
HOLD_ALIAS = {'B0': 'base', 'B2': 'gate', 'B4': 'gatec1', 'B5': 'gatec1', 'B6': 'B7', 'B7': 'B7', 'B10': 'B10', 'B11': 'B10'}   # B5/B6/B11 estimates bit-identical to B4/B7/B10
HOLD_NOTE = {'B5': 'holdout = B4 table (bit-identical estimates)', 'B6': 'holdout = B7 table (bit-identical)', 'B11': 'holdout = B10 table (bit-identical on 144+107 flights x3 reps)'}
F = json.load(open(HERE / 'feats.json'))
MECH = {r['ep']: r['cls'] for r in json.load(open(SM / 'b6fix/mech_table.json'))}   # B6 diagnostics (>3 m flights of fresh/selected only)


# ----------------------------------------------------------------------------------------------------------- stats helpers
def wilson(k, n, z=Z):
    if n == 0: return (float('nan'),) * 2
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)

def jeffreys(k, n): return (k + 0.5) / (n + 1.0)

def fmt(k, n):
    if n == 0: return '-'
    lo, hi = wilson(k, n); return f'{k}/{n} {100*k/n:.1f}% [{100*lo:.1f},{100*hi:.1f}]'

def cboot(bad, scene, rng, B=1000):
    """Scene-cluster bootstrap CI of a rate. bad: bool array; scene: array of scene ids."""
    if len(bad) == 0: return (float('nan'),) * 2
    u, inv = np.unique(scene, return_inverse=True); k = np.bincount(inv, weights=bad.astype(float)); n = np.bincount(inv).astype(float)
    ix = rng.integers(0, len(u), (B, len(u))); r = k[ix].sum(1) / n[ix].sum(1)
    return tuple(np.percentile(r, [2.5, 97.5]))

def classify(f):
    if f['flat'] > 0.2 or f['dark'] > 0.2: return CLASSES[5]
    if f['start'] == 'static': return CLASSES[0]
    v = f['speed0']; a = f['angle'] if f['angle'] is not None else 0.0
    if v < 0.3: return CLASSES[1]
    if v >= 1.8: return CLASSES[4]
    return CLASSES[3] if a >= 90 else CLASSES[2]

def tags(f):
    t = []
    if f['start'] == 'mid' and f['speed0'] >= 0.3 and (f['angle'] or 0) >= 135: t.append('reverse>=135')
    if f['flat'] > 0.05: t.append('flat>0.05')
    t.append('path<45' if f['travel'] < 45 else 'path45-65' if f['travel'] < 65 else 'path>=65')
    t.append('extent<3' if f['extent'] < 3 else 'extent3-5' if f['extent'] < 5 else 'extent>=5')
    t.append('cat:' + f['catalog']); t.append('set:' + str(f.get('setting')))
    return t

def mech_tag(ep, f, cls):
    if ep in MECH: return 'diag: ' + MECH[ep]
    h = {CLASSES[5]: 'rule: textureless/dark scene (suspect starved coasting)', CLASSES[4]: 'rule: fast start (suspect startup runaway)',
         CLASSES[3]: 'rule: wrong-direction start (suspect startup lock-out/runaway)', CLASSES[1]: 'rule: slow/ambiguous mid start (suspect heading-prior over-speed/scale)',
         CLASSES[2]: 'rule: regular mid start (startup chaos or late drift; needs diag.c)', CLASSES[0]: 'rule: static (starved coasting / late drift; needs diag.c)'}
    return h[cls]


# ------------------------------------------------------------------------------------------------------------- table loading
def read_table(p):
    d = json.load(open(p)); out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            a = v.get('ate') if isinstance(v, dict) else v
            if a is not None: out[k] = float(a)
    else:
        for r in d:
            a = r.get('ate', r.get('ate_full'))
            if a is not None: out[r['episode']] = float(a)
    return out

def registry(bid):
    """-> {set: {ep: ate}}, notes"""
    out = {}; notes = []
    n = int(bid[1:])
    if n <= 9:
        S = json.load(open(SM / f'matrix/store/{bid}.json'))
        out['fresh'] = {e: r['ate'] for e, r in S['fresh'].items() if r.get('ate') is not None}
        out['sel'] = {e: r['ate'] for e, r in S['sel'].items() if r.get('ate') is not None}
    else:
        out['sel'] = read_table(SM / 'learned_c/tables/s171_b11_r0.json'); out['fresh'] = read_table(SM / 'learned_c/tables/f3_b11_r0.json')
        notes.append('fresh = 107 unselected fold-3 flights only (the other 604 not run for B10/B11); sel = learned_c replicate r0; sel/f3 scenes overlap net training rosters (not honest)')
    h = HOLD_ALIAS.get(bid)
    if h and (SM / f'holdout/table_{h}.json').exists():
        out['holdout'] = read_table(SM / f'holdout/table_{h}.json')
        if bid in HOLD_NOTE: notes.append(HOLD_NOTE[bid])
    return out, notes

def ref_tables():
    """B0 and B2 (and B7, B10 where defined) per flight on all sets, for server-link inference."""
    return {b: registry(b)[0] for b in ('B0', 'B2', 'B7', 'B10')}


# ---------------------------------------------------------------------------------------------------------------- requirements
def req_rate(p, n=12): return 1 - p ** (1.0 / n)

def zero_fail_n(rate, conf=0.95): return math.ceil(math.log(1 - conf) / math.log(1 - rate))


# ------------------------------------------------------------------------------------------ class table for one build/set
def class_table(A, st, rng):
    """A: ep->ate on set st. returns (md lines, per-class dict)"""
    eps = [e for e in A if e in F and F[e]['set'] == st]
    ate = np.array([A[e] for e in eps]); cl = np.array([classify(F[e]) for e in eps]); sc = np.array([F[e]['catalog'] + F[e]['scene'] for e in eps])
    res = {}; L = ['| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |', '|--|--|--|--|--|--|']
    def row(name, m):
        n = int(m.sum())
        if n == 0: return
        k3 = int((ate[m] > 3).sum()); k5 = int((ate[m] > 5).sum()); lo, hi = cboot(ate[m] > 3, sc[m], rng, 600)
        res[name] = dict(n=n, k3=k3, k5=k5, mean=float(ate[m].mean()))
        L.append(f'| {name} | {n} | {ate[m].mean():.2f} | {fmt(k3, n)} | {fmt(k5, n)} | [{100*lo:.1f},{100*hi:.1f}] |')
    for c in CLASSES: row(c, cl == c)
    row('ALL', np.ones(len(eps), bool))
    L.append('| *overlay tags (not exclusive)* | | | | | |')
    tg = [tags(F[e]) for e in eps]
    for t in ['reverse>=135', 'flat>0.05', 'path<45', 'path45-65', 'path>=65', 'extent<3', 'extent3-5', 'extent>=5', 'cat:hssd-train', 'cat:hssd-val', 'cat:procthor', 'set:K', 'set:K2']:
        m = np.array([t in x for x in tg]); row(t, m)
    return L, res


def worst(A, st, k=8):
    eps = sorted([e for e in A if e in F and F[e]['set'] == st], key=lambda e: -A[e])[:k]; L = []
    for e in eps:
        f = F[e]; c = classify(f); L.append(f"| {e} | {A[e]:.2f} | {c} | v0 {f['speed0']:.2f} ang {('%.0f' % f['angle']) if f['angle'] is not None else '-'} path {f['travel']:.0f} flat {f['flat']:.2f} dark {f['dark']:.2f} | {mech_tag(e, f, c)} |")
    return L


# ------------------------------------------------------------------------------------------------ server link (inference)
def composition():
    """P(class | mid) and P(flat/dark | static) pooled over the three sets (all flights with features)."""
    cnt = {c: 0 for c in CLASSES}
    for f in F.values(): cnt[classify(f)] += 1
    return cnt

def prior(pm):
    """prior class probabilities of a server episode given mid-start share pm. flat/dark flights are split by start type in the pool; we keep the pooled
    composition inside each start type (flat/dark stays its own class and is taken out of the start type it belongs to)."""
    cnt = {c: 0 for c in CLASSES}
    cs = {'static': 0, 'mid': 0}
    for f in F.values():
        c = classify(f); cnt[c] += 1; cs[f['start']] += 1
    fd_static = sum(1 for f in F.values() if classify(f) == CLASSES[5] and f['start'] == 'static'); fd_mid = cnt[CLASSES[5]] - fd_static
    pr = {}
    for c in CLASSES[:5]:
        if c == CLASSES[0]: pr[c] = (1 - pm) * cnt[c] / cs['static']
        else: pr[c] = pm * cnt[c] / cs['mid']
    pr[CLASSES[5]] = (1 - pm) * fd_static / cs['static'] + pm * fd_mid / cs['mid']
    return pr

BINS = [0.5, 1.5, 3.0, 5.0]
def bin_of(x): return int(np.searchsorted(BINS, x, side='right'))   # 0:<0.5 1:<1.5 2:<3 3:<5 4:>=5

def server_posteriors(pm, R, alpha=3.0):
    """INFERENCE: class posterior of each server episode from (B0 ATE, B2 ATE) via the pool joint distribution per class (flights with both builds), smoothed; e7aa also
    uses G's Sim(3) scale < 0.75 signature among G>3 pool flights (edge/sig.json). Path length is not used (correlation with ATE ~0.06)."""
    pr = prior(pm); nb = len(BINS) + 1
    cls_of = {e: classify(f) for e, f in F.items()}
    joint = {c: np.zeros((nb, nb)) for c in CLASSES}
    for st in ('fresh', 'sel', 'holdout'):
        a0 = R['B0'].get(st, {}); a2 = R['B2'].get(st, {})
        for e in a0:
            if e in a2 and e in F: joint[cls_of[e]][bin_of(a0[e]), bin_of(a2[e])] += 1
    sig = json.load(open(SM / 'edge/sig.json'))
    low = {c: [0, 0] for c in CLASSES}   # among G>3: [scale<0.75, total]
    for e, d in sig.items():
        if e in F and 'G' in d and d['G']['ate_rmse'] > 3:
            c = cls_of[e]; low[c][1] += 1; low[c][0] += d['G']['sim3_scale'] < 0.75
    tot = sum(j.sum() for j in joint.values()); mb = sum(j.sum(1) for j in joint.values()) / tot; mg = sum(j.sum(0) for j in joint.values()) / tot
    post = []
    for (ep, path, b0, g) in SERVER:
        w = {}
        for c in CLASSES:
            j = joint[c]; n = j.sum(); lik = (j[bin_of(b0), bin_of(g)] + alpha * mb[bin_of(b0)] * mg[bin_of(g)]) / (n + alpha) / (mb[bin_of(b0)] * mg[bin_of(g)])
            if ep == 'e7aa5aee': lik *= (low[c][0] + 0.5) / (low[c][1] + 1.0)
            w[c] = pr[c] * lik
        s = sum(w.values()); post.append({c: w[c] / s for c in CLASSES})
    return post

def history_cat(b0, g):
    if g > 3 and b0 > 3: return 'E both>3'
    if g > 3: return 'C G>3, base<=3'
    if b0 > 3: return 'D base>3, G<=3'
    if max(b0, g) > 1.5: return 'B max in (1.5,3]'
    return 'A both<=1.5'
HCATS = ['A both<=1.5', 'B max in (1.5,3]', 'C G>3, base<=3', 'D base>3, G<=3', 'E both>3']

def history_rates(A, R, sets=('holdout',)):
    """P(build >3 | (base,G) history category) from flights where build, B0 and B2 are all available on the given sets."""
    k = {h: 0 for h in HCATS}; n = {h: 0 for h in HCATS}
    for st in sets:
        for e, a in A.get(st, {}).items():
            if e in R['B0'].get(st, {}) and e in R['B2'].get(st, {}):
                h = history_cat(R['B0'][st][e], R['B2'][st][e]); n[h] += 1; k[h] += a > 3
    return k, n

def p_clean_class(rates, post):
    """rates: class->per-flight failure prob. returns P(all 12 <=3) and per-episode failure probs."""
    pj = [sum(p[c] * rates[c] for c in CLASSES) for p in post]
    return float(np.prod([1 - x for x in pj])), pj

def contribution(rates, post):
    base, _ = p_clean_class(rates, post); out = {}
    for c in CLASSES:
        r2 = dict(rates); r2[c] = 0.0; pc, _ = p_clean_class(r2, post)
        r3 = dict(rates); r3[c] = rates[c] / 2; ph, _ = p_clean_class(r3, post)
        out[c] = (pc - base, sum(p[c] * rates[c] for p in post), ph - base)   # (gain if class never fails, expected failing episodes from class, gain if its rate is halved)
    return base, out

def proxy_pclean(A, st, pm, rng, K=60, boot=0):
    """12-draw proxy: slot j draws one flight of the set whose path length is among the K nearest to the server path (start type mid with prob pm). Exact (analytic) mean over
    draws = prod_j q_j.  boot>0: scene-cluster bootstrap of the set."""
    eps = [e for e in A if e in F and F[e]['set'] == st]
    if not eps: return float('nan'), (float('nan'),) * 2
    ok = np.array([A[e] <= 3 for e in eps]); tr = np.array([F[e]['travel'] for e in eps]); mid = np.array([F[e]['start'] == 'mid' for e in eps])
    sc = np.array([F[e]['catalog'] + F[e]['scene'] for e in eps]); sd = np.array([s[1] for s in SERVER])
    def run(idx):
        o, t, m = ok[idx], tr[idx], mid[idx]; P = 1.0
        for d in sd:
            nn = np.argsort(np.abs(t - d))[:K]; mm = m[nn]; q = pm * o[nn][mm].mean() + (1 - pm) * o[nn][~mm].mean() if mm.any() and (~mm).any() else o[nn].mean(); P *= q
        return P
    p0 = run(np.arange(len(eps))); ci = (float('nan'),) * 2
    if boot:
        u, inv = np.unique(sc, return_inverse=True); members = [np.where(inv == i)[0] for i in range(len(u))]; v = []
        for _ in range(boot):
            pick = rng.integers(0, len(u), len(u)); v.append(run(np.concatenate([members[i] for i in pick])))
        ci = tuple(np.percentile(v, [5, 95]))
    return p0, ci


# ------------------------------------------------------------------------------------------------------------- report
def report(bid, label, T, notes, R, rng, full=True):
    L = [f'# {bid}: {label}', '']
    for n in notes: L.append(f'* note: {n}')
    sets = [s for s in ('holdout', 'fresh', 'sel') if s in T and len(T[s])]
    honesty = {'holdout': 'CLEAN one-shot set (honest)', 'fresh': 'never tuned on, but partly used in adoption decisions (mildly optimistic)', 'sel': 'used for tuning/selection (optimistic)'}
    L += ['## 1. Overall', '| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |', '|--|--|--|--|--|--|--|--|--|--|']
    cls_res = {}
    for st in sets:
        a = np.array([T[st][e] for e in T[st] if e in F]); n = len(a)
        L.append(f'| {st} | {n} | {a.mean():.3f} | {np.median(a):.2f} | {np.percentile(a,90):.2f} | {a.max():.1f} | {fmt(int((a>3).sum()), n)} | {fmt(int((a>5).sum()), n)} | {int((a>10).sum())} | {honesty[st]} |')
    L.append('')
    L.append('## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)')
    for st in sets:
        tbl, res = class_table(T[st], st, rng); cls_res[st] = res
        L += [f'### {st}', ''] + tbl + ['']
    L.append('## 3. P(all 12 server episodes <= 3 m)')
    L += ['Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):', '',
          '| estimator | set | pm=0.5 | pm=0.75 |', '|--|--|--|--|']
    out = {}
    for st in sets:
        row = []
        for pm in (0.5, 0.75):
            p, ci = proxy_pclean(T[st], st, pm, rng, boot=200); row.append(f'{p:.2f} [{ci[0]:.2f},{ci[1]:.2f}]'); out[('proxy', st, pm)] = p
        L.append(f'| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | {st} | {row[0]} | {row[1]} |')
    for st in sets:
        a = np.array([T[st][e] for e in T[st] if e in F]); k = int((a > 3).sum()); n = len(a); r = jeffreys(k, n)
        L.append(f'| flat rate, (1-r)^12, r=Jeffreys {100*r:.1f}% (Wilson-upper r={100*wilson(k, n)[1]:.1f}% -> {(1-wilson(k, n)[1])**12:.2f}) | {st} | {(1-r)**12:.2f} | {(1-r)**12:.2f} |')
    # class-conditional using per-episode posteriors
    L.append('')
    L.append('Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):')
    L += ['', '| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |', '|--|--|--|--|--|']
    crate = {}; M = 10.0
    pool = {c: [sum(cls_res[st][c]['k3'] for st in sets if c in cls_res[st]), sum(cls_res[st][c]['n'] for st in sets if c in cls_res[st])] for c in CLASSES}
    rp = {c: jeffreys(*pool[c]) for c in CLASSES}
    srcs = [('holdout (shrunk, m=10, to pooled-all-sets rate)', 'holdout', 'shrunk'), ('holdout (Jeffreys only)', 'holdout', 'jeff')] + [(st + ' (Jeffreys)', st, 'jeff') for st in sets if st != 'holdout'] + [('pooled all sets (Jeffreys)', None, 'pool')]
    for lab, st, mode in srcs:
        if st is not None and st not in sets: continue
        rates = {}; ab = {}
        for c in CLASSES:
            if mode == 'pool': k, n = pool[c]; a0, b0 = k + 0.5, n - k + 0.5
            else:
                r = cls_res[st].get(c, dict(k3=0, n=0)); k, n = r['k3'], r['n']
                a0, b0 = (k + 0.5, n - k + 0.5) if mode == 'jeff' else (k + M * rp[c], n - k + M * (1 - rp[c]))
            rates[c] = a0 / (a0 + b0); ab[c] = (a0, b0)
        crate[lab] = rates
        for pm in (0.5, 0.75):
            post = server_posteriors(pm, R); p, pj = p_clean_class(rates, post)
            dr = [p_clean_class({c: rng.beta(*ab[c]) for c in CLASSES}, post)[0] for _ in range(1000)]
            L.append(f'| {lab} | {pm} | {p:.2f} | [{np.percentile(dr,5):.2f},{np.percentile(dr,95):.2f}] | {sum(pj):.2f} |'); out[('class', lab, pm)] = p; out[('lo5', lab, pm)] = float(np.percentile(dr, 5))
    HK = 'holdout (shrunk, m=10, to pooled-all-sets rate)'
    if HK in crate:
        L += ['', 'Per-episode link (INFERENCE; posterior over classes from the episode\'s (B0, G) server ATEs; p(fail) = sum_c post_c * rate_c with the shrunk holdout rates):', '',
              '| episode | path m | B0 -> G server ATE | class posterior (pm=0.75, top3) | p(>3 m) pm=0.5 | p(>3 m) pm=0.75 |', '|--|--|--|--|--|--|']
        P5 = server_posteriors(0.5, R); P75 = server_posteriors(0.75, R)
        for j, (ep, path, b0, g) in enumerate(SERVER):
            top = sorted(P75[j].items(), key=lambda kv: -kv[1])[:3]
            L.append(f'| {ep} | {path} | {b0} -> {g} | ' + ', '.join(f'{c.split(" (")[0]} {100*w:.0f}%' for c, w in top) + f' | {100*sum(P5[j][c]*crate[HK][c] for c in CLASSES):.1f}% | {100*sum(P75[j][c]*crate[HK][c] for c in CLASSES):.1f}% |')
    # history-conditioned
    if 'holdout' in T:
        k, n = history_rates({'holdout': T['holdout'], 'fresh': T.get('fresh', {}), 'sel': T.get('sel', {})}, R, sets=('holdout',))
        hr = {h: jeffreys(k[h], n[h]) for h in HCATS}
        hist = [history_cat(b0, g) for (_, _, b0, g) in SERVER]; pj = [hr[h] for h in hist]
        L += ['', 'History-conditioned (INFERENCE): P(build >3 m | the episode\'s observed (B0, G) server result category), rates from the holdout flights (Jeffreys):', '',
              '| category | holdout k/n (build >3 m) | rate | server episodes in category |', '|--|--|--|--|']
        for h in HCATS: L.append(f'| {h} | {k[h]}/{n[h]} | {100*hr[h]:.1f}% | {sum(x == h for x in hist)} |')
        L.append(f'\nP(12 clean) history-conditioned = {np.prod([1-x for x in pj]):.2f}; expected # >3 m = {sum(pj):.2f}. (cell counts are tiny: treat as a sanity check, not an estimate)')
        out[('hist', 'holdout', 0)] = float(np.prod([1 - x for x in pj]))
    # contribution
    HK = 'holdout (shrunk, m=10, to pooled-all-sets rate)'
    if HK in crate:
        L += ['', '## 4. Which class drives the miss probability (holdout class rates shrunk to the pooled rate, class-conditional model)', '',
              '| class | pm | class rate used (holdout, shrunk) | expected episodes >3 m | gain in P(12 clean) if this class never fails | if its rate is halved |', '|--|--|--|--|--|--|']
        for pm in (0.5, 0.75):
            post = server_posteriors(pm, R); base, con = contribution(crate[HK], post)
            for c in CLASSES: L.append(f'| {c} | {pm} | {100*crate[HK][c]:.1f}% | {con[c][1]:.2f} | {con[c][0]:+.3f} (from {base:.2f}) | {con[c][2]:+.3f} |')
    # requirements
    L += ['', '## 5. Requirement check (flight-level >3 m rate r needed so that P(no episode >3 m among 12) >= target, equal rates)', '',
          '| target | needed r | zero-failure flights for 95% upper bound <= r | holdout k/n (Wilson upper) |', '|--|--|--|--|']
    for p in (0.5, 0.8, 0.9):
        r = req_rate(p); hs = ''
        if 'holdout' in T:
            a = np.array([T['holdout'][e] for e in T['holdout'] if e in F]); k = int((a > 3).sum()); hs = f'{k}/{len(a)} ({100*wilson(k, len(a))[1]:.1f}%)  ' + ('POINT OK' if k / len(a) <= r else 'POINT FAILS')
        L.append(f'| {p} | {100*r:.2f}% | {zero_fail_n(r)} | {hs} |')
    HK2 = 'holdout (shrunk, m=10, to pooled-all-sets rate)'
    if ('class', HK2, 0.75) in out:
        pt = min(out[('class', HK2, 0.5)], out[('class', HK2, 0.75)]); lo = min(out[('lo5', HK2, 0.5)], out[('lo5', HK2, 0.75)])
        tier = lambda v: '0.9' if v >= 0.9 else '0.8' if v >= 0.8 else '0.5' if v >= 0.5 else 'none'
        L.insert(2, f'**VERDICT (holdout class-conditional, worse of pm 0.5/0.75): P(12 clean) point {pt:.2f}, 5% lower bound {lo:.2f}. Certified tier by point estimate: {tier(pt)}; by lower bound: {tier(lo)}. '
                    f'(tiers: P>=0.5/0.8/0.9; see section 5 for the evidence a new clean set would have to provide.)**\n')
    # worst flights
    L += ['', '## 6. Worst flights (>3 m listed first; mechanism tags: diag = b6fix mech_table for B6/B7-era flights; rule = observable-only suspicion, POST-HOC for holdout)', '',
          '| flight | ATE | class | features | mechanism |', '|--|--|--|--|--|']
    for st in sets:
        L.append(f'| **{st}** | | | | |'); L += worst(T[st], st)
    return '\n'.join(L), out, cls_res


def persistence(out):
    """POST-HOC chaos-floor analysis: how stable are >3 m failures across builds? (holdout: B2,B4,B7,B10; fresh: B2,B4,B7)."""
    L = ['# Failure persistence across builds (POST-HOC analysis of existing tables; not used to tune anything)', '']
    for st, bl in (('holdout', ['B2', 'B4', 'B7', 'B10']), ('fresh', ['B2', 'B4', 'B7'])):
        T = {b: registry(b)[0][st] for b in bl}; eps = [e for e in T[bl[0]] if all(e in T[b] for b in bl) and e in F]
        fail = {b: np.array([T[b][e] > 3 for e in eps]) for b in bl}; nf = np.sum([fail[b] for b in bl], 0)
        L += [f'## {st} (n={len(eps)} flights scored by every build in {bl})', '', '| number of builds failing the flight (>3 m) | flights |', '|--|--|']
        for k in range(len(bl) + 1): L.append(f'| {k} | {(nf == k).sum()} |')
        L += ['', '| later build | earlier build | P(later fails | earlier failed) | P(later fails | earlier ok) = "new-failure rate" |', '|--|--|--|--|']
        for i in range(1, len(bl)):
            a, b = bl[i], bl[i - 1]; fa, fb = fail[a], fail[b]
            L.append(f'| {a} | {b} | {fa[fb].sum()}/{fb.sum()} = {100*fa[fb].mean():.0f}% | {fa[~fb].sum()}/{(~fb).sum()} = {100*fa[~fb].mean():.1f}% |')
        last = bl[-1]; others = [b for b in bl[:-1]]; ok_all = np.all([~fail[b] for b in others], 0)
        L += ['', f'{last} fails on {fail[last].sum()} flights; {int((fail[last] & ok_all).sum())} of them were OK (<=3 m) in ALL of {others} (new/chaotic failures: rate {100*(fail[last] & ok_all).sum()/ok_all.sum():.1f}% of {ok_all.sum()} flights that all older builds solved) and '
              f'{int((fail[last] & ~ok_all).sum())} also failed in at least one older build (persistent).', '']
    (out / 'PERSISTENCE.md').write_text('\n'.join(L) + '\n')


def requirements(out, rng):
    """Per-class and overall >3 m rates needed for P(12 clean) >= 0.5/0.8/0.9 (class-conditional model at pm 0.5/0.75), starting from B11's shrunk holdout class rates."""
    T, _ = registry('B11'); R = ref_tables(); st = 'holdout'
    eps = [e for e in T[st] if e in F]; ate = {e: T[st][e] for e in eps}
    res = {c: [0, 0] for c in CLASSES}
    for e in eps: c = classify(F[e]); res[c][1] += 1; res[c][0] += ate[e] > 3
    pool = {c: [0, 0] for c in CLASSES}
    for s2 in ('fresh', 'sel', 'holdout'):
        for e, a in T[s2].items():
            if e in F: c = classify(F[e]); pool[c][1] += 1; pool[c][0] += a > 3
    M = 10.0; cur = {}
    for c in CLASSES:
        rp = jeffreys(*pool[c]); cur[c] = (res[c][0] + M * rp) / (res[c][1] + M)
    L = ['# Requirements: flight-level >3 m failure rates needed for P(no server episode >3 m)', '',
         f'Equal-rate benchmark: r = 1-p^(1/12): ' + ', '.join(f'p>={p}: {100*req_rate(p):.2f}%' for p in (0.5, 0.8, 0.9)) + '. B11 holdout point rate 8/240 = 3.33% (Wilson 95% [1.7, 6.4]%).', '',
         'Class-conditional model (server class posteriors, INFERENCE). Starting from the B11 shrunk holdout class rates, scale all classes by a common factor f so that P(12 clean) hits the target:', '',
         '| pm | target | f | overall flight-level rate (prior-weighted) | ' + ' | '.join(c.split(' (')[0] for c in CLASSES) + ' |', '|' + '--|' * (4 + len(CLASSES))]
    for pm in (0.5, 0.75):
        post = server_posteriors(pm, R); pr = prior(pm)
        L.append(f'| {pm} | now | 1.00 | {100*sum(pr[c]*cur[c] for c in CLASSES):.2f}% (P={p_clean_class(cur, post)[0]:.2f}) | ' + ' | '.join(f'{100*cur[c]:.1f}%' for c in CLASSES) + ' |')
        for p in (0.5, 0.8, 0.9):
            lo, hi = 0.0, 3.0
            for _ in range(60):
                mid = 0.5 * (lo + hi); r = {c: min(1.0, mid * cur[c]) for c in CLASSES}
                if p_clean_class(r, post)[0] >= p: lo = mid
                else: hi = mid
            f = lo; r = {c: min(1.0, f * cur[c]) for c in CLASSES}
            L.append(f'| {pm} | {p} | {f:.2f} | {100*sum(pr[c]*r[c] for c in CLASSES):.2f}% | ' + ' | '.join(f'{100*r[c]:.1f}%' for c in CLASSES) + ' |')
    def nreq(r, k):
        for n in range(1, 5000):
            if sum(math.comb(n, i) * r ** i * (1 - r) ** (n - i) for i in range(k + 1)) < 0.05: return n
    L += ['', 'Interpretation: the target rows are the per-class rates a build must reach (same relative profile as B11); p>=0.9 needs a ~4-5x lower failure rate in every class (and flat/dark is a ~17-19% class rate by itself), '
          'which is at or below the measured chaos floor (new-failure rate 0.9-2.2% per flight per build change, PERSISTENCE.md).', '',
          'Exact-binomial 95% evidence needed (flights n so that observing k failures excludes a true rate above r): ', '', '| r (target) | k=0 | k=1 | k=2 |', '|--|--|--|--|']
    for p in (0.5, 0.8, 0.9): r = req_rate(p); L.append(f'| {100*r:.2f}% (p>={p}) | {nreq(r, 0)} | {nreq(r, 1)} | {nreq(r, 2)} |')
    L.append('\nThe existing holdout (n=240, B11 k=8) cannot certify p>=0.8 or 0.9; only a new clean set can, and it can be used once per candidate.')
    (out / 'REQUIREMENTS.md').write_text('\n'.join(L) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true'); ap.add_argument('--build', action='append', default=[]); ap.add_argument('--name')
    ap.add_argument('--fresh'); ap.add_argument('--sel'); ap.add_argument('--holdout'); ap.add_argument('--out', default=str(HERE / 'out')); ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(exist_ok=True, parents=True); rng = np.random.default_rng(a.seed)
    R = ref_tables(); summary = {}
    jobs = []
    if a.all or a.build:
        for b, lab in BUILDS:
            if a.all or b in a.build:
                T, notes = registry(b); jobs.append((b, lab, T, notes))
    if a.name:
        T = {}
        for st in ('fresh', 'sel', 'holdout'):
            p = getattr(a, st)
            if p: T[st] = read_table(p)
        jobs.append((a.name, 'custom candidate', T, []))
    for b, lab, T, notes in jobs:
        md, o, cr = report(b, lab, T, notes, R, rng); (out / f'{b}.md').write_text(md + '\n'); summary[b] = {f'{k[0]}|{k[1]}|{k[2]}': v for k, v in o.items()}
        print(f'wrote {out}/{b}.md', {k: round(v, 3) for k, v in o.items() if k[0] == 'class' and str(k[1]).startswith('holdout (shrunk')})
    json.dump(summary, open(out / 'summary.json', 'w'), indent=1)
    if a.all: persistence(out); requirements(out, rng)
    HK = 'holdout (shrunk, m=10, to pooled-all-sets rate)'
    S = ['# Scorecard summary (generated by certify.py; per-build details in <build>.md)', '',
         '| build | set | n | >3 m (Wilson 95%) | >5 m | P(12 clean) class-cond. holdout-shrunk pm=.5 / .75 | proxy holdout pm=.5 / .75 | history-cond. |', '|--|--|--|--|--|--|--|--|']
    for b, lab, T, notes in jobs:
        sm = summary[b]
        for st in ('holdout', 'fresh', 'sel'):
            if st not in T or not T[st]: continue
            a = np.array([T[st][e] for e in T[st] if e in F]); n = len(a)
            extra = ''
            if st == 'holdout':
                g = lambda k: sm.get(k, float('nan'))
                extra = f"{g('class|'+HK+'|0.5'):.2f} / {g('class|'+HK+'|0.75'):.2f} | {g('proxy|holdout|0.5'):.2f} / {g('proxy|holdout|0.75'):.2f} | {g('hist|holdout|0'):.2f}"
            else: extra = f"| proxy {st}: {sm.get('proxy|'+st+'|0.5', float('nan')):.2f} / {sm.get('proxy|'+st+'|0.75', float('nan')):.2f} |"
            S.append(f'| {b} {lab} | {st} | {n} | {fmt(int((a > 3).sum()), n)} | {fmt(int((a > 5).sum()), n)} | {extra} |' if st == 'holdout' else f'| {b} | {st} | {n} | {fmt(int((a > 3).sum()), n)} | {fmt(int((a > 5).sum()), n)} {extra}')
    (out / 'SUMMARY.md').write_text('\n'.join(S) + '\n')


if __name__ == '__main__':
    main()
