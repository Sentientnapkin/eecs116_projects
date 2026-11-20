"""Audit a packaged guest without turning unknown checks into passes.

Default release mode stops at the first failure/unknown of twelve required
checks. --smoke runs a narrower artifact audit, explicitly not release approval.
Optional --run-abi performs the official five-step check on the exact binary.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

EVALUATOR='9b1b07906aff5a3e6f00155e7aecf967d90aa960'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(package, smoke=False, run_abi=False):
    package=Path(package).resolve()
    manifest_path=package/'manifest.json'
    if not manifest_path.is_file():
        raise ValueError(f'Missing package manifest: {manifest_path}')
    m=json.loads(manifest_path.read_text())
    wasm=package/m.get('wasm_file','solution.wasm')
    current=sha(wasm)
    evidence=m.get('evidence',{})
    checks=[]
    required=['provenance_freeze','c_cpp_dependencies','official_abi','determinism',
      'causality','reset_reinit','mid_start','zero_filled','fuel','full_backend_parity',
      'standard_report_and_gates','package_integrity']

    def ev(key,bind=True):
        path=package/evidence[key] if key in evidence else None
        if path is None or not path.is_file():
            return None
        d=json.loads(path.read_text())
        if bind and d.get('wasm_sha256',d.get('sha256',d.get('guest',{}).get('sha256')))!=current:
            return None
        return d

    def result(name,passed,reason):
        checks.append({'check':name,'status':'not_checked' if passed is None else ('pass' if passed else 'fail'),
                       'reason':reason})
        return passed is True

    def integrity():
        errors=[]
        if wasm.read_bytes()[:8]!=b'\0asm\x01\0\0\0':
            errors.append('invalid wasm magic/version')
        if current!=m.get('wasm_sha256'):
            errors.append('wasm SHA differs from manifest')
        for relative,digest in m.get('files',{}).items():
            file=package/relative
            if not file.is_file() or sha(file)!=digest:
                errors.append('missing/changed file '+relative)
        if not m.get('files'):
            errors.append('no package file hashes')
        return not errors,('; '.join(errors) if errors else 'Exact binary and recorded package file hashes match')

    def cppdeps():
        b=json.loads((package/'build.json').read_text())
        commands=b.get('commands',[])
        compile_commands=[c for c in commands if '-c' in c]
        ok=bool(compile_commands) and all(any(str(x).endswith(('.cpp','.cc','.c','.cxx')) for x in c) for c in compile_commands)
        ok=ok and b.get('wasm_sha256')==current and bool(b.get('dependencies')) and bool(b.get('sources'))
        return ok,'C/C++ compile commands, source hashes and dependency hashes recorded for exact wasm' if ok else 'Missing or mismatched C/C++ build provenance'

    if run_abi:
        command=[sys.executable,'-m','viobench','check',str(wasm),'--frames','5']
        completed=subprocess.run(command,text=True,capture_output=True,env=os.environ.copy())
        (package/'abi-check.log').write_text(completed.stdout+completed.stderr)
        d={'wasm_sha256':current,'command':command,'returncode':completed.returncode,
           'pass':completed.returncode==0 and 'check: ok (5 steps)' in completed.stdout}
        (package/'abi_evidence.json').write_text(json.dumps(d,indent=2)+'\n')
        evidence['official_abi']='abi_evidence.json'
        # Evidence is included in a new manifest revision, without changing wasm.
        m['evidence']=evidence
        m['files']['abi-check.log']=sha(package/'abi-check.log')
        m['files']['abi_evidence.json']=sha(package/'abi_evidence.json')
        manifest_path.write_text(json.dumps(m,indent=2)+'\n')
    if smoke:
        ok,why=integrity(); result('package_integrity',ok,why)
        ok,why=cppdeps(); result('c_cpp_dependencies',ok,why)
        d=ev('official_abi')
        result('official_abi',bool(d.get('pass')) if d else None,'Exact-binary official five-step evidence' if d else 'Not run; use --run-abi')
        passed=all(c['status']=='pass' for c in checks if c['check']!='official_abi') and all(c['status']!='fail' for c in checks)
        return {'mode':'smoke','pass':passed,'release_pass':False,'checks':checks,
            'qualification':'Artifact smoke audit only; missing release checks remain unverified',
            'wasm_sha256':current,'checked_at':datetime.now(timezone.utc).isoformat()}

    halted=False
    for name in required:
        if halted:
            result(name,None,'Stopped after first unmet required check')
            continue
        passed=None; why='Required exact-binary evidence unavailable'
        if name=='provenance_freeze':
            d=ev('provenance_freeze')
            if d:
                passed=d.get('clean_checkout') is True and d.get('byte_reproducible_rebuild') is True
                why='Clean frozen checkout and byte-identical rebuild evidence' if passed else 'Checkout not clean/frozen or reproducible rebuild unverified'
        elif name=='c_cpp_dependencies':
            passed,why=cppdeps()
        elif name=='official_abi':
            d=ev('official_abi')
            if d: passed=d.get('pass') is True; why='Official five-step checker on exact packaged wasm'
        elif name in ('determinism','causality'):
            d=ev('future_poison')
            if d:
                rows=d.get('results',[])
                if name=='determinism':
                    passed=bool(rows) and all(r.get('checks',{}).get('repeat') is True for r in rows)
                    why='Fresh-process bitwise-repeat evidence'
                else:
                    fixtures={r.get('fixture') for r in rows}
                    prefixes={r.get('prefix_frames') for r in rows}
                    all_combinations=all(any(r.get('fixture')==f and r.get('prefix_frames')==k for r in rows) for f in fixtures for k in (600,1200))
                    has_mid=any('mid' in str(f).lower() for f in fixtures)
                    passed=(len(fixtures)>=3 and {600,1200}<=prefixes and all_combinations and has_mid and
                        all(r.get('checks',{}).get('prefix') is True and r.get('checks',{}).get('poison') is True for r in rows))
                    why='Requires 600/1200 prefixes and poisoned future on 3 fixtures including mid-start'
        elif name=='reset_reinit':
            d=ev(name)
            if d:
                passed=d.get('first_pose_identity') is True and d.get('init_twice_reproduces') is True
                why='Identity first pose and repeat init() evidence'
        elif name=='mid_start':
            d=ev(name)
            if d:
                passed=(d.get('static_flights',0)>=6 and d.get('mid_flights',0)>=6 and
                    d.get('all_finite') is True and d.get('exceptions',1)==0 and
                    d.get('max_speed_m_s',float('inf'))<=d.get('speed_bound_m_s',12))
                why='Requires 6 static+6 mid-start flights, finite output, zero exceptions and bounded speed'
        elif name in ('zero_filled','fuel'):
            d=ev('selected171_scores')
            if d:
                rows=d.get('rows',[])
                complete=len(rows)==171 and len({r.get('episode') for r in rows})==171
                if name=='zero_filled':
                    passed=complete and all(r.get('filled_full')==0 and r.get('ate_full') is not None for r in rows)
                    why='All 171 declared flights scored with zero evaluator-filled frames'
                else:
                    passed=complete and all(r.get('peak_fuel_per_frame') is not None and r['peak_fuel_per_frame']<1e10 for r in rows)
                    why='All 171 recorded peak fuel values below 1e10/frame'
        elif name=='full_backend_parity':
            d=ev(name)
            if d:
                passed=d.get('pass') is True and d.get('scope')=='full_composite' and d.get('n',0)>=10 and d.get('max_ate_relative_delta',float('inf'))<=.01
                why='Requires full-composite parity on 10 flights within 1%; selector-only parity is insufficient'
        elif name=='standard_report_and_gates':
            d=ev(name)
            if d:
                passed=(d.get('metric')=='mean_unaligned_ate_m' and {'selected171','clean','pool'}<=set(d.get('sets',{})) and
                    d.get('seeds')==[217,218,219] and d.get('gates_pass') is True and d.get('fresh_final_set_pass') is True)
                why='Standard reports, three seeds, declared gates, and fresh final confirmation required'
        elif name=='package_integrity':
            passed,why=integrity()
        if not result(name,passed,why):
            halted=True
    return {'mode':'release','pass':not halted,'release_pass':not halted,'checks':checks,
        'wasm_sha256':current,'checked_at':datetime.now(timezone.utc).isoformat(),
        'qualification':'User uploads; this tool never submits'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('package',type=Path)
    p.add_argument('--smoke',action='store_true')
    p.add_argument('--run-abi',action='store_true')
    a=p.parse_args()
    try:
        report=audit(a.package,a.smoke,a.run_abi)
    except Exception as exc:
        report={'mode':'smoke' if a.smoke else 'release','pass':False,'release_pass':False,
            'error':f'{type(exc).__name__}: {exc}','checks':[]}
    a.package.mkdir(parents=True,exist_ok=True)
    (a.package/('preflight-smoke.json' if a.smoke else 'preflight.json')).write_text(json.dumps(report,indent=2)+'\n')
    if (a.package/'manifest.json').is_file():
        files=[f for f in sorted(a.package.rglob('*')) if f.is_file() and f.name!='SHA256SUMS']
        (a.package/'SHA256SUMS').write_text(''.join(f'{sha(f)}  {f.relative_to(a.package)}\n' for f in files))
    print(json.dumps(report,indent=2))
    if not report['pass']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
