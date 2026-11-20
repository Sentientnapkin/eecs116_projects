"""Write one oracle solution_<arm>.c per arm from the original gp_msckf solution.c + oracle_table.h (ORACLE ONLY).
Usage: python make_arms.py   -> oracle/arms/<arm>.c
Arm name: v<exact|noisy>_s<vsig>_t<exact|noisy|none>_s<tsig>; flags replace the #define lines (-D does not work)."""
import re, sys
from pathlib import Path
here = Path(__file__).parent
SRC = (here / '../../../Final Project/classical_vio/gp_msckf/solution.c').resolve().read_text()
TABLE = (here / 'oracle_table.h').read_text()
BLOCK_TILT = r'''
    /* ORACLE tilt: roll/pitch from the true up direction in the body frame (R f_up = +z) */
    {
        const OracleRow *o = oracle_lookup();
        if (o && ORACLE_TILT) {
            double up[3] = {o->up[0], o->up[1], o->up[2]};
            align_to_z(up, R);
            if (ORACLE_TILT_NOISE > 0) { /* noisy estimate: tilt error ~ N(0, sigma) about the world x,y axes */
                double w[3] = {ORACLE_TILT_NOISE * oracle_gauss(o), ORACLE_TILT_NOISE * oracle_gauss(o), 0}, dR[9], Rn[9];
                exp_so3(w, dR); m3mul(dR, R, Rn); memcpy(R, Rn, sizeof R);
            }
        }
    }
'''
BLOCK_VEL = r'''
    /* ORACLE velocity: true body-frame velocity rotated by the filter's initial R (world<-body) */
    {
        const OracleRow *o = oracle_lookup();
        if (o && ORACLE_VEL) {
            double v[3];
            for (int i = 0; i < 3; i++) v[i] = R[3*i]*o->vb[0] + R[3*i+1]*o->vb[1] + R[3*i+2]*o->vb[2];
            for (int i = 0; i < 3; i++) vel[i] = v[i] + ORACLE_VEL_NOISE * oracle_gauss(o);
            fprintf(stderr, "ORACLE hit v_world=%.4f %.4f %.4f vb=%.4f %.4f %.4f\n", vel[0], vel[1], vel[2], o->vb[0], o->vb[1], o->vb[2]);
        } else fprintf(stderr, "ORACLE %s\n", o ? "hit (vel off)" : "MISS");
    }
'''
HELPERS = r'''
#include <stdio.h>
''' + TABLE + r'''
static const OracleRow *oracle_lookup(void) {
    for (int i = 0; i < ORACLE_N; i++)
        if (fabs(oracle_rows[i].fx - fx) < 2e-3 && fabs(oracle_rows[i].fy - fy) < 2e-3 &&
            fabs(oracle_rows[i].cx - cx) < 2e-3 && fabs(oracle_rows[i].cy - cy) < 2e-3) return &oracle_rows[i];
    return NULL;
}
static unsigned long long oracle_state;
static double oracle_gauss(const OracleRow *o) { /* deterministic per episode: LCG seeded from intrinsics */
    if (!oracle_state) oracle_state = (unsigned long long)(o->fx * 1e4) * 2654435761ULL + 88172645463325252ULL;
    double u[2];
    for (int k = 0; k < 2; k++) { oracle_state = oracle_state * 6364136223846793005ULL + 1442695040888963407ULL;
        u[k] = ((oracle_state >> 11) + 0.5) / 9007199254740992.0; }
    return sqrt(-2 * log(u[0])) * cos(2 * M_PI * u[1]);
}
'''
def make(name, vel, vnoise, vsig, tilt, tnoise, tsig):
    s = SRC
    s = re.sub(r'#define INIT_TILT_STD [0-9.]+', f'#define INIT_TILT_STD {tsig if tilt else 0.05}', s)
    s = re.sub(r'#define INIT_VELOCITY_STD [0-9.]+', f'#define INIT_VELOCITY_STD {vsig if vel else 1.0}', s)
    defs = (f'#define ORACLE_VEL {int(vel)}\n#define ORACLE_VEL_NOISE {vsig if vnoise else 0.0}\n'
            f'#define ORACLE_TILT {int(tilt)}\n#define ORACLE_TILT_NOISE {tsig if tnoise else 0.0}\n')
    s = s.replace('static void set_block(', defs + HELPERS + '\nstatic void set_block(', 1)
    assert 'static double fx' not in HELPERS
    s = s.replace('    align_to_z(f, R);\n    memcpy(R0, R, sizeof R);', '    align_to_z(f, R);' + BLOCK_TILT + '    memcpy(R0, R, sizeof R);', 1)
    s = s.replace('    last_t = t;\n}\n\n/* one IMU sample', BLOCK_VEL + '    last_t = t;\n}\n\n/* one IMU sample', 1)
    assert BLOCK_VEL in s and BLOCK_TILT in s and 'ORACLE_N' in s
    (here / 'arms').mkdir(exist_ok=True)
    (here / 'arms' / f'{name}.c').write_text(s)
arms = []
for sg in (0.01, 0.1, 0.3, 0.6, 1.0):
    arms.append((f'vx_{sg}', 1, 0, sg, 0, 0, 0.05))      # exact truth velocity, claimed sigma sg
for sg in (0.1, 0.3, 0.6, 1.0):
    arms.append((f'vn_{sg}', 1, 1, sg, 0, 0, 0.05))      # truth + N(0,sg) noise, claimed sigma sg
for sg in (0.02, 0.05, 0.1):
    arms.append((f'tx_{sg}', 0, 0, 1.0, 1, 0, sg))       # exact truth tilt
    arms.append((f'tn_{sg}', 0, 0, 1.0, 1, 1, sg))       # noisy tilt
for sg in (0.1, 0.3, 0.6, 1.0):
    arms.append((f'bx_{sg}', 1, 0, sg, 1, 0, 0.02))      # both exact
for a in arms: make(*a)
print([a[0] for a in arms])
