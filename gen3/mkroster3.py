"""Roster v3: free-yaw majority (65%), per-class style mixes from the free-yaw sweeps, all splits regenerated."""
import json,random,glob,collections as C
exec(open('mkroster2.py').read().split("\nMIX=")[0])
S2=lambda b,lo,hi:{**V[b],"CRUISE_SPEED_MIN":lo,"CRUISE_SPEED_MAX":hi}
V.update({'HE':S2('H',2.0,3.0),'DE':S2('D',2.0,3.0),'HL':S2('H',1.5,2.5)})
MIX={'free-yaw':{'room':{'HE':.3,'DE':.3,'HL':.15,'A':.1,'D':.15},'warehouse':{'EH':.25,'E':.15,'K':.15,'DE':.2,'D':.15,'C':.1},'forest':{'EH':.4,'E':.2,'K':.15,'DE':.1,'C':.15}},
     'benchmark':{'room':{'H':.4,'D':.25,'B':.15,'G5':.2},'warehouse':{'EH':.3,'C':.25,'D5':.25,'K':.2},'forest':{'EH':.4,'K':.25,'C':.2,'D5':.15}}}
GAIN={'room':(.55,1.1),'warehouse':(.8,1.2),'forest':(1.15,1.8)};FREE=.65;HOVER=.2
sp=json.load(open(R+'tmp/vf/scene_splits.json'));CRASH={'ProcTHOR-Train-121','ProcTHOR-Train-124','103997940_171031257','104348361_171513414','ProcTHOR-Train-89'}
cat={'procthor':'procthor-train','hssd-train':'hssd-train','hssd-val':'hssd-val'}
rooms={s:sorted([(cat[k.split('|')[0]],k.split('|')[1]) for k,v in sp.items() if v==s and k.split('|')[1] not in CRASH]) for s in('train','val','test_v1')}
G3=R+'gen3/scenes/'
def outs(kind,split):
    vs={'train':range(1,21),'val':range(21,23),'test':range(23,25)}[split]
    return [('orig',kind.capitalize(),None)],[('variant',f'{kind}-{i:03d}',G3+f'{kind}-{i:03d}.glb') for i in vs]
rng=random.Random(20261127);seed=9300000;F=[]
def flight(split,cls,catg,scene,glb,variant):
    global seed
    reg='free-yaw' if rng.random()<FREE else 'benchmark';mx=MIX[reg][cls];st=rng.choices(list(mx),list(mx.values()))[0];hover=rng.random()<HOVER
    f=dict(id=f's3v3{split[:2]}-{cls[:2]}-{seed}',split=split,setting_class=cls,catalog=catg,scene=scene,scene_variant=variant,seed=seed,motion_style=st,task_overrides=V[st],regime=reg,
           start='hover' if hover else 'mid-flight',exposure_s=round(rng.uniform(0,.05),5),blur_space='linear' if rng.random()<.75 else 'srgb',gain=round(rng.uniform(*GAIN[cls]),3),roster_version=3)
    if glb: f['glb']=glb
    if hover: f.update(seconds=60.0,hold_seconds=1.0)
    else: c=round(round(rng.uniform(3,30)/.05)*.05,2);f.update(seconds=round(60+c,2),hold_seconds=.2,crop_start_s=c)
    seed+=1;F.append(f)
for split,(nr,nw,nf) in {'val':(300,150,150),'test':(300,150,150),'train':(5000,2500,2500)}.items():
    rs=rooms['test_v1' if split=='test' else split];c=C.Counter()
    for i in range(nr): s=min(rs,key=lambda s:(c[s],rng.random()));c[s]+=1;flight(split,'room',s[0],s[1],None,None)
    for kind,n in(('warehouse',nw),('forest',nf)):
        off,var=outs(kind,split);c=C.Counter()
        for i in range(n):
            if i%2==0: flight(split,kind,'orig',off[0][1],None,'official')
            else: v=min(var,key=lambda v:(c[v[1]],rng.random()));c[v[1]]+=1;flight(split,kind,'variant',v[1],v[2],v[1])
vt=[f for f in F if f['split']!='train'];tr=[f for f in F if f['split']=='train'];rng.shuffle(vt);rng.shuffle(tr);F=vt+tr
json.dump({'flights':F,'styles':V,'mix':MIX,'gain':GAIN,'free_yaw_fraction':FREE,'hover_fraction':HOVER,'free_yaw_params':{'offset':'U(0,2pi)','amplitude_rad':'U(0.2,1.2)','omega_rad_s':'U(0.2,0.9)','phase':'U(0,2pi)'}},open('cfg/roster3.json','w'))
print(len(F),C.Counter((f['split'],f['setting_class']) for f in F));print(C.Counter(f['regime'] for f in F),C.Counter(f['start'] for f in F));print(C.Counter(f['motion_style'] for f in F))
built=set()
for p in('cfg/configs.json','cfg/configs2.json'):
    built|={(json.dumps(x['task_overrides'],sort_keys=True),x['hold_seconds'],x['regime']) for x in json.load(open(p))}
for p in('fybuild.jsonl','fybuild2.jsonl'):
    pass
fy={json.dumps(V[s],sort_keys=True) for s in['K','A','C','D','H','EH','E','HE','DE','HL']}|{json.dumps(S2('A',2.0,3.0),sort_keys=True)}
built|={(o,.2,'free-yaw') for o in fy}
need={(json.dumps(f['task_overrides'],sort_keys=True),f['hold_seconds'],f['regime']) for f in F}-built
json.dump([dict(task_overrides=json.loads(o),hold_seconds=h,regime=r,scene='ProcTHOR-Train-3',catalog='procthor-train',seconds=60,build_only=1,id=f'b{i}') for i,(o,h,r) in enumerate(sorted(need))],open('cfg/configs3.json','w'));print('configs to build',len(need))
