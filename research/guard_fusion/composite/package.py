"""Package an already-built composite with immutable evidence; never submit it.

Packages remain experimental unless every separate release preflight is met.
A passed selector check alone is not full-guest parity or gate approval.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile

from ...preflight import audit

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE_SUFFIXES={'.cpp','.c','.cc','.cxx','.h','.hpp','.hh','.cmake','.txt','.patch','.json','.py','.md','.sh','.S'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):
            h.update(chunk)
    return h.hexdigest()


def source_archive(source,output):
    """Deterministic code snapshot; build objects/libraries are hash-recorded separately."""
    files=[f for f in sorted(source.rglob('*')) if f.is_file() and
           (f.suffix in SOURCE_SUFFIXES or f.name in ('CMakeLists.txt','Makefile'))]
    with output.open('wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as tar:
                for file in files:
                    data=file.read_bytes()
                    info=tarfile.TarInfo(str(file.relative_to(source)))
                    info.size=len(data); info.mode=0o644; info.mtime=0
                    tar.addfile(info,io.BytesIO(data))
    return {str(f.relative_to(source)):sha(f) for f in files}


def package(build,out,config=None,evidence=None):
    build=Path(build).resolve(); out=Path(out).resolve()
    meta=json.loads((build/'build.json').read_text())
    wasm=build/'composite.wasm'
    if sha(wasm)!=meta['wasm_sha256']:
        raise ValueError('Built wasm does not match build.json')
    if wasm.read_bytes()[:8]!=b'\0asm\x01\0\0\0':
        raise ValueError('Not wasm binary version1')
    if not meta.get('commands') or not meta.get('sources') or not meta.get('dependencies'):
        raise ValueError('Missing C++ build provenance')
    for relative,digest in meta['sources'].items():
        file=build/'source'/relative
        if not file.is_file() or sha(file)!=digest:
            raise ValueError('Source changed since build: '+relative)
    config=Path(config) if config else (build/'selector_config.json')
    if not config.is_file():
        raise ValueError('Pass --config for older builds without selector_config.json')
    cfg=json.loads(config.read_text())
    canonical=ROOT/'research/artifacts/n2-kfinputs-frozen/package/source-code-and-canonical-weights.tar.gz'
    if not canonical.is_file() or sha(canonical)!=meta.get('canonical_archive_sha256'):
        raise ValueError('Canonical weight archive missing or hash changed')
    with tarfile.open(canonical) as archive:
        for filename in ('weights.f32','model_config.h','counts.json'):
            expected=archive.extractfile('newest-cpp-source/canonical/'+filename).read()
            if not (build/filename).is_file() or (build/filename).read_bytes()!=expected:
                raise ValueError('Weight/model snapshot differs from recorded canonical archive: '+filename)
    if meta.get('selector_config') is not None and meta['selector_config']!=cfg['arm']:
        raise ValueError('Selected config differs from build config')
    out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(wasm,out/'solution.wasm')
    shutil.copy2(build/'build.json',out/'build.json')
    shutil.copy2(config,out/'selector_config.json')
    for filename in ('weights.f32','model_config.h','counts.json'):
        file=build/filename
        if file.is_file():
            shutil.copy2(file,out/filename)
    bundled_sources=source_archive(build/'source',out/'source.tar.gz')
    evidence_map={}
    if evidence:
        (out/'evidence').mkdir()
        for key,path in evidence.items():
            path=Path(path).resolve()
            if not key.replace('_','').isalnum():
                raise ValueError('Evidence key must contain only letters, numbers and underscores')
            # JSON evidence is copied exactly; the audit checks its binary SHA.
            json.loads(path.read_text())
            target=out/'evidence'/(key+'.json')
            shutil.copy2(path,target)
            evidence_map[key]=str(target.relative_to(out))
    git_head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
    git_status=subprocess.run(['git','status','--short'],cwd=ROOT,text=True,capture_output=True,check=True).stdout
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),
       'status':'experimental; G1 not passed; full release checks pending',
       'wasm_file':'solution.wasm','wasm_sha256':sha(out/'solution.wasm'),
       'inference_language':'C++17','evaluator_commit':'9b1b07906aff5a3e6f00155e7aecf967d90aa960',
       'selector':cfg['arm'],'n2_backend':meta.get('n2_backend'),
       'canonical_archive_sha256':meta.get('canonical_archive_sha256'),
       'build_directory':str(build),'git':{'head':git_head,'status':git_status,
           'clean_checkout':not bool(git_status),'byte_reproducible_rebuild':'not_checked'},
       'dependencies':meta['dependencies'],'source_bundle_files':bundled_sources,
       'qualification':'Code snapshot and dependency hashes supplied; external toolchain/static libraries required for rebuild. Selector-only parity does not establish full-backend parity. User uploads; no submission performed.',
       'evidence':evidence_map,
       'files':{str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file()}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    smoke=audit(out,smoke=True)
    release=audit(out)
    (out/'preflight-smoke.json').write_text(json.dumps(smoke,indent=2)+'\n')
    (out/'preflight.json').write_text(json.dumps(release,indent=2)+'\n')
    (out/'README.txt').write_text(
        'Experimental composite VIO guest, not submitted.\n'
        'solution.wasm is the C++ artifact for local testing; Sebastian controls any upload.\n'
        'Review manifest.json and preflight.json before use. Full G1 and release checks are not passed.\n'
        'The N2 component uses OpenCV4.12; it is a new backend with separate measured results.\n'
        'source.tar.gz contains source code, while dependency hashes refer to external build inputs.\n')
    allhashes={str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file()}
    (out/'SHA256SUMS').write_text(''.join(f'{digest}  {file}\n' for file,digest in allhashes.items()))
    return manifest,smoke,release


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--config',type=Path)
    p.add_argument('--evidence',action='append',default=[],metavar='KEY=JSON')
    p.add_argument('--zip',dest='archive',type=Path)
    a=p.parse_args()
    evidence={}
    for item in a.evidence:
        key,value=item.split('=',1); evidence[key]=Path(value)
    manifest,smoke,release=package(a.build,a.out,a.config,evidence)
    if a.archive:
        a.archive.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(a.archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for file in sorted(a.out.rglob('*')):
                if file.is_file():
                    info=zipfile.ZipInfo(str(file.relative_to(a.out)),date_time=(1980,1,1,0,0,0))
                    info.compress_type=zipfile.ZIP_DEFLATED
                    z.writestr(info,file.read_bytes())
    print(json.dumps({'package':str(a.out),'wasm_sha256':manifest['wasm_sha256'],
        'smoke_pass':smoke['pass'],'release_pass':release['release_pass'],
        'qualification':manifest['status']},indent=2))
    if not smoke['pass']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
