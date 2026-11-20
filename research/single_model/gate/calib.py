"""Per-flight disparity series (from the gate_dbg build) + truth start speed. Search slice only (folds 0-2) unless --val."""
import sys, glob, json; sys.path.insert(0,'.')
import numpy as np
from research.guard_fusion import traj as T
from research.single_model.run_variant import *
def series(name, slices=('search',)):
    tg=tags(); D=glob.glob(str(OUT/f'{name}/eval/{name}-*'))[0]; rows=[]
    for e in sorted(tg):
        f=fold(tg[e])
        if slice_of(f) not in slices: continue
        t,g,_=T.load_truth(T.DEFAULT_RAW,e)
        a=np.loadtxt(glob.glob(f'{D}/{e}/report/logs/*/estimate.tum')[0],comments='#')
        d=a[:,1]; idx=[i for i in range(1,len(d)) if d[i]>=0 and (i<2 or d[i]!=d[i-1] or True)]
        # one value per clone pair: sample at frames 4,8,...,(<=60)
        pair=[(i,d[i]) for i in range(4,64,4) if i<len(d)]
        sp=np.linalg.norm(g[:,7:10],axis=1)
        rows.append(dict(e=e,start=tg[e]['start'],sl=slice_of(f),d=[float(x) for _,x in pair],
                         sp0=float(sp[0]),sp05=float(sp[:10].mean()),sp1=float(sp[:20].mean()),
                         spk=[float(sp[max(i-4,0):i+1].mean()) for i,_ in pair]))
    return rows
if __name__=='__main__':
    rows=series(sys.argv[1], ('search','val') if '--val' in sys.argv else ('search',))
    json.dump(rows,open(sys.argv[2],'w'))
    for st in ('static','mid'):
        R=[r for r in rows if r['start']==st]; print(st,len(R))
        for k in range(8):
            v=np.array([r['d'][k] for r in R if len(r['d'])>k and r['d'][k]>=0]); 
            if len(v): print(f' pair {k+1} (t~{0.045+0.2*(k+1):.2f}) n={len(v)} d pct 0/10/50/90/100:',np.percentile(v,[0,10,50,90,100]).round(2))
        print(' sp0.5 pct',np.percentile([r['sp05'] for r in R],[0,10,50,90,100]).round(2))
