import json,sys,re,glob,numpy as np,os
R='/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/'
F='/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/fresh/'
tf={d['episode']:d for d in json.load(open(F+'truth_feats.json'))}
def T(n): return {r['episode']:r for r in json.load(open((F if not n.startswith('mh_') else '/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/multihyp/tables/')+f'table_{n}.json'))}
def feats(name,ep):
    d=glob.glob(R+f'fresh_mh_{name}/eval/*/{ep}/report/logs/*/stderr.txt')
    if not d: return None
    M=[]
    for l in open(d[0]):
        if l.startswith('M '):
            p=dict(x.split('=') for x in l.split()[1:]); M.append([float(p[k]) for k in('nis','nisk','nisn','pn','pk','fs','fn')])
    return np.array(M)
def D(name,ep):
    d=glob.glob(R+f'fresh_mh_{name}/eval/*/{ep}/report/logs/*/stderr.txt')
    out=[]
    for l in open(d[0]):
        if l.startswith('D '):
            p=dict(x.split('=') for x in l.split()[1:]); out.append([float(p[k]) for k in('att','gate','used','Pv')])
    return np.array(out)

def flightfeats(name,ep,Tw):
    M=feats(name,ep); Dd=D(name,ep)
    n=int(Tw*20); M=M[:n]; Dd=Dd[:n]
    f={}
    f['nis']=M[:,0].sum()/max(M[:,1].sum(),1)
    f['fchi']=M[:,5].sum()/max(M[:,6].sum(),1)
    f['pri']=M[:,3].sum()/max(M[:,4].sum(),1)
    f['acc']=Dd[:,2].sum()/max(Dd[:,0].sum(),1)
    f['rej']=Dd[:,1].sum()/max(Dd[:,0].sum(),1)
    f['Pv']=Dd[-1,3]
    return f
