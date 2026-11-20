"""python -m research.single_model.autoloop.status : leaderboard, Pareto front, sensitivity, categories, progress/ETA."""
import json, time, sys
from pathlib import Path
from research.single_model.autoloop import params as P, scoring as S

HERE = Path(__file__).resolve().parent


def render(final=False, top=10):
    L = []; rows = S.read_ledger(); st = json.loads((HERE / 'state.json').read_text()) if (HERE / 'state.json').exists() else {}
    srch = {r['hash']: r for r in rows if r['type'] == 'search'}; ok = {h: r for h, r in srch.items() if r.get('metrics')}
    fa = {r['hash']: r for r in rows if r['type'] == 'freshA' and r.get('metrics')}; fb = {r['hash']: r for r in rows if r['type'] == 'freshB' and r.get('metrics')}
    dh = P.vhash(P.default_vec()); ref = ok.get(st.get('ref') or dh)
    if not ref:
        return 'no reference evaluated yet (loop still in INIT); evaluations in ledger: %d' % len(rows)
    rm = ref['metrics']; d = ok.get(dh)
    cfg = st.get('cfg', {}); spent = st.get('spent_saved', st.get('spent', 0)); bud = cfg.get('budget_h', 5) * 3600
    tail = [r['ts'] for r in rows if r['type'] == 'search' and r.get('ts')]
    rate = len(ok) / max(spent / 3600, 1e-6)
    L.append(f"== PROGRESS: phase {st.get('phase')} | step {st.get('step', 0):.3f} gen {st.get('gen')} | budget used {spent/3600:.2f}h / {bud/3600:.1f}h "
             f"| ETA {max(0, bud - spent)/3600:.2f}h | {len(ok)} vectors ok, {len(srch) - len(ok)} failed/ill-posed, {len(fa)} fresh-A, {len(fb)} fresh-B | {rate:.1f} vec/h | last eval {time.strftime('%H:%M:%S', time.localtime(max(tail))) if tail else '-'}")
    L.append(f"   state mtime {time.strftime('%H:%M:%S', time.localtime((HERE/'state.json').stat().st_mtime)) if (HERE/'state.json').exists() else '-'}; promotions: {len(st.get('promotions', []))}")
    L.append(f"== REFERENCE {ref['hash']} search {rm['search']:.3f} (reps {[round(x,3) for x in rm['search_reps']]}) val {rm['val']:.3f} static {rm['static']:.3f} mid {rm['mid']:.3f} "
             f">3/5/10: {rm['n3']}/{rm['n5']}/{rm['n10']} fuel peak {rm['fuel_peak']/1e6:.2f}M" + (f" | fresh-A {fa[ref['hash']]['metrics']['mean']:.3f}" if ref['hash'] in fa else ''))
    if d and d['hash'] != ref['hash']:
        dm = d['metrics']; L.append(f"   default (gate build): search {dm['search']:.3f} val {dm['val']:.3f} -> improvement {dm['search'] - rm['search']:+.3f}")
    L.append('== LEADERBOARD (feasible vs current reference first; sorted by replicate-mean search ATE)')
    L.append('hash         search  val    static mid    >3 >5 >10 fuelM  d_vs_ref fresh-A  feas  delta vs default')
    rk = sorted(ok.values(), key=lambda r: S.key(r['metrics'], S.judge(r['metrics'], None, rm, None)['feasible']))
    for r in rk[:top]:
        m = r['metrics']; j = S.judge(m, None, rm, None)
        L.append(f"{r['hash']} {m['search']:.3f}  {m['val']:.3f}  {m['static']:.3f}  {m['mid']:.3f}  {m['n3']:2d} {m['n5']:2d} {m['n10']:2d}  {m['fuel_peak']/1e6:5.2f}  {j['improvement']:+.3f}  "
                 f"{fa[r['hash']]['metrics']['mean']:.3f}  {'yes' if j['feasible'] else 'no '}  {json.dumps(r['delta'])[:70]}" if r['hash'] in fa else
                 f"{r['hash']} {m['search']:.3f}  {m['val']:.3f}  {m['static']:.3f}  {m['mid']:.3f}  {m['n3']:2d} {m['n5']:2d} {m['n10']:2d}  {m['fuel_peak']/1e6:5.2f}  {j['improvement']:+.3f}  -      {'yes' if j['feasible'] else 'no '}  {json.dumps(r['delta'])[:70]}")
    L.append('== PARETO front (replicate-mean search ATE vs peak fuel), all valid vectors')
    for a in S.pareto([(r['metrics']['search'], r['metrics']['fuel_peak'], h) for h, r in ok.items()])[:12]:
        L.append(f"   {a[2]} search {a[0]:.3f} fuel {a[1]/1e6:.2f}M {json.dumps(ok[a[2]]['delta'])[:80]}")
    L.append('== SENSITIVITY (phase A one-at-a-time; best/worst = change of replicate-mean search ATE vs default; sorted by effect)')
    if d:
        out = []
        for n in P.NAMES:
            pts = [(r['metrics']['search'] - d['metrics']['search'], r['params'][n]) for r in ok.values() if list(r['delta']) == [n]]
            if pts: out.append((min(p[0] for p in pts), max(p[0] for p in pts), n, pts))
        out.sort(key=lambda x: -(max(0, -x[0]) + 0.25 * (x[1] - x[0])))
        for lo, hi, n, pts in out[:40]:
            L.append(f"   {n:20s} default {P.REG[n]['default']:<8g} best {lo:+.3f} worst {hi:+.3f}  " + ' '.join(f"{v:g}:{x:+.2f}" for x, v in sorted(pts, key=lambda p: p[1])))
    L.append('== CATEGORIES (mean over visible flights; reference | default | best feasible)')
    best = next((r for r in rk if S.judge(r['metrics'], None, rm, None)['feasible']), ref)
    for c, v in rm['cats'].items():
        dv = d['metrics']['cats'].get(c, {}).get('mean', float('nan')) if d else float('nan'); bv = best['metrics']['cats'].get(c, {}).get('mean', float('nan'))
        L.append(f"   {c:20s} n={v['n']:3d} ref {v['mean']:.3f} default {dv:.3f} best {bv:.3f}  worst flight {v['worst'][0]} {v['worst'][1]:.2f}")
    if fa:
        L.append('== FRESH-A (475 unselected flights, tuning confirmation)')
        for h, r in list(fa.items())[-8:]:
            m = r['metrics']; L.append(f"   {h} mean {m['mean']:.3f} static {m.get('static', 0):.3f} mid {m.get('mid', 0):.3f} >3/5/10 {m['n3']}/{m['n5']}/{m['n10']} ang135-180 {m.get('mid_ang_135_180', float('nan')):.2f}")
    if fb:
        L.append('== FRESH-B (held out, final top-3 only)')
        for h, r in fb.items():
            m = r['metrics']; L.append(f"   {h} mean {m['mean']:.3f} >3/5/10 {m['n3']}/{m['n5']}/{m['n10']} {'(default)' if h == dh else ''}")
    return '\n'.join(L)

if __name__ == '__main__':
    print(render())
