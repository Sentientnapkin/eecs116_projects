// Startup initializer bridge: the other team's stage-2 EKF (goats/submission_stage2 vio.cpp, unmodified copy in ../goats)
// behind a C interface for GSLV (gslv.c, INI_MODE != 0). Parameters = their submission (parameters.h):
// stage=0.5, seed_px=3, init_tilt=0.45; everything else at their defaults; no depth-hypothesis bank (bank_frames=0).
#include "vio.cpp"

#ifndef INI_SET
#define INI_SET
#endif

static vio::Vio ini_vio;

extern "C" {
void ini_init(double fx, double fy, double cx, double cy, const double *T) {
    vio::Params q;
    {
        vio::Params &p = q;
        p.stage = 0.5; p.seed_px = 3; p.init_tilt = 0.45;
        INI_SET
    }
    ini_vio.P = q;
    ini_vio.init(fx, fy, cx, cy, T);
}
void ini_step(double t, const uint8_t *frame, const double *imu, int n, double *out) { ini_vio.step(t, frame, imu, n, out); }
// R (world W <- body, row-major), p, v, bg, ba, g (W), B = [b1 b2] (3x2 row-major), C = 17x17 core covariance
void ini_state(double *R, double *p, double *v, double *bg, double *ba, double *g, double *B, double *C) {
    const vio::Vio &S = ini_vio;
    for (int i = 0; i < 9; i++) R[i] = S.R.m[i];
    p[0] = S.p.x, p[1] = S.p.y, p[2] = S.p.z;
    v[0] = S.v.x, v[1] = S.v.y, v[2] = S.v.z;
    bg[0] = S.bg.x, bg[1] = S.bg.y, bg[2] = S.bg.z;
    ba[0] = S.ba.x, ba[1] = S.ba.y, ba[2] = S.ba.z;
    g[0] = S.g.x, g[1] = S.g.y, g[2] = S.g.z;
    B[0] = S.b1.x, B[1] = S.b2.x, B[2] = S.b1.y, B[3] = S.b2.y, B[4] = S.b1.z, B[5] = S.b2.z;
    for (int i = 0; i < 17; i++)
        for (int j = 0; j < 17; j++) C[17 * i + j] = 0.5 * ((double)S.C[i][j] + (double)S.C[j][i]);
}
int ini_restarts(void) { return ini_vio.stats[13]; }
// health / scene summary: [rho_med, nis, n_alive, restarts, vel var sum, speed, n_updated, streak]
void ini_diag(double *o) {
    const vio::Vio &S = ini_vio;
    o[0] = S.rho_med, o[1] = S.nis, o[2] = S.n_alive, o[3] = S.stats[13], o[4] = (double)S.C[6][6] + S.C[7][7] + S.C[8][8];
    o[5] = vio::norm(S.v), o[6] = S.n_updated, o[7] = S.streak;
}
}
