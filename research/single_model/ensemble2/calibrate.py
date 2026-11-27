"""Calibrate deterministic work estimates from development-only Wasmtime traces.

Primary cost uses mean work by job shape. Secondary reservations use the maximum
observed work by shape. Real total fuel and lag are subsequently checked on replay;
these empirical estimates are not a hard real-time bound on unseen inputs.
"""
from pathlib import Path
import glob,json
import numpy as np
HERE=Path(__file__).resolve().parent

def main():
    fs=sorted(glob.glob(str(HERE/'replays/shared_bulk_prof/st2dev/*.npz')))
    jobs=np.concatenate([np.load(f)['jobs'] for f in fs]);out=[];meta=[]
    for job in range(1,22):
        s=jobs[(jobs[:,1]==0)&(jobs[:,2]==job)]
        if not len(s):continue
        for key in sorted(set(map(tuple,s[:,3:6]))):
            v=s[np.all(s[:,3:6]==key,axis=1),6];a,b,c=map(int,key)
            packed=(job<<24)+(a<<16)+(b<<8)+c
            mean=int(np.ceil(v.mean()));bound=int(v.max()*1.02+300)
            out.append((packed,mean,bound));meta.append(dict(job=job,a=a,b=b,c=c,n=len(v),mean=mean,bound=bound))
    # Primary FE prediction uses recorded call/cell counts at function exit.
    text='/* Generated from 24 development flights, never holdout. */\n'
    text+='static const struct {unsigned key;int mean,bound;} ens_models[]={\n'
    text+=''.join('{%du,%d,%d},\n'%row for row in sorted(out))+'};\n'
    (HERE/'models.h').write_text(text)
    (HERE/'calibration.json').write_text(json.dumps(dict(flights=len(fs),jobs=meta),indent=2)+'\n')
    print('calibrated',len(out),'job shapes from',len(fs),'flights')

if __name__=='__main__':main()
