import os,sys,json
from pathlib import Path
sys.path.insert(0,'/tmp/vio_overnight/gpu')
import context_train as T
T.EPOCHS=200
Base=T.L.AblNet
T.L.AblNet=lambda cin,nvec,npts=0: Base(cin,nvec,npts,chs=(32,48,64,96))
T.main()
for p in T.OUT.rglob('result.json'):
 d=json.loads(p.read_text());d['architecture_channels']=[32,48,64,96];d['epochs']=200;d['purpose']='Matched capacity-by-context teacher diagnostic; no downstream ATE or WASM inference claim';p.write_text(json.dumps(d,indent=2)+'\n')
