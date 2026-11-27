import sys; sys.path.insert(0,'tools'); import numpy as np; from fl import *
z=sys.argv[1]; f=Flight(z,41,frames=False)
ba,bg,sa,sg=f.oracle_biases(); print('ba',ba,'bg',bg,'resid sd',sa,sg)
g=f.gt_init(); print('v0',g['v0'],'g',g['g'])
for lab,kw in (('gyro_bgt',dict(bg=bg)),('gyro0',{}),('Rgt',dict(Rgt=True))):
  pi=f.preint(**kw)
  for k in (5,10,20,40):
    t=pi['dt'][k]; p=t*g['v0']+.5*t*t*g['g']+pi['al'][k]-pi['Bp'][k]@ba
    v=g['v0']+t*g['g']+pi['be'][k]-pi['Bv'][k]@ba
    rerr=np.degrees(np.linalg.norm(logm(pi['R'][k].T@g['Rrel'][k])))
    print(lab,k,'perr %.4f verr %.4f rot %.3fdeg |p| %.2f'%(np.linalg.norm(p-g['p'][k]),np.linalg.norm(v-g['v'][k]),rerr,np.linalg.norm(g['p'][k])))
