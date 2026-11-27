"""python3 fuel.py NAME [NAME...] [--pool=v3val]: pooled per-frame fuel over the keep flights: peak, p99, p95, mean (M)."""
import sys,glob,numpy as np
pool=next((x.split('=')[1] for x in sys.argv if x.startswith('--pool=')),'v3val')
keep=set(open(f'/data/backups/rganapa/Sebastian/gen3/agents/anchors/pools/{pool}.keep').read().split())
for n in [x for x in sys.argv[1:] if not x.startswith('--')]:
    fs=[];mx=[]
    for spec in n.split('+'):
        for f in glob.glob(f'/data/backups/rganapa/Sebastian/gen3/evals/an_{spec}/{pool}/an_{spec}-*/*/report/logs/*/fuel.npy'):
            if f.split('/')[-5] in keep: a=np.load(f).ravel();fs.append(a);mx.append(a.max())
    a=np.concatenate(fs);print('%-24s flights %d peak %.2fM p99 %.2fM p95 %.2fM mean %.2fM flight-peak median %.2fM'%(n,len(fs),a.max()/1e6,np.percentile(a,99)/1e6,np.percentile(a,95)/1e6,a.mean()/1e6,np.median(mx)/1e6))
