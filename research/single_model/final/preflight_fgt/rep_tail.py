import json,glob,sys
sys.path.insert(0,'.')
from research.single_model.run_variant import slice_of
R='research/results/single_model/'
def load(n): return {x['e']:x for x in json.loads((__import__('pathlib').Path(R+n+'/report.json')).read_text())['rows_visible']}
for nm in ('tails_ref','tails_comb2','fgt_rep'):
    for i in range(3):
        d=load(f'{nm}_r{i}'); print(nm,i,'>5m:',[(e.split('-',1)[1] if '-' in e else e,round(r['new'],1)) for e,r in d.items() if r['new']>5 and slice_of(r['fold'])!='sealed'])
