/* ===================================================================================================================
 * INI: startup initializer from the other team's stage-2 EKF (ini_bridge.cpp -> vio.cpp; read-only reference copy).
 * INI_MODE 0: off (unchanged GSLV). 1: their filter alone for frames 0..INI_N-1 (its output is ours), GSLV starts at
 * frame INI_N from their state (R, p, v, biases, gravity -> tilt) and covariance. 2: both run from frame 0; at frame
 * INI_N their body-frame velocity and gravity direction are fused into GSLV as one measurement (covariance x INI_FINF).
 * =================================================================================================================== */
#ifndef INI_MODE
#define INI_MODE 0
#endif
#ifndef INI_N
#define INI_N 40
#endif
#ifndef INI_VINF
#define INI_VINF 1.0      /* mode 1: velocity covariance multiplier at handover */
#endif
#ifndef INI_TINF
#define INI_TINF 1.0      /* mode 1: attitude/gravity covariance multiplier at handover */
#endif
#ifndef INI_BFLOOR
#define INI_BFLOOR 0.0    /* mode 1: bias variances at least this share of GSLV's own bias prior */
#endif
#ifndef INI_GATEREL
#define INI_GATEREL 1     /* mode 1: release the startup (heading) velocity prior at handover */
#endif
#ifndef INI_NET
#define INI_NET 1         /* mode 1: keep GSLV's learned-velocity net (lc) after handover */
#endif
#ifndef INI_FINF
#define INI_FINF 1.0      /* mode 2: measurement covariance multiplier */
#endif
#ifndef INI_FGRAV
#define INI_FGRAV 1       /* mode 2: also fuse the gravity direction */
#endif
#ifndef INI_NOPRIOR
#define INI_NOPRIOR 0     /* mode 2: no startup heading prior (their velocity replaces it) */
#endif
#ifndef INI_FVMIN
#define INI_FVMIN 0.0     /* mode 2/1: velocity sd floor (m/s) of the handed-over estimate */
#endif
#if INI_MODE
void ini_init(double fx, double fy, double cx, double cy, const double *T);
void ini_step(double t, const uint8_t *frame, const double *imu, int n, double *out);
void ini_state(double *R, double *p, double *v, double *bg, double *ba, double *g, double *B, double *C);
static int ini_k, ini_pending;
static double ini_Rt[9], ini_p[3], ini_v[3], ini_bg[3], ini_ba[3], ini_g[3], ini_B[6], ini_C[17 * 17];
/* J C J^T for an n x 17 Jacobian J (row-major), into out (n x n) */
static void ini_jcjt(const double *J, int n, double *out) {
    static double JC[24 * 17];
    for (int i = 0; i < n; i++)
        for (int j = 0; j < 17; j++) { double s = 0; for (int k = 0; k < 17; k++) s += J[17 * i + k] * ini_C[17 * k + j]; JC[17 * i + j] = s; }
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++) { double s = 0; for (int k = 0; k < 17; k++) s += JC[17 * i + k] * J[17 * j + k]; out[n * i + j] = s; }
}
/* mode 1: GSLV core state from theirs. GSLV world = R_A W with R_A taking their "up" (-g) to +z; R0 = R_A. */
static void ini_handover(void) {
    ini_state(ini_Rt, ini_p, ini_v, ini_bg, ini_ba, ini_g, ini_B, ini_C);
    double up[3] = {-ini_g[0], -ini_g[1], -ini_g[2]}, RA[9];
    align_to_z(up, RA);
    memcpy(R0, RA, sizeof R0);
    m3mul(RA, ini_Rt, R);
    m3vec(RA, ini_p, pos); m3vec(RA, ini_v, vel);
    memcpy(bg, ini_bg, sizeof bg); memcpy(ba, ini_ba, sizeof ba);
    /* error map: phi (world rotation of R_A) = [z]x R_A B dg; TH = Rt^T RA^T phi + dth; TH0 = RA^T phi;
       dP = RA dp - [RA p]x phi; dV = RA dv - [RA v]x phi; biases identity */
    double ez[9], z[3] = {0, 0, 1}, RAB[6], Phi[6], tmp[9], A[9], Rw[3], Sk[9];
    skew(z, ez);
    for (int i = 0; i < 3; i++) for (int j = 0; j < 2; j++) RAB[2 * i + j] = RA[3 * i] * ini_B[j] + RA[3 * i + 1] * ini_B[2 + j] + RA[3 * i + 2] * ini_B[4 + j];
    for (int i = 0; i < 3; i++) for (int j = 0; j < 2; j++) Phi[2 * i + j] = ez[3 * i] * RAB[j] + ez[3 * i + 1] * RAB[2 + j] + ez[3 * i + 2] * RAB[4 + j];
    static double J[18 * 17];
    memset(J, 0, sizeof J);
    /* TH */
    m3tmul(R, I3, tmp); /* R^T = Rt^T RA^T */
    for (int i = 0; i < 3; i++) {
        J[17 * (TH + i) + i] = 1;
        for (int j = 0; j < 2; j++) J[17 * (TH + i) + 15 + j] = tmp[3 * i] * Phi[j] + tmp[3 * i + 1] * Phi[2 + j] + tmp[3 * i + 2] * Phi[4 + j];
        for (int j = 0; j < 2; j++) J[17 * (TH0 + i) + 15 + j] = RA[i] * Phi[j] + RA[3 + i] * Phi[2 + j] + RA[6 + i] * Phi[4 + j];
    }
    for (int blk = 0; blk < 2; blk++) { /* P (their 3..5) and V (their 6..8) */
        int row = blk == 0 ? P : V, col = blk == 0 ? 3 : 6;
        m3vec(RA, blk == 0 ? ini_p : ini_v, Rw);
        skew(Rw, Sk);
        for (int i = 0; i < 3; i++) {
            for (int j = 0; j < 3; j++) J[17 * (row + i) + col + j] = RA[3 * i + j];
            for (int j = 0; j < 2; j++) J[17 * (row + i) + 15 + j] = -(Sk[3 * i] * Phi[j] + Sk[3 * i + 1] * Phi[2 + j] + Sk[3 * i + 2] * Phi[4 + j]);
        }
    }
    for (int i = 0; i < 3; i++) { J[17 * (BG + i) + 9 + i] = 1; J[17 * (BA + i) + 12 + i] = 1; }
    (void)A;
    static double Pc[18 * 18];
    ini_jcjt(J, 18, Pc);
    double sv = sqrt(INI_VINF), st = sqrt(INI_TINF);
    for (int i = 0; i < 18; i++)
        for (int j = 0; j < 18; j++) {
            double s = 1;
            if ((i >= V && i < V + 3)) s *= sv;
            if ((j >= V && j < V + 3)) s *= sv;
            if (i < 3 || (i >= TH0 && i < TH0 + 3)) s *= st;
            if (j < 3 || (j >= TH0 && j < TH0 + 3)) s *= st;
            Pm[i * MAXD + j] = Pc[18 * i + j] * s;
        }
    for (int i = 0; i < 3; i++) {
        double fg = INI_BFLOOR * GYRO_BIAS_MAX * GYRO_BIAS_MAX / 3, fa = INI_BFLOOR * ACCEL_BIAS_MAX * ACCEL_BIAS_MAX / 3;
        if (Pm[(BG + i) * MAXD + BG + i] < fg) Pm[(BG + i) * MAXD + BG + i] = fg;
        if (Pm[(BA + i) * MAXD + BA + i] < fa) Pm[(BA + i) * MAXD + BA + i] = fa;
        double fv = INI_FVMIN * INI_FVMIN;
        if (Pm[(V + i) * MAXD + V + i] < fv) Pm[(V + i) * MAXD + V + i] = fv;
    }
}
/* lower Cholesky of an n x n SPD matrix (n <= 6) in place; returns 0 on failure */
static int ini_chol(double *A, int n) {
    for (int j = 0; j < n; j++) {
        double s = A[n * j + j];
        for (int k = 0; k < j; k++) s -= A[n * j + k] * A[n * j + k];
        if (!(s > 0)) return 0;
        A[n * j + j] = sqrt(s);
        for (int i = j + 1; i < n; i++) { double t = A[n * i + j]; for (int k = 0; k < j; k++) t -= A[n * i + k] * A[n * j + k]; A[n * i + j] = t / A[n * j + j]; }
        for (int i = 0; i < j; i++) A[n * i + j] = 0;
    }
    return 1;
}
/* mode 2: body-frame velocity R^T v and gravity direction R^T (-z) from their state, one whitened update */
static void ini_feed(void) {
    ini_state(ini_Rt, ini_p, ini_v, ini_bg, ini_ba, ini_g, ini_B, ini_C);
    int n = INI_FGRAV ? 6 : 3;
    static double J[6 * 17], Sz[36], Hw[6 * MAXD], rw[6];
    double zb[6], vb[3], gn = sqrt(ini_g[0] * ini_g[0] + ini_g[1] * ini_g[1] + ini_g[2] * ini_g[2]), gu[3], gb[3], Sv[9], Sg[9];
    for (int i = 0; i < 3; i++) gu[i] = ini_g[i] / gn;
    m3tvec(ini_Rt, ini_v, vb); m3tvec(ini_Rt, gu, gb);
    skew(vb, Sv); skew(gb, Sg);
    memset(J, 0, sizeof J);
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { J[17 * i + j] = Sv[3 * i + j]; J[17 * i + 6 + j] = ini_Rt[3 * j + i]; }
    if (INI_FGRAV)
        for (int i = 0; i < 3; i++) {
            for (int j = 0; j < 3; j++) J[17 * (3 + i) + j] = Sg[3 * i + j];
            for (int j = 0; j < 2; j++) J[17 * (3 + i) + 15 + j] = ini_Rt[i] * ini_B[j] + ini_Rt[3 + i] * ini_B[2 + j] + ini_Rt[6 + i] * ini_B[4 + j];
        }
    ini_jcjt(J, n, Sz);
    for (int i = 0; i < n * n; i++) Sz[i] *= INI_FINF;
    for (int i = 0; i < 3; i++) if (Sz[4 * i] < INI_FVMIN * INI_FVMIN) Sz[4 * i] = INI_FVMIN * INI_FVMIN;
    if (INI_FGRAV) for (int i = 3; i < 6; i++) Sz[7 * i] += 1e-4; /* rank 2 + the unobserved radial direction */
    /* GSLV predictions and Jacobians */
    double pv[3], pg[3], mz[3] = {0, 0, -1}, Spv[9], Spg[9];
    m3tvec(R, vel, pv); m3tvec(R, mz, pg);
    skew(pv, Spv); skew(pg, Spg);
    static double H[6 * MAXD];
    memset(H, 0, sizeof H);
    for (int i = 0; i < 3; i++) {
        zb[i] = vb[i] - pv[i];
        for (int j = 0; j < 3; j++) { H[i * MAXD + TH + j] = Spv[3 * i + j]; H[i * MAXD + V + j] = R[3 * j + i]; }
        if (INI_FGRAV) { zb[3 + i] = gb[i] - pg[i]; for (int j = 0; j < 3; j++) H[(3 + i) * MAXD + TH + j] = Spg[3 * i + j]; }
    }
    if (!ini_chol(Sz, n)) return;
    for (int i = 0; i < n; i++) { /* forward substitution: L^-1 r, L^-1 H */
        double s = zb[i];
        for (int k = 0; k < i; k++) s -= Sz[n * i + k] * rw[k];
        rw[i] = s / Sz[n * i + i];
        for (int c = 0; c < D; c++) {
            double t = H[i * MAXD + c];
            for (int k = 0; k < i; k++) t -= Sz[n * i + k] * Hw[k * MAXD + c];
            Hw[i * MAXD + c] = t / Sz[n * i + i];
        }
        for (int c = D; c < MAXD; c++) Hw[i * MAXD + c] = 0;
    }
    update(rw, Hw, n, 1.0, INFINITY);
}
#endif

