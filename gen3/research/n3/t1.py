import sys,os
sys.argv=['sim.py','src/ins_N.c','NET_SIG=0.44 PSTAT=1']
os.environ['PS']='1'
import importlib.util
spec=importlib.util.spec_from_file_location('sim','sim.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
so=m.build('src/ins_N.c','NET_SIG=0.44 PSTAT=1')
import glob
fl=sorted(glob.glob('/data/backups/rganapa/Sebastian/gen3/research/e1/cache/*.npz'))[:3]
for f in fl: print(m.run((so,f)))
