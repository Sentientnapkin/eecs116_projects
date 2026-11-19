"""Build the actual corrected visual native guest, unlike export.py's plain host.so."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=root/'results/loop/fusion-completion/artifacts/n2-218-knownrot_a_replace-parity-repair-trace')
    parser.add_argument('--opencv-build', type=Path, default=Path('/dev/shm/sebastian-vio/codex-fusion-opencv412-native'))
    parser.add_argument('--opencv-source', type=Path, default=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/build/runtime/src/opencv'))
    args = parser.parse_args()
    command = ['c++','-std=c++17','-O3','-ffp-contract=off','-fPIC','-shared',
               '-DODO_KF_GRID','-DODO_KFG_RECOVER_RANSAC_MASK','-DODO_VEL_FUSION',
               '-DODO_FUSION_REQUIRE_ACCEPTED_ROTATION','-I',str(args.build),
               '-I','/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native',
               '-I',str(args.opencv_build)]
    for module in ('core','imgproc','video','calib3d','features2d','flann'):
        command += ['-I',str(args.opencv_source/'modules'/module/'include')]
    command += [str(root/'native_odometry/guest.cpp'),'-L',str(args.opencv_build/'lib'),
                '-Wl,-rpath,'+str(args.opencv_build/'lib'),'-lopencv_core','-lopencv_imgproc',
                '-lopencv_video','-lopencv_calib3d','-o',str(args.build/'host_visual.so')]
    subprocess.run(command,check=True)
    metadata={'command':command,'host_visual_sha256':hashlib.sha256((args.build/'host_visual.so').read_bytes()).hexdigest()}
    (args.build/'host_visual.build.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))


if __name__=='__main__':main()
