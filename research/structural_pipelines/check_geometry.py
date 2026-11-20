"""Compile/run sensor-geometry contracts against the exact built source snapshot."""
import argparse
import json
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__); p.add_argument('build',type=Path); a=p.parse_args()
record=json.loads((a.build/'build.json').read_text())['variants']['combined']
command=record['commands'][0]
source=Path(__file__).resolve().with_name('test_geometry.cpp')
command=[str(source) if arg.endswith('/source/guest.cpp') else arg for arg in command]
command=[arg for arg in command if arg not in ('-shared','-fPIC')]
command.insert(1,f'-I{a.build.resolve()}/source')
command[-1]=str(a.build.resolve()/'geometry_test')
subprocess.run(command,check=True)
result=subprocess.run([command[-1]],check=True,text=True,capture_output=True)
print(result.stdout,end='')
(a.build/'geometry.json').write_text(json.dumps({'passed':True,'output':result.stdout,'command':command},indent=2)+'\n')
