"""Linux WASI parity of the deployed displacement path; fuel per complete call."""
import argparse,json,subprocess,tempfile,sys
from pathlib import Path
import numpy as np
import torch
import wasmtime
from models import load
from data import validation
from train import prepare
HERE=Path(__file__).resolve().parent;WASI=Path('/data/backups/rganapa/Sebastian/tmp/viobench-toolchain/wasi-sdk')
def main():
 a=argparse.ArgumentParser();a.add_argument('--ckpt',required=True);a.add_argument('--weights',required=True);a.add_argument('--n',type=int,default=24);a.add_argument('--out',required=True);a=a.parse_args();torch.set_num_threads(1)
 m,ck=load(a.ckpt);val=validation(a.n,seed=7303);ims,Hs,aux,tgt=val[:4]
 with torch.no_grad():
  im,ma,ax,_=prepare(ims,Hs,aux,tgt,'cpu',False);ref=m(im,ma,ax).numpy()
 tmp=Path(tempfile.mkdtemp(prefix='stlearn_parity_'));wasm=tmp/'parity.wasm';w=Path(a.weights).resolve()
 subprocess.run([str(WASI/'bin/clang'),'--target=wasm32-wasip1',f'--sysroot={WASI}/share/wasi-sysroot','-O3','-msimd128','-Wl,--initial-memory=67108864',f'-I{w.parent}',f'-I{HERE}',str(HERE/'parity_main.c'),'-lm','-o',str(wasm)],check=True)
 cfg=wasmtime.Config();cfg.consume_fuel=True;eng=wasmtime.Engine(cfg);module=wasmtime.Module.from_file(eng,str(wasm));outs=[];warped=[];fuel=[]
 for i in range(a.n):
  with (tmp/'in.bin').open('wb') as f:f.write(ims[i].numpy().astype('uint8').tobytes());f.write(Hs[i].numpy().astype('float64').tobytes());f.write(aux[i].numpy().astype('float32').tobytes())
  store=wasmtime.Store(eng);store.set_fuel(100_000_000_000);wc=wasmtime.WasiConfig();wc.preopen_dir(str(tmp),'.');store.set_wasi(wc);linker=wasmtime.Linker(eng);linker.define_wasi();inst=linker.instantiate(store,module)
  try:inst.exports(store)['_start'](store)
  except wasmtime.ExitTrap as e:assert e.code==0
  raw=np.fromfile(tmp/'out.bin','float32');outs.append(raw[:12]);warped.append(raw[12:].reshape(2,2,96,128));fuel.append(100_000_000_000-store.get_fuel())
 out=np.stack(outs);warped=np.stack(warped);diff=np.abs(out-ref);r=dict(model=ck.get('name'),n=a.n,output_max_abs=float(diff.max()),output_mean_abs=float(diff.mean()),warp_max_abs=float(np.abs(warped[:,:,0]-im[:,1:].numpy()).max()),mask_mismatches=int((warped[:,:,1]!=ma[:,1:].numpy()).sum()),fuel_per_call_max=max(fuel),fuel_per_call_mean=float(np.mean(fuel)),frames_for_20M_net_only=int(np.ceil(max(fuel)/20e6)),frames_for_5M_net_budget=int(np.ceil(max(fuel)/5e6)),passed=bool(diff.max()<=1e-5),scope='12 deployed displacement mean/Laplace outputs; auxiliary velocity head is offline only')
 Path(a.out).write_text(json.dumps(r,indent=2));print(json.dumps(r),flush=True)
 if not r['passed']:raise SystemExit('C parity target failed')
if __name__=='__main__':main()
