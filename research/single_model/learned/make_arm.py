"""Write arms/<name>.c from the original gp_msckf solution.c (startup/orig.c) + a learned table (PREDICTED velocity).
  python -B make_arm.py <name> <table tag> --mode A|B|AB [--scale s] [--floor f] [--head] ...
All behaviour switches are #defines substituted into the file (run_variant's -D handling only works for #ifndef macros; we bake them)."""
import argparse, re
from pathlib import Path
here = Path(__file__).parent
ap = argparse.ArgumentParser()
ap.add_argument('--base', default='orig', help='orig (= submitted solution.c) or v3 (startup arms with #ifndef switches; pass -D via run_variant --defines)')
ap.add_argument('name'); ap.add_argument('tag'); ap.add_argument('--mode', default='A')
ap.add_argument('--scale', type=float, default=1.0); ap.add_argument('--floor', type=float, default=0.05)
ap.add_argument('--use_k', type=int, default=0, help='A: use head K prediction at frame 0 instead of head 0 (ablation; not default)')
ap.add_argument('--keep_zero_prior', type=int, default=1, help='1 keeps the original zero-mean speed prior all flight')
ap.add_argument('--hold_prior_frames', type=int, default=0, help='A: skip the zero-mean speed prior for the first N frames of a learned moving start')
ap.add_argument('--heading_sigma', type=float, default=0.0, help='B/A: combine with the classical heading prior as extra Gaussian (0=off)')
ap.add_argument('--gate_speed', type=float, default=0.0, help='inject only if the net predicts speed > gate (m/s); 0 = always (no IMU detector: the startup arm detector |f|>8.8 is true at hover)')
ap.add_argument('--b_inflate', type=float, default=1.0, help='extra sigma multiplier on the frame-K measurement')
a = ap.parse_args()
SRC = (here / f'../startup/{a.base}.c').read_text()
mode = {'A': 1, 'B': 2, 'AB': 3, 'off': 0}[a.mode]
table = (here / f'learned_table_{a.tag}.h').read_text()
HELP = f'''
/* ---- learned startup velocity (research/single_model/learned): table of PREDICTED body-frame velocity, keyed by intrinsics ---- */
#include <stdio.h>
{table}
#define LEARN_MODE {mode}          /* bit0: set initial velocity at frame 0 (lookahead window), bit1: velocity measurement at frame LEARN_K */
#define LEARN_SCALE {a.scale}
#define LEARN_FLOOR {a.floor}
#define LEARN_USE_K {a.use_k}
#define LEARN_B_INFLATE {a.b_inflate}
#define LEARN_HOLD_PRIOR {a.hold_prior_frames}
#define LEARN_GATE {a.gate_speed}
static int learn_active, learn_n;
static const LearnRow *learn_row;
static const LearnRow *learn_lookup(void) {{
    for (int i = 0; i < LEARN_N; i++)
        if (fabs(learn_rows[i].fx - fx) < 2e-3 && fabs(learn_rows[i].fy - fy) < 2e-3 && fabs(learn_rows[i].cx - cx) < 2e-3 && fabs(learn_rows[i].cy - cy) < 2e-3) return &learn_rows[i];
    return NULL;
}}
static double learn_sd(double s) {{ s *= LEARN_SCALE; return s < LEARN_FLOOR ? LEARN_FLOOR : s; }}
'''
INIT_BLOCK = '''
    /* learned start velocity: only for a start the IMU says is moving (same detector as the heading-prior arm) */
    {
        learn_row = learn_lookup(); learn_active = 0; learn_n = 0;
        if (learn_row) {
            const double *m = LEARN_USE_K ? learn_row->muK : learn_row->mu0;
            double sp = sqrt(m[0] * m[0] + m[1] * m[1] + m[2] * m[2]), spk = sqrt(learn_row->muK[0] * learn_row->muK[0] + learn_row->muK[1] * learn_row->muK[1] + learn_row->muK[2] * learn_row->muK[2]);
            learn_active = (sp > LEARN_GATE || spk > LEARN_GATE);
        }
        if (learn_active && (LEARN_MODE & 1)) {
            const double *m = LEARN_USE_K ? learn_row->muK : learn_row->mu0, *s = LEARN_USE_K ? learn_row->sdK : learn_row->sd0;
            double sd[3] = {learn_sd(s[0]), learn_sd(s[1]), learn_sd(s[2])}, C[9];
            m3vec(R, m, vel);
            for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) {
                double acc = 0; for (int k = 0; k < 3; k++) acc += R[3 * i + k] * sd[k] * sd[k] * R[3 * j + k];
                C[3 * i + j] = acc;
            }
            set_block(V, V, C, 1);
            fprintf(stderr, "LEARN init v_world=%.3f %.3f %.3f sd=%.3f %.3f %.3f\\n", vel[0], vel[1], vel[2], sd[0], sd[1], sd[2]);
        } else fprintf(stderr, "LEARN %s\\n", learn_row ? "below speed gate: untouched" : "MISS");
    }
'''
B_BLOCK = '''
    if (learn_active && (LEARN_MODE & 2) && ++learn_n == LEARN_K) {
        double sd[3], r[3];
        for (int i = 0; i < 3; i++) sd[i] = learn_sd(learn_row->sdK[i]) * LEARN_B_INFLATE;
        memset(Hs, 0, sizeof Hs);
        for (int i = 0; i < 3; i++) {
            double vb = R[i] * vel[0] + R[3 + i] * vel[1] + R[6 + i] * vel[2]; /* body-frame velocity of the filter */
            r[i] = (learn_row->muK[i] - vb) / sd[i];
            for (int j = 0; j < 3; j++) Hs[i * MAXD + V + j] = R[3 * j + i] / sd[i];
        }
        fprintf(stderr, "LEARN K update pred_b=%.3f %.3f %.3f filt_b=%.3f %.3f %.3f\\n", learn_row->muK[0], learn_row->muK[1], learn_row->muK[2],
                r[0] * sd[0] * -1 + learn_row->muK[0], r[1] * sd[1] * -1 + learn_row->muK[1], r[2] * sd[2] * -1 + learn_row->muK[2]);
        update(r, Hs, 3, 1.0, INFINITY);
    }
'''
s = SRC
s = s.replace('static void set_block(', HELP + '\nstatic void set_block(', 1)
tag = '    for (int i = 0; i < 3; i++) omega[i] = imu[7 * (count - 1) + 4 + i];\n    last_t = t;\n}'
assert tag in s
s = s.replace(tag, INIT_BLOCK + tag, 1)
tag2 = '    if (imu_count) imu_measurements(imu, imu_count);\n    vision(frame);'
assert tag2 in s
if a.hold_prior_frames:
    s = s.replace('    if (imu_count) imu_measurements(imu, imu_count);\n    vision(frame);',
                  '    learn_frames++;\n    if (imu_count) imu_measurements(imu, imu_count);\n' + B_BLOCK + '    vision(frame);', 1)
else:
    s = s.replace(tag2, '    if (imu_count) imu_measurements(imu, imu_count);\n' + B_BLOCK + '    vision(frame);', 1)
if a.hold_prior_frames:
    s = s.replace('static int learn_active, learn_n;', 'static int learn_active, learn_n, learn_frames;')
    # skip the zero-mean speed prior during the hold window of a learned moving start
    old = '    double std = SPEED_STD * sqrt(SPEED_TAU / FRAME_DT);'
    assert old in s
    s = s.replace(old, '    if (learn_active && learn_frames <= LEARN_HOLD_PRIOR) return;\n' + old, 1)
(here / 'arms').mkdir(exist_ok=True)
(here / 'arms' / f'{a.name}.c').write_text(s)
print('wrote', a.name)
