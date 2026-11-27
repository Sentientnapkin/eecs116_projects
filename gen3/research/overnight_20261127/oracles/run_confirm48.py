import subprocess,json
from pathlib import Path
G=Path('/data/backups/rganapa/Sebastian/gen3'); P=G/'research/i3'; V='/data/backups/rganapa/Sebastian/venv-teacher/bin/python'; POOL='/tmp/vio_overnight/oracles/pool48'; SRC='/tmp/vio_overnight/oracles/sn_or.c'; OUT=Path('/tmp/vio_overnight/oracles'); LOG=OUT/'confirm48.log'
BASE='PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0 SN=1 NS_GCOST=1 MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=4.0 AN_CEF=6 EDGE=1 EDGE_MYTH=10.0'
items=[('sn_anchor_confirm48',None,True),('sn_or_control_confirm48','OR=1',False),('sn_or_perfect02_confirm48','OR=1 OR_VEL=0.02 OR_VEL_EV=10 OR_VEL_ON=1 OR_NK=0',False),('sn_or_iid01_confirm48','OR=1 OR_VEL=0.1 OR_VEL_EV=10 OR_VEL_ON=1 OR_NK=1 OR_NT=0',False)]
def run(cmd):
 r=subprocess.run(cmd,text=True,capture_output=True)
 with LOG.open('a') as f:f.write('\n$ '+' '.join(cmd)+'\n'+r.stdout+r.stderr+'\n')
 if r.returncode: raise SystemExit(f'FAIL {r.stdout[-1000:]} {r.stderr[-2000:]}')
 print(r.stdout.strip(),flush=True)
def main():
 LOG.write_text('48-flight oracle confirmations\n')
 for name,flags,anchor in items:
  if anchor: wasm=G/'agents/anchors/builds/snace6e1/solution.wasm'
  else:
   wasm=P/'builds'/name/'solution.wasm'
   if not wasm.exists():run([V,str(P/'tools/mk.py'),name,BASE+' '+flags,SRC])
  run([V,'-B',str(G/'evalpool.py'),name,str(wasm),POOL,'3'])
  if name=='sn_or_control_confirm48':
   a=json.load(open(G/'evals/sn_anchor_confirm48__pool48.json'));b=json.load(open(G/'evals/sn_or_control_confirm48__pool48.json'))
   ok=len(a)==len(b)==48 and all(x['id']==y['id'] and x['ate']==y['ate'] and x['err']==y['err'] for x,y in zip(a,b))
   if not ok:raise SystemExit('OR1-off failed exact 48/48 identity, aborting confirmation arms')
   print('OR1_OFF_EXACT_IDENTITY 48/48',flush=True)
 print('CONFIRM48_FINISHED',flush=True)
if __name__=='__main__':main()
