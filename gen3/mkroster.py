import json,random,collections as C
R='/data/backups/rganapa/Sebastian/'
K={"CRUISE_SPEED_MIN":3.0,"CRUISE_SPEED_MAX":4.5,"MAX_ACCELERATION":6.0,"MAX_JERK":30.0,"MAX_YAW_RATE":2.0,"ROADMAP_SPACING":1.0,"CONNECTION_DISTANCE":6.0}
A={**K,"MAX_YAW_RATE":1.0,"MAX_JERK":80.0,"MAX_ACCELERATION":12.0};B={**A,"PHASE_ACCELERATION":1.0,"PHASE_JERK":6.0};Cc={**B,"TARGET_POSITION_ERROR_CLIP":2.5}
D={**Cc,"MAX_JERK":120.0,"MAX_ACCELERATION":15.0};G={**K,"MAX_YAW_RATE":1.0,"MAX_JERK":200.0,"MAX_ACCELERATION":20.0,"PHASE_ACCELERATION":2.0,"PHASE_JERK":10.0}
V={'K':K,'A':A,'B':B,'C':Cc,'D':D,'D5':{**D,"MAX_YAW_RATE":0.5},'E':{**Cc,"CRUISE_SPEED_MIN":2.0,"CRUISE_SPEED_MAX":3.0},'G5':{**G,"MAX_YAW_RATE":0.5}}
MIX={'room':{'D5':.25,'D':.15,'G5':.15,'B':.15,'A':.1,'K':.1,'E':.1},'warehouse':{'A':.25,'C':.2,'D5':.15,'K':.15,'E':.1,'G5':.15},'forest':{'K':.25,'A':.25,'E':.15,'C':.15,'D5':.1,'G5':.1}}
sp=json.load(open(R+'tmp/vf/scene_splits.json'));CRASH={'ProcTHOR-Train-121','ProcTHOR-Train-124','103997940_171031257'}
cat={'procthor':'procthor-train','hssd-train':'hssd-train','hssd-val':'hssd-val'}
rooms={s:sorted([(cat[k.split('|')[0]],k.split('|')[1]) for k,v in sp.items() if v==s and k.split('|')[1] not in CRASH]) for s in('train','val','test_v1')}
G3=R+'gen3/scenes/'
def outs(kind,split):
    off=[('orig',kind.capitalize(),None)]
    vs={'train':range(1,21),'val':range(21,23),'test':range(23,25)}[split]
    return off,[('variant',f'{kind}-{i:03d}',G3+f'{kind}-{i:03d}.glb') for i in vs]
rng=random.Random(20261125);seed=9000000;F=[]
def flight(split,cls,catg,scene,glb,variant=None):
    global seed
    st=rng.choices(list(MIX[cls]),list(MIX[cls].values()))[0];hover=rng.random()<.2;iy=(not hover) and rng.random()<.10
    f=dict(id=f's3{split[:2]}-{cls[:2]}-{seed}',split=split,setting_class=cls,catalog=catg,scene=scene,scene_variant=variant,seed=seed,motion_style=st,task_overrides=V[st],
           regime='independent-yaw' if iy else 'benchmark',start='hover' if hover else 'mid-flight',exposure_s=round(rng.uniform(0,.05),5),blur_space='linear' if rng.random()<.75 else 'srgb')
    if glb: f['glb']=glb
    if hover: f.update(seconds=60.0,hold_seconds=1.0)
    else: c=round(round(rng.uniform(3,30)/.05)*.05,2);f.update(seconds=round(60+c,2),hold_seconds=.2,crop_start_s=c)
    seed+=1;F.append(f)
N={'train':(5000,2500,2500),'val':(300,150,150),'test':(300,150,150)}
for split,(nr,nw,nf) in N.items():
    rs=rooms['test_v1' if split=='test' else split];c=C.Counter()
    for i in range(nr):
        s=min(rs,key=lambda s:(c[s],rng.random()));c[s]+=1;flight(split,'room',s[0],s[1],None)
    for kind,n in(('warehouse',nw),('forest',nf)):
        off,var=outs(kind,split);c=C.Counter()
        for i in range(n):
            if i%2==0: flight(split,kind,'orig',off[0][1],None,'official')
            else: v=min(var,key=lambda v:(c[v[1]],rng.random()));c[v[1]]+=1;flight(split,kind,'variant',v[1],v[2],v[1])
rng.shuffle(F)
# order: val/test first so evaluation sets exist early, then train
F.sort(key=lambda f:{'val':0,'test':0,'train':1}[f['split']])
json.dump({'flights':F,'styles':V,'mix':MIX},open('cfg/roster.json','w'))
print(len(F),C.Counter((f['split'],f['setting_class']) for f in F));print(C.Counter(f['motion_style'] for f in F),C.Counter(f['start'] for f in F),C.Counter(f['regime'] for f in F))
cfg={(json.dumps(f['task_overrides'],sort_keys=True),f['hold_seconds'],f['regime']) for f in F};print('configs',len(cfg))
json.dump([dict(task_overrides=json.loads(o),hold_seconds=h,regime=r) for o,h,r in sorted(cfg)],open('cfg/configs.json','w'))
