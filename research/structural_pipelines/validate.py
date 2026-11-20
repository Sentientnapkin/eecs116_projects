"""Synthetic ABI/reset/prefix checks; no benchmark episodes or truth trajectories are read."""
import argparse
import ctypes as ct
import json
from pathlib import Path
import tempfile
import cv2
import numpy as np
from viobench.tools.abi.config import default_guest_config
from viobench.tools.runner.sandbox import Sandbox
from viobench.tools.runner.engine import Engine


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('build',type=Path); p.add_argument('--frames',type=int,default=70); a=p.parse_args()
    build=a.build.resolve(); meta=json.loads((build/'build.json').read_text())
    camera=default_guest_config(); camera.update(fx=160.,fy=160.,cx=159.5,cy=119.5)
    camera['T_cam_imu']=np.eye(4).tolist(); camera['T_cam_imu'][0][3]=.08
    engine=Engine(); rows={}; traces={}; states={}
    # Render two horizontal line families in a room, camera up is -Y.
    image=np.zeros((240,320,3),np.uint8)
    def project(p):
        x,y,z=p; return (int(round(160*x/z+159.5)),int(round(160*y/z+119.5)))
    for y in (-1.5,1.5):
        for z in np.linspace(2.5,9,10): cv2.line(image,project((-4,y,z)),project((4,y,z)),(200,200,200),1)
        for x in np.linspace(-4,4,13): cv2.line(image,project((x,y,2.5)),project((x,y,10)),(200,200,200),1)
    def inputs(i):
        t=10.045+i*.05
        packet=np.zeros((10,7)); packet[:,0]=t-.05+np.arange(1,11)*.005
        packet[:,2]=-9.81
        # After room anchoring, introduce a small gyro bias, preserving image evidence.
        if i>=36: packet[:,5]=.025
        return t,image,packet
    for name,record in meta['variants'].items():
        outputs=[]; peak=0; host=ct.CDLL(str(build/name/'host.so'))
        array=np.ctypeslib.ndpointer
        host.host_weights.argtypes=[array(np.float32,flags='C_CONTIGUOUS')]
        weights=np.fromfile(build/name/'weights.f32',dtype='<f4'); host.host_weights(weights)
        host.init.argtypes=[ct.c_char_p,ct.c_uint32]
        host.step.argtypes=[ct.c_double,array(np.uint8,flags='C_CONTIGUOUS'),array(np.float64,flags='C_CONTIGUOUS'),ct.c_int,array(np.float64,flags='C_CONTIGUOUS')]
        config=json.dumps(camera).encode(); assert host.init(config,len(config))==0
        with tempfile.TemporaryDirectory() as log:
            guest=Sandbox(Path(record['wasm']),engine=engine,log_dir=log); guest.init(camera)
            max_host_delta=0
            for i in range(a.frames):
                t,rgb,packet=inputs(i); result=guest.step(t,rgb,packet)
                values=np.r_[result.pose,result.twist]
                assert np.isfinite(values).all() and abs(np.linalg.norm(values[3:7])-1)<1e-9
                if i==0: np.testing.assert_array_equal(values[:7],[0,0,0,0,0,0,1])
                outputs.append(values); peak=max(peak,result.fuel)
                native=np.empty(13); assert host.step(t,rgb,packet,len(packet),native)==0
                max_host_delta=max(max_host_delta,float(np.max(np.abs(native-values))))
            if name!='control':
                # Read state from the same scored binary via its exported function.
                store=guest.store; exports=guest.instance.exports(store)
                ptr=exports['alloc'](store,64)
                exports['structure_state'](store,ptr)
                state=np.frombuffer(exports['memory'].read(store,ptr,ptr+64),dtype='<f8').copy()
                states[name]=state.tolist()
                if name in ('manhattan','combined'):
                    assert state[0]==1, f'{name}: gravity never qualified'
                    assert state[1]==1 and state[4]>0, f'{name}: structural frontend never activated: {state}'
        # New instance with a shorter stream: must match its emitted prefix exactly.
        with tempfile.TemporaryDirectory() as log:
            short=Sandbox(Path(record['wasm']),engine=engine,log_dir=log); short.init(camera)
            for i in range(min(45,a.frames)):
                result=short.step(*inputs(i))
                np.testing.assert_array_equal(np.r_[result.pose,result.twist],outputs[i])
        # Same native instance reset must discard every structural state and reproduce first output.
        assert host.init(config,len(config))==0
        reset=np.empty(13); assert host.step(*inputs(0),10,reset)==0
        np.testing.assert_array_equal(reset,outputs[0])
        assert max_host_delta<=.002, f'{name}: synthetic native/Wasm discrepancy exceeds 2 mm'
        traces[name]=np.array(outputs)
        rows[name]={'frames':a.frames,'finite':True,'identity_origin':True,'reset':True,'prefix_exact':True,
                    'synthetic_peak_fuel':peak,'native_wasm_max_component_delta':max_host_delta}
        print(name,rows[name],states.get(name),flush=True)
    assert meta['variants']['control']['sha256']=='8b05b203adc1f045b67df12399ee6b9e0caf28015b7d31678f5378968e2d60cf'
    # Without translational parallax the direction-only variant must leave the control path unchanged (up to roundtrip FP).
    np.testing.assert_allclose(traces['direction'],traces['control'],atol=1e-12,rtol=0)
    report={'guest_sha256':{n:r['sha256'] for n,r in meta['variants'].items()},'status':'synthetic validation passed; dataset scoring not run','checks':rows,'structure_state':states,
            'state_fields':['gravity_ready','anchored','yaw','support','yaw_updates','direction_updates','direction_valid','direction_angle'],
            'control_rebuild_byte_identical':True,'limitations':['Synthetic fuel is not whole-dataset peak fuel.','Existing frozen visual-backend parity limitation remains.']}
    (build/'validation.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__': main()
