"""Per-flight gate decision from the GATE_DEBUG=1 build (rows: x=last disparity, y=released, z=pairs+1000*moving). Truth only for fold!=4."""
import sys,glob,json,collections; sys.path.insert(0,'.')
import numpy as np
from research.single_model.run_variant import tags,fold,slice_of
from research.guard_fusion import traj as T
D=glob.glob('research/results/single_model/preflight_gate_dbg/eval/*/')[0]
tg=tags();out={};conf=collections.Counter();flags=[];vis=[]
for e in sorted(tg):
    f=glob.glob(D+e+'/report/logs/*/estimate.tum')[0]
    a=np.loadtxt(f,comments='#')
    t=a[:,0]; d=a[:,1]; rel=a[:,2]; z=a[:,3]
    mv=(z[1:]>=1000).any(); pairs=np.where(z>=1000,z-1000,z)
    fr=np.arange(len(a))
    if not mv: dec,fd='imu-static(gate inactive)',None
    else:
        ri=np.where(rel[1:]==1)[0]; hi=np.where(pairs[1:]>=999)[0]
        if len(ri): dec,fd='released',int(ri[0]+1)
        elif len(hi): dec,fd='held',int(hi[0]+1)
        else: dec,fd='undecided',None
    fo=fold(tg[e]); st=tg[e]['start']
    r=dict(e=e,start=st,fold=fo,imu_moving=bool(mv),decision=dec,frame=fd,t=None if fd is None else float(t[fd]),maxd_to_dec=None if fd is None else float(np.nanmax(d[1:fd+1][d[1:fd+1]>=0])) if (d[1:fd+1]>=0).any() else None)
    if fo!=4:
        tt,g,_=T.load_truth(T.DEFAULT_RAW,e); v=np.linalg.norm(g[:,7:10],axis=1); r['v0']=float(v[tt<=tt[0]+0.45].mean() if False else v[:10].mean())
        vis.append(r)
    out[e]=r; conf[(st,dec)]+=1
print('frame index of decision (time) distribution:',collections.Counter((r['frame'],round(r['t'],3)) for r in out.values() if r['frame']))
print('confusion ALL 171 (start tag x decision):')
for k in sorted(conf): print(' ',k,conf[k])
print('\nflag: static flights with IMU moving but not released:',[ (r['e'],r['decision']) for r in out.values() if r['start']=='static' and r['imu_moving'] and r['decision']!='released'] or 'none')
print('static flights IMU-static (gate inactive):',sum(r['start']=='static' and not r['imu_moving'] for r in out.values()),'of',sum(r['start']=='static' for r in out.values()),'; static flights released by gate:',sum(r['start']=='static' and r['decision']=='released' for r in out.values()))
print('mid flights released (visible only, with true start speed):')
for r in vis:
    if r['start']=='mid' and r['decision']=='released': print('  %s fold%d frame %d t %.3f v0 %.2f maxd %.2f %s'%(r['e'],r['fold'],r['frame'],r['t'],r['v0'],r['maxd_to_dec'],'FLAG v0>0.5' if r['v0']>0.5 else ''))
print('mid released fold4 (count only):',sum(r['start']=='mid' and r['decision']=='released' and r['fold']==4 for r in out.values()))
print('mid IMU-static (visible) with v0:',[(r['e'],round(r['v0'],2)) for r in vis if r['start']=='mid' and not r['imu_moving']])
print('visible-only confusion:',sorted(collections.Counter((r['start'],r['decision']) for r in vis).items()))
print('mid visible by v0 bin x decision:')
for lo,hi in((0,.2),(.2,.5),(.5,1),(1,99)):
    c=collections.Counter(r['decision'] for r in vis if r['start']=='mid' and lo<=r['v0']<hi);print('  v0 %.1f-%.1f'%(lo,hi),dict(c))
print('static visible v0 max',max(r['v0'] for r in vis if r['start']=='static'))
json.dump(out,open('research/single_model/final/preflight_gate/gate_decisions.json','w'),indent=0)
