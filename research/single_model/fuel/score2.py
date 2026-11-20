import sys; sys.path.insert(0,'.')
from math import log
from score_calc import area
def brentq(f,a,b):
    for _ in range(80):
        m=(a+b)/2
        if f(a)*f(m)<=0: b=m
        else: a=m
    return (a+b)/2
A=[(113,5.09),(3.4e9,.475)]            # scenario A: identity-pose + VINS-Mono (OpenVINS/tiny_cnn/dead_reckoning dominated)
# scenario B: a hypothetical extra baseline (F,0.6) chosen so the server's claimed 2.71% at (20.9M,1.244) is reproduced
f=lambda F: area([(113,5.09),(F,0.6)],(20.9e6,1.244))[1]-2.71
F=brentq(f,3e7,2e10); B=[(113,5.09),(F,0.6)]
print('scenario B baseline fuel %.3g (reproduces 2.71%% claim)'%F)
pts=[('G as submitted (22.54M, 1.244)',(22.54e6,1.244)),('exact rewrite (11.97M, 1.244)',(11.97e6,1.244)),('exact + f32 KLT + det/2 (8.7M, 1.244)',(8.7e6,1.244)),
     ('exact + 20% ATE worse than 1.244 at 8.7M (1.49)',(8.7e6,1.49)),('30% fuel cut only (15.8M,1.244)',(15.8e6,1.244)),('10% ATE cut only (22.54M,1.12)',(22.54e6,1.12)),
     ('exact AND 10% ATE cut (11.97M,1.12)',(11.97e6,1.12))]
for lab,p in pts:
    print('%-52s A: %.3f%%   B: %.3f%%'%(lab,area(A,p)[1],area(B,p)[1]))
# marginals (d score / d ln fuel, d score / d ln ATE) at (22.54M,1.244) and at (12M,1.244)
import numpy as np
for nm,Bs in (('A',A),('B',B)):
    for f0 in (22.54e6,12e6):
        e=1e-4
        s0=area(Bs,(f0,1.244))[1]
        df=(area(Bs,(f0*(1-e),1.244))[1]-s0)/e; da=(area(Bs,(f0,1.244*(1-e)))[1]-s0)/e
        print(nm,'at %.1fM,1.244 m: +%.3f score per 1x ln-unit(100%%) fuel cut; +%.3f per 100%% ATE cut => 30%% fuel cut = %.3f pt, 10%% ATE cut = %.3f pt; 30%% fuel == %.1f%% ATE'%(f0/1e6,df,da,df*(-np.log(0.7)),da*(-np.log(0.9)),100*(1-np.exp(-df*(-np.log(0.7))/da))))
