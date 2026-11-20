import json,glob,sys
sys.path.insert(0,'.')
import numpy as np
from research.single_model.run_variant import tags,fold,slice_of
R='research/results/single_model/'
def L(n): return {r['episode']:r for r in json.load(open(glob.glob(R+n+'/eval/*/scores.json')[0]))['rows']}
M=L('fgt_merged');F=L('final_f0');G=L('preflight_gate_a');T=L('tails_adopted');tg=tags()
vis=[e for e in M if fold(tg[e])!=4]
n4=sum(fold(tg[e])==4 for e in M)
print('flights',len(M),'visible (fold!=4)',len(vis),'fold4 (not analysed)',n4)
def stat(D,es): return np.mean([D[e]['ate_full'] for e in es])
for sl in('search','val'):
  for st in('all','static','mid'):
    es=[e for e in vis if slice_of(fold(tg[e]))==sl and (st=='all' or tg[e]['start']==st)]
    print(sl,st,len(es),' '.join(f'{k} {stat(D,es):.3f}' for k,D in (('f0',F),('G',G),('T',T),('merged',M))))
# all-171 aggregates, no ids
for k,D in (('f0',F),('G',G),('T',T),('merged',M)):
    v=[D[e]['ate_full'] for e in D]; print('171 mean',k,round(np.mean(v),3),'max',round(max(v),2),'>5',sum(x>5 for x in v),'>10',sum(x>10 for x in v))
print('merged >10m (visible):',[(e,round(M[e]['ate_full'],2)) for e in vis if M[e]['ate_full']>10])
for nm,D in (('f0',F),('G',G),('T',T)):
    d=[(e,tg[e]['start'],fold(tg[e]),D[e]['ate_full'],M[e]['ate_full']) for e in vis if abs(M[e]['ate_full']-D[e]['ate_full'])>0.3]
    print(f'--- merged vs {nm}: visible flights differing >0.3 m: {len(d)}; fold4 count differing >0.3:',sum(abs(M[e]['ate_full']-D[e]['ate_full'])>0.3 for e in M if fold(tg[e])==4))
    for r in sorted(d,key=lambda r:r[3]-r[4]): print('  %s %s fold%d %s %.2f merged %.2f d %+.2f'%(r[0],r[1],r[2],nm,r[3],r[4],r[4]-r[3]))
