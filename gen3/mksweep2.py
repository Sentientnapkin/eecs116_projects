import json,random
K={"CRUISE_SPEED_MIN":3.0,"CRUISE_SPEED_MAX":4.5,"MAX_ACCELERATION":6.0,"MAX_JERK":30.0,"MAX_YAW_RATE":2.0,"ROADMAP_SPACING":1.0,"CONNECTION_DISTANCE":6.0}
C={**K,"MAX_YAW_RATE":1.0,"MAX_JERK":80.0,"MAX_ACCELERATION":12.0,"PHASE_ACCELERATION":1.0,"PHASE_JERK":6.0,"TARGET_POSITION_ERROR_CLIP":2.5};D={**C,"MAX_JERK":120.0,"MAX_ACCELERATION":15.0}
H={**D,"MAX_YAW_RATE":0.7,"MAX_JERK":200.0,"MAX_ACCELERATION":20.0,"PHASE_JERK":10.0,"PHASE_ACCELERATION":2.0}
V={'H':H,'H2':{**H,"TARGET_POSITION_ERROR_CLIP":3.5,"MAX_YAW_RATE":0.5},'EH':{**D,"CRUISE_SPEED_MIN":2.0,"CRUISE_SPEED_MAX":3.0,"MAX_YAW_RATE":0.7},'E3':{**D,"CRUISE_SPEED_MIN":1.6,"CRUISE_SPEED_MAX":2.6,"MAX_YAW_RATE":0.7,"MAX_JERK":200.0,"MAX_ACCELERATION":20.0}}
SC=[('room','ProcTHOR-Train-3','procthor-train'),('room','ProcTHOR-Train-17','procthor-train'),('room','103997478_171030528','hssd-train'),('warehouse','Warehouse','orig'),('forest','Forest','orig')]
F=[];s=8200000
for v,o in V.items():
    for c,sc,cat in SC:
        if v.startswith('E') and c=='room': continue
        if v.startswith('H') and c!='room': continue
        for i in range(4): F.append(dict(id=f'sw2-{v}-{sc}-{i}',variant=v,setting_class=c,scene=sc,catalog=cat,seed=s,seconds=40,task_overrides=o));s+=1
random.Random(0).shuffle(F);json.dump({'flights':F},open('cfg/sweep3.json','w'));print(len(F))
