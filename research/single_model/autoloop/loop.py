"""Unattended resumable optimisation loop (see README.md).  python -m research.single_model.autoloop.loop [--budget-h 5]
No LLM involvement. All decisions are functions of ledger.jsonl + state.json, so a crash/restart resumes where it stopped."""
import argparse, fcntl, json, math, os, shutil, signal, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from research.single_model.autoloop import params as P, scoring as S
from research.single_model import run_variant as RV

HERE = Path(__file__).resolve().parent
STATE = HERE / 'state.json'; LOGMD = HERE / 'LOG.md'; STOPF = HERE / 'STOP'; LOGS = HERE / 'logs'
PY = sys.executable
DEFAULT_CFG = dict(budget_h=5.0, reserve_min=25.0, reps=3, workers=24, concurrent=2, load_max=140.0, a_frac=0.40, b_frac=0.70,
                   topk=12, seed=20261120, keep_best=20, step0=0.30, step_min=0.07, mu=4, lam=6)


class Loop:
    def __init__(self, cfg):
        self.cfg = cfg; self.lock = threading.RLock(); self.stop = False
        LOGS.mkdir(exist_ok=True)
        self.state = json.loads(STATE.read_text()) if STATE.exists() else dict(phase='init', spent=0.0, step=cfg['step0'], gen=0, ref=None, promotions=[], top=[], active=[], started=time.time())
        self.state['cfg'] = cfg; self.t_run = time.time()
        self.rows = {}                                    # (hash, stage) -> ledger row
        for r in S.read_ledger(): self.rows[(r['hash'], r['type'])] = r
        self.pool = ThreadPoolExecutor(cfg['concurrent'])
        self.dh = P.vhash(P.default_vec())
        signal.signal(signal.SIGTERM, lambda *a: self._sig()); signal.signal(signal.SIGINT, lambda *a: self._sig())

    def _sig(self):
        self.stop = True; self.log('signal received: finishing in-flight evaluations, no new launches')

    # ---- bookkeeping
    def spent(self): return self.state['spent'] + time.time() - self.t_run
    def budget(self): return self.cfg['budget_h'] * 3600
    def save(self):
        with self.lock:
            self.state['spent_saved'] = self.spent(); s = dict(self.state); s['spent'] = self.spent()
            tmp = STATE.with_suffix('.tmp'); tmp.write_text(json.dumps(s, indent=1)); tmp.replace(STATE)
    def log(self, msg, md=True):
        line = f"- {time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        if md:
            with open(LOGMD, 'a') as f: f.write(line + '\n')
    def halt(self, frac=1.0):
        return self.stop or STOPF.exists() or self.spent() >= self.budget() * frac - (self.cfg['reserve_min'] * 60 if frac >= 1.0 else 0)

    def wait_load(self):
        while True:
            try: l = float(open('/proc/loadavg').read().split()[0])
            except Exception: l = 0
            if l <= self.cfg['load_max'] or self.stop or STOPF.exists(): return
            time.sleep(30)

    # ---- evaluation
    def _append(self, row):
        with self.lock:
            with open(S.LEDGER, 'a') as f: f.write(json.dumps(row) + '\n')
            self.rows[(row['hash'], row['type'])] = row

    def _run_job(self, h, vec, stage, keep):
        res = S.load_res(h, stage)
        if res is not None: return res                    # finished earlier, crash before ledger write
        for attempt in range(2):
            self.wait_load()
            if self.stop or STOPF.exists(): return None
            job = dict(hash=h, vec=vec, stage=stage, reps=self.cfg['reps'], workers=self.cfg['workers'], keep=keep)
            jf = LOGS / f'{h}.{stage}.job.json'; jf.write_text(json.dumps(job))
            env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONPATH=str(RV.ROOT))
            with open(LOGS / f'{h}.{stage}.log', 'w') as lg:
                try: subprocess.run([PY, '-B', '-m', 'research.single_model.autoloop.evalvec', str(jf)], cwd=RV.ROOT, env=env, stdout=lg, stderr=subprocess.STDOUT, timeout=3600)
                except subprocess.TimeoutExpired: pass
            res = S.load_res(h, stage)
            if res is not None: return res
        return dict(hash=h, stage=stage, vec=P.norm(vec), flights={}, fuel={}, p95={}, med={}, errors=['crash/timeout'], wasm_size=[], wasm_sha=[], src_sha=[], wall_s=0)

    def eval_search(self, vec):
        v = P.norm(vec); h = P.vhash(v); k = (h, 'search')
        if k in self.rows: return self.rows[k]
        why = P.ill_posed(v)
        if why:
            r = dict(type='search', hash=h, params=v, status='ill_posed:' + why, ts=time.time(), metrics=None); self._append(r); return r
        res = self._run_job(h, v, 'search', True)
        if res is None: return None
        if res['errors'] or not res['flights']:
            r = dict(type='search', hash=h, params=v, status='failed', errors=res['errors'][:3], ts=time.time(), wall_s=res.get('wall_s'), metrics=None)
        else:
            m = S.metrics(res)
            r = dict(type='search', hash=h, params=v, delta={n: v[n] for n in P.NAMES if v[n] != P.REG[n]['default']}, status='ok' if m['valid'] else 'invalid',
                     metrics=m, ts=time.time(), wall_s=round(res['wall_s'], 1), src_sha=res['src_sha'][0], wasm_sha=res['wasm_sha'][0], wasm_size=res['wasm_size'][0])
        self._append(r); self.prune(); return r

    def eval_fresh(self, vec, stage='freshA'):
        v = P.norm(vec); h = P.vhash(v); k = (h, stage)
        if k in self.rows: return self.rows[k]
        res = self._run_job(h, v, stage, False)
        if res is None: return None
        if not res['flights']: r = dict(type=stage, hash=h, status='failed', metrics=dict(valid=False), ts=time.time())
        else:
            m = S.fresh_metrics(res); r = dict(type=stage, hash=h, status='ok', metrics=m, ts=time.time(), wall_s=round(res['wall_s'], 1), wasm_sha=res['wasm_sha'][0])
        self._append(r); return r

    def batch(self, vecs, phase_frac=1.0):
        seen, todo = set(), []
        for v in vecs:
            h = P.vhash(v)
            if h in seen: continue
            seen.add(h); todo.append(P.norm(v))
        def task(v):
            if self.halt(phase_frac): return None
            return self.eval_search(v)
        return [r for r in self.pool.map(task, todo) if r is not None and r.get('metrics')]

    def prune(self):
        """keep the eval outputs (trajectories) of the best keep_best search vectors only."""
        with self.lock:
            ref = self.ref_row()
            if ref is None: return
            ok = [r for (h, t), r in self.rows.items() if t == 'search' and r.get('metrics')]
            ranked = sorted(ok, key=lambda r: S.key(r['metrics'], S.judge(r['metrics'], None, ref['metrics'], None)['feasible']))
            keep = {r['hash'] for r in ranked[:self.cfg['keep_best']]} | {self.dh, self.state['ref']}
            for r in ok:
                if r['hash'] not in keep:
                    shutil.rmtree(RV.OUT / f"loop_{r['hash']}_r0", ignore_errors=True)

    # ---- reference handling
    def ref_row(self):
        h = self.state.get('ref'); return self.rows.get((h, 'search')) if h else None
    def ref_fresh(self): return self.rows.get((self.state['ref'], 'freshA'))

    def decide(self, rows, label):
        """screen -> fresh-A -> promote at most one candidate."""
        ref = self.ref_row(); rm = ref['metrics']
        scored = []
        for r in rows:
            if r['hash'] == ref['hash'] or not r.get('metrics'): continue
            j = S.judge(r['metrics'], None, rm, None)
            if j['screen']: scored.append((S.key(r['metrics'], True), r, j))
        scored.sort(key=lambda x: x[0])
        if not scored:
            ms = [rr['metrics']['search'] for rr in rows if rr.get('metrics')]
            self.log(f'{label}: no candidate passed the search screen (best raw improvement {rm["search"] - min(ms):+.3f})' if ms else f'{label}: no evaluated candidates', md=False)
            return None
        top = scored[:3]
        fas = list(self.pool.map(lambda x: self.eval_fresh(x[1]['params'], 'freshA'), top))
        rfa = self.ref_fresh()['metrics']
        for (k, r, j), fa in zip(top, fas):
            if fa is None: continue
            fm = fa['metrics']
            ok = S.fresh_ok(fm, rfa)
            self.log(f"{label}: screen-pass {r['hash']} d_search={j['improvement']:+.3f} val {r['metrics']['val']:.3f} delta={r['delta']} | fresh-A {fm.get('mean', float('nan')):.3f} (ref {rfa['mean']:.3f}) n5 {fm.get('n5')}/{rfa['n5']} n10 {fm.get('n10')}/{rfa['n10']} -> {'PROMOTE' if ok else 'reject'}", md=True)
            if ok:
                self.promote(r, fa, j); return r
        return None

    def promote(self, r, fa, j):
        old = self.ref_row(); res_c, res_r = S.load_res(r['hash']), S.load_res(old['hash'])
        bs = S.bootstrap(res_c, res_r) if res_c and res_r else {}
        m = r['metrics']
        self.state['ref'] = r['hash']; self.state['promotions'].append(dict(hash=r['hash'], t=self.spent(), prev=old['hash'], search=m['search'], val=m['val'], fresh_a=fa['metrics']['mean']))
        self.log(f"PROMOTED {r['hash']}: replicate-mean search {old['metrics']['search']:.3f} -> {m['search']:.3f}, val {old['metrics']['val']:.3f} -> {m['val']:.3f}, "
                 f"paired bootstrap (cand-ref, scene) {bs}, fresh-A {fa['metrics']['mean']:.3f}, fuel {m['fuel_peak']/1e6:.2f}M; changed vs default: {r['delta']}")
        self.save()

    # ---- phases
    def init_phase(self):
        self.log('INIT: evaluating default vector (reproduction check) and fresh-A reference')
        from research.single_model.autoloop import evalvec; evalvec.pool('freshA'); evalvec.pool('freshB')
        dv = P.default_vec()
        a, b = self.pool.map(lambda f: f(), [lambda: self.eval_search(dv), lambda: self.eval_fresh(dv, 'freshA')])
        res = S.load_res(self.dh)
        ref = json.loads(Path(next((P.REF_RUN / 'eval').glob('*/scores.json'))).read_text())
        ra = {x['episode']: x['ate_full'] for x in ref['rows']}
        same = sum(ra.get(e) == v[0] for e, v in res['flights'].items())
        sha_ok = res['wasm_sha'][0] == P.GATE_WASM_SHA
        msg = f"reproduction: wasm sha == inv_adopted.wasm {sha_ok}; visible flights identical to preflight_gate_a: {same}/{len(res['flights'])}"
        self.log(msg)
        if same != len(res['flights']):
            self.log('ABORT: default vector does not reproduce the adopted.c reference scores'); raise SystemExit(2)
        if not sha_ok: self.log('WARNING: wasm sha differs from results/single_model/inv_adopted/solution.wasm (ATEs identical)')
        try:
            tab = {r['episode']: r['ate'] for r in json.loads((RV.ROOT / 'research/single_model/inventive/fresh_table_c1.json').read_text())}
            fres = S.load_res(self.dh, 'freshA'); ns = sum(tab.get(e) == v[0] for e, v in fres['flights'].items())
            self.log(f'fresh-A default vs inventive/fresh_table_c1.json: {ns}/{len(fres["flights"])} identical')
        except Exception as e: self.log(f'fresh table compare skipped: {e}')
        self.state['ref'] = self.dh; self.state['phase'] = 'A'; self.save()

    def levels(self, n, lvl):
        r = P.REG[n]; d = r['default']
        if r['kind'] == 'i':
            return d + (1 if lvl > 1 else -1) * max(1, int(round(abs(d * (lvl - 1 if lvl > 1 else 1 - lvl)))))
        return d * lvl

    def phase_A(self):
        self.log(f"PHASE A: one-at-a-time sensitivity sweeps (38 params x 0.5/0.8/1.25/2.0, replicate-averaged), cap {self.cfg['a_frac']:.0%} of budget")
        flat = set(json.loads((HERE / 'flat_params.json').read_text())['flat']) if (HERE / 'flat_params.json').exists() else set()
        self.log('phase A skips parameters measured flat on the G-based run: ' + ', '.join(sorted(flat)))
        for lv in ([0.8, 1.25], [0.5, 2.0]):
            vecs = []
            for n in P.NAMES:
                if n in flat: continue
                for l in lv:
                    v = P.default_vec(); v[n] = self.levels(n, l); v = P.norm(v)
                    if v[n] != P.REG[n]['default']: vecs.append(v)
            rows = self.batch(vecs, self.cfg['a_frac'])
            if self.halt(self.cfg['a_frac']): break
        # rank parameters
        sens = self.sensitivity(); self.state['top'] = [s['name'] for s in sens[:self.cfg['topk']]]; self.state['active'] = [s['name'] for s in sens[:20]]
        self.log('PHASE A done; top parameters by effect: ' + ', '.join(f"{s['name']}({s['best']:+.2f}/{s['range']:.2f})" for s in sens[:self.cfg['topk']]))
        every = [r for (h, t), r in self.rows.items() if t == 'search' and r.get('metrics') and len(r['delta']) == 1]
        self.decide(every, 'A-decision')
        self.state['phase'] = 'B'; self.save()

    def sensitivity(self):
        d = self.rows[(self.dh, 'search')]['metrics']['search']; out = []
        for n in P.NAMES:
            pts = [r['metrics']['search'] for (h, t), r in self.rows.items() if t == 'search' and r.get('metrics') and list(r['delta']) == [n]]
            if pts: out.append(dict(name=n, best=min(pts) - d, worst=max(pts) - d, range=max(pts) - min(pts), n=len(pts)))
        out.sort(key=lambda s: -(max(0, -s['best']) + 0.25 * s['range']))
        return out

    def neighbours(self, vec, n, s):
        r = P.REG[n]; v = vec[n]; res = []
        for sign in (1, -1):
            if r['kind'] == 'i': nv = v + sign * max(1, int(round(v * s)))
            elif r['scale'] == 'log': nv = v * (1 + s) ** sign
            else: nv = v + sign * s * (r['hi'] - r['lo']) * 0.5
            w = dict(vec); w[n] = nv; w = P.norm(w)
            if w[n] != vec[n]: res.append(w)
        return res

    def phase_B(self):
        self.log(f"PHASE B: coordinate descent on top {self.cfg['topk']} parameters with step halving (step {self.state['step']:.3f})")
        while not self.halt(self.cfg['b_frac']) and self.state['step'] >= self.cfg['step_min']:
            ref = self.ref_row(); rv = ref['params']; s = self.state['step']
            vecs = [w for n in self.state['top'] for w in self.neighbours(rv, n, s)]
            rows = self.batch(vecs, self.cfg['b_frac'])
            # combination of the individually helpful single-parameter moves
            good = []
            for r in rows:
                j = S.judge(r['metrics'], None, ref['metrics'], None)
                if j['feasible'] and j['improvement'] > 0:
                    ch = [n for n in P.NAMES if r['params'][n] != rv[n]]
                    if len(ch) == 1: good.append((j['improvement'], ch[0], r['params'][ch[0]]))
            good.sort(reverse=True); combo = []
            for k in (3, 2):
                if len(good) >= k:
                    w = dict(rv)
                    for _, n, val in good[:k]: w[n] = val
                    combo.append(P.norm(w))
            if combo: rows += self.batch(combo, self.cfg['b_frac'])
            if self.halt(self.cfg['b_frac']): 
                self.decide(rows, f'B step {s:.3f}'); break
            if self.decide(rows, f'B step {s:.3f}') is None:
                self.state['step'] = s / 2; self.log(f"B: no promotion at step {s:.3f}; halving to {s/2:.3f}", md=True)
            self.save()
        self.state['phase'] = 'C'; self.save()

    def phase_C(self):
        self.log(f"PHASE C: ({self.cfg['mu']},{self.cfg['lam']}) evolution strategy around the best vectors for the remaining budget")
        active = self.state['active'] or P.NAMES[:20]
        while not self.halt(1.0):
            g = self.state['gen']; rng = np.random.default_rng([self.cfg['seed'], g])
            ref = self.ref_row(); rm = ref['metrics']
            cand = []
            for (h, t), r in self.rows.items():
                if t == 'search' and r.get('metrics') and r['metrics']['valid']:
                    j = S.judge(r['metrics'], None, rm, None)
                    cand.append((S.key(r['metrics'], j['feasible'] or h == ref['hash']), r))
            cand.sort(key=lambda x: x[0]); parents = [r['params'] for _, r in cand[:self.cfg['mu']]] or [ref['params']]
            sig = max(0.05, 0.25 * 0.95 ** g); kids = []; tries = 0
            while len(kids) < self.cfg['lam'] and tries < 200:
                tries += 1; p = dict(parents[rng.integers(len(parents))])
                if len(parents) > 1 and rng.random() < 0.3:
                    q = parents[rng.integers(len(parents))]
                    for n in P.NAMES:
                        if rng.random() < 0.5: p[n] = q[n]
                for n in rng.choice(active, size=int(rng.integers(2, 6)), replace=False):
                    r = P.REG[n]
                    if r['kind'] == 'i': p[n] = p[n] + int(rng.choice([-1, 1]))
                    elif r['scale'] == 'log': p[n] = p[n] * math.exp(rng.normal(0, sig))
                    else: p[n] = p[n] + rng.normal(0, sig * 0.25 * (r['hi'] - r['lo']))
                p = P.norm(p)
                if P.ill_posed(p) or (P.vhash(p), 'search') in self.rows or any(P.vhash(p) == P.vhash(k) for k in kids): continue
                kids.append(p)
            rows = self.batch(kids)
            best = min([r['metrics']['search'] for r in rows] or [float('nan')])
            self.log(f'C gen {g}: {len(rows)} children, best child search {best:.3f}, ref {rm["search"]:.3f}, sigma {sig:.3f}', md=False)
            self.decide(rows, f'C gen {g}')
            self.state['gen'] = g + 1; self.save()
        self.state['phase'] = 'final'; self.save()

    def final(self):
        self.log('FINAL: top-3 on held-out fresh-B and summary')
        ref = self.ref_row(); rm = ref['metrics']
        fin = [ref['hash'], self.dh]
        ok = []
        for (h, t), r in self.rows.items():
            if t == 'search' and r.get('metrics') and h not in fin:
                j = S.judge(r['metrics'], None, rm, None)
                if j['feasible']: ok.append((S.key(r['metrics'], True), h))
        ok.sort(); cands = []
        for _, h in ok[:6]:
            fa = self.rows.get((h, 'freshA'))
            if fa is None and len(cands) < 3: fa = self.eval_fresh(self.rows[(h, 'search')]['params'], 'freshA')
            if fa and S.fresh_ok(fa['metrics'], self.ref_fresh()['metrics']): cands.append(h)
            if len(cands) >= 2: break
        fin += cands
        self.state['finalists'] = fin
        list(self.pool.map(lambda h: self.eval_fresh(self.rows[(h, 'search')]['params'], 'freshB'), fin))
        self.save(); self.write_summary(); self.state['phase'] = 'stopped' if (self.stop or STOPF.exists()) else 'done'; self.save()

    def write_summary(self):
        from research.single_model.autoloop import status
        (HERE / 'SUMMARY.md').write_text('# Autoloop summary\n\n```\n' + status.render(final=True) + '\n```\n')
        (HERE / 'best').mkdir(exist_ok=True)
        for h in self.state.get('finalists', []):
            r = self.rows[(h, 'search')]; (HERE / 'best' / f'{h}.c').write_text(P.render(r['params']))
            (HERE / 'best' / f'{h}.params.json').write_text(json.dumps(r['params'], indent=1))
        self.log('summary written to SUMMARY.md; finalist sources in best/')

    def run(self):
        self.log(f"loop start/resume: phase={self.state['phase']} spent={self.spent()/3600:.2f}h of {self.cfg['budget_h']}h, cfg={ {k: v for k, v in self.cfg.items()} }")
        while True:
            ph = self.state['phase']
            if self.halt(1.0) and ph not in ('final', 'done', 'stopped'):
                self.state['resume'] = ph; self.state['phase'] = ph = 'final'
            if ph == 'init': self.init_phase()
            elif ph == 'A': self.phase_A()
            elif ph == 'B': self.phase_B()
            elif ph == 'C': self.phase_C()
            elif ph == 'final': self.final()
            else: break
            self.log(f"phase -> {self.state['phase']}")
            if self.state['phase'] in ('done', 'stopped'): break
        self.log('loop finished'); self.save()


def main():
    ap = argparse.ArgumentParser()
    for k, v in DEFAULT_CFG.items(): ap.add_argument('--' + k.replace('_', '-'), type=type(v), default=None)
    a = ap.parse_args(); cfg = dict(DEFAULT_CFG)
    if STATE.exists(): cfg.update(json.loads(STATE.read_text()).get('cfg', {}))
    for k in DEFAULT_CFG:
        if getattr(a, k) is not None: cfg[k] = getattr(a, k)
    lk = open(HERE / 'loop.lock', 'w')
    try: fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: raise SystemExit('another loop process holds loop.lock')
    lp = Loop(cfg)
    if lp.state['phase'] == 'stopped' or (lp.state['phase'] == 'done' and a.budget_h is not None):   # resume after STOP / extended budget
        lp.state['phase'] = lp.state.get('resume', 'C')
    lp.run()

if __name__ == '__main__':
    main()
