import re, pathlib, shutil, subprocess, sys, os
root=pathlib.Path('/data/backups/rganapa/Sebastian/gen3'); task=pathlib.Path('/tmp/vio_loop2/fuel'); bulk=pathlib.Path('/dev/shm/vio_loop2/fuel')
src=(root/'agents/anchors/base_sn.c').read_text()
# Inject entry/exit marks around major current-build work units; instrument whichever conditional definition is active.
pat=re.compile(r'static\s+[^;{}]*?\b(map_relocalize|msckf_update|build_pyramid|detect|track_all|vision)\s*\([^;{}]*?\)\s*\{')
ins=[]
for m in pat.finditer(src):
    name=m.group(1); start=m.end()-1; depth=1; i=m.end()
    while depth:
        if src[i]=='{': depth+=1
        elif src[i]=='}': depth-=1
        i+=1
    end=i-1
    idx={'map_relocalize':20,'msckf_update':30,'build_pyramid':40,'detect':50,'track_all':60,'vision':70}[name]
    ins.append((start+1, f' i1m({idx}); ')); ins.append((end, f' i1m({idx+1}); '))
for pos,text in sorted(ins,reverse=True): src=src[:pos]+text+src[pos:]
src='__attribute__((import_module("env"), import_name("mark"))) extern void i1m(int);\n'+src
out=bulk/'profile_src'; out.mkdir(parents=True,exist_ok=True); (out/'solution.c').write_text(src)
shutil.copy2('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/linejac/CMakeLists.txt',out/'CMakeLists.txt')
flags=(task/'control.flags').read_text().split(); cflags=' '.join('-D'+x for x in flags)
tc='/data/backups/rganapa/Sebastian/tmp/viobench-toolchain'; nat='/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native'
cmds=[['cmake','-S',str(out),'-B',str(bulk/'build/profile'),f'-DCMAKE_TOOLCHAIN_FILE={tc}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={nat}',f'-DCMAKE_C_FLAGS={cflags}'],['cmake','--build',str(bulk/'build/profile')]]
for c in cmds:
 p=subprocess.run(c,capture_output=True,text=True)
 if p.returncode: print(p.stdout[-2000:],p.stderr[-4000:]);sys.exit(p.returncode)
shutil.copy2(bulk/'build/profile/solution.wasm',bulk/'profile.wasm')
import hashlib
print('profile_wasm',hashlib.sha256((bulk/'profile.wasm').read_bytes()).hexdigest(),'markers',len(ins)//2,flush=True)
