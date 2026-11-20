"""Build an isolated experimental three-way C++ guest against ONE OpenCV 4.12.

This is a new backend, not the frozen OpenCV 5.1 N2 binary. Its measured N2 and
composite scores must be reported independently. Reuses SHA-recorded upstream
static libraries from the isolated VIO builds; never changes their sources.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNTIME = Path('/dev/shm/sebastian-vio/viobench/viobench/solution')
SDK = RUNTIME / 'build/toolchain/wasi-sdk/bin/clang++'
PIN = RUNTIME / 'examples/native'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def renamed(text, prefix):
    text = re.sub(r'VIOBENCH_EXPORT\(\w+\)\s*', '', text)
    # Only global ABI definitions; estimator methods named init/step stay intact.
    pattern = r'(?m)^((?:extern "C" )?(?:int32_t|void\s*\*)\s*)(abi_version|alloc|frame_width|init|step)(\s*\()'
    return re.sub(pattern, lambda m: m[1] + prefix + '_' + m[2] + m[3], text)


def declarations(prefix):
    return '\n'.join(f'extern "C" {signature};' for signature in (
        f'int32_t {prefix}_abi_version()', f'void *{prefix}_alloc(uint32_t)',
        f'int32_t {prefix}_frame_width()', f'int32_t {prefix}_init(const char*,uint32_t)',
        f'int32_t {prefix}_step(double,const uint8_t*,const double*,int32_t,double*)'))


def flags(build):
    result = []
    for line in (build/'CMakeFiles/solution.dir/flags.make').read_text().splitlines():
        if line.startswith(('CXX_DEFINES = ', 'CXX_INCLUDES = ')):
            result += shlex.split(line.split(' = ', 1)[1])
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--config', type=Path, default=HERE.parent/'selected_config_safe.json')
    p.add_argument('--vins-build', type=Path, default=Path('/dev/shm/sebastian-vio/guard-fixes/vins_mono/build'))
    p.add_argument('--ov-build', type=Path, default=Path('/dev/shm/sebastian-vio/guard-fixes/openvins/build'))
    a = p.parse_args()
    config = json.loads(a.config.read_text())['arm']
    if (config['mode'] != 'absolute' or config['agreement_space'] != 'position'
            or config['referee'] != 'position' or config['blend'] != .5
            or config['smooth_s'] != .5 or config['max_speed'] != 12.
            or config['max_accel'] != 100. or config['fallback_abs'] != 6.
            or config['fallback_rel'] != 1. or not config['check_init']
            or not config['name'].endswith('-safe')):
        raise ValueError('Selector port supports only the validated absolute safe consensus family')
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    src = out/'source'; src.mkdir()
    shutil.copy2(a.config, out/'selector_config.json')
    native = RUNTIME/'runtime/native'
    commands = []

    def run(cmd):
        commands.append(list(map(str, cmd)))
        subprocess.run(list(map(str,cmd)), cwd=out, check=True)

    objects = []
    for name, prefix, build, ready in (
        ('vins_mono', 'vins', a.vins_build, 'state.output_ready'),
        ('openvins', 'ovsub', a.ov_build, 'chain_state.anchored')):
        dest = src/name
        shutil.copytree(PIN/name, dest)
        file = dest/'solution.cpp'
        text = renamed(file.read_text(), prefix)
        if name == 'vins_mono':
            old = 'if (state.estimator) throw std::runtime_error("init called twice");'
            if old not in text:
                raise ValueError('Pinned VINS init reset context changed')
            text = text.replace(old, 'state = State{}; // full episode reset, including tracker and gauge', 1)
        text = '#include <cstdint>\n' + declarations(prefix) + '\n' + text
        text += f'\nextern "C" int {prefix}_ready() {{ return {ready}; }}\n'
        file.write_text(text)
        obj = out/(prefix+'.o')
        run([SDK, '-O2', '-DNDEBUG', '-std=c++17', '-msimd128', '-fwasm-exceptions',
             '-mllvm', '-wasm-use-legacy-eh=false', *flags(build), '-I'+str(dest), '-c', file, '-o', obj])
        objects.append(obj)
    dest = src/'n2'; shutil.copytree(ROOT/'research/native_odometry', dest, ignore=shutil.ignore_patterns('__pycache__'))
    archive = ROOT/'research/artifacts/n2-kfinputs-frozen/package/source-code-and-canonical-weights.tar.gz'
    with tarfile.open(archive) as tf:
        for name in ('weights.f32','weights.S','model_config.h','counts.json'):
            (out/name).write_bytes(tf.extractfile('newest-cpp-source/canonical/'+name).read())
    file = dest/'guest.cpp'
    file.write_text('#include <cstdint>\n'+declarations('n2')+'\n'+renamed(file.read_text(),'n2'))
    opencv = RUNTIME/'build/runtime/opencv-build'
    # The runtime includes retain the 4.12 compatibility headers.
    common = [SDK, '-O3', '-ffp-contract=off', '-std=c++17', '-msimd128', '-fwasm-exceptions',
              '-mllvm', '-wasm-use-legacy-eh=false', '-DODO_INPUT_KF_GRID', '-DODO_WASM_TILE8X32',
              '-DODO_WASM_UNROLL_K2', '-I'+str(out), '-I'+str(native), *flags(a.vins_build)]
    nobj = out/'n2.o'
    run([*common, '-c', file, '-o', nobj]); objects.append(nobj)
    shutil.copy2(HERE/'guest.cpp', src/'guest.cpp')
    shutil.copy2(HERE/'selector.hpp', src/'selector.hpp')
    obj = out/'guest.o'
    run([*common, f"-DFUSION_AGREEMENT_ABS={config['agreement_abs']}",
         f"-DFUSION_AGREEMENT_REL={config['agreement_rel']}",
         '-I'+str(src), '-c', src/'guest.cpp', '-o', obj]); objects.append(obj)
    libs = [a.vins_build/'libvins_mono.a', a.ov_build/'libopenvins.a', a.vins_build/'ceres/lib/libceres.a']
    libs += [opencv/f'lib/libopencv_{n}.a' for n in ('video','dnn')]
    libs += [opencv/'3rdparty/lib/liblibprotobuf.a']
    libs += [opencv/f'lib/libopencv_{n}.a' for n in ('calib3d','features2d','imgproc','flann','core')]
    libs += [opencv/'3rdparty/lib/libzlib.a']
    run([SDK, '-O3', '-msimd128', '-fwasm-exceptions', '-mexec-model=reactor',
         '-Wl,--initial-memory=134217728', '-Wl,-z,stack-size=16777216', '-Wl,--stack-first',
         '-Wl,--strip-debug', *objects, out/'weights.S', *libs, '-lunwind','-lpthread','-o',out/'composite.wasm'])
    report = {'status':'experimental; full G1 failed; runtime validation pending',
              'wasm_sha256':sha(out/'composite.wasm'), 'selector_config':config,
              'n2_backend':'OpenCV4.12; separate measurements required',
              'canonical_archive_sha256':sha(archive), 'commands':commands,
              'dependencies':{str(f):sha(f) for f in libs},
              'sources':{str(f.relative_to(src)):sha(f) for f in src.rglob('*') if f.is_file()}}
    (out/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','wasm_sha256','n2_backend')}))


if __name__ == '__main__':
    main()
