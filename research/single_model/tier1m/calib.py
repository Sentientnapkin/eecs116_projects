"""calib.py TAG: regress per-frame fuel on governor counters (PV marks 16-19,38,39,43-45) for a GOV profile run"""
import numpy as np, glob, sys
F=[np.load(f) for f in sorted(glob.glob('../../results/single_model/t1m_prof_%s/*.npz'%sys.argv[1]))]
V=np.concatenate([z['vals'][1:] for z in F]); T=np.concatenate([z['tot'][1:] for z in F]); C=np.concatenate([z['cnt'][1:] for z in F])
X=np.stack([np.ones(len(T)), V[:,19], V[:,38], V[:,44], V[:,16], V[:,45], (V[:,39]>0).astype(float), V[:,18], V[:,17]],1)
names=['fixed','prior','pyr(vis)','klt call','cell','row','batch','map','unit']
b,*_=np.linalg.lstsq(X,T,rcond=None)
pred=X@b; r=T-pred
print('coef (k):', ', '.join('%s %.1f'%(n,c/1e3) for n,c in zip(names,b)))
print('resid sd %.0fk, max over %.0fk; gov pred (mark43) mean %.0fk vs actual %.0fk; actual peak %.2fM'%(r.std()/1e3, r.max()/1e3, V[:,43].mean(), T.mean()/1e3, T.max()/1e6))
print('rows/frame %.2f, frames with batch %.2f, units/frame %.2f, cells/frame %.2f'%(V[:,45].mean(), (V[:,39]>0).mean(), V[:,17].mean(), V[:,16].mean()))
