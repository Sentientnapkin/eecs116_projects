import json
K={"CRUISE_SPEED_MIN":3.0,"CRUISE_SPEED_MAX":4.5,"MAX_ACCELERATION":6.0,"MAX_JERK":30.0,"MAX_YAW_RATE":2.0,"ROADMAP_SPACING":1.0,"CONNECTION_DISTANCE":6.0}
A={**K,"MAX_YAW_RATE":1.0,"MAX_JERK":80.0,"MAX_ACCELERATION":12.0};B={**A,"PHASE_ACCELERATION":1.0,"PHASE_JERK":6.0};C={**B,"TARGET_POSITION_ERROR_CLIP":2.5}
V={'K':K,'A':A,'B':B,'C':C,'D':{**C,"MAX_JERK":120.0,"MAX_ACCELERATION":15.0},'E':{**C,"CRUISE_SPEED_MIN":2.0,"CRUISE_SPEED_MAX":3.0},'F':{**C,"TARGET_POSITION_ERROR_CLIP":3.5,"TRACKING_MARGIN":.15},'G':{**K,"MAX_YAW_RATE":1.0,"MAX_JERK":200.0,"MAX_ACCELERATION":20.0,"PHASE_ACCELERATION":2.0,"PHASE_JERK":10.0}}
SC=[('room','ProcTHOR-Train-3','procthor-train'),('room','ProcTHOR-Train-17','procthor-train'),('room','103997478_171030528','hssd-train'),('warehouse','Warehouse','orig'),('forest','Forest','orig')]
F=[];s=8100000
for v,o in V.items():
    for c,sc,cat in SC:
        for i in range(2): F.append(dict(id=f'sw-{v}-{sc}-{i}',variant=v,setting_class=c,scene=sc,catalog=cat,seed=s,seconds=40,task_overrides=o));s+=1
import random;random.Random(0).shuffle(F);json.dump({'flights':F},open('cfg/sweep.json','w'));print(len(F))
