"""Build one-file lc_*.c: gate.c (G = f0 + movement gate) + learned net (lc_core.h + weights header inlined).
  python -B make_lc.py <out.c> <weights dir> [NAME=VALUE ...]   (NAME=VALUE overrides the LC_* defaults by #define before the core)"""
import sys
from pathlib import Path
here = Path(__file__).parent
import os
BASE = os.environ.get('LC_BASE', str(here / '../frontend/adopted_fbh.c'))   # B6 = G+C1+FB
gate = Path(BASE).read_text()
out, wdir, defs = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
core = (here / os.environ.get('LC_CORE', 'lc_core.h')).read_text().replace('#include "lc_weights.h"', (wdir / 'lc_weights.h').read_text())
pre = ''.join(f'#define {d.split("=")[0]} {d.split("=")[1]}\n' for d in defs)
a = 'static void imu_measurements(const double *imu, int n) {'
assert gate.count(a) == 1
gate = gate.replace(a, '/* ---- learned startup net (learned_c) ---- */\n' + pre + core + '\n' + a, 1)
b = '&& tt < START_T + (INV_FADE > 0 ? INV_FADE : 0);'
assert gate.count(b) == 1
gate = gate.replace(b, '&& tt < START_T + (INV_FADE > 0 ? INV_FADE : 0) && !LC_PRIOR_OFF;', 1)
c = '        m3mul(R, R_bc, Rwc_prev);\n        initialized = 1;\n'
assert gate.count(c) == 1
gate = gate.replace(c, c + '        lc_begin(frame, imu, imu_count);\n', 1)
d = '    if (imu_count) imu_measurements(imu, imu_count);\n    vision(frame);'
assert gate.count(d) == 1
gate = gate.replace(d, '    if (imu_count) imu_measurements(imu, imu_count);\n    lc_step(frame, imu, imu_count);\n    vision(frame);', 1)
Path(out).write_text(gate); print('wrote', out, len(gate))
