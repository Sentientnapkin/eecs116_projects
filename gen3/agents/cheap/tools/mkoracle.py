"""mkoracle.py POOL FLIGHT OUT_H: per-frame ground-truth body (IMU-axes) velocity table for an oracle TEST build (never a submission)."""
import sys, json
from pathlib import Path
import numpy as np
from viobench.tools.datasets.storage import read_episode
ep = read_episode(Path(sys.argv[1]) / (sys.argv[2] + '.zip'), frames='none'); gt = ep.ground_truth_state()
cfg = ep.config if hasattr(ep, 'config') else None
import zipfile
z = zipfile.ZipFile(Path(sys.argv[1]) / (sys.argv[2] + '.zip'))
T = None
for n in z.namelist():
    if n.endswith('cam0/sensor.yaml'):
        t = z.read(n).decode(); import re
        nums = [float(x) for x in re.findall(r'-?\d+\.?\d*(?:e-?\d+)?', t.split('T_BS')[1])][2:18] if 'T_BS' in t else None
        T = np.array(nums).reshape(4, 4) if nums else None
print(T)
Rbc = T[:3, :3]  # body <- camera (EuRoC T_BS)
vb = gt[:, 7:10] @ Rbc.T
L = [f'#define OR_N {len(vb)}', f'static const float OR_V[{len(vb)}][3] = {{'] + ['{%.4f,%.4f,%.4f},' % tuple(v) for v in vb] + ['};']
open(sys.argv[3], 'w').write('\n'.join(L) + '\n')
