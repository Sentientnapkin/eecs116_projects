import json,random
exec(open('mkroster2.py').read().split("\nMIX=")[0])
S2=lambda b,lo,hi:{**V[b],"CRUISE_SPEED_MIN":lo,"CRUISE_SPEED_MAX":hi}
V2={'HE':S2('H',2.0,3.0),'DE':S2('D',2.0,3.0),'AE':S2('A',2.0,3.0),'HL':S2('H',1.5,2.5)}
SC=[('room','ProcTHOR-Train-3','procthor-train'),('room','ProcTHOR-Train-17','procthor-train'),('room','103997478_171030528','hssd-train'),('room','ProcTHOR-Train-48','procthor-train')]
r=random.Random(6);F=[];B=[];s=8400000
for st,o in V2.items():
    B.append(dict(id=f'b-{st}',regime='free-yaw',scene='ProcTHOR-Train-3',catalog='procthor-train',seconds=60,hold_seconds=.2,task_overrides=o,build_only=1))
    for c,sc,cat in SC:
        for i in range(4):
            cs=round(r.uniform(3,20),2);F.append(dict(id=f'fy2-{st}-{sc}-{i}',style=st,regime='free-yaw',setting_class=c,scene=sc,catalog=cat,seed=s,seconds=round(48+cs,2),hold_seconds=.2,crop_start_s=cs,task_overrides=o,exposure_s=r.uniform(0,.05),blur_space='linear',gain=round(r.uniform(.55,1.1),3)));s+=1
r.shuffle(F);json.dump({'flights':F},open('cfg/fysweep2.json','w'));json.dump({'flights':B},open('cfg/fybuild2.json','w'));json.dump(V2,open('cfg/styles_v2extra.json','w'));print(len(F))
