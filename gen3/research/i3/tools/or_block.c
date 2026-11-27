/* ===================== i3 ORACLE HARNESS (offline diagnostics ONLY; reads an embedded GT table) ===================== */
#if OR
static const unsigned char or_blob[] = {
#embed OR_TAB
};
static double or_Rfg[9], or_pg0[3], or_dsd, or_scale, or_ar[16][3], or_bias[16][3], or_arT[16];
static int or_nf, or_off, or_N;
static unsigned long long or_rng;
static double or_Rh[64][9], or_dvh[64][3], or_vpre[3];
enum { C_VEL, C_SPD, C_DIR, C_VZ, C_GRAV, C_BG, C_BA, C_ROT, C_RT, C_DZ, C_ALT, C_POS, C_DEP, C_COR };
/* consistency accumulators */
static double or_s[40]; static long or_cnt; static long or_tri_h[8];
static double or_u01(void) { or_rng ^= or_rng << 13; or_rng ^= or_rng >> 7; or_rng ^= or_rng << 17; return ((or_rng >> 11) + 0.5) / 9007199254740992.0; }
static double or_gauss(void) { double u1 = or_u01(), u2 = or_u01(); return sqrt(-2 * log(u1)) * cos(6.283185307179586 * u2); }
static double or_hgauss(unsigned long long h) { /* deterministic gaussian from a hash (same draw on repeated calls) */
    unsigned long long s = or_rng; or_rng = h * 0x9E3779B97F4A7C15ull + 0x632BE59BD9B4E019ull; if (!or_rng) or_rng = 1;
    for (int i = 0; i < 3; i++) or_u01();
    double g = or_gauss(); or_rng = s; return g;
}
/* additive noise sample (actual sd = OR_NK * sd) of type OR_NT for channel ch, component i; dtev = time since last event of ch */
static double or_noise(int ch, int i, double sd, double t) {
    double s = OR_NK * sd;
#if OR_NT == 0
    return s * or_gauss();
#elif OR_NT == 1
    double dtev = t - or_arT[ch]; if (i == 2 || ch == C_SPD || ch == C_VZ || ch == C_ALT || ch == C_DZ) or_arT[ch] = t;
    double rho = exp(-(dtev > 0 ? dtev : 0) / OR_TAU); if (or_arT[ch] < -1e8) rho = 0;
    or_ar[ch][i] = rho * or_ar[ch][i] + sqrt(1 - rho * rho) * s * or_gauss(); return or_ar[ch][i];
#elif OR_NT == 2
    (void)t; return s * or_bias[ch][i];
#else
    (void)t; return or_u01() < OR_OUTP ? OR_OUTK * s * or_gauss() : s * or_gauss();
#endif
}
static void or_q2m(const double *q, double *m) { /* xyzw */
    double x = q[0], y = q[1], z = q[2], w = q[3], n = sqrt(x * x + y * y + z * z + w * w); x /= n; y /= n; z /= n; w /= n;
    m[0] = 1 - 2 * (y * y + z * z); m[1] = 2 * (x * y - z * w); m[2] = 2 * (x * z + y * w);
    m[3] = 2 * (x * y + z * w); m[4] = 1 - 2 * (x * x + z * z); m[5] = 2 * (y * z - x * w);
    m[6] = 2 * (x * z - y * w); m[7] = 2 * (y * z + x * w); m[8] = 1 - 2 * (x * x + y * y);
}
static void or_log(const double *m, double *w) {
    double c = (m[0] + m[4] + m[8] - 1) * 0.5; c = c > 1 ? 1 : c < -1 ? -1 : c;
    double a = acos(c), s = sin(a), f = a < 1e-9 ? 0.5 : a / (2 * s);
    w[0] = f * (m[7] - m[5]); w[1] = f * (m[2] - m[6]); w[2] = f * (m[3] - m[1]);
}
/* GT at frame k in the filter frame F: body->F rotation, body position (rel. frame 0), world velocity, biases */
static void or_gt(int k, double *Rfb, double *pf, double *vf, double *bgt, double *bat) {
    if (k < 0) k = 0; if (k >= or_N) k = or_N - 1;
    float f[16]; memcpy(f, or_blob + or_off + (size_t)k * 64, 64);
    double q[4] = {f[3], f[4], f[5], f[6]}, Rgb[9], d[3] = {f[0] - or_pg0[0], f[1] - or_pg0[1], f[2] - or_pg0[2]}, vg[3] = {f[7], f[8], f[9]};
    or_q2m(q, Rgb);
    if (Rfb) m3mul(or_Rfg, Rgb, Rfb);
    if (pf) m3vec(or_Rfg, d, pf);
    if (vf) m3vec(or_Rfg, vg, vf);
    if (bgt) for (int i = 0; i < 3; i++) bgt[i] = f[10 + i];
    if (bat) for (int i = 0; i < 3; i++) bat[i] = f[13 + i];
}
static void or_init(const double *imu) {
    or_k = 0; or_i = -1; int n; memcpy(&n, or_blob, 4);
    for (int i = 0; i < n; i++) {
        double key[3]; memcpy(key, or_blob + 4 + 32 * i, 24);
        if (fabs(imu[1] - key[0]) < 1e-7 && fabs(imu[2] - key[1]) < 1e-7 && fabs(imu[3] - key[2]) < 1e-7) { or_i = i; break; }
    }
    memset(or_s, 0, sizeof or_s); or_cnt = 0; memset(or_tri_h, 0, sizeof or_tri_h);
    if (or_i < 0) { fprintf(stderr, "ORX nomatch\n"); return; }
    int off; memcpy(&or_N, or_blob + 4 + 32 * or_i + 24, 4); memcpy(&off, or_blob + 4 + 32 * or_i + 28, 4);
    int hdr = 4 + 32 * n; or_off = hdr + 4 * off;
    float f[16]; memcpy(f, or_blob + or_off, 64);
    double q[4] = {f[3], f[4], f[5], f[6]}, Rgb[9], u[3], A[9];
    or_q2m(q, Rgb); u[0] = Rgb[6]; u[1] = Rgb[7]; u[2] = Rgb[8]; /* R_gb^T e_z */
    align_to_z(u, A);
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) or_Rfg[3 * i + j] = A[3 * i] * Rgb[3 * j] + A[3 * i + 1] * Rgb[3 * j + 1] + A[3 * i + 2] * Rgb[3 * j + 2];
    for (int i = 0; i < 3; i++) or_pg0[i] = f[i];
    or_rng = 0x2545F4914F6CDD1Dull ^ ((unsigned long long)(or_i + 1) * 1000003ull) ^ ((unsigned long long)OR_SEED << 32); if (!or_rng) or_rng = 7;
    for (int c = 0; c < 16; c++) { or_arT[c] = -1e9; for (int i = 0; i < 3; i++) { or_ar[c][i] = 0; or_bias[c][i] = or_gauss(); } }
    or_scale = OR_SCALE * or_gauss();
}
static void or_pre(void) { memcpy(or_vpre, vel, sizeof vel); }
static void or_postprop(void) { for (int i = 0; i < 3; i++) or_dvh[or_k & 63][i] = vel[i] - or_vpre[i]; }
static double or_H[3 * MAXD];
static int or_upd(double *r, int k, double sd) { /* rows in or_H (unscaled), residual r; assumed sd */
    for (int a = 0; a < k; a++) { r[a] /= sd; for (int j = 0; j < D; j++) or_H[a * MAXD + j] /= sd; }
    upd_reuse = 0;
    return update(r, or_H, k, 1.0, OR_GATE > 0 ? OR_GATE : INFINITY);
}
static int or_sched(int k, int ev, int t0, int t1) { return k >= t0 && k <= t1 && (k - t0) % ev == 0; }
static int or_clone_age(int want) { /* clone index whose frame age is closest to want (age > 0) */
    int best = -1, bd = 1 << 30;
    for (int c = 0; c < nclones; c++) { int age = or_k - or_cfr[clones[c].id & 1023]; if (age <= 0) continue; int d = abs(age - want); if (d < bd) { bd = d; best = c; } }
    return best;
}
static void or_step(void) {
    if (or_i < 0) return;
    int k = or_k; double t = k * 0.05;
    double Rt[9], pt[3], vt[3], bgt[3], bat[3], r[3];
    or_gt(k, Rt, pt, vt, bgt, bat);
#if OR_VEL_ON
    if (or_sched(k, OR_VEL_EV, OR_VEL_T0, OR_VEL_T1) && k - OR_VEL_LAT >= 0) {
        int kk = k - OR_VEL_LAT; double Rk[9], vk[3], vb[3];
        or_gt(kk, Rk, 0, vk, 0, 0); m3tvec(Rk, vk, vb);
        memset(or_H, 0, sizeof or_H);
#if OR_VEL_MODE == 0
        double z[3], h[3], sk[9];
        for (int i = 0; i < 3; i++) z[i] = vb[i] * (1 + or_scale) + or_noise(C_VEL, i, OR_VEL, t);
        if (OR_VEL_LAT > 0) { /* compensate the latency with the filter's own history: R(kk) z + sum of IMU dv since kk */
            double zw[3]; m3vec(or_Rh[kk & 63], z, zw);
            for (int j = kk + 1; j <= k; j++) for (int i = 0; i < 3; i++) zw[i] += or_dvh[j & 63][i];
            m3tvec(R, zw, z);
        }
        m3tvec(R, vel, h); skew(h, sk);
        for (int i = 0; i < 3; i++) { r[i] = z[i] - h[i]; for (int j = 0; j < 3; j++) { or_H[i * MAXD + V + j] = R[3 * j + i]; or_H[i * MAXD + TH + j] = sk[3 * i + j]; } }
        or_upd(r, 3, OR_VEL);
#elif OR_VEL_MODE == 1
        double s = sqrt(vel[0] * vel[0] + vel[1] * vel[1] + vel[2] * vel[2]);
        if (s > 1e-3) {
            r[0] = sqrt(vb[0] * vb[0] + vb[1] * vb[1] + vb[2] * vb[2]) * (1 + or_scale) + or_noise(C_SPD, 0, OR_VEL, t) - s;
            for (int j = 0; j < 3; j++) or_H[V + j] = vel[j] / s;
            or_upd(r, 1, OR_VEL);
        }
#elif OR_VEL_MODE == 2
        double sb = sqrt(vb[0] * vb[0] + vb[1] * vb[1] + vb[2] * vb[2]), s = sqrt(vel[0] * vel[0] + vel[1] * vel[1] + vel[2] * vel[2]);
        if (sb > 0.3 && s > 0.05) {
            double z[3], h[3], sk[9], zn = 0, M[9];
            for (int i = 0; i < 3; i++) { z[i] = vb[i] / sb + or_noise(C_DIR, i, OR_VEL, t); zn += z[i] * z[i]; }
            zn = sqrt(zn); for (int i = 0; i < 3; i++) z[i] /= zn;
            m3tvec(R, vel, h); for (int i = 0; i < 3; i++) h[i] /= s; skew(h, sk);
            for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { double a = 0; for (int q = 0; q < 3; q++) a += ((i == q) - h[i] * h[q]) * R[3 * j + q]; M[3 * i + j] = a / s; }
            for (int i = 0; i < 3; i++) { r[i] = z[i] - h[i]; for (int j = 0; j < 3; j++) { or_H[i * MAXD + V + j] = M[3 * i + j]; or_H[i * MAXD + TH + j] = sk[3 * i + j]; } }
            or_upd(r, 3, OR_VEL);
        }
#else
        r[0] = vk[2] * (1 + or_scale) + or_noise(C_VZ, 0, OR_VEL, t) - vel[2]; or_H[V + 2] = 1; or_upd(r, 1, OR_VEL);
#endif
    }
#endif
#if OR_GRAV_ON
    if (or_sched(k, OR_GRAV_EV, 0, OR_GRAV_T1)) {
        double z[3], h[3], sk[9], zn = 0;
        for (int i = 0; i < 3; i++) { z[i] = Rt[6 + i] + or_noise(C_GRAV, i, OR_GRAV, t); zn += z[i] * z[i]; }
        zn = sqrt(zn); for (int i = 0; i < 3; i++) z[i] /= zn;
        for (int i = 0; i < 3; i++) h[i] = R[6 + i];
        skew(h, sk); memset(or_H, 0, sizeof or_H);
        for (int i = 0; i < 3; i++) { r[i] = z[i] - h[i]; for (int j = 0; j < 3; j++) or_H[i * MAXD + TH + j] = sk[3 * i + j]; }
        or_upd(r, 3, OR_GRAV);
    }
#endif
#if OR_BG_ON
    if (or_sched(k, OR_BG_EV, 0, OR_BG_T1)) {
        memset(or_H, 0, sizeof or_H);
        for (int i = 0; i < 3; i++) { r[i] = bgt[i] + or_noise(C_BG, i, OR_BG, t) - bg[i]; or_H[i * MAXD + BG + i] = 1; }
        or_upd(r, 3, OR_BG);
    }
#endif
#if OR_BA_ON
    if (or_sched(k, OR_BA_EV, 0, OR_BA_T1)) {
        memset(or_H, 0, sizeof or_H);
        for (int i = 0; i < 3; i++) { r[i] = bat[i] + or_noise(C_BA, i, OR_BA, t) - ba[i]; or_H[i * MAXD + BA + i] = 1; }
        or_upd(r, 3, OR_BA);
    }
#endif
#if OR_ROT_ON
    if (or_sched(k, OR_ROT_EV, 1, OR_ROT_T1)) {
        double Z[9], Ra[9], hM[9], E[9], w[3], n[3], En[9], Z2[9], Mx[9];
        const double *Rref; int col;
        if (OR_ROT_MODE == 0) { or_gt(0, Ra, 0, 0, 0, 0); Rref = R0; col = TH0; }
        else { int c = or_clone_age(1); if (c < 0) goto rot_done; or_gt(or_cfr[clones[c].id & 1023], Ra, 0, 0, 0, 0); Rref = clones[c].R; col = CORE + 6 * c; }
        m3tmul(Ra, Rt, Z);
        for (int i = 0; i < 3; i++) n[i] = or_noise(C_ROT, i, OR_ROT, t);
        exp_so3(n, En); m3mul(Z, En, Z2);
        m3tmul(Rref, R, hM); m3tmul(hM, Z2, E); or_log(E, w);
        m3tmul(R, Rref, Mx); memset(or_H, 0, sizeof or_H);
        for (int i = 0; i < 3; i++) { r[i] = w[i]; or_H[i * MAXD + TH + i] = 1; for (int j = 0; j < 3; j++) or_H[i * MAXD + col + j] = -Mx[3 * i + j]; }
        or_upd(r, 3, OR_ROT);
    }
rot_done:;
#endif
#if OR_RT_ON || OR_DZ_ON
    if (or_sched(k, OR_RT_EV, OR_RT_EV, 1 << 30)) {
        int c = or_clone_age(OR_RT_SPAN);
        if (c >= 0) {
            int kc = or_cfr[clones[c].id & 1023]; double Rc[9], pc[3], d[3], z[3], h[3], sk[9], tmp[3];
            or_gt(kc, Rc, pc, 0, 0, 0);
            for (int i = 0; i < 3; i++) d[i] = pt[i] - pc[i];
            int col = CORE + 6 * c; memset(or_H, 0, sizeof or_H);
#if OR_RT_ON
            double nd = sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]), sd = OR_RT * nd + OR_RT_ABS;
            m3tvec(Rc, d, z);
            for (int i = 0; i < 3; i++) z[i] = z[i] * (1 + or_scale) + or_noise(C_RT, i, sd, t);
            for (int i = 0; i < 3; i++) tmp[i] = pos[i] - clones[c].p[i];
            m3tvec(clones[c].R, tmp, h); skew(h, sk);
            for (int i = 0; i < 3; i++) { r[i] = z[i] - h[i];
                for (int j = 0; j < 3; j++) { or_H[i * MAXD + P + j] = clones[c].R[3 * j + i]; or_H[i * MAXD + col + 3 + j] = -clones[c].R[3 * j + i]; or_H[i * MAXD + col + j] = sk[3 * i + j]; } }
            or_upd(r, 3, sd);
#else
            r[0] = d[2] * (1 + or_scale) + or_noise(C_DZ, 0, OR_DZ, t) - (pos[2] - clones[c].p[2]);
            or_H[P + 2] = 1; or_H[col + 5] = -1; or_upd(r, 1, OR_DZ);
#endif
        }
    }
#endif
#if OR_ALT_ON
    if (or_sched(k, OR_ALT_EV, OR_ALT_EV, 1 << 30)) {
        memset(or_H, 0, sizeof or_H); r[0] = pt[2] + or_noise(C_ALT, 0, OR_ALT, t) - pos[2]; or_H[P + 2] = 1; or_upd(r, 1, OR_ALT);
    }
#endif
#if OR_POS_ON
    if (or_sched(k, OR_POS_EV, OR_POS_EV, 1 << 30)) {
        memset(or_H, 0, sizeof or_H);
        for (int i = 0; i < 3; i++) { r[i] = pt[i] + or_noise(C_POS, i, OR_POS, t) - pos[i]; or_H[i * MAXD + P + i] = 1; }
        or_upd(r, 3, OR_POS);
    }
#endif
    memcpy(or_Rh[k & 63], R, sizeof R);
    /* ---- consistency (NEES) vs GT, after all updates of this frame ---- */
    {
        double ev[3], ep[3], E[9], w[3], ww[3], A[9], x[3], sk2;
        for (int i = 0; i < 3; i++) { ev[i] = vel[i] - vt[i]; ep[i] = pos[i] - pt[i]; }
        m3tmul(Rt, R, E); or_log(E, w); m3vec(R, w, ww);
        double nees[5] = {0, 0, 0, 0, 0}; int blk[5] = {V, P, TH, BG, BA}; double *er[5] = {ev, ep, w, 0, 0}, eb[3], ea[3];
        for (int i = 0; i < 3; i++) { eb[i] = bg[i] - bgt[i]; ea[i] = ba[i] - bat[i]; } er[3] = eb; er[4] = ea;
        for (int b = 0; b < 5; b++) {
            for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) A[3 * i + j] = Pm[(blk[b] + i) * MAXD + blk[b] + j];
            nees[b] = solve3(A, er[b], x) ? er[b][0] * x[0] + er[b][1] * x[1] + er[b][2] * x[2] : 0;
        }
        /* tilt: world-frame xy components of the orientation error, P_w = R P R^T */
        double Pw[9], T1[9], Pt[9];
        for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) Pt[3 * i + j] = Pm[(TH + i) * MAXD + TH + j];
        m3mul(R, Pt, T1); for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) Pw[3 * i + j] = T1[3 * i] * R[3 * j] + T1[3 * i + 1] * R[3 * j + 1] + T1[3 * i + 2] * R[3 * j + 2];
        double dt2 = Pw[0] * Pw[4] - Pw[1] * Pw[3], ntilt = dt2 > 1e-300 ? (ww[0] * (Pw[4] * ww[0] - Pw[1] * ww[1]) + ww[1] * (Pw[0] * ww[1] - Pw[3] * ww[0])) / dt2 : 0;
        sk2 = ww[0] * ww[0] + ww[1] * ww[1];
        if (k >= 20) {
            int q = 0;
            for (int b = 0; b < 5; b++) or_s[q++] += nees[b];
            or_s[q++] += ntilt;
            or_s[q++] += ev[0] * ev[0] + ev[1] * ev[1] + ev[2] * ev[2]; or_s[q++] += Pm[V * MAXD + V] + Pm[(V + 1) * MAXD + V + 1] + Pm[(V + 2) * MAXD + V + 2];
            or_s[q++] += ep[0] * ep[0] + ep[1] * ep[1] + ep[2] * ep[2]; or_s[q++] += Pm[P * MAXD + P] + Pm[(P + 1) * MAXD + P + 1] + Pm[(P + 2) * MAXD + P + 2];
            or_s[q++] += sk2; or_s[q++] += Pw[0] + Pw[4];
            or_s[q++] += ww[2] * ww[2]; or_s[q++] += Pw[8];
            or_s[q++] += eb[0] * eb[0] + eb[1] * eb[1] + eb[2] * eb[2]; or_s[q++] += Pm[BG * MAXD + BG] + Pm[(BG + 1) * MAXD + BG + 1] + Pm[(BG + 2) * MAXD + BG + 2];
            or_s[q++] += ea[0] * ea[0] + ea[1] * ea[1] + ea[2] * ea[2]; or_s[q++] += Pm[BA * MAXD + BA] + Pm[(BA + 1) * MAXD + BA + 1] + Pm[(BA + 2) * MAXD + BA + 2];
            or_s[q++] += ev[2] * ev[2]; or_s[q++] += Pm[(V + 2) * MAXD + V + 2];
            or_s[q++] += ep[2] * ep[2]; or_s[q++] += Pm[(P + 2) * MAXD + P + 2];
            or_s[q++] += nees[0] > 11.34; or_s[q++] += nees[1] > 11.34; or_s[q++] += ntilt > 9.21; /* 99% chi2 exceedance */
            or_cnt++;
        }
        if (k == or_N - 1) {
            fprintf(stderr, "ORS %d %ld", or_i, or_cnt);
            for (int q = 0; q < 25; q++) fprintf(stderr, " %.6g", or_s[q] / (or_cnt ? or_cnt : 1));
            fprintf(stderr, "\nORF");
            for (int q = 0; q < 8; q++) fprintf(stderr, " %ld", or_tri_h[q]);
            fprintf(stderr, "\n");
        }
    }
}
/* GT-pose triangulation of a feature track (positions in F), rms reprojection residual in px (-1: failed) */
static double or_tri(int n, double (*Rw)[9], double (*pw)[3], const double *x, const double *y, double *pf) {
    double A[9] = {0}, b[3] = {0};
    for (int k = 0; k < n; k++) {
        double bc[3] = {x[k], y[k], 1}, bw[3]; m3vec(Rw[k], bc, bw);
        double nn = sqrt(bw[0] * bw[0] + bw[1] * bw[1] + bw[2] * bw[2]); for (int i = 0; i < 3; i++) bw[i] /= nn;
        for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { double m = (i == j) - bw[i] * bw[j]; A[3 * i + j] += m; b[i] += m * pw[k][j]; }
    }
    double lmin, lmax; sym3_eig_minmax(A, &lmin, &lmax); if (lmin < 1e-5 * lmax || !solve3(A, b, pf)) return -1;
    for (int it = 0; it < 3; it++) {
        double JtJ[9] = {0}, Jtr[3] = {0}, dx[3];
        for (int k = 0; k < n; k++) {
            double d[3] = {pf[0] - pw[k][0], pf[1] - pw[k][1], pf[2] - pw[k][2]}, pc[3]; m3tvec(Rw[k], d, pc);
            if (pc[2] < 0.05) return -1;
            double iz = 1 / pc[2], J[6], jp[6] = {iz, 0, -pc[0] * iz * iz, 0, iz, -pc[1] * iz * iz}, rv[2] = {x[k] - pc[0] * iz, y[k] - pc[1] * iz};
            for (int r2 = 0; r2 < 2; r2++) for (int c = 0; c < 3; c++) J[3 * r2 + c] = jp[3 * r2] * Rw[k][c] + jp[3 * r2 + 1] * Rw[k][3 + c] + jp[3 * r2 + 2] * Rw[k][6 + c];
            for (int i = 0; i < 3; i++) { Jtr[i] += J[i] * rv[0] + J[3 + i] * rv[1]; for (int j = 0; j < 3; j++) JtJ[3 * i + j] += J[i] * J[j] + J[3 + i] * J[3 + j]; }
        }
        if (!solve3(JtJ, Jtr, dx)) return -1;
        for (int i = 0; i < 3; i++) pf[i] += dx[i];
    }
    double s = 0;
    for (int k = 0; k < n; k++) {
        double d[3] = {pf[0] - pw[k][0], pf[1] - pw[k][1], pf[2] - pw[k][2]}, pc[3]; m3tvec(Rw[k], d, pc);
        if (pc[2] < 0.05) return -1;
        double ex = x[k] - pc[0] / pc[2], ey = y[k] - pc[1] / pc[2]; s += ex * ex + ey * ey;
    }
    return sqrt(s / n) * fx;
}
/* feature hook (after triangulation): perfect correspondences (OR_COR) and/or a depth measurement (OR_DEP).
   returns -1 drop the feature, 1 a depth row is to be added (*dz = measured anchor depth), 0 nothing */
static int or_feat(Obs *o, const int *ci, double *pf, double *dz) {
    if (or_i < 0 || o->n < 2) return 0;
    double Rw[MAX_OBS][9], pw[MAX_OBS][3], g[3];
    for (int k = 0; k < o->n; k++) {
        double Rb[9], pb[3], t[3]; or_gt(or_cfr[clones[ci[k]].id & 1023], Rb, pb, 0, 0, 0);
        m3mul(Rb, R_bc, Rw[k]); m3vec(Rb, p_bc, t); for (int i = 0; i < 3; i++) pw[k][i] = pb[i] + t[i];
    }
    double rms = or_tri(o->n, Rw, pw, o->x, o->y, g);
    or_tri_h[rms < 0 ? 0 : rms < 0.25 ? 1 : rms < 0.5 ? 2 : rms < 1 ? 3 : rms < 2 ? 4 : rms < 5 ? 5 : rms < 20 ? 6 : 7]++;
    unsigned long long hk = ((unsigned long long)(o->tid + 7) * 1315423911ull) ^ ((unsigned long long)o->cid[0] * 2654435761ull) ^ ((unsigned long long)OR_SEED << 40);
#if OR_COR
    if (rms < 0 || rms > OR_COR_REJ) return -1;
    for (int k = 0; k < o->n; k++) {
        double d[3] = {g[0] - pw[k][0], g[1] - pw[k][1], g[2] - pw[k][2]}, pc[3]; m3tvec(Rw[k], d, pc);
        o->x[k] = pc[0] / pc[2] + OR_COR_PX / fx * or_hgauss(hk + 2 * k + 11);
        o->y[k] = pc[1] / pc[2] + OR_COR_PX / fx * or_hgauss(hk + 2 * k + 12);
    }
    if (!triangulate(o, ci, pf)) return -1;
#endif
#if OR_DEP_ON
    if (rms < 0 || rms > OR_DEP_REJ) return 0;
    {
        double d[3] = {g[0] - pw[0][0], g[1] - pw[0][1], g[2] - pw[0][2]}, pc[3]; m3tvec(Rw[0], d, pc);
        double dt = pc[2], e;
#if OR_NT == 2
        e = OR_NK * OR_DEP * or_bias[C_DEP][0];
#elif OR_NT == 3
        e = OR_NK * OR_DEP * (or_hgauss(hk + 3) > 2.326 ? OR_OUTK : 1.0) * or_hgauss(hk + 5); /* 1% tail of a hash draw ~ outlier */
#else
        e = OR_NK * OR_DEP * or_hgauss(hk + 5);
#endif
        *dz = dt * (1 + or_scale + e); or_dsd = OR_DEP * dt;
        return 1;
    }
#endif
    (void)pf; (void)dz; return 0;
}
#endif
/* ===================== end i3 ORACLE HARNESS ===================== */
