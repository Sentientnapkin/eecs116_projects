import json,random
exec(open('mkroster2.py').read().split("\nMIX=")[0])   # V incl. H,H2,EH
SC=[('room','ProcTHOR-Train-3','procthor-train'),('room','ProcTHOR-Train-17','procthor-train'),('room','103997478_171030528','hssd-train'),('room','106366410_174226806','hssd-train'),('warehouse','Warehouse','orig'),('forest','Forest','orig')]
GAIN={'room':(.55,1.1),'warehouse':(.8,1.2),'forest':(1.15,1.8)}
r=random.Random(5);F=[];B=[];s=8300000
for st in ['K','A','C','D','H','EH','E']:
    B.append(dict(id=f'b-{st}',regime='free-yaw',scene='ProcTHOR-Train-3',catalog='procthor-train',seconds=60,hold_seconds=.2,task_overrides=V[st],build_only=1))
    for c,sc,cat in SC:
        for i in range(3):
            cs=round(r.uniform(3,20),2);F.append(dict(id=f'fy-{st}-{sc}-{i}',style=st,regime='free-yaw',setting_class=c,scene=sc,catalog=cat,seed=s,seconds=round(48+cs,2),hold_seconds=.2,crop_start_s=cs,task_overrides=V[st],exposure_s=r.uniform(0,.05),blur_space='linear',gain=round(r.uniform(*GAIN[c]),3)));s+=1
r.shuffle(F);json.dump({'flights':F},open('cfg/fysweep.json','w'));json.dump({'flights':B},open('cfg/fybuild.json','w'));print(len(F),len(B))
