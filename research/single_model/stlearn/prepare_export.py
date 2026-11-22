"""Synthetic shape/parity check before spending days on the student ladder."""
import json,sys,subprocess
from pathlib import Path
import torch
from models import Motion,CONFIGS
HERE=Path(__file__).resolve().parent
for name in ['S100','S25','S6','S2']:
 p=HERE/'work/shape_checks'/name;p.mkdir(parents=True,exist_ok=True);m=Motion(CONFIGS[name]);torch.save(dict(model=m.state_dict(),config=m.cfg,name=name),(p/'shape.pt'))
 subprocess.run([sys.executable,str(HERE/'export_c.py'),'--ckpt',str(p/'shape.pt'),'--out',str(p/'dt_weights.h')],check=True)
 subprocess.run([sys.executable,str(HERE/'parity.py'),'--ckpt',str(p/'shape.pt'),'--weights',str(p/'dt_weights.h'),'--n','4','--out',str(p/'parity.json')],check=True)
print('ALL SHAPE/PARITY CHECKS PASS (untrained; not candidates)',flush=True)
