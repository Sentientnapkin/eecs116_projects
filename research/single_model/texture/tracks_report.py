import pickle,sys,numpy as np
r=pickle.load(open('research/results/single_model/texture_dbg/perflight.pkl','rb'))
S=[d for d in r.values() if d['slice']=='search']
def f(d,k,sl): x=d['c'][k][sl]; return float(np.mean(x)) if len(x) else np.nan
print('group n  ATE  alive(0-2s) long(0-2s) alive(all) long(all) acc/frame(all) kerr/fr ktex/fr koob/fr tri/fr chi/fr bright flat dark')
for lab,G in (('static',[d for d in S if d['start']=='static']),('mid',[d for d in S if d['start']=='mid']),
              ('mid bad>3m',[d for d in S if d['start']=='mid' and d['ate']>3]),('mid good',[d for d in S if d['start']=='mid' and d['ate']<=3]),
              ('static >1.2m',[d for d in S if d['start']=='static' and d['ate']>1.2]),
              ('dark(bright<60)',[d for d in S if np.mean(d['c']['bright'])<60]),('all',S)):
    if not G: continue
    m=lambda k,sl: np.mean([f(d,k,sl) for d in G])
    a,b=slice(0,40),slice(0,None)
    print(f"{lab:16s}{len(G):3d} {np.mean([d['ate'] for d in G]):5.2f} {m('alive',a):6.1f} {m('long',a):6.1f} {m('alive',b):6.1f} {m('long',b):6.1f}  {m('acc',b):5.1f} {m('kerr',b):5.1f} {m('ktex',b):5.1f} {m('koob',b):5.1f} {m('tri',b):5.1f} {m('chi',b):5.1f} {np.mean([np.mean(d['c']['bright']) for d in G]):6.1f} {np.mean([d['flat'] for d in G]):.2f} {np.mean([d['dark'] for d in G]):.2f}")
# starved flights
st=[(e,d) for e,d in r.items() if d['slice']=='search' and np.mean(d['c']['long'][:40])<6]
print('starved (mean long tracks <6 in first 2 s):',len(st),[ (e[-8:],d['start'],round(d['ate'],1)) for e,d in st])
ate=np.array([d['ate'] for d in S]); lo=np.array([np.mean(d['c']['long']) for d in S]); 
