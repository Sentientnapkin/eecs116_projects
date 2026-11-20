"""Replay recorded compile/link commands into fresh objects and compare wasm bytes.

Source and include paths stay identical to the frozen snapshot. Only output
object paths change; no existing build output is overwritten. Dependency/source
digests are verified first. This proves local byte reproducibility, not a clean
git checkout or portable rebuild on a different compiler.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args(); build=a.build.resolve()
    record=json.loads((build/'build.json').read_text())
    for name,digest in record['sources'].items():
        if sha(build/'source'/name)!=digest:raise ValueError(f'source changed: {name}')
    for path,digest in record['dependencies'].items():
        if sha(path)!=digest:raise ValueError(f'dependency changed: {path}')
    actual=sha(build/'composite.wasm')
    if actual!=record['wasm_sha256']:raise ValueError('original wasm changed')
    commands=[]
    with tempfile.TemporaryDirectory(dir='/dev/shm',prefix='fusion-rebuild-') as temp:
        temp=Path(temp); replacements={}
        for original in record['commands']:
            command=[replacements.get(str(s),str(s)) for s in original]
            index=command.index('-o')+1
            old=str(original[index]); dest=str(temp/Path(old).name)
            command[index]=dest; replacements[old]=dest
            commands.append(command)
            subprocess.run(command,cwd=build,check=True)
        rebuilt=sha(temp/'composite.wasm')
    report={'wasm_sha256':actual,'rebuild_wasm_sha256':rebuilt,
            'byte_reproducible_rebuild':actual==rebuilt,'pass':actual==rebuilt,
            'clean_checkout':False,'qualification':'Local frozen-source rebuild; checkout freeze not claimed',
            'compiler_sha256':sha(record['commands'][0][0]),'commands':commands}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='commands'},indent=2))
    if actual!=rebuilt:raise SystemExit(1)


if __name__=='__main__':main()
