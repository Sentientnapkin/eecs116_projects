import glob,re,json,hashlib,sys,numpy as np
sys.path.insert(0,'.')
from research.single_model.run_variant import tags
R='research/results/single_model/'
fd=glob.glob(R+'preflight_c1_fbh_dbg/eval/*/')[0]; fa=glob.glob(R+'preflight_c1_fbh_a/eval/*/')[0]
tg=tags(); rows=[]; ident=0; nan=[]
def rd(f): return [l.split() for l in open(f).read().splitlines() if not l.startswith('#')]
for p in sorted(glob.glob(fd+'*/report/logs/*/stderr.txt')):
    e=p.split('/')[-5]; m=re.findall(r'FBD frame (\d+) tracked (\d+) fwdok (\d+) checked (\d+) dropped (\d+)',open(p).read())
    if re.search(r'\bnan\b|\binf\b',open(p).read().replace('FBD','').lower()): nan.append(e)
    fr,tr,fo,ch,dr=map(int,m[-1]); rows.append((e,tg[e]['start'],fr,tr,fo,ch,dr))
    ta=glob.glob(fa+e+'/report/logs/*/estimate.tum')[0]; td=glob.glob(fd+e+'/report/logs/*/estimate.tum')[0]
    ident+=hashlib.sha256(open(ta,'rb').read()).hexdigest()==hashlib.sha256(open(td,'rb').read()).hexdigest()
print('flights',len(rows),'final frame',set(r[2] for r in rows),'dbg estimate.tum identical to release build:',ident,'nan/inf in stderr:',nan)
a=np.array([[r[3],r[4],r[5],r[6]] for r in rows],float)
for st in('all','static','mid'):
    s=np.array([[r[3],r[4],r[5],r[6]] for r in rows if st=='all' or r[1]==st],float)
    fr_chk=s[:,3]/s[:,2]; fr_trk=s[:,3]/s[:,0]; fr_fwd=s[:,3]/s[:,1]
    print(st,len(s),'per-flight mean: dropped/checked %.4f (min %.4f max %.4f), dropped/forward-OK tracks %.4f, dropped/all-tracked %.4f, checked/forward-ok %.3f'%(fr_chk.mean(),fr_chk.min(),fr_chk.max(),fr_fwd.mean(),fr_trk.mean(),(s[:,2]/s[:,1]).mean()))
