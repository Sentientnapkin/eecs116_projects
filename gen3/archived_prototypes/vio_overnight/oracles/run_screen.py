import subprocess,sys,json
from pathlib import Path
G=Path('/data/backups/rganapa/Sebastian/gen3'); P=G/'research/i3'; V='/data/backups/rganapa/Sebastian/venv-teacher/bin/python'; POOL='/tmp/vio_overnight/oracles/pool24'; SRC='/tmp/vio_overnight/oracles/sn_or.c'; OUT=Path('/tmp/vio_overnight/oracles'); LOG=OUT/'screen.log'
BASE='PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0 SN=1 NS_GCOST=1 MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=4.0 AN_CEF=6 EDGE=1 EDGE_MYTH=10.0'
arms=[('control','OR=1'),('perfect02_ev10','OR=1 OR_VEL=0.02 OR_VEL_EV=10 OR_VEL_ON=1 OR_NK=0'),('iid01_ev10','OR=1 OR_VEL=0.1 OR_VEL_EV=10 OR_VEL_ON=1 OR_NK=1 OR_NT=0'),('corr01_tau2_ev10','OR=1 OR_VEL=0.1 OR_VEL_EV=10 OR_VEL_ON=1 OR_NK=1 OR_NT=1 OR_TAU=2.0'),('iid01_initial','OR=1 OR_VEL=0.1 OR_VEL_EV=1 OR_VEL_T1=0 OR_VEL_ON=1 OR_NK=1 OR_NT=0'),('iid01_first1s','OR=1 OR_VEL=0.1 OR_VEL_EV=1 OR_VEL_T1=20 OR_VEL_ON=1 OR_NK=1 OR_NT=0')]
def run(cmd):
 r=subprocess.run(cmd,text=True,capture_output=True)
 with LOG.open('a') as f: f.write('\n$ '+' '.join(cmd)+'\n'+r.stdout+r.stderr+'\n')
 if r.returncode: raise SystemExit(f'FAIL {cmd}: {r.stdout[-1000:]} {r.stderr[-2000:]}')
 print(r.stdout.strip(),flush=True)
def main():
 with LOG.open('w') as f: f.write('SN current anchor oracle screen\n')
 run([V,'-B',str(G/'evalpool.py'),'sn_anchor_screen',str(G/'agents/anchors/builds/snace6e1/solution.wasm'),POOL,'3'])
 for name,flags in arms:
  wasm=P/'builds'/('sn_or_'+name)/'solution.wasm'
  if not wasm.exists(): run([V,str(P/'tools/mk.py'),'sn_or_'+name,BASE+' '+flags,SRC])
  run([V,'-B',str(G/'evalpool.py'),'sn_or_'+name,str(wasm),POOL,'3'])
  if name=='control':
   import json
   a=json.load(open(G/'evals/sn_anchor_screen__pool24.json')); b=json.load(open(G/f'evals/sn_or_{name}__pool24.json'))
   ok=len(a)==len(b)==24 and all(x['id']==y['id'] and x['ate']==y['ate'] and x['err']==y['err'] for x,y in zip(a,b))
   if not ok: raise SystemExit('OR1 off failed exact per-flight identity; aborting armed screen')
   print('OR1_OFF_EXACT_IDENTITY 24/24',flush=True)
print('SCREEN_FINISHED',flush=True)
if __name__=='__main__': main()
