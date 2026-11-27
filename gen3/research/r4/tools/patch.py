"""patch.py: base.c -> base_r4.c with R4LOG (stderr track/state/net logging) and R4INJ (velocity-table injection at the net hook)."""
from pathlib import Path
D=Path(__file__).resolve().parent.parent
s=(D/'base.c').read_text()
def rep(a,b,cnt=1):
    global s
    assert s.count(a)==cnt,(a,s.count(a)); s=s.replace(a,b)
HDR='''
#ifndef R4LOG
#define R4LOG 0
#endif
#ifndef R4INJ
#define R4INJ 0
#endif
static double r4_t, r4_t0 = -1, r4_tk; static int r4_fl = -1;
#if R4INJ
#include "r4tab.h"
static void r4_match(const double *row) { /* pick the flight whose first IMU row matches (offline oracle only) */
    double best = 1e30; r4_fl = -1;
    for (int f = 0; f < R4_NF; f++) { double d = 0; for (int j = 0; j < 6; j++) d += fabs(R4_FP[f][j] - row[1 + j]); if (d < best) { best = d; r4_fl = f; } }
    if (best > 1e-3) r4_fl = -1;
}
static void r4_inject(double *mu, double *sd) {
    if (r4_fl < 0) return;
    int i = (int)floor((r4_tk - r4_t0) * 20.0 + 0.5); if (i < 0 || i >= 1200) return;
    const short *e = R4_V[r4_fl][i]; if (e[3] <= 0) return;
    double s = e[3] * 1e-3;
    for (int k = 0; k < 3; k++) {
        double m = e[k] * 1e-3;
#if R4INJ == 1
        mu[k] = m; sd[k] = s;
#elif R4INJ == 2
        mu[k] = m;
#elif R4INJ == 3
        { double a = 1 / (sd[k] * sd[k]), b = 1 / (s * s); mu[k] = (a * mu[k] + b * m) / (a + b); sd[k] = 1 / sqrt(a + b); }
#endif
    }
}
#endif
'''
rep('#include <wasm_simd128.h>\n','#include <wasm_simd128.h>\n'+HDR)
rep('''        double vb[3]; m3tvec(lc_Rf5, vk_nom, vb); /* clone in frame-K body axes */''','''#if R4LOG
        fprintf(stderr, "N %.6f %d %.4f %.4f %.4f %.4f %.4f %.4f\\n", r4_tk, tc_nanch, mu[0], mu[1], mu[2], sd[0], sd[1], sd[2]);
#endif
#if R4INJ
        r4_inject(mu, sd);
#endif
        double vb[3]; m3tvec(lc_Rf5, vk_nom, vb); /* clone in frame-K body axes */''')
rep('            memcpy(lc_Rf5, R, sizeof lc_Rf5); memcpy(lc_vf5, vel, sizeof lc_vf5);\n','            memcpy(lc_Rf5, R, sizeof lc_Rf5); memcpy(lc_vf5, vel, sizeof lc_vf5); r4_tk = r4_t;\n')
rep('int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {\n','''int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
    r4_t = t;
    if (r4_t0 < 0 && imu_count > 0) { r4_t0 = t;
#if R4LOG
        fprintf(stderr, "F %.6f %.9g %.9g %.9g %.9g %.9g %.9g %.9g fx %.6f %.6f %.6f %.6f\\n", t, imu[0], imu[1], imu[2], imu[3], imu[4], imu[5], imu[6], fx, fy, cx, cy);
#endif
#if R4INJ
        r4_match(imu);
#endif
    }
''')
rep('''    vision(frame);\n#if NET_SLICE\n''','''    vision(frame);
#if R4LOG
    { fprintf(stderr, "X %.6f %d %.5f %.5f %.5f %.6f %.6f %.6f %.5f %.5f %.5f", t, frame_no, vel[0], vel[1], vel[2], bg[0], bg[1], bg[2], pos[0], pos[1], pos[2]);
      for (int i = 0; i < 9; i++) fprintf(stderr, " %.6f", R[i]);
      fprintf(stderr, "\\nT");
      for (int i = 0; i < MAX_TRACKS; i++) if (tracks[i].alive) fprintf(stderr, " %d %d %.3f %.3f", i, tracks[i].born, tracks[i].x, tracks[i].y);
      fprintf(stderr, "\\n"); }
#endif
#if NET_SLICE
''')
(D/'base_r4.c').write_text(s)
