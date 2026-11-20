import sys,json,numpy as np
sys.path.insert(0,'.')
from research.single_model.run_variant import OUT
def load(n): return {x['e']:x for x in json.loads((OUT/f'{n}/report.json').read_text())['rows_visible']}
a=load(sys.argv[1]); b=load(sys.argv[2])
d=[(b[e]['new']-a[e]['new'],e,a[e]['new'],b[e]['new']) for e in a if b[e]['fold'] in (0,1,2)]
d.sort()
print('n flights',len(d),'|d|<1e-3:',sum(abs(x[0])<1e-3 for x in d),' <0.02:',sum(abs(x[0])<0.02 for x in d))
for x in d[:6]+d[-6:]: print('%+.3f %s %.3f -> %.3f'%x)
