"""python3 sc.py NAME [NAME...] [--pool v3val]  : score.py-style paired comparison vs gslvlj + regime / start-speed / tails"""
import sys,json,random,statistics as s,subprocess
a=[x for x in sys.argv[1:] if not x.startswith('--')];pool='v1val' if '--v1' in sys.argv else 'v3val'
E='/data/backups/rganapa/Sebastian/gen3/evals/'
BASE=next((x.split("=")[1] for x in sys.argv if x.startswith("--base=")),"gslvlj")
files=[E+f"{BASE}__{pool}.json"]+[E+(n if n.startswith(('gslvlj','net_')) else f'pr_{n}')+f'__{pool}.json' for n in a]
subprocess.run(['python3','/data/backups/rganapa/Sebastian/gen3/score.py']+files,cwd='/data/backups/rganapa/Sebastian/gen3')
def load(p): return {r['id']:r for r in json.load(open(p)) if r.get('ate') is not None}
R=[load(f) for f in files];ids=sorted(set.intersection(*[set(r) for r in R]))
def cat(r):
    if r['start']=='hover': return 'hover'
    v=r.get('start_fwd_speed') or 0
    return 'mid:back' if v<-0.2 else 'mid:side' if v<0.5 else 'mid:fwd'
print('%-28s'%'name',' '.join('%-16s'%k for k in ['benchmark','free-yaw','hover','mid:back','mid:side','mid:fwd','>3m','>5m','fails']))
for f,r in zip(files,R):
    rows=[r[i] for i in ids];out=[]
    for k in ['benchmark','free-yaw']:
        v=[x['ate'] for x in rows if x['regime']==k];out.append('%.3f(n=%d)'%(s.mean(v),len(v)) if v else '-')
    for k in ['hover','mid:back','mid:side','mid:fwd']:
        v=[x['ate'] for x in rows if cat(x)==k];out.append('%.3f(n=%d)'%(s.mean(v),len(v)) if v else '-')
    out+=[str(sum(x['ate']>3 for x in rows)),str(sum(x['ate']>5 for x in rows)),str(len(json.load(open(f)))-len(r))]
    print('%-28s'%f.split('/')[-1].split('__')[0],' '.join('%-16s'%o for o in out))
