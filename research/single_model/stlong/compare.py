"""Paired scene bootstrap of rep-averaged mean UNALIGNED ATE; exact pool coverage."""
import argparse,json
from pathlib import Path
import numpy as np
from evaluate import H,baseline,suffix

def compare(name,pools,nreps=3):
    A=[];B=[];AF=[];BF=[];scene=[]
    for rep in range(nreps):
        aa=[];bb=[];ss=[]
        for pool in pools:
            br,bf=baseline(pool,rep); ar=json.load(open(H/f'tables/{name+suffix(rep)}__{pool}.json'))
            b={r['ep']:r for r in br};a={r['ep']:r for r in ar};assert a.keys()==b.keys()
            ks=sorted(a);aa.extend(a[k]['ate_rmse'] for k in ks);bb.extend(b[k]['ate_rmse'] for k in ks);ss.extend((b[k]['cat'],b[k]['scene']) for k in ks)
            assert all(a[k]['ok'] and a[k]['filled_frames']==0 for k in ks)
            BF.append(bf)
            for p in (H/'results'/(name+suffix(rep))/pool).glob('*/report/logs/*/fuel.npy'): AF.append(np.load(p))
        if rep: assert ss==scene
        else:scene=ss
        A.append(aa);B.append(bb)
    a,b=np.array(A).T,np.array(B).T;d=(a-b).mean(1);us=sorted(set(scene));groups=[np.array([i for i,s in enumerate(scene) if s==u]) for u in us];rng=np.random.default_rng(0)
    boot=np.array([d[np.concatenate([groups[i] for i in rng.integers(len(us),size=len(us))])].mean() for _ in range(5000)])
    af,bf=np.concatenate(AF),np.concatenate(BF)
    r=dict(set='+'.join(pools),n=len(a),reps=nreps,base=float(b.mean()),arm=float(a.mean()),pct=100*(a.mean()/b.mean()-1),delta=float(d.mean()),ci=np.percentile(boot,[2.5,97.5]).tolist(),base_tails=[int((b>t).sum()) for t in [3,5,10]],arm_tails=[int((a>t).sum()) for t in [3,5,10]],base_peak=int(bf.max()),arm_peak=int(af.max()),base_p99=float(np.percentile(bf,99)),arm_p99=float(np.percentile(af,99)),filled=0,per_rep_arm=a.mean(0).tolist())
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--reps',type=int,default=3);p.add_argument('--pools',default='st2dev,st3');p.add_argument('--all',action='store_true');a=p.parse_args()
    sets=[[x] for x in ['st2dev','st3','st2conf','fconf','fdev','st1dev','st1conf']]+[['st2dev','st3']] if a.all else [a.pools.split(',')]
    results=[compare(a.name,s,a.reps) for s in sets]
    (H/f'tables/{a.name}_comparison_r{a.reps}.json').write_text(json.dumps(results,indent=1))
    print('| set (n) | GSLV | candidate | change | paired scene CI (m) | >3/5/10 GSLV → candidate | peak M GSLV/candidate | p99 M GSLV/candidate |')
    print('|---|---:|---:|---:|---|---|---|---|')
    for r in results:
        print(f"| {r['set']} ({r['n']}) | {r['base']:.4f} | {r['arm']:.4f} | {r['pct']:+.1f}% | [{r['ci'][0]:+.4f}, {r['ci'][1]:+.4f}] | {'/'.join(map(str,r['base_tails']))} → {'/'.join(map(str,r['arm_tails']))} | {r['base_peak']/1e6:.2f}/{r['arm_peak']/1e6:.2f} | {r['base_p99']/1e6:.2f}/{r['arm_p99']/1e6:.2f} |")
