import json,glob,sys,collections
sys.path.insert(0,'.')
from research.single_model.run_variant import tags,fold
R='research/results/single_model/'
tg=tags()
def rows(n): return {r['episode']:r for r in json.load(open(glob.glob(R+n+'/eval/*/scores.json')[0]))['rows']}
M=rows('fgt_merged');G=rows('preflight_gate_a');T=rows('tails_adopted');F=rows('final_f0');GR=rows('fgt_guard0')
d=glob.glob(R+'fgt_dbg2/eval/*/')[0]
out={}
for e in M:
    p=glob.glob(d+e+'/report/logs/*/estimate.tum')
    last=open(p[0]).read().strip().splitlines()[-1].split()
    v=[float(x) for x in last[1:8]]
    out[e]=dict(rel=v[0],latch=v[1],tf=v[2],vi_ok=int(v[3]),defer=int(v[4]),blk=int(v[5]),speed=v[6],start=tg[e]['start'],fold=fold(tg[e]))
json.dump(out,open('research/single_model/final/preflight_fgt/audit_all171.json','w'),indent=0)
# aggregate stats over all 171 (no ids for fold 4)
mv=[e for e in out if out[e]['start']=='mid']; st=[e for e in out if out[e]['start']=='static']
print('static flights',len(st),'with G release',sum(out[e]['rel']>=0 for e in st),'T fired(vi_ok=1)',sum(out[e]['vi_ok']==1 for e in st),'(static not moving => neither feature active unless detector says moving)')
print('moving-detected: counted below over all flights with any gate/T activity')
act=[e for e in out if out[e]['rel']>=0 or out[e]['latch']>=0 or out[e]['vi_ok']>0 or out[e]['defer'] or out[e]['blk']]
print('flights with activity',len(act),'of 171')
c=collections.Counter()
for e in act:
    o=out[e]; c[('G_rel' if o['rel']>=0 else 'G_latch' if o['latch']>=0 else 'G_none', 'T_fired' if o['vi_ok']==1 else 'T_kept_prior(agree)' if o['vi_ok']==2 else 'T_none')]+=1
for k,v in sorted(c.items()): print(k,v)
print('G release frames:',sorted(collections.Counter(int(out[e]['rel']) for e in out if out[e]['rel']>=0).items()))
print('G latch frames:',sorted(collections.Counter(int(out[e]['latch']) for e in out if out[e]['latch']>=0).items()))
print('T decision frames:',sorted(collections.Counter(int(out[e]['tf']) for e in out if out[e]['tf']>=0).items()))
print('both G release and T fired (any order):',[ (e if out[e]['fold']!=4 else 'fold4', out[e]['rel'],out[e]['tf'],out[e]['vi_ok']) for e in out if out[e]['rel']>=0 and out[e]['vi_ok']==1])
print('T blocked by released (count>0):',sum(out[e]['blk']>0 for e in out),' deferred (count>0):',sum(out[e]['defer']>0 for e in out))
print('G release AND T would have fired w/o guard (blk>0 or defer>0), ids (fold!=4):',[(e,int(out[e]['rel']),out[e]['blk'],out[e]['defer'],round(F[e]['ate_full'],2),round(M[e]['ate_full'],2),round(GR[e]['ate_full'],2)) for e in out if (out[e]['blk'] or out[e]['defer']) and out[e]['fold']!=4])
print('flights where guard changed result (merged vs guard0 differ):',sum(M[e]['ate_full']!=GR[e]['ate_full'] for e in M))
# explanation of the flights differing from f0 >0.3 (fold!=4)
print('\nper-flight audit, flights with |merged-f0|>0.3 or |merged-T|>0.3 or |merged-G|>0.3 (fold!=4):')
for e in sorted(out):
    o=out[e]
    if o['fold']==4: continue
    if max(abs(M[e]['ate_full']-X[e]['ate_full']) for X in (F,G,T))>0.3:
        print(f"{e} {o['start']} f0 {F[e]['ate_full']:.2f} G {G[e]['ate_full']:.2f} T {T[e]['ate_full']:.2f} M {M[e]['ate_full']:.2f} | G_rel {o['rel']:.0f} G_latch {o['latch']:.0f} T_frame {o['tf']:.0f} vi_ok {o['vi_ok']} speed {o['speed']:.2f}")
