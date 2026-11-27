import json,sys,time
sys.argv=['x'];import g3,viobench.tools.datasets.generate.simulation as S,hyperdrone
for i,c in enumerate(json.load(open('cfg/configs.json'))):
    t=time.time();g3.set_template(c['task_overrides']);kl=S.SimConfig
    if c['regime']=='independent-yaw':
        from robust_sim import IndependentYaw as kl
    sim=kl(instances=1,duration_seconds=60,hold_seconds=c['hold_seconds'],waypoints=48,fov=105.,fov_range=30.)
    h=sim.render_header(200.0);env=hyperdrone.HyperDrone([S.scene_references(['ProcTHOR-Train-3'])['ProcTHOR-Train-3']],config=hyperdrone.Config(num_worlds=1,spec_header=str(h)),seed=0,parameters={"cameras":{"camera0":{"fov":105.}}});env.close()
    print(i,round(time.time()-t),'s',flush=True)
print('PREBUILD DONE',flush=True)
