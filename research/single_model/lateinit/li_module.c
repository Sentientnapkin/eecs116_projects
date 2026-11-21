/* =====================================================================================================================
 * lateinit (LI): late closed-form visual-inertial initialization for moving starts.
 * From frame 0 on, buffer the gyro/accel preintegration (body-0 axes) at every frame and the normalized coordinates of
 * every live track. At LI_T s, solve the linear least squares of Kaiser/Martinelli/Campos form for the body velocity
 * at frame 0 (v0) and gravity in body-0 axes (g0) with the feature depths eliminated (Schur complement per feature):
 *     d_ij x ( lambda_j d_kj + c_k - c_i ) = 0,   c_i = v0 t_i + g0 t_i^2 / 2 + alpha_i + R_i p_bc
 * (d: bearing in body-0 axes, k: first observation of feature j), then refine with |g0| = GRAVITY (tangent space,
 * 3 iterations), re-weight by depth and drop outlier features. If the solution is well conditioned (|g_LS| close to
 * GRAVITY, small velocity and gravity sd), the nominal state is rewritten: R0 tilts to the solved gravity (yaw kept),
 * current/clone orientations follow, current velocity/position and clone positions come from the closed-form
 * trajectory since frame 0 (this removes the position offset accumulated during the start, like a replay from t=0).
 * ===================================================================================================================== */
#ifndef LI_MODE
#define LI_MODE 0           /* 0 off; 1 observe (log only); 2 apply */
#endif
#ifndef LI_T
#define LI_T 1.5            /* s: solve time */
#endif
#ifndef LI_T2
#define LI_T2 0.0           /* s: retry time when the first solve is rejected (0: none) */
#endif
#ifndef LI_MINOBS
#define LI_MINOBS 6         /* frames a feature must be seen in */
#endif
#ifndef LI_GTOL
#define LI_GTOL 0.15        /* | |g_LS| / GRAVITY - 1 | above this: reject */
#endif
#ifndef LI_SGMAX
#define LI_SGMAX 3.0        /* deg: max sd of the gravity direction */
#endif
#ifndef LI_SVMAX
#define LI_SVMAX 0.25       /* m/s: max sd (norm) of v0 */
#endif
#ifndef LI_DV
#define LI_DV 0.0           /* apply only if |v_cf - v_filter| (m/s) > LI_DV or tilt difference (deg) > LI_DTH */
#endif
#ifndef LI_DTH
#define LI_DTH 0.0
#endif
#ifndef LI_PCOV
#define LI_PCOV 0           /* 1: velocity block of P <- closed-form covariance (x LI_PINF), cross terms of V cleared */
#endif
#ifndef LI_PINF
#define LI_PINF 4.0
#endif
#ifndef LI_POS
#define LI_POS 1            /* 1: replace position (and clone positions) by the closed-form trajectory; 0: keep */
#endif
#ifndef LI_STATIC
#define LI_STATIC 0         /* 1: also for static (hover) starts */
#endif
#ifndef LI_MAPFLUSH
#define LI_MAPFLUSH 1
#endif
#if LI_MODE
#define LI_NF 64            /* recorded frames (3.2 s) */
#define LI_MAXG 1024
static int li_nf, li_state, li_clf[64], li_lastclone;
static int li_have_net; static double li_net_mu[3], li_net_sd[3];
static double li_next;
static double li_t0, li_ft[LI_NF], li_fR[LI_NF][9], li_fa[LI_NF][3], li_fb[LI_NF][3];
static int li_fn[LI_NF], li_fg[LI_NF][MAX_TRACKS];
static float li_fx[LI_NF][MAX_TRACKS], li_fy[LI_NF][MAX_TRACKS];
static double li_Ri[9], li_al[3], li_be[3], li_tl;
static int li_gcnt[LI_MAXG], li_gfirst[LI_MAXG];
static double li_gw[LI_MAXG];
static void li_reset(double t) {
    li_genc = 0; li_nf = 0; li_state = 0; li_have_net = 0; li_next = LI_T; li_t0 = t; li_tl = t; li_lastclone = -1;
    for (int i = 0; i < MAX_TRACKS; i++) li_gen[i] = tracks[i].alive ? li_genc++ : -1;
    memcpy(li_Ri, I3, sizeof li_Ri); memset(li_al, 0, sizeof li_al); memset(li_be, 0, sizeof li_be);
}
static void li_imu(const double *imu, int n) { /* preintegration in body-0 axes with the filter's current bias estimates */
    if (li_state || li_nf >= LI_NF) return;
    for (int r = 0; r < n; r++) {
        const double *row = imu + 7 * r;
        double dt = row[0] - li_tl;
        if (dt <= 0) continue;
        li_tl = row[0];
        double w[3], a[3], Ra[3], dR[9], Rn[9];
        for (int i = 0; i < 3; i++) { w[i] = (row[4 + i] - bg[i]) * dt; a[i] = row[1 + i] - ba[i]; }
        m3vec(li_Ri, a, Ra);
        for (int i = 0; i < 3; i++) { li_al[i] += li_be[i] * dt + 0.5 * Ra[i] * dt * dt; li_be[i] += Ra[i] * dt; }
        exp_so3(w, dR); m3mul(li_Ri, dR, Rn); memcpy(li_Ri, Rn, sizeof Rn);
    }
}
static void li_record(void) {
    if (li_state || li_nf >= LI_NF) return;
    if (!li_have_net && lc_active && lc_applied && tc_nanch == 0) {
        li_have_net = 1;
        for (int i = 0; i < 3; i++) {
            double lv = lc_out[9 + i]; lv = lv < -7 ? -7 : lv > 4 ? 4 : lv;
            double s = LC_SCALE * exp(0.5 * lv); li_net_sd[i] = s < LC_FLOOR ? LC_FLOOR : s; li_net_mu[i] = lc_out[6 + i];
        }
    }
    int k = li_nf++, n = 0;
    li_ft[k] = li_tl - li_t0;
    memcpy(li_fR[k], li_Ri, sizeof li_Ri); memcpy(li_fa[k], li_al, sizeof li_al); memcpy(li_fb[k], li_be, sizeof li_be);
    for (int i = 0; i < MAX_TRACKS; i++) {
        if (!tracks[i].alive || li_gen[i] < 0 || li_gen[i] >= LI_MAXG) continue;
        li_fg[k][n] = li_gen[i]; li_fx[k][n] = (float)((tracks[i].x - cx) / fx); li_fy[k][n] = (float)((tracks[i].y - cy) / fy); n++;
    }
    li_fn[k] = n;
#ifdef LI_DUMP
    fprintf(stderr, "LF %d %.6f", k, li_ft[k]); for (int i = 0; i < 9; i++) fprintf(stderr, " %.9f", li_Ri[i]); for (int i = 0; i < 3; i++) fprintf(stderr, " %.9f", li_al[i]); for (int i = 0; i < 3; i++) fprintf(stderr, " %.9f", li_be[i]); fprintf(stderr, "\n");
    for (int m = 0; m < n; m++) fprintf(stderr, "LO %d %d %.7f %.7f\n", k, li_fg[k][m], li_fx[k][m], li_fy[k][m]);
    if (k == 0) { fprintf(stderr, "LX"); for (int i = 0; i < 9; i++) fprintf(stderr, " %.9f", R_bc[i]); for (int i = 0; i < 3; i++) fprintf(stderr, " %.9f", p_bc[i]); fprintf(stderr, " %.6f %.6f %.6f %.6f\n", fx, fy, cx, cy); }
#endif
    if (nclones > 0 && clones[nclones - 1].id != li_lastclone) { li_lastclone = clones[nclones - 1].id; li_clf[li_lastclone & 63] = k; }
}
static void li_bearing(int k, double x, double y, double *d) { /* unit bearing of a frame-k observation in body-0 axes */
    double ray[3] = {x, y, 1.0}, rb[3], nn = sqrt(x * x + y * y + 1.0);
    for (int i = 0; i < 3; i++) ray[i] /= nn;
    m3vec(R_bc, ray, rb); m3vec(li_fR[k], rb, d);
}
/* one pass over all observations: accumulate the Schur-reduced 6x6 normal equations (pass 0) or residuals (pass 1) */
static double li_lam[LI_MAXG], li_res[LI_MAXG];
#ifndef LI_NET
#define LI_NET 1            /* 1: the startup net's body velocity at frame LC_K enters the LS as a prior (fixes the scale) */
#endif
#ifndef LI_PIX
#define LI_PIX 1.5          /* px: vision noise used to weight the net prior against the bearing rows */
#endif
#ifndef LI_D0
#define LI_D0 3.0           /* m: typical depth (unweighted first pass) */
#endif
static void li_netprior(double *H, double *rhs, int it) {
    if (!LI_NET || !li_have_net || LC_K >= li_nf) return;
    int k = LC_K;
    for (int a = 0; a < 3; a++) {
        double row[6], w = LI_PIX / fx / li_net_sd[a] * (it == 0 ? LI_D0 : 1.0), b = li_net_mu[a];
        for (int c = 0; c < 3; c++) { row[c] = li_fR[k][3 * c + a]; row[3 + c] = li_fR[k][3 * c + a] * li_ft[k]; b -= li_fR[k][3 * c + a] * li_fb[k][c]; }
        for (int i = 0; i < 6; i++) { for (int j = 0; j < 6; j++) H[i * 6 + j] += w * w * row[i] * row[j]; rhs[i] += w * w * row[i] * b; }
    }
}
static int li_pass(double *H, double *rhs, const double *x, int pass, int nlast) {
    int used = 0;
    double AtA[36], Ata[6], ata, Atb[6], atb;
    for (int g = 0; g < li_genc && g < LI_MAXG; g++) {
        if (li_gcnt[g] < LI_MINOBS || li_gw[g] <= 0) continue;
        int k = li_gfirst[g];
        double dk[3], xk = 0, yk = 0;
        for (int m = 0; m < li_fn[k]; m++) if (li_fg[k][m] == g) { xk = li_fx[k][m]; yk = li_fy[k][m]; break; }
        li_bearing(k, xk, yk, dk);
        double pk[3]; m3vec(li_fR[k], p_bc, pk);
        memset(AtA, 0, sizeof AtA); memset(Ata, 0, sizeof Ata); memset(Atb, 0, sizeof Atb); ata = atb = 0;
        double ssr = 0; int nr = 0;
        for (int i = k + 1; i <= nlast; i++) {
            int m;
            for (m = 0; m < li_fn[i]; m++) if (li_fg[i][m] == g) break;
            if (m == li_fn[i]) continue;
            double d[3], K[9], pi[3], e[3], col[3], A[18], b[3];
            li_bearing(i, li_fx[i][m], li_fy[i][m], d);
            skew(d, K);
            m3vec(li_fR[i], p_bc, pi);
            double tk = li_ft[k], ti = li_ft[i], w = li_gw[g];
            for (int q = 0; q < 3; q++) e[q] = li_fa[k][q] - li_fa[i][q] + pk[q] - pi[q];
            m3vec(K, dk, col); m3vec(K, e, b);
            for (int r = 0; r < 3; r++) {
                col[r] *= w; b[r] = -b[r] * w;
                for (int c = 0; c < 3; c++) { A[r * 6 + c] = w * K[3 * r + c] * (tk - ti); A[r * 6 + 3 + c] = w * K[3 * r + c] * 0.5 * (tk * tk - ti * ti); }
            }
            if (pass == 0) {
                for (int r = 0; r < 3; r++) {
                    for (int a = 0; a < 6; a++) {
                        for (int c = 0; c < 6; c++) AtA[a * 6 + c] += A[r * 6 + a] * A[r * 6 + c];
                        Ata[a] += A[r * 6 + a] * col[r]; Atb[a] += A[r * 6 + a] * b[r];
                    }
                    ata += col[r] * col[r]; atb += col[r] * b[r];
                }
            } else {
                for (int r = 0; r < 3; r++) {
                    double s = col[r] * li_lam[g] - b[r];
                    for (int a = 0; a < 6; a++) s += A[r * 6 + a] * x[a];
                    ssr += s * s;
                }
                nr += 2;
            }
        }
        if (pass == 0) {
            if (ata < 1e-12) { li_gw[g] = 0; continue; }
            for (int a = 0; a < 6; a++) {
                for (int c = 0; c < 6; c++) H[a * 6 + c] += AtA[a * 6 + c] - Ata[a] * Ata[c] / ata;
                rhs[a] += Atb[a] - Ata[a] * atb / ata;
            }
            /* depth along d_k for the current x (filled when x != 0): lambda = (atb - Ata.x) / ata */
            double s = atb; for (int a = 0; a < 6; a++) s -= Ata[a] * x[a];
            li_lam[g] = s / ata;
        } else {
            li_res[g] = nr ? ssr / nr : 0;
        }
        used++;
    }
    return used;
}
static int li_solve6(const double *H, const double *r, const double *c, const double *n, double *x, double *cov5) {
    /* minimise x^T H x - 2 x^T r with x = M y + c, M = [I 0; 0 B] (B: tangent basis at n), y = (v0, dg); x out */
    double B[6], t[3] = {1, 0, 0};
    if (fabs(n[0]) > 0.8) { t[0] = 0; t[1] = 1; }
    double b1[3] = {n[1] * t[2] - n[2] * t[1], n[2] * t[0] - n[0] * t[2], n[0] * t[1] - n[1] * t[0]}, nb = sqrt(b1[0] * b1[0] + b1[1] * b1[1] + b1[2] * b1[2]);
    for (int i = 0; i < 3; i++) b1[i] /= nb;
    double b2[3] = {n[1] * b1[2] - n[2] * b1[1], n[2] * b1[0] - n[0] * b1[2], n[0] * b1[1] - n[1] * b1[0]};
    for (int i = 0; i < 3; i++) { B[2 * i] = b1[i]; B[2 * i + 1] = b2[i]; }
    double M[30] = {0}; /* 6 x 5 */
    for (int i = 0; i < 3; i++) M[i * 5 + i] = 1;
    for (int i = 0; i < 3; i++) for (int j = 0; j < 2; j++) M[(3 + i) * 5 + 3 + j] = B[2 * i + j];
    double rc[6], H5[25], r5[5], L[25];
    for (int a = 0; a < 6; a++) { double s = r[a]; for (int b = 0; b < 6; b++) s -= H[a * 6 + b] * c[b]; rc[a] = s; }
    for (int i = 0; i < 5; i++) {
        double s = 0; for (int a = 0; a < 6; a++) s += M[a * 5 + i] * rc[a]; r5[i] = s;
        for (int j = 0; j < 5; j++) { double u = 0; for (int a = 0; a < 6; a++) for (int b = 0; b < 6; b++) u += M[a * 5 + i] * H[a * 6 + b] * M[b * 5 + j]; H5[i * 5 + j] = u; }
    }
    memcpy(L, H5, sizeof L);
    if (!cholesky(L, 5)) return 0;
    chol_solve(L, 5, r5);
    for (int a = 0; a < 6; a++) { double s = c[a]; for (int i = 0; i < 5; i++) s += M[a * 5 + i] * r5[i]; x[a] = s; }
    if (cov5) for (int j = 0; j < 5; j++) { double e[5] = {0}; e[j] = 1; chol_solve(L, 5, e); for (int i = 0; i < 5; i++) cov5[i * 5 + j] = e[i]; }
    return 1;
}
static int li_try(void) {
    int N = li_nf - 1;
    if (N < 8) return 0;
    for (int g = 0; g < LI_MAXG; g++) { li_gcnt[g] = 0; li_gfirst[g] = -1; li_gw[g] = 1; }
    for (int k = 0; k <= N; k++) for (int m = 0; m < li_fn[k]; m++) { int g = li_fg[k][m]; if (li_gfirst[g] < 0) li_gfirst[g] = k; li_gcnt[g]++; }
    double H[36], rhs[6], x[6] = {0}, c[6] = {0}, n[3], cov5[25], gls = 0;
    int used = 0;
    for (int it = 0; it < 2; it++) { /* it 0: unweighted; it 1: weights 1/depth, outliers dropped */
        memset(H, 0, sizeof H); memset(rhs, 0, sizeof rhs);
        used = li_pass(H, rhs, x, 0, N);
        if (used < 8) return -1;
        li_netprior(H, rhs, it);
        double L[36]; memcpy(L, H, sizeof L);
        if (it == 0) {
            double xx[6]; memcpy(xx, rhs, sizeof xx);
            if (!cholesky(L, 6)) return -2;
            chol_solve(L, 6, xx);
            gls = sqrt(xx[3] * xx[3] + xx[4] * xx[4] + xx[5] * xx[5]);
            if (gls < 1e-6) return -3;
            for (int i = 0; i < 3; i++) n[i] = xx[3 + i] / gls;
        }
        for (int k = 0; k < 4; k++) { /* tangent refinement with |g| fixed */
            for (int i = 0; i < 3; i++) c[3 + i] = GRAVITY * n[i];
            if (!li_solve6(H, rhs, c, n, x, cov5)) return -4;
            double gn = sqrt(x[3] * x[3] + x[4] * x[4] + x[5] * x[5]);
            for (int i = 0; i < 3; i++) n[i] = x[3 + i] / gn;
        }
        for (int i = 0; i < 3; i++) x[3 + i] = GRAVITY * n[i];
        /* depths and residuals at the solution */
        memset(H, 0, sizeof H); memset(rhs, 0, sizeof rhs);
        li_pass(H, rhs, x, 0, N);
        li_pass(H, rhs, x, 1, N);
        if (it == 0) {
            double med[LI_MAXG]; int nm = 0;
            for (int g = 0; g < li_genc && g < LI_MAXG; g++) if (li_gcnt[g] >= LI_MINOBS && li_gw[g] > 0) {
                double lam = li_lam[g];
                if (lam < 0.2) { li_gw[g] = 0; continue; }
                li_gw[g] = 1.0 / lam;
                med[nm++] = li_res[g] / (lam * lam);
            }
            if (nm < 8) return -5;
            /* median of normalized residuals (selection by partial sort) */
            for (int a = 0; a <= nm / 2; a++) for (int b = a + 1; b < nm; b++) if (med[b] < med[a]) { double t = med[a]; med[a] = med[b]; med[b] = t; }
            double thr = 9.0 * med[nm / 2];
            for (int g = 0; g < li_genc && g < LI_MAXG; g++) if (li_gw[g] > 0 && li_gcnt[g] >= LI_MINOBS && li_res[g] * li_gw[g] * li_gw[g] > thr) li_gw[g] = 0;
        }
    }
    /* noise variance from the weighted residuals, covariance of (v0, dg) */
    double ssr = 0; int nobs = 0;
    for (int g = 0; g < li_genc && g < LI_MAXG; g++) if (li_gw[g] > 0 && li_gcnt[g] >= LI_MINOBS) { ssr += li_res[g] * 2 * (li_gcnt[g] - 1); nobs += 2 * (li_gcnt[g] - 1); }
    double s2 = nobs > used + 5 ? ssr / (nobs - used - 5) : 1e9;
    double sv = sqrt(s2 * (cov5[0] + cov5[6] + cov5[12])), sg = sqrt(s2 * (cov5[18] + cov5[24])) / GRAVITY * 57.29578;
    /* state at frame N in body-0 axes */
    double tN = li_ft[N], vT[3], pT[3];
    for (int i = 0; i < 3; i++) { vT[i] = x[i] + x[3 + i] * tN + li_fb[N][i]; pT[i] = x[i] * tN + 0.5 * x[3 + i] * tN * tN + li_fa[N][i]; }
    /* filter's view in body-0 axes */
    double vf[3], pf[3], gf[3], ed[3] = {0, 0, -1}, gfn[3];
    m3tvec(R0, vel, vf); m3tvec(R0, pos, pf); m3tvec(R0, ed, gfn);
    for (int i = 0; i < 3; i++) gf[i] = gfn[i];
    double dth = acos(fmin(1.0, fmax(-1.0, gf[0] * n[0] + gf[1] * n[1] + gf[2] * n[2]))) * 57.29578;
    double dv = sqrt((vT[0] - vf[0]) * (vT[0] - vf[0]) + (vT[1] - vf[1]) * (vT[1] - vf[1]) + (vT[2] - vf[2]) * (vT[2] - vf[2]));
    int ok = fabs(gls / GRAVITY - 1.0) < LI_GTOL && sv < LI_SVMAX && sg < LI_SGMAX;
    int apply = ok && (dv > LI_DV || dth > LI_DTH);
#ifdef LI_DBG
    { double gc[3], vc[3], pc[3], gfc[3], vfc[3], pfc[3]; double Rcb[9]; for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) Rcb[3 * i + j] = R_bc[3 * j + i];
      double up[3] = {-n[0], -n[1], -n[2]}, upf[3] = {-gf[0], -gf[1], -gf[2]};
      double pTc[3], pfc0[3], l1[3], l2[3], Rr[9]; m3vec(li_fR[N], p_bc, l1); m3tmul(R0, R, Rr); m3vec(Rr, p_bc, l2); for (int i = 0; i < 3; i++) { pTc[i] = pT[i] + l1[i] - p_bc[i]; pfc0[i] = pf[i] + l2[i] - p_bc[i]; }
      m3vec(Rcb, up, gc); m3vec(Rcb, vT, vc); m3vec(Rcb, pTc, pc); m3vec(Rcb, upf, gfc); m3vec(Rcb, vf, vfc); m3vec(Rcb, pfc0, pfc);
      fprintf(stderr, "LI t=%.3f N=%d used=%d gls=%.3f sv=%.3f sg=%.2f dv=%.3f dth=%.2f ok=%d apply=%d | up_cf %.5f %.5f %.5f v_cf %.4f %.4f %.4f p_cf %.4f %.4f %.4f | up_f %.5f %.5f %.5f v_f %.4f %.4f %.4f p_f %.4f %.4f %.4f\n",
              tN, N, used, gls, sv, sg, dv, dth, ok, apply, gc[0], gc[1], gc[2], vc[0], vc[1], vc[2], pc[0], pc[1], pc[2], gfc[0], gfc[1], gfc[2], vfc[0], vfc[1], vfc[2], pfc[0], pfc[1], pfc[2]); }
#endif
    if (!ok) return -6;
    if (!apply || LI_MODE < 2) return 1;
    /* rewrite: Q (body-0) maps n -> gf; R0' = R0 Q; world left rotation Qm = R0 Q R0^T */
    double ax[3] = {n[1] * gf[2] - n[2] * gf[1], n[2] * gf[0] - n[0] * gf[2], n[0] * gf[1] - n[1] * gf[0]};
    double sa = sqrt(ax[0] * ax[0] + ax[1] * ax[1] + ax[2] * ax[2]), ca = n[0] * gf[0] + n[1] * gf[1] + n[2] * gf[2], Q[9], Qm[9], T1[9], R0n[9];
    double ang = atan2(sa, ca), wv[3] = {0, 0, 0};
    if (sa > 1e-12) for (int i = 0; i < 3; i++) wv[i] = ax[i] / sa * ang;
    exp_so3(wv, Q);
    m3mul(R0, Q, R0n);
    { double R0t[9]; for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) R0t[3 * i + j] = R0[3 * j + i]; m3mul(R0n, R0t, Qm); }
    m3mul(Qm, R, T1); memcpy(R, T1, sizeof T1);
    for (int cc = 0; cc < nclones; cc++) { m3mul(Qm, clones[cc].R, T1); memcpy(clones[cc].R, T1, sizeof T1); }
    memcpy(R0, R0n, sizeof R0n);
    m3vec(R0, vT, vel);
    if (LI_POS) {
        m3vec(R0, pT, pos);
        for (int cc = 0; cc < nclones; cc++) {
            int k = li_clf[clones[cc].id & 63];
            if (clones[cc].id > li_lastclone || li_lastclone - clones[cc].id >= 64 || k < 0 || k > N) { double pp[3]; m3vec(Qm, clones[cc].p, pp); memcpy(clones[cc].p, pp, sizeof pp); continue; }
            double pk[3]; for (int i = 0; i < 3; i++) pk[i] = x[i] * li_ft[k] + 0.5 * x[3 + i] * li_ft[k] * li_ft[k] + li_fa[k][i];
            m3vec(R0, pk, clones[cc].p);
        }
    } else {
        double pp[3]; m3vec(Qm, pos, pp); memcpy(pos, pp, sizeof pp);
        for (int cc = 0; cc < nclones; cc++) { m3vec(Qm, clones[cc].p, pp); memcpy(clones[cc].p, pp, sizeof pp); }
    }
    if (LI_PCOV) {
        double Cv[9], C2[9], Ct[9];
        for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) Cv[3 * i + j] = LI_PINF * s2 * cov5[i * 5 + j];
        m3mul(R0, Cv, C2); for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) Ct[3 * i + j] = R0[3 * j + i]; m3mul(C2, Ct, Cv);
        for (int i = 0; i < 3; i++) for (int j = 0; j < D; j++) { Pm[(V + i) * MAXD + j] = 0; Pm[j * MAXD + V + i] = 0; }
        for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) Pm[(V + i) * MAXD + V + j] = Cv[3 * i + j] + (i == j ? 0.01 : 0);
    }
#if MAP_MODE
    if (LI_MAPFLUSH) for (int k = 0; k < MAP_N; k++) mp[k].valid = 0;
#endif
    return 2;
}
static void li_step(void) {
    if (li_state || !(moving || LI_STATIC)) return;
    double tt = li_tl - li_t0;
    if (tt + 1e-6 < li_next) return;
    if (lc_active && (!lc_applied || (tc_nanch > 0 && lc_next < 6))) return; /* a net measurement is in flight */
    int r = li_try();
    if (r <= 0 && LI_T2 > li_next && li_nf < LI_NF) { li_next = LI_T2; return; }
    li_state = 1;
}
#endif
