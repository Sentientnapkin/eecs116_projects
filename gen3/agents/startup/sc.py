"""sc.py [--v1] [--base=NAME] NAME [NAME..] (names: evals/st_NAME or full eval names): paired vs base (default net_auto_727_sp10).
raw, srv-w, d [CI], hover/mid, mid back/side/fwd, tails >1/>2/>3 m, peak."""
import sys,json,random,statistics as s
pool='v1val' if '--v1' in sys.argv else 'v3val'
BASE=next((x.split('=')[1] for x in sys.argv if x.startswith('--base=')),'net_auto_727_sp10')
E='/data/backups/rganapa/Sebastian/gen3/evals/'
names=[x for x in sys.argv[1:] if not x.startswith('--')]
def fn(n): return E+(n if n.startswith(('net_','pr_','gslv','nv2_')) else 'st_'+n)+f'__{pool}.json'
W={'room':(12/24,1/12),'warehouse':(6/24,4/6),'forest':(6/24,1/6)}
def load(p): return {r['id']:r for r in json.load(open(p)) if r.get('ate') is not None}
def swm(rows):
    tot=0
    for c,(wc,hv) in W.items():
        h=[r['ate'] for r in rows if r['setting_class']==c and r['start']=='hover'];m=[r['ate'] for r in rows if r['setting_class']==c and r['start']!='hover']
        if not h or not m: return float('nan')
        tot+=wc*(hv*s.mean(h)+(1-hv)*s.mean(m))
    return tot
def cat(r):
    if r['start']=='hover': return 'hover'
    v=r.get('start_fwd_speed') or 0
    return 'back' if v<-0.2 else 'side' if v<0.5 else 'fwd'
R0=load(fn(BASE));
for n in [BASE]+names:
    R=load(fn(n));ids=sorted(set(R)&set(R0));rows=[R[i] for i in ids];a=[r['ate'] for r in rows]
    d=[R[i]['ate']-R0[i]['ate'] for i in ids];rng=random.Random(0);bs=sorted(s.mean(rng.choices(d,k=len(d))) for _ in range(2000))
    # server-weighted diff CI
    def sw_of(sel): return swm([R[i] for i in sel])-swm([R0[i] for i in sel])
    rng=random.Random(1);bw=sorted(sw_of(rng.choices(ids,k=len(ids))) for _ in range(300))
    c={k:s.mean([r['ate'] for r in rows if cat(r)==k]) for k in ('hover','back','side','fwd')}
    mid=s.mean([r['ate'] for r in rows if r['start']!='hover'])
    print(f"{n:24s} n{len(ids)} raw {s.mean(a):.3f} sw {swm(rows):.3f} d {s.mean(d):+.3f} [{bs[50]:+.3f},{bs[1949]:+.3f}] dsw {sw_of(ids):+.3f} [{bw[7]:+.3f},{bw[292]:+.3f}] hov {c['hover']:.3f} mid {mid:.3f} (b/s/f {c['back']:.3f}/{c['side']:.3f}/{c['fwd']:.3f}) >1/2/3 {sum(x>1 for x in a)}/{sum(x>2 for x in a)}/{sum(x>3 for x in a)} peak {max(r.get('peak') or 0 for r in rows)/1e6:.2f}M")
