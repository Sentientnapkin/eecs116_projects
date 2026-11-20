from splice import *
import numpy as np
T={r['episode']:r for r in json.load(open('../fresh/table_mh_h0.json'))}
eps=sorted(T)[:3]
for ep in eps:
    Ea=est('h0',ep); Eb=est('h2',ep)
    print(ep,'ate h0 %.3f (tab %.3f) h2 %.3f'%(ate(ep,Ea),T[ep]['ate'],ate(ep,Eb)),'splice@60 %.3f'%ate(ep,splice(Ea,Eb,60)), 'splice@0', '%.3f'%ate(ep,splice(Ea,Eb,0)),Ea.shape, Ea[0,:7])
