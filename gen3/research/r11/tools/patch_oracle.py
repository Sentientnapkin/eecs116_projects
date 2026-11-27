"""patch_oracle.py IN.c OUT.c: add ORACLE test hooks (default ORACLE=0 -> identical code). TEST builds only.
Flags (all need -DORACLE=1 and oracle_tab.h next to solution.c):
 OR_V    0 off | 1 GT velocity in every net application | 2 startup net only | 3 periodic re-anchors only
 OR_VM   0 full vector | 1 speed only (net direction x |v_gt|) | 2 direction only (v_gt dir x |net|)
 OR_SD   0 net sigma | >0 constant sigma (m/s, before LC_SCALE*tc_lcscale) | -1 oracle-error sigma max(|net-gt|,OR_SDF) per axis (net mu)
 OR_LAT  1: startup measurement applied at frame K (no net latency), GT velocity, sigma OR_LSD
 OR_V0   1: initial velocity = GT v0 at frame 0 with sigma OR_V0SD
 OR_G    1: initial attitude from GT gravity direction (2: + tilt sigma 0.01)
 OR_B    1: initial gyro+accel bias = 2 s LS estimate (small sigma) | 2 gyro only | 3 accel only
"""
import sys
s = open(sys.argv[1]).read()
def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (old[:60], s.count(old)); s = s.replace(old, new)

hdr = r'''
#ifndef ORACLE
#define ORACLE 0
#endif
#if ORACLE
#include "oracle_tab.h"
#ifndef OR_V
#define OR_V 0
#endif
#ifndef OR_VM
#define OR_VM 0
#endif
#ifndef OR_SD
#define OR_SD 0.0
#endif
#ifndef OR_SDF
#define OR_SDF 0.03
#endif
#ifndef OR_LAT
#define OR_LAT 0
#endif
#ifndef OR_LSD
#define OR_LSD 0.1
#endif
#ifndef OR_V0
#define OR_V0 0
#endif
#ifndef OR_V0SD
#define OR_V0SD 0.1
#endif
#ifndef OR_G
#define OR_G 0
#endif
#ifndef OR_B
#define OR_B 0
#endif
static int or_fid = -1, or_fr = -1, or_kidx = 0;
static void or_find(const double *imu) {
    or_fid = -1;
    for (int f = 0; f < OR_F; f++) { int ok = 1; for (int j = 0; j < 6; j++) if (fabs(OR_KEY[f][j] - imu[1 + j]) > 1e-9) { ok = 0; break; }
        if (ok) { or_fid = f; return; } }
}
static void or_vel(int fr, double *v) { if (fr < 0) fr = 0; if (fr >= OR_NF) fr = OR_NF - 1; for (int i = 0; i < 3; i++) v[i] = OR_VT[or_fid][fr][i]; }
#endif
static void initialize(const double *imu, int count, double t) {'''
rep('static void initialize(const double *imu, int count, double t) {', hdr)

# gravity oracle: replace f before align
rep('''        for (int i = 0; i < 3; i++) f[i] += imu[7 * r + 1 + i] / count;
    align_to_z(f, R);''', '''        for (int i = 0; i < 3; i++) f[i] += imu[7 * r + 1 + i] / count;
#if ORACLE
    or_find(imu);
    if (OR_G && or_fid >= 0) { double fo[3]; for (int i = 0; i < 3; i++) fo[i] = OR_UP0[or_fid][i] * 9.81; align_to_z(fo, R); } else
#endif
    align_to_z(f, R);''')
# tilt sigma, biases, v0
rep('''    double ts = moving ? MOVE_TILT_STD : INIT_TILT_STD, vs = moving ? MOVE_VEL_STD : INIT_VELOCITY_STD;''',
    '''    double ts = moving ? MOVE_TILT_STD : INIT_TILT_STD, vs = moving ? MOVE_VEL_STD : INIT_VELOCITY_STD;
#if ORACLE
    if (OR_G == 2 && or_fid >= 0) ts = 0.01;
#endif''')
rep('''    set_block(BA, BA, I3, INV_BAZ > 0 ? INV_BAZ * INV_BAZ : ACCEL_BIAS_MAX * ACCEL_BIAS_MAX / 3);''',
    '''    set_block(BA, BA, I3, INV_BAZ > 0 ? INV_BAZ * INV_BAZ : ACCEL_BIAS_MAX * ACCEL_BIAS_MAX / 3);
#if ORACLE
    if (or_fid >= 0 && (OR_B == 1 || OR_B == 2)) { for (int i = 0; i < 3; i++) bg[i] = OR_BG[or_fid][i]; set_block(BG, BG, I3, 0.002 * 0.002); }
    if (or_fid >= 0 && (OR_B == 1 || OR_B == 3)) { for (int i = 0; i < 3; i++) ba[i] = OR_BA[or_fid][i]; set_block(BA, BA, I3, 0.02 * 0.02); }
    if (or_fid >= 0 && OR_V0) { double vb0[3]; or_vel(0, vb0); m3vec(R, vb0, vel); set_block(V, V, I3, OR_V0SD * OR_V0SD); }
#endif''')
# frame counter + K index
rep('''int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {''',
    '''int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
#if ORACLE
    or_fr++;
#endif''')
rep('''            memcpy(lc_Rf5, R, sizeof lc_Rf5); memcpy(lc_vf5, vel, sizeof lc_vf5);
#if VKC''', '''            memcpy(lc_Rf5, R, sizeof lc_Rf5); memcpy(lc_vf5, vel, sizeof lc_vf5);
#if ORACLE
            or_kidx = or_fr;
#endif
#if VKC''')
# zero-latency startup oracle: right after the frame-K stash
rep('''            memcpy(ns_rgb5, frame, sizeof ns_rgb5); ns_have5 = 1; gov_used += GC_STASH;
#else''', '''            memcpy(ns_rgb5, frame, sizeof ns_rgb5); ns_have5 = 1; gov_used += GC_STASH;
#if ORACLE
            if (OR_LAT && tc_nanch == 0 && or_fid >= 0) {
                double vg[3]; or_vel(or_kidx, vg);
                for (int i = 0; i < 3; i++) { lc_out[6 + i] = (float)vg[i]; lc_out[9 + i] = (float)log(OR_LSD * OR_LSD); }
                lc_apply(); lc_next = 6; ns_pos = NS_STEPS; return;
            }
#endif
#else''')
# measurement substitution in lc_apply
rep('''        sd[i] = s < fl ? fl : s; mu[i] = lc_out[6 + i];
    }''', '''        sd[i] = s < fl ? fl : s; mu[i] = lc_out[6 + i];
    }
#if ORACLE
    if (or_fid >= 0 && !(OR_LAT && tc_nanch == 0)) {
        int use = OR_V == 1 || (OR_V == 2 && tc_nanch == 0) || (OR_V == 3 && tc_nanch > 0);
        double vg[3]; or_vel(or_kidx, vg);
        double ng = sqrt(vg[0] * vg[0] + vg[1] * vg[1] + vg[2] * vg[2]), nm = sqrt(mu[0] * mu[0] + mu[1] * mu[1] + mu[2] * mu[2]);
        if (OR_SD < 0 && (OR_V == 0 || use)) for (int i = 0; i < 3; i++) { double e = fabs(mu[i] - vg[i]); if (e < OR_SDF) e = OR_SDF; sd[i] = LC_SCALE * tc_lcscale * e; }
        if (use) {
            for (int i = 0; i < 3; i++) {
                if (OR_VM == 0) mu[i] = vg[i];
                else if (OR_VM == 1) mu[i] = nm > 1e-6 ? mu[i] / nm * ng : mu[i];
                else mu[i] = ng > 1e-6 ? vg[i] / ng * nm : mu[i];
                if (OR_SD > 0) { double s2 = LC_SCALE * tc_lcscale * OR_SD; sd[i] = s2; }
            }
        }
    }
#endif''')
rep('''    initialized = 0;
#if HARDEN''', '''    initialized = 0;
#if ORACLE
    or_fr = -1;
#endif
#if HARDEN''')
open(sys.argv[2], 'w').write(s)
print('patched ok')
