from pathlib import Path
import json,sys
w=Path(__file__).resolve().parent
for name in sys.argv[1:]:
 d=json.loads((w/'tables'/f'{name}_final.json').read_text());out={}
 for p in ('st2dev','st3','st2conf','fdev','fconf'):
  if p not in d:out[p]={'complete':False};continue
  r=d[p];rel=r['arm']/r['base']-1
  out[p]={'complete':True,'delta_percent':100*rel,'within_2pct':bool(rel<=.02),'CI_includes_zero':bool(r['ci'][0]<=0<=r['ci'][1]),'accuracy_pass':bool(rel<=.02 or r['ci'][0]<=0<=r['ci'][1]),'fuel_pass':bool(r['peak']<=4.5),'no_new_gt5_pass':not r['new5'],'new_gt5':r['new5']}
 passed=all(r.get('complete') and r['accuracy_pass'] and r['fuel_pass'] and r['no_new_gt5_pass'] for r in out.values())
 report={'name':name,'pass':passed,'sets':out};(w/'tables'/f'{name}_gates.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
