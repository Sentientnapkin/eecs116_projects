"""Build one-file lc_*.c: gate.c (G = f0 + movement gate) + learned net (lc_core.h + weights header inlined).
  python -B make_lc.py <out.c> <weights dir> [NAME=VALUE ...]   (NAME=VALUE overrides the LC_* defaults by #define before the core)"""
import sys
from pathlib import Path
here = Path(__file__).parent
gate = (here / '../final/submit/gate.c').read_text()
out, wdir, defs = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
core = (here / 'lc_core.h').read_text().replace('#include "lc_weights.h"', (wdir / 'lc_weights.h').read_text())
pre = ''.join(f'#define {d.split("=")[0]} {d.split("=")[1]}\n' for d in defs)
a = 'static void imu_measurements(const double *imu, int n) {'
assert gate.count(a) == 1
gate = gate.replace(a, '/* ---- learned startup net (learned_c) ---- */\n' + pre + core + '\n' + a, 1)
b = '    int startup = moving && PRIOR_MODE && !gate_released && last_t - t_start < START_T;'
assert gate.count(b) == 1
gate = gate.replace(b, '    int startup = moving && PRIOR_MODE && !gate_released && last_t - t_start < START_T && !(LC_REPLACE && lc_applied);', 1)
c = '        m3mul(R, R_bc, Rwc_prev);\n        initialized = 1;\n'
assert gate.count(c) == 1
gate = gate.replace(c, c + '        lc_begin(frame, imu, imu_count);\n', 1)
d = '    if (imu_count) imu_measurements(imu, imu_count);\n    vision(frame);'
assert gate.count(d) == 1
gate = gate.replace(d, '    if (imu_count) imu_measurements(imu, imu_count);\n    lc_step(frame, imu, imu_count);\n    vision(frame);', 1)
Path(out).write_text(gate); print('wrote', out, len(gate))
