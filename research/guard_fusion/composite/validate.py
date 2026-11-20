"""Compare the compiled streaming selector with the frozen safe Python rule.

This checks selector arithmetic on saved source outputs, independently of the
OpenCV 4.12 composite backend and without claiming full-guest parity.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np

from ..guards import GuardConfig, replay
from ..traj import DEFAULT_RAW, DEFAULT_SELECTED, list_episodes, load_episode

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selected',type=Path,default=DEFAULT_SELECTED)
    p.add_argument('--raw',type=Path,default=DEFAULT_RAW)
    p.add_argument('--config',type=Path,default=HERE.parent/'selected_config_safe.json')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=24)
    a=p.parse_args()
    cfg=GuardConfig(**json.loads(a.config.read_text())['arm'])
    with tempfile.TemporaryDirectory(dir='/dev/shm',prefix='guard-selector-') as temp:
        temp=Path(temp)
        wrapper=temp/'wrapper.cpp'
        wrapper.write_text('''#include "selector.hpp"
extern "C" void replay_selector(int n,const double *t,const double *x,const unsigned char *ready,double *out) {
    fusion::Selector s;
    for(int k=0;k<n;++k) {
        bool r[3]; for(int j=0;j<3;++j) r[j]=ready[k*3+j];
        s.step(t[k],reinterpret_cast<const double (*)[13]>(x+k*39),r,out+k*13);
    }
}
''')
        subprocess.run(['c++','-std=c++17','-O3','-ffp-contract=off','-shared','-fPIC',
                        f'-DFUSION_AGREEMENT_ABS={cfg.agreement_abs}',f'-DFUSION_AGREEMENT_REL={cfg.agreement_rel}',
                        '-I'+str(HERE),str(wrapper),'-o',str(temp/'selector.so')],check=True)
        lib=ctypes.CDLL(str(temp/'selector.so'))
        fn=lib.replay_selector
        ptr=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        fn.argtypes=[ctypes.c_int,ptr,ptr,np.ctypeslib.ndpointer(dtype=np.uint8,flags='C_CONTIGUOUS'),ptr]
        def one(episode):
            e=load_episode(a.selected,a.raw,episode)
            names=('vins','openvins','n2'); t=np.ascontiguousarray(e['t'])
            states=np.ascontiguousarray(np.stack([e['sources'][s]['raw_states'] for s in names],axis=1))
            ready=np.ones((len(t),3),dtype=np.uint8)
            for j,s in enumerate(names[:2]):
                init=e['sources'][s]['init_s']
                ready[:,j]=False if init is None else t>=init-1e-6
            out=np.empty((len(t),13),dtype=np.float64)
            fn(len(t),t,states,ready,out)
            reference=replay(t,e['sources'],cfg)
            delta=float(np.max(np.abs(out[:,:3]-reference[:,:3,3])))
            return {'episode':episode,'max_position_delta_m':delta,'pass':delta<1e-9}
        with ThreadPoolExecutor(a.workers) as pool:
            rows=list(pool.map(one,list_episodes(a.selected)))
    report={'scope':'C++ selector vs Python on saved sources; not full composite parity',
            'config':cfg.to_dict(),'n':len(rows),'max_position_delta_m':max(r['max_position_delta_m'] for r in rows),
            'pass':all(r['pass'] for r in rows),'rows':rows}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
    if not report['pass']: raise SystemExit(1)


if __name__=='__main__':main()
