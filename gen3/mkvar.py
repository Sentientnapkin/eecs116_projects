import re,random,json,sys
O=sys.argv[1];out={}
def sub(t,k,v):
    t,n=re.subn(rf'(?m)^{k} = .*$',f'{k} = {v}',t);assert n==1,k;return t
for kind in('warehouse','forest'):
    src=open(f'{O}/{kind}/{kind}.py').read();open(f'scenes/{kind}-000.py','w').write(src);out[f'{kind}-000']={}
    for i in range(1,25):
        r=random.Random(f'{kind}{i}');c={'SEED':i}
        if kind=='warehouse':
            c.update(RACK_OCCUPANCY=round(r.uniform(.3,.95),2),LIGHT_INTENSITY=round(60*r.uniform(.6,1.5),1),AMBIENT=round(r.uniform(.2,.5),3))
        else:
            b=r.uniform(.75,1.2)
            c.update(MATURE_DENSITY=round(.05*r.uniform(.6,1.25),4),YOUNG_DENSITY=round(.14*r.uniform(.6,1.2),4),MIDSTOREY_COUNT=r.randint(50,120),SNAG_COUNT=r.randint(3,12),LOG_COUNT=r.randint(8,20),SCATTERED_ROCKS=r.randint(12,34),STUMP_COUNT=r.randint(8,22),
              AMBIENT=tuple(round(x*b*r.uniform(.96,1.04),3) for x in(1.05,1.08,1.12)))
        t=src
        for k,v in c.items(): t=sub(t,k,v)
        n=f'{kind}-{i:03d}';open(f'scenes/{n}.py','w').write(t);out[n]=c
json.dump(out,open('scenes/params.json','w'),indent=1)
