import json,glob,sys,collections
sys.path.insert(0,'.')
from research.single_model.run_variant import tags,fold
R='research/results/single_model/'; tg=tags()
d=glob.glob(R+(sys.argv[1] if len(sys.argv)>1 else 'preflight_c1_dbg')+'/eval/*/')[0]
out={}
for e in tg:
    p=glob.glob(d+e+'/report/logs/*/estimate.tum')
    if not p: continue
    v=[float(x) for x in open(p[0]).read().strip().splitlines()[-1].split()[1:4]]
    x,y,z=int(round(v[0])),int(round(v[1]))+1,int(round(v[2]))
    out[e]=dict(start=tg[e]['start'],fold=fold(tg[e]),n_active=x%10000,runmax=x//10000,off_frame=y%10000-1,
                reason={0:'none',1:'time(>1.0s)',2:'gyro>0.12',3:'|f|-g>1'}[(y//10000)%100],first=y//1000000-1,moving=z%10,last=z//10-1)
# off_frame decoding: off=-1 encoded as -1+10000*reason -> handled below
for e,o in out.items():
    pass
json.dump({e:o for e,o in out.items() if o['fold']!=4},open('research/single_model/final/preflight_c1/hold_audit_flights_'+(sys.argv[1] if len(sys.argv)>1 else 'preflight_c1_dbg')+'.json','w'),indent=0)
print('flights',len(out))
conf=collections.Counter((o['start'],'moving' if o['moving'] else 'hover') for o in out.values()); print('confusion start label vs detector:',dict(conf))
act=[o for o in out.values() if o['n_active']>0]
print('hold activated on',len(act),'flights; by start label',dict(collections.Counter(o['start'] for o in act)))
print('flights with moving=0 (hold eligible):',sum(1 for o in out.values() if not o['moving']),'; of which hold never activated:',sum(1 for o in out.values() if not o['moving'] and o['n_active']==0))
print('active frame count histogram (eligible):',sorted(collections.Counter(o['n_active'] for o in out.values() if not o['moving']).items()))
print('first active frame:',sorted(collections.Counter(o['first'] for o in act).items()),' last active frame:',sorted(collections.Counter(o['last'] for o in act).items()))
print('switch-off reason/frame (eligible):',sorted(collections.Counter((o['reason'],o['off_frame']) for o in out.values() if not o['moving']).items()))
mid=[o for o in out.values() if o['start']=='mid']
print('MID-start flights:',len(mid),'detector moving',sum(o['moving'] for o in mid),'hold-eligible (moving=0)',sum(1 for o in mid if not o['moving']),'with any active frame',sum(o['n_active']>0 for o in mid),'max consecutive active frames on any mid flight',max(o['runmax'] for o in mid))
st=[o for o in out.values() if o['start']=='static']
print('STATIC flights:',len(st),'detector says moving',sum(o['moving'] for o in st),'hold active',sum(o['n_active']>0 for o in st),'max run',max(o['runmax'] for o in st))
print('static flights switched off before time limit (gyro/force reason):',sum(1 for o in st if o['reason'] in('gyro>0.12','|f|-g>1')))
for e,o in sorted(out.items()):
    if o['fold']==4: continue
    if o['start']=='static' and (o['moving'] or o['reason'] in('gyro>0.12','|f|-g>1') or o['n_active']!=13) or o['start']=='mid' and not o['moving']:
        print('  note',e,o)
