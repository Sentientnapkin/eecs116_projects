from pathlib import Path
import json,hashlib,sys
w=Path(__file__).resolve().parent;p=w/(sys.argv[1] if len(sys.argv)>1 else 'final/preflight')
passed=0
for g in range(3):
 d=json.loads((p/f'poison_{g}.json').read_text());assert len(d['results'])==246
 assert all(r['pass'] and all(r['checks'].values()) and not any(r['failures'].values()) for r in d['results'])
 passed+=len(d['results'])
reset=(p/'reset.txt').read_text();assert 'RESET PASS' in reset
rr=[json.loads(l) for l in reset.splitlines() if l.startswith('{')];assert len(rr)==8
assert 'exit 0' in (p/'abi_check.txt').read_text()
assert 'imports: []' in (p/'imports.txt').read_text()
s='ABI PASS; zero imports; poison/prefix/repeat '+str(passed)+'/738 PASS; reset 8/8 PASS.\n'
print(s);(p/'summary.txt').write_text(s)
