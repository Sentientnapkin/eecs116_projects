"""python3 lcstat.py NAME [POOL]: net landings per flight (LC apply lines in stderr of an LC_DEBUG build), latency, |innov| rms"""
import sys,glob,re,statistics as s
n=sys.argv[1];pool=sys.argv[2] if len(sys.argv)>2 else 's60'
cnt=[];lat=[];r2=[];fr=[]
for f in glob.glob(f'/data/backups/rganapa/Sebastian/gen3/evals/an_{n}/{pool}/an_{n}-*/*/report/logs/*/stderr.txt'):
    L=[l for l in open(f) if l.startswith('LC apply')];cnt.append(len(L))
    nf=sum(1 for _ in open(f.replace('stderr.txt','estimate.tum')));fr.append(nf)
    for l in L:
        w=l.split();lat.append(int(w[3] if w[2]=='frame' else w[3]))
        i=w.index('r') if 'r' in w else w.index('(x')-4
        if 'r' in w: v=[float(x) for x in w[i+1:i+4]]
        else: v=[float(x) for x in w[w.index('innov_b')+1:w.index('innov_b')+4]]
        r2.append(sum(x*x for x in v)/3)
print('%-12s flights %d landings/flight %.1f (frames/flight %.0f -> every %.1f frames) latency mean %.1f max %d  innov rms %.2f med %.2f'%(n,len(cnt),s.mean(cnt),s.mean(fr),s.mean(fr)/max(1e-9,s.mean(cnt)),s.mean(lat),max(lat),s.mean(r2)**.5,s.median(r2)**.5))
