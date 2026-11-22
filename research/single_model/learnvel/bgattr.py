import re, glob, sys, numpy as np
f=glob.glob(f'../../results/single_model/lv_{sys.argv[1]}/one/*/*/report/logs/*/stderr.txt')[0]
t0,t1=float(sys.argv[2]),float(sys.argv[3])
prev=None; net=False; att=0; acc={'net':np.zeros(3),'vis':np.zeros(3),'none':np.zeros(3)}; rows=[]
for l in open(f):
    if l.startswith('LC apply'): net=True
    m=re.match(r'D f=(\d+) .*att=(\d+)',l)
    if m: att=int(m.group(2))
    m=re.match(r'E f=(\d+) .*bg=([-\d.]+),([-\d.]+),([-\d.]+)',l)
    if m:
        fr=int(m.group(1)); bg=np.array([float(m.group(i)) for i in (2,3,4)])
        if prev is not None and t0<=fr*0.05<=t1:
            d=bg-prev; k='net' if net else ('vis' if att>0 else 'none'); acc[k]+=d
            if np.abs(d).max()>0.002: rows.append((fr*0.05,k,att,d))
        prev=bg; net=False
for k,v in acc.items(): print(k,'sum dbg',np.round(v,4))
for r in rows[:40]: print('t %.2f %s att %d dbg %s'%(r[0],r[1],r[2],np.round(r[3],4)))
