import json,glob,hashlib,sys
R='research/results/single_model/'
def L(n):
    d=json.load(open(glob.glob(R+n+'/eval/*/scores.json')[0])); return {r['episode']:r for r in d['rows']},glob.glob(R+n+'/eval/*/')[0]
def sh(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
def cmp(a,b):
    A,fa=L(a);B,fb=L(b);same=0;miss=0;ate=0;bad=[]
    for e in A:
        pa=glob.glob(fa+e+'/report/logs/*/estimate.tum');pb=glob.glob(fb+e+'/report/logs/*/estimate.tum')
        if not pa or not pb: miss+=1;continue
        if sh(pa[0])==sh(pb[0]): same+=1
        else: bad.append(e)
        ate+=A[e]['ate_full']==B[e]['ate_full']
    print(f'{a} vs {b}: n={len(A)}/{len(B)} estimate.tum identical {same}, missing {miss}, ate_full identical {ate}, differing {len(bad)}')
for a,b in [x.split(',') for x in sys.argv[1:]]: cmp(a,b)
