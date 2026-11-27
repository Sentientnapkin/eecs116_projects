"""Roster v4 = roster v3 + hover supplements (val/test: +100 warehouse, +50 forest hovers each) + more hovers in not-yet-generated
train warehouse/forest flights (targets 40% / 25%). Same ids for unchanged flights; generated flights untouched."""
import json,random,glob,collections as C
exec(open('mkroster3.py').read().split("\nrng=random.Random")[0])          # V, MIX, GAIN, rooms, outs, FREE
d=json.load(open('cfg/roster3.json'));F=d['flights']
done={p.split('/')[-1][:-5] for p in glob.glob('out/up/*.done')}|{p.split('/')[-1][:-5] for p in glob.glob('out/ep/*.json')}
rng=random.Random(20261128);seed=9500000;S=[]
def hover(split,cls,catg,scene,glb,variant):
    global seed
    reg='free-yaw' if rng.random()<FREE else 'benchmark';mx=MIX[reg][cls];st=rng.choices(list(mx),list(mx.values()))[0]
    f=dict(id=f's3v3{split[:2]}-{cls[:2]}-h{seed}',split=split,setting_class=cls,catalog=catg,scene=scene,scene_variant=variant,seed=seed,motion_style=st,task_overrides=V[st],regime=reg,
           start='hover',exposure_s=round(rng.uniform(0,.05),5),blur_space='linear' if rng.random()<.75 else 'srgb',gain=round(rng.uniform(*GAIN[cls]),3),roster_version=3,hover_supplement=True,seconds=60.0,hold_seconds=1.0)
    if glb: f['glb']=glb
    seed+=1;S.append(f)
for split in('val','test'):
    for kind,n in(('warehouse',100),('forest',50)):
        off,var=outs(kind,split)
        for i in range(n):
            if i%2==0: hover(split,kind,'orig',off[0][1],None,'official')
            else: v=var[(i//2)%len(var)];hover(split,kind,'variant',v[1],v[2],v[1])
target={'warehouse':.40,'forest':.25};conv=C.Counter()
for cls,t in target.items():
    T=[f for f in F if f['split']=='train' and f['setting_class']==cls];have=sum(f['start']=='hover' for f in T);need=int(t*len(T))-have
    cand=[f for f in T if f['start']!='hover' and f['id'] not in done];rng.shuffle(cand)
    for f in cand[:max(0,need)]:
        f['start']='hover';f['seconds']=60.0;f['hold_seconds']=1.0;f.pop('crop_start_s',None);f['hover_converted']=True;conv[cls]+=1
rng.shuffle(S);vt=[f for f in F if f['split']!='train'];tr=[f for f in F if f['split']=='train']
d['flights']=S+vt+tr;d['note']='v4 = v3 + hover supplements (val/test) + train hover share warehouse 40% forest 25%'
json.dump(d,open('cfg/roster4.json','w'));print('supplements',len(S),'converted train',dict(conv),'total',len(d['flights']))
built=set()
for p in('cfg/configs.json','cfg/configs2.json','cfg/configs3.json'):
    built|={(json.dumps(x['task_overrides'],sort_keys=True),x['hold_seconds'],x['regime']) for x in json.load(open(p))}
fy={json.dumps(V[s],sort_keys=True) for s in['K','A','C','D','H','EH','E','HE','DE','HL']}
built|={(o,.2,'free-yaw') for o in fy}
need={(json.dumps(f['task_overrides'],sort_keys=True),f['hold_seconds'],f['regime']) for f in d['flights']}-built
print('configs still to build',len(need))
