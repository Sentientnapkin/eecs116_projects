/* atepush EDGE: MSCKF rows of one edgelet feature (see edge_mod.c). One residual per observation, n_k . (z_k - pi_k(P)),
 * P = c_0 + d * ray_0 (d by 1-D Gauss-Newton), feature removed by the left null space of dr/dP on the 2 directions
 * orthogonal to the 3-D line (direction N_0 x N_k of the back-projected edge planes). Gate as feature_rows. */
static int edge_rows(const Obs *o_in, int *nrows) {
    Obs o; int ci[MAX_OBS]; o.n = 0;
    for (int k = 0; k < o_in->n; k++) {
        int c = clone_index(o_in->cid[k]);
        if (c < 0) continue;
        ci[o.n] = c; o.cid[o.n] = o_in->cid[k]; o.x[o.n] = o_in->x[k]; o.y[o.n] = o_in->y[k]; o.enx[o.n] = o_in->enx[k]; o.eny[o.n] = o_in->eny[k]; o.n++;
    }
    if (o.n < EDGE_MINOBS) return 0;
    tc_att++;
    const int m = o.n;
    double Rwc[MAX_OBS][9], pwc[MAX_OBS][3], Nw[MAX_OBS][3];
    for (int k = 0; k < m; k++) {
        camera_pose(&clones[ci[k]], Rwc[k], pwc[k]);
        double l[3] = {o.enx[k], o.eny[k], -(o.enx[k] * o.x[k] + o.eny[k] * o.y[k])}, nn = 0;
        m3vec(Rwc[k], l, Nw[k]);
        for (int i = 0; i < 3; i++) nn += Nw[k][i] * Nw[k][i];
        nn = 1 / sqrt(nn); for (int i = 0; i < 3; i++) Nw[k][i] *= nn;
    }
    double L[3] = {0, 0, 0}, lb = 0;
    for (int k = 1; k < m; k++) {
        double c3[3] = {Nw[0][1] * Nw[k][2] - Nw[0][2] * Nw[k][1], Nw[0][2] * Nw[k][0] - Nw[0][0] * Nw[k][2], Nw[0][0] * Nw[k][1] - Nw[0][1] * Nw[k][0]};
        double q = c3[0] * c3[0] + c3[1] * c3[1] + c3[2] * c3[2];
        if (q > lb) { lb = q; L[0] = c3[0]; L[1] = c3[1]; L[2] = c3[2]; }
    }
    lb = sqrt(lb);
    if (lb < EDGE_LMIN) { tc_tri++; return 0; }
    for (int i = 0; i < 3; i++) L[i] /= lb;
    double u0[3] = {o.x[0], o.y[0], 1.0}, w0[3];
    m3vec(Rwc[0], u0, w0);
    double sa = 0, sb = 0;
    for (int k = 1; k < m; k++) {
        double a = 0, b = 0;
        for (int i = 0; i < 3; i++) { a += Nw[k][i] * w0[i]; b += Nw[k][i] * (pwc[k][i] - pwc[0][i]); }
        sa += a * a; sb += a * b;
    }
    if (sa < 1e-12) { tc_tri++; return 0; }
    double d = sb / sa, J2 = 0, R2 = 0;
    if (!(d > MIN_DEPTH && d < MAX_DEPTH)) { tc_tri++; return 0; }
    for (int it = 0; it < 4; it++) {
        double Jr = 0; J2 = 0; R2 = 0;
        for (int k = 1; k < m; k++) {
            double P[3], dp[3], pc[3], wc[3];
            for (int i = 0; i < 3; i++) { P[i] = pwc[0][i] + d * w0[i]; dp[i] = P[i] - pwc[k][i]; }
            m3tvec(Rwc[k], dp, pc); m3tvec(Rwc[k], w0, wc);
            if (pc[2] < 1e-3) { tc_tri++; return 0; }
            double iz = 1 / pc[2];
            double r = o.enx[k] * (o.x[k] - pc[0] * iz) + o.eny[k] * (o.y[k] - pc[1] * iz);
            double J = -(o.enx[k] * (wc[0] * iz - pc[0] * iz * iz * wc[2]) + o.eny[k] * (wc[1] * iz - pc[1] * iz * iz * wc[2]));
            { double al = -o.eny[k] * (o.x[k] - pc[0] * iz) + o.enx[k] * (o.y[k] - pc[1] * iz), s0 = EDGE_PIX / fx;
              double wk = s0 / sqrt(s0 * s0 + al * al * EDGE_SANG * EDGE_SANG); r *= wk; J *= wk; }
            J2 += J * J; Jr += J * r; R2 += r * r;
        }
        if (J2 < 1e-18) { tc_tri++; return 0; }
        d -= Jr / J2;
        if (!(d > MIN_DEPTH && d < MAX_DEPTH)) { tc_tri++; return 0; }
    }
    if ((EDGE_PIX / fx) / sqrt(J2) > EDGE_DREL * d) { tc_tri++; return 0; }
    if (EDGE_RMAX > 0 && sqrt(R2 / (m - 1)) * fx > EDGE_RMAX) { tc_gate++; return 0; } /* post-fit residual (last GN pass) */
    double pf[3];
    for (int i = 0; i < 3; i++) pf[i] = pwc[0][i] + d * w0[i];
    for (int k = 0; k < m; k++) {
        double dp[3], pc[3];
        for (int i = 0; i < 3; i++) dp[i] = pf[i] - pwc[k][i];
        m3tvec(Rwc[k], dp, pc);
        if (!(pc[2] > MIN_DEPTH && pc[2] < MAX_DEPTH)) { tc_tri++; return 0; }
    }
    /* basis orthogonal to the line */
    double e1[3], e2[3];
    { double a[3] = {1, 0, 0}; if (fabs(L[0]) > 0.6) { a[0] = 0; a[1] = 1; }
      double t = a[0] * L[0] + a[1] * L[1] + a[2] * L[2], nn = 0;
      for (int i = 0; i < 3; i++) { e1[i] = a[i] - t * L[i]; nn += e1[i] * e1[i]; }
      nn = 1 / sqrt(nn); for (int i = 0; i < 3; i++) e1[i] *= nn;
      e2[0] = L[1] * e1[2] - L[2] * e1[1]; e2[1] = L[2] * e1[0] - L[0] * e1[2]; e2[2] = L[0] * e1[1] - L[1] * e1[0]; }
    double RbcT[9];
    m3tmul(R_bc, I3, RbcT);
    memset(Hx, 0, m * MAXD * sizeof(double));
    for (int k = 0; k < m; k++) {
        const Clone *c = &clones[ci[k]];
        double dp[3], pc[3], u[3], tmp[3], sku[9], A[6], ev[3], hf[3];
        for (int i = 0; i < 3; i++) dp[i] = pf[i] - pwc[k][i];
        m3tvec(Rwc[k], dp, pc);
        double iz = 1 / pc[2], jp[6] = {iz, 0, -pc[0] * iz * iz, 0, iz, -pc[1] * iz * iz};
        rr[k] = o.enx[k] * (o.x[k] - pc[0] * iz) + o.eny[k] * (o.y[k] - pc[1] * iz);
        double wk; { double al = -o.eny[k] * (o.x[k] - pc[0] * iz) + o.enx[k] * (o.y[k] - pc[1] * iz), s0 = EDGE_PIX / fx;
          wk = s0 / sqrt(s0 * s0 + al * al * EDGE_SANG * EDGE_SANG); } /* slide x normal-angle error inflates the row noise */
        rr[k] *= wk;
        for (int i = 0; i < 3; i++) tmp[i] = pf[i] - c->p[i];
        m3tvec(c->R, tmp, u);
        for (int r2 = 0; r2 < 2; r2++)
            for (int cc = 0; cc < 3; cc++) A[3 * r2 + cc] = jp[3 * r2] * RbcT[cc] + jp[3 * r2 + 1] * RbcT[3 + cc] + jp[3 * r2 + 2] * RbcT[6 + cc];
        for (int cc = 0; cc < 3; cc++) ev[cc] = wk * (o.enx[k] * A[cc] + o.eny[k] * A[3 + cc]);
        skew(u, sku);
        int off = CORE + 6 * ci[k];
        for (int cc = 0; cc < 3; cc++) {
            double s_th = 0, s_p = 0;
            for (int t = 0; t < 3; t++) { s_th += ev[t] * sku[3 * t + cc]; s_p += ev[t] * c->R[3 * cc + t]; }
            Hx[k * MAXD + off + cc] = s_th; Hx[k * MAXD + off + 3 + cc] = -s_p; hf[cc] = s_p;
        }
#if EDGE_DBG >= 2
        { /* numerical Jacobian check (debug only) */
            double worst = 0, hmax = 0;
            for (int a = 0; a < 6; a++) {
                Clone cp = *c; double eps = 1e-6;
                if (a < 3) { double w[3] = {0, 0, 0}; w[a] = eps; rot_right(cp.R, w); } else cp.p[a - 3] += eps;
                double Rw2[9], pw2[3], dp2[3], pc2[3]; camera_pose(&cp, Rw2, pw2);
                for (int i = 0; i < 3; i++) dp2[i] = pf[i] - pw2[i];
                m3tvec(Rw2, dp2, pc2);
                double r2 = wk * (o.enx[k] * (o.x[k] - pc2[0] / pc2[2]) + o.eny[k] * (o.y[k] - pc2[1] / pc2[2]));
                double num = -(r2 - rr[k]) / eps, an = Hx[k * MAXD + off + a];
                if (fabs(num - an) > worst) worst = fabs(num - an); if (fabs(an) > hmax) hmax = fabs(an);
            }
            fprintf(stderr, "EJ k=%d worst %.3g hmax %.3g\n", k, worst, hmax);
        }
#endif
        if (EDGE_NS3) { Hf[k * 3 + 0] = hf[0]; Hf[k * 3 + 1] = hf[1]; Hf[k * 3 + 2] = hf[2]; } else {
        Hf[k * 3 + 0] = hf[0] * e1[0] + hf[1] * e1[1] + hf[2] * e1[2];
        Hf[k * 3 + 1] = hf[0] * e2[0] + hf[1] * e2[1] + hf[2] * e2[2]; }
    }
    int nzc[6 * MAX_OBS], nnz = 0, seen[MAX_CLONES + 1] = {0};
    for (int k = 0; k < m; k++)
        if (!seen[ci[k]]) { seen[ci[k]] = 1; for (int q = 0; q < 6; q++) nzc[nnz++] = CORE + 6 * ci[k] + q; }
    const int NC = EDGE_NS3 ? 3 : 2;
    for (int c = 0; c < NC; c++) {
        double norm = 0, v[2 * MAX_OBS];
        for (int i = c; i < m; i++) norm += Hf[i * 3 + c] * Hf[i * 3 + c];
        norm = sqrt(norm);
        if (norm < 1e-14) continue;
        double alpha = Hf[c * 3 + c] > 0 ? -norm : norm, vn = 0;
        for (int i = c; i < m; i++) v[i] = Hf[i * 3 + c];
        v[c] -= alpha;
        for (int i = c; i < m; i++) vn += v[i] * v[i];
        if (vn < 1e-30) continue;
        for (int j = c; j < NC; j++) {
            double s = 0;
            for (int i = c; i < m; i++) s += v[i] * Hf[i * 3 + j];
            s *= 2 / vn;
            for (int i = c; i < m; i++) Hf[i * 3 + j] -= s * v[i];
        }
        for (int jj = 0; jj < nnz; jj++) {
            int j = nzc[jj]; double s = 0;
            for (int i = c; i < m; i++) s += v[i] * Hx[i * MAXD + j];
            s *= 2 / vn;
            for (int i = c; i < m; i++) Hx[i * MAXD + j] -= s * v[i];
        }
        double s = 0;
        for (int i = c; i < m; i++) s += v[i] * rr[i];
        s *= 2 / vn;
        for (int i = c; i < m; i++) rr[i] -= s * v[i];
    }
    const int k0 = m - NC;
    const double *H0 = Hx + NC * MAXD, *r0 = rr + NC;
    if (k0 < 1) return 0;
    int sk = GATE2 && g_dx;
    if (sk && !gflag[g_cur_b]) return 0;
    if (!sk) {
        double sigma2 = (EDGE_PIX / fx) * (EDGE_PIX / fx);
        for (int a = 0; a < k0; a++)
            for (int jj = 0; jj < nnz; jj++) {
                int j = nzc[jj]; double s = 0;
                for (int q = 0; q < nnz; q++) s += H0[a * MAXD + nzc[q]] * Pm[nzc[q] * MAXD + j];
                H0P[a * MAXD + j] = s;
            }
        for (int a = 0; a < k0; a++)
            for (int b = 0; b <= a; b++) {
                double s = 0;
                for (int q = 0; q < nnz; q++) s += H0P[a * MAXD + nzc[q]] * H0[b * MAXD + nzc[q]];
                Sm[a * k0 + b] = Sm[b * k0 + a] = s + (a == b ? sigma2 : 0);
            }
        if (!cholesky(Sm, k0)) return 0;
        double y[2 * MAX_OBS], ry[2 * MAX_OBS];
        for (int a = 0; a < k0; a++) {
            ry[a] = r0[a];
            if (g_dx) { double q = 0; for (int jj = 0; jj < nnz; jj++) q += H0[a * MAXD + nzc[jj]] * g_dx[nzc[jj]]; ry[a] += q; }
        }
        memcpy(y, ry, k0 * sizeof(double));
        chol_solve(Sm, k0, y);
        double m2 = 0;
        for (int a = 0; a < k0; a++) m2 += ry[a] * y[a];
        double gq = chi2_quantile(k0);
        tc_nis += m2 / gq;
        if (EDGE_DBG && !g_dx) { fprintf(stderr, "EO f=%d m=%d nis=%.2f d=%.2f |", frame_no, m, m2 / gq, d); for (int k = 0; k < m; k++) fprintf(stderr, " %d %.6f %.6f %.5f %.5f", e_cfr[o.cid[k] & 4095], o.x[k], o.y[k], o.enx[k], o.eny[k]); fprintf(stderr, "\n"); }
        if (m2 > gq) { tc_gate++; if (GATE2) gflag[g_cur_b] = 0; return 0; }
        if (GATE2) gflag[g_cur_b] = 1;
    }
    if (*nrows + k0 > MAX_ROWS) return 0;
    const double hw = PIXEL_STD / EDGE_PIX;
    for (int a = 0; a < k0; a++) {
        for (int j = 0; j < D; j++) Hbig[(*nrows + a) * MAXD + j] = hw * H0[a * MAXD + j];
        rbig[*nrows + a] = hw * r0[a];
    }
    *nrows += k0; e_rows += k0;
    return 1;
}
