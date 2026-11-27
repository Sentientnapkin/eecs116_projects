import json,random,collections as C
exec(open('mkroster.py').read().split("MIX=")[0])          # K,A,B,Cc,D,G,V and paths
H={**D,"MAX_YAW_RATE":0.7,"MAX_JERK":200.0,"MAX_ACCELERATION":20.0,"PHASE_JERK":10.0,"PHASE_ACCELERATION":2.0}
V.update({'H':H,'H2':{**H,"TARGET_POSITION_ERROR_CLIP":3.5,"MAX_YAW_RATE":0.5},'EH':{**D,"CRUISE_SPEED_MIN":2.0,"CRUISE_SPEED_MAX":3.0,"MAX_YAW_RATE":0.7}})
MIX={'room':{'H':.35,'D':.15,'H2':.15,'G5':.1,'B':.1,'A':.05,'K':.05,'E':.05},'warehouse':{'EH':.3,'C':.2,'D5':.15,'G5':.1,'A':.1,'K':.1,'E':.05},'forest':{'EH':.35,'K':.15,'E':.1,'D5':.1,'C':.1,'A':.1,'G5':.1}}
G3=R+'gen3/scenes/'
def outs(kind,split):
    vs={'train':range(1,21),'val':range(21,23),'test':range(23,25)}[split]
    return [('orig',kind.capitalize(),None)],[('variant',f'{kind}-{i:03d}',G3+f'{kind}-{i:03d}.glb') for i in vs]
GAIN={'room':(.55,1.1),'warehouse':(.8,1.2),'forest':(1.15,1.8)}
old=json.load(open('cfg/roster.json'));done={p.split('/')[-1][:-5] for p in __import__('glob').glob('out/up/s3*.done')}
keep=[f for f in old['flights'] if f['split']!='train']
sp=json.load(open(R+'tmp/vf/scene_splits.json'));CRASH={'ProcTHOR-Train-121','ProcTHOR-Train-124','103997940_171031257','104348361_171513414','ProcTHOR-Train-89'}
cat={'procthor':'procthor-train','hssd-train':'hssd-train','hssd-val':'hssd-val'}
rooms=sorted([(cat[k.split('|')[0]],k.split('|')[1]) for k,v in sp.items() if v=='train' and k.split('|')[1] not in CRASH])
rng=random.Random(20261126);seed=9100000;T=[]
ntr=10000-sum(1 for f in old['flights'] if f['split']=='train' and f['id'] in done)
def flight(cls,catg,scene,glb,variant):
    global seed
    st=rng.choices(list(MIX[cls]),list(MIX[cls].values()))[0];hover=rng.random()<.2;iy=(not hover) and rng.random()<.25
    f=dict(id=f's3tr-{cls[:2]}-{seed}',split='train',setting_class=cls,catalog=catg,scene=scene,scene_variant=variant,seed=seed,motion_style=st,task_overrides=V[st],
           regime='independent-yaw' if iy else 'benchmark',start='hover' if hover else 'mid-flight',exposure_s=round(rng.uniform(0,.05),5),blur_space='linear' if rng.random()<.75 else 'srgb',gain=round(rng.uniform(*GAIN[cls]),3),roster_version=2)
    if glb: f['glb']=glb
    if hover: f.update(seconds=60.0,hold_seconds=1.0)
    else: c=round(round(rng.uniform(3,30)/.05)*.05,2);f.update(seconds=round(60+c,2),hold_seconds=.2,crop_start_s=c)
    seed+=1;T.append(f)
nr=ntr//2;nw=(ntr-nr)//2;nf=ntr-nr-nw;c=C.Counter()
for i in range(nr): s=min(rooms,key=lambda s:(c[s],rng.random()));c[s]+=1;flight('room',s[0],s[1],None,None)
for kind,n in(('warehouse',nw),('forest',nf)):
    off,var=outs(kind,'train');c=C.Counter()
    for i in range(n):
        if i%2==0: flight(kind,'orig',off[0][1],None,'official')
        else: v=min(var,key=lambda v:(c[v[1]],rng.random()));c[v[1]]+=1;flight(kind,'variant',v[1],v[2],v[1])
rng.shuffle(T);F=keep+T
json.dump({'flights':F,'styles':V,'mix':MIX,'gain':GAIN,'note':'val/test from roster v1; train regenerated (v2) after the motion sweep'},open('cfg/roster2.json','w'))
print('train new',len(T),'kept old-train done',10000-ntr,'val/test',len(keep),C.Counter(f['motion_style'] for f in T),C.Counter(f['regime'] for f in T))
prev={(json.dumps(x['task_overrides'],sort_keys=True),x['hold_seconds'],x['regime']) for x in json.load(open('cfg/configs.json'))}
cfg={(json.dumps(f['task_overrides'],sort_keys=True),f['hold_seconds'],f['regime']) for f in F}-prev
json.dump([dict(task_overrides=json.loads(o),hold_seconds=h,regime=r) for o,h,r in sorted(cfg)],open('cfg/configs2.json','w'));print('new configs',len(cfg))
