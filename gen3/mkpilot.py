import json,random
K={"CRUISE_SPEED_MIN":3.0,"CRUISE_SPEED_MAX":4.5,"MAX_ACCELERATION":6.0,"MAX_JERK":30.0,"MAX_YAW_RATE":2.0,"ROADMAP_SPACING":1.0,"CONNECTION_DISTANCE":6.0}
K2={**K,"CRUISE_SPEED_MIN":4.0,"CRUISE_SPEED_MAX":6.0,"MAX_ACCELERATION":8.0,"MAX_JERK":40.0}
ST={'stock':{},'K':K,'K2':K2,'M':{**K,"CRUISE_SPEED_MIN":1.2,"CRUISE_SPEED_MAX":2.2,"MAX_ACCELERATION":3.0,"MAX_JERK":10.0}}
r=random.Random(1);F=[];n=8000000
for cls,sc,cat in(('warehouse','Warehouse','orig'),('forest','Forest','orig'),('room','ProcTHOR-Train-3','procthor-train')):
    for k in ST:
        for i in range(4):
            F.append(dict(id=f'p-{cls}-{k}-{i}',setting_class=cls,scene=sc,catalog=cat,setting=k,seed=n,seconds=60,hold_seconds=1.0,exposure_s=r.uniform(0,.05),blur_space=r.choice(['linear','srgb']),task_overrides=ST[k]));n+=1
json.dump({'flights':F},open('cfg/pilot.json','w'));print(len(F))
