/* ===================================================================================================================
 * geomstarve LINE: straight-edge LINE features for vision-starved scenes (flat-shaded polygons on black).
 * A line track = EDGE_LS sample edgelets on one straight image edge (each tracked by a 1-D search along its normal,
 * gyro de-rotated, as atepush edgelets); the samples may slide along the edge (harmless: only the line is measured).
 * At clone frames the 2-D line through the alive samples is recorded (centroid, normal, half extent). In the MSCKF the
 * feature is a 3-D line (4 DoF: point Q + unit direction D); each observation gives 2 residuals = signed distances of the
 * two recorded segment endpoints from the projected line l = Qc x Dc; the 4 line DoF are removed by the left null space
 * (2m - 4 rows). Line initialised from the back-projected planes, refined by Gauss-Newton; Jacobians by central
 * differences (exact enough: eps 1e-6 on smooth functions). Noise EDGE_PIX px per endpoint distance.
 * =================================================================================================================== */
#ifndef EDGE_LINE
#define EDGE_LINE 0
#endif
#if EDGE_LINE
#ifndef EDGE_LS
#define EDGE_LS 3          /* samples per line */
#endif
#ifndef EDGE_LSP
#define EDGE_LSP 8.0       /* px spacing of the samples at spawn */
#endif
#ifndef EDGE_LCOL
#define EDGE_LCOL 1.0      /* px: max distance of a sample from the line through the outer samples */
#endif
#ifndef EDGE_LMINSP
#define EDGE_LMINSP 6.0    /* px: min extent of the alive samples */
#endif
#ifndef EDGE_LMINOBS
#define EDGE_LMINOBS 3     /* clone observations (2m - 4 rows) */
#endif
#ifndef EDGE_LROWX
#define EDGE_LROWX 0       /* GOV: extra row-equivalents charged per line feature (its numeric-Jacobian / Gauss-Newton cost) */
#endif
#ifndef EDGE_VERT
#define EDGE_VERT 0        /* Manhattan: a line within EDGE_VTH deg of the world vertical whose vertical refit fits within EDGE_VRMAX px
                              is used as an exactly vertical 3-D line (2 DoF, 2m-2 rows): direct tilt information */
#endif
#ifndef EDGE_HORIZ
#define EDGE_HORIZ 0       /* Manhattan: near-horizontal lines used as exactly horizontal (3 DoF, 2m-3 rows) */
#endif
#ifndef EDGE_HTH
#define EDGE_HTH 10.0
#endif
#ifndef EDGE_MYAW
#define EDGE_MYAW 0        /* Manhattan yaw: horizontal lines near phi0 + k 90 deg (phi0 learnt from the first EDGE_MYN accepted
                              horizontal lines) are used with that exact direction (2 DoF, 2m-2 rows): heading information */
#endif
#ifndef EDGE_MYN
#define EDGE_MYN 15
#endif
#ifndef EDGE_MYR
#define EDGE_MYR 0.85      /* min resultant length of exp(4 i phi) to fix phi0 */
#endif
#ifndef EDGE_MYTH
#define EDGE_MYTH 6.0      /* deg */
#endif
#ifndef EDGE_VTH
#define EDGE_VTH 15.0
#endif
#ifndef EDGE_VRMAX
#define EDGE_VRMAX 3.0
#endif
#ifndef EDGE_LMAXF
#define EDGE_LMAXF 1000    /* max line features per update call (fuel peak) */
#endif
#ifndef EDGE_LTRY
#define EDGE_LTRY 1        /* spawn: candidate gradient maxima tried per cell */
#endif
#ifndef EDGE_LRESP
#define EDGE_LRESP 1       /* re-spawn dead samples of a line along it */
#endif
typedef struct { int alive, pol; double x[EDGE_LS], y[EDGE_LS], nx[EDGE_LS], ny[EDGE_LS], con[EDGE_LS]; int sal[EDGE_LS]; Obs obs; } LineT;
static LineT lines[EDGE_N];
static Obs llost[2 * EDGE_N];
static int nllost;
static long l_spawn, l_rows, l_att, l_tri, l_rmax, l_gate, l_ok, l_kcol, l_vert, l_horiz, l_myaw;
static double my_c, my_s, my_phi0; static int my_n, my_fixed;
static void line_reset(void) { my_c = my_s = my_phi0 = 0; my_n = my_fixed = 0; memset(lines, 0, sizeof lines); nllost = 0; l_spawn = l_rows = l_att = l_tri = l_rmax = l_gate = l_ok = l_kcol = 0; }
static int line_alive(void) { int n = 0; for (int i = 0; i < EDGE_N; i++) if (lines[i].alive) for (int k = 0; k < EDGE_LS; k++) n += lines[i].sal[k]; return n; } /* tracked samples */
static void line_kill(LineT *L) {
    L->alive = 0;
    if (L->obs.n >= EDGE_LMINOBS && nllost < 2 * EDGE_N) { llost[nllost] = L->obs; llost[nllost].tid = -1; llost[nllost].edge = 2; nllost++; }
}
/* track one sample: rotation-predicted, 1-D search along its normal; 1 ok */
static int ltrack1(const uint8_t *I, const double *Rrel, double *x, double *y, double *nx, double *ny, double *con, int pol) {
    double ray[3] = {(*x - cx) / fx, (*y - cy) / fy, 1.0}, rp[3];
    m3vec(Rrel, ray, rp);
    double gx = *x, gy = *y;
    if (rp[2] > 1e-3) { gx = fx * rp[0] / rp[2] + cx; gy = fy * rp[1] / rp[2] + cy; }
    double s, c, mx, my, coh, en;
    if (gx < 8 || gy < 8 || gx > IMG_W - 9 || gy > IMG_H - 9) return 0;
    if (!esearch(I, gx, gy, *nx, *ny, EDGE_S, pol, &s, &c)) return 0;
    double px = gx + s * *nx, py = gy + s * *ny;
    if (px < 8 || py < 8 || px > IMG_W - 9 || py > IMG_H - 9) return 0;
    etensor(I, (int)floor(px + 0.5), (int)floor(py + 0.5), &mx, &my, &coh, &en);
    double dt = mx * *nx + my * *ny;
    if (coh < EDGE_COH || en < EDGE_E || fabs(dt) < EDGE_ANG || c < 0.5 * *con) return 0;
    if (dt < 0) { mx = -mx; my = -my; }
    *x = px; *y = py; *nx = mx; *ny = my; *con = c;
    return 1;
}
/* place a sample near (x, y) on an edge with normal ~ (nx, ny), polarity pol: 1 ok */
static int lplace(const uint8_t *I, double x, double y, double nx, double ny, int pol, double *ox, double *oy, double *onx, double *ony, double *ocon) {
    if (x < 10 || y < 10 || x > IMG_W - 11 || y > IMG_H - 11) return 0;
    double s, c, mx, my, coh, en;
    if (!esearch(I, x, y, nx, ny, 3.0, pol, &s, &c)) return 0;
    double px = x + s * nx, py = y + s * ny;
    if (px < 8 || py < 8 || px > IMG_W - 9 || py > IMG_H - 9) return 0;
    etensor(I, (int)floor(px + 0.5), (int)floor(py + 0.5), &mx, &my, &coh, &en);
    double dt = mx * nx + my * ny;
    if (coh < EDGE_COH || en < EDGE_E || fabs(dt) < EDGE_ANG) return 0;
    if (dt < 0) { mx = -mx; my = -my; }
    *ox = px; *oy = py; *onx = mx; *ony = my; *ocon = c;
    return 1;
}
/* line geometry of the alive samples: outer pair (a, b), unit direction t, extent; 0 if < 2 alive */
static int lgeom(const LineT *L, int *ia, int *ib, double *tx, double *ty, double *ext) {
    int a = -1, b = -1; double best = -1;
    for (int i = 0; i < EDGE_LS; i++) if (L->sal[i]) for (int j = i + 1; j < EDGE_LS; j++) if (L->sal[j]) {
        double d = (L->x[j] - L->x[i]) * (L->x[j] - L->x[i]) + (L->y[j] - L->y[i]) * (L->y[j] - L->y[i]);
        if (d > best) { best = d; a = i; b = j; }
    }
    if (a < 0) return 0;
    double e = sqrt(best); *ia = a; *ib = b; *ext = e;
    if (e < 1e-6) { *tx = 1; *ty = 0; return 1; }
    *tx = (L->x[b] - L->x[a]) / e; *ty = (L->y[b] - L->y[a]) / e;
    return 1;
}
static void line_track_all(int cur, const double *Rrel) {
    const uint8_t *I = pyr[cur][0];
    for (int i = 0; i < EDGE_N; i++) {
        LineT *L = &lines[i];
        if (!L->alive) continue;
        int na = 0;
        for (int k = 0; k < EDGE_LS; k++) if (L->sal[k]) { L->sal[k] = ltrack1(I, Rrel, &L->x[k], &L->y[k], &L->nx[k], &L->ny[k], &L->con[k], L->pol); na += L->sal[k]; }
        int a, b; double tx, ty, ext;
        if (na < 2 || !lgeom(L, &a, &b, &tx, &ty, &ext) || ext < EDGE_LMINSP) { line_kill(L); continue; }
        /* straightness: other samples near the outer-pair line; normals perpendicular to it */
        int bad = 0;
        for (int k = 0; k < EDGE_LS; k++) if (L->sal[k]) {
            double d = -(L->x[k] - L->x[a]) * ty + (L->y[k] - L->y[a]) * tx;
            if (fabs(d) > EDGE_LCOL || fabs(L->nx[k] * tx + L->ny[k] * ty) > 0.15) { bad = 1; break; }
        }
        if (bad) { GSD(l_kcol++); line_kill(L); continue; }
        if (EDGE_LRESP && na < EDGE_LS) { /* re-spawn dead samples beyond the alive extent (alternating ends) */
            double nx = -ty, ny = tx; if (nx * L->nx[a] + ny * L->ny[a] < 0) { nx = -nx; ny = -ny; }
            for (int k = 0; k < EDGE_LS; k++) if (!L->sal[k]) {
                int end = k & 1; double sx = end ? L->x[b] + EDGE_LSP * tx : L->x[a] - EDGE_LSP * tx, sy = end ? L->y[b] + EDGE_LSP * ty : L->y[a] - EDGE_LSP * ty;
                if (lplace(I, sx, sy, nx, ny, L->pol, &L->x[k], &L->y[k], &L->nx[k], &L->ny[k], &L->con[k])) {
                    double d = -(L->x[k] - L->x[a]) * ty + (L->y[k] - L->y[a]) * tx;
                    L->sal[k] = fabs(d) <= EDGE_LCOL;
                }
            }
        }
    }
}
static void line_record(void) {
    int cid = clones[nclones - 1].id;
    e_cfr[cid & 4095] = frame_no;
    for (int i = 0; i < EDGE_N; i++) {
        LineT *L = &lines[i];
        if (!L->alive) continue;
        int a, b; double tx, ty, ext;
        if (!lgeom(L, &a, &b, &tx, &ty, &ext)) continue;
        Obs *o = &L->obs;
        if (o->n == MAX_OBS) {
            memmove(o->cid, o->cid + 1, (MAX_OBS - 1) * sizeof(int)); memmove(o->x, o->x + 1, (MAX_OBS - 1) * sizeof(double));
            memmove(o->y, o->y + 1, (MAX_OBS - 1) * sizeof(double)); memmove(o->enx, o->enx + 1, (MAX_OBS - 1) * sizeof(float));
            memmove(o->eny, o->eny + 1, (MAX_OBS - 1) * sizeof(float)); memmove(o->ehl, o->ehl + 1, (MAX_OBS - 1) * sizeof(float)); o->n--;
        }
        /* segment endpoints in normalized coordinates: the outer samples projected on the line through the centroid */
        double mx = 0, my = 0; int na = 0;
        for (int k = 0; k < EDGE_LS; k++) if (L->sal[k]) { mx += L->x[k]; my += L->y[k]; na++; }
        mx /= na; my /= na;
        double ax = mx - 0.5 * ext * tx, ay = my - 0.5 * ext * ty, bx = mx + 0.5 * ext * tx, by = my + 0.5 * ext * ty;
        double nax = (ax - cx) / fx, nay = (ay - cy) / fy, nbx = (bx - cx) / fx, nby = (by - cy) / fy;
        double ux = nbx - nax, uy = nby - nay, ul = sqrt(ux * ux + uy * uy);
        o->cid[o->n] = cid; o->x[o->n] = 0.5 * (nax + nbx); o->y[o->n] = 0.5 * (nay + nby);
        o->enx[o->n] = (float)(-uy / ul); o->eny[o->n] = (float)(ux / ul); o->ehl[o->n] = (float)(0.5 * ul); o->n++;
    }
}
static void line_detect(int cur) {
    int live = 0; for (int i = 0; i < MAX_TRACKS; i++) live += tracks[i].alive;
    if (live >= EDGE_LIVE) return;
    const uint8_t *I = pyr[cur][0];
    int occ[EDGE_GX * EDGE_GY] = {0};
    const int cw = IMG_W / EDGE_GX, ch = IMG_H / EDGE_GY;
#define LOCC(px_, py_) { int a_ = (int)((px_) / cw), b_ = (int)((py_) / ch); if (a_ >= 0 && a_ < EDGE_GX && b_ >= 0 && b_ < EDGE_GY) occ[b_ * EDGE_GX + a_] = 1; }
    for (int i = 0; i < MAX_TRACKS; i++) if (tracks[i].alive) LOCC(tracks[i].x, tracks[i].y)
    for (int i = 0; i < EDGE_N; i++) if (lines[i].alive) for (int k = 0; k < EDGE_LS; k++) if (lines[i].sal[k]) LOCC(lines[i].x[k], lines[i].y[k])
    int slot = 0, ncell = 0;
    for (int kk = 0; kk < EDGE_GX * EDGE_GY; kk++) {
        int cell = EDGE_DMAX < 100000 ? (e_dcur + kk) % (EDGE_GX * EDGE_GY) : kk;
        if (occ[cell]) continue;
        if (ncell >= EDGE_DMAX) { e_dcur = cell; return; }
        ncell++;
        while (slot < EDGE_N && lines[slot].alive) slot++;
        if (slot >= EDGE_N) { if (EDGE_DMAX < 100000) e_dcur = cell; return; }
        int x0 = (cell % EDGE_GX) * cw, y0 = (cell / EDGE_GX) * ch;
        int xa = x0 < 12 ? 12 : x0, ya = y0 < 12 ? 12 : y0, xb = x0 + cw > IMG_W - 12 ? IMG_W - 12 : x0 + cw, yb = y0 + ch > IMG_H - 12 ? IMG_H - 12 : y0 + ch;
        int cbx[EDGE_LTRY], cby[EDGE_LTRY], cbm[EDGE_LTRY], nc = 0; /* top-EDGE_LTRY gradient pixels, >= 4 px apart */
        for (int y = ya; y < yb; y += EDGE_DSTR)
            for (int x = xa; x < xb; x += EDGE_DSTR) {
                const uint8_t *p = I + y * IMG_W + x;
                int mg = abs(p[1] - p[-1]) + abs(p[IMG_W] - p[-IMG_W]);
                if (mg < EDGE_C) continue;
                int near = -1;
                for (int q = 0; q < nc; q++) if (abs(cbx[q] - x) < 4 && abs(cby[q] - y) < 4) { near = q; break; }
                if (near >= 0) { if (mg > cbm[near]) { cbm[near] = mg; cbx[near] = x; cby[near] = y; } continue; }
                if (nc < EDGE_LTRY) { cbx[nc] = x; cby[nc] = y; cbm[nc] = mg; nc++; continue; }
                int w = 0; for (int q = 1; q < nc; q++) if (cbm[q] < cbm[w]) w = q;
                if (mg > cbm[w]) { cbx[w] = x; cby[w] = y; cbm[w] = mg; }
            }
        int done = 0;
        for (int tr = 0; tr < nc && !done; tr++) {
            int bq = -1; for (int q = 0; q < nc; q++) if (cbm[q] > 0 && (bq < 0 || cbm[q] > cbm[bq])) bq = q;
            if (bq < 0) break;
            int bx = cbx[bq], by = cby[bq]; cbm[bq] = 0;
            double nx, ny, coh, en;
            etensor(I, bx, by, &nx, &ny, &coh, &en);
            if (coh < EDGE_COH || en < EDGE_E) continue;
            { int near = 0; for (int i = 0; i < MAX_TRACKS; i++) if (tracks[i].alive && fabs(tracks[i].x - bx) < 8 && fabs(tracks[i].y - by) < 8) { near = 1; break; } if (near) continue; }
            const uint8_t *p = I + by * IMG_W + bx;
            double gn = nx * (p[1] - p[-1]) + ny * (p[IMG_W] - p[-IMG_W]);
            int pol = gn >= 0 ? 1 : -1;
            LineT T; memset(&T, 0, sizeof T); T.pol = pol;
            double tx = -ny, ty = nx; int ok = 1;
            for (int k = 0; k < EDGE_LS && ok; k++) {
                double off = (k - 0.5 * (EDGE_LS - 1)) * EDGE_LSP;
                ok = lplace(I, bx + off * tx, by + off * ty, nx, ny, pol, &T.x[k], &T.y[k], &T.nx[k], &T.ny[k], &T.con[k]);
                T.sal[k] = ok;
            }
            if (!ok) continue;
            int a, b; double ux, uy, ext;
            if (!lgeom(&T, &a, &b, &ux, &uy, &ext) || ext < EDGE_LMINSP) continue;
            int bad = 0;
            for (int k = 0; k < EDGE_LS; k++) { double d = -(T.x[k] - T.x[a]) * uy + (T.y[k] - T.y[a]) * ux; if (fabs(d) > EDGE_LCOL || fabs(T.nx[k] * ux + T.ny[k] * uy) > 0.15) bad = 1; }
            if (bad) continue;
            T.alive = 1; T.obs.edge = 2; T.obs.tid = -1;
            lines[slot] = T; done = 1;
            for (int k = 0; k < EDGE_LS; k++) LOCC(T.x[k], T.y[k])
            GSD(l_spawn++);
        }
    }
#undef LOCC
}
static int line_take_b(Obs *bt, int nb, int full, int *rw, int cap) {
    int keep = 0, l_took = 0;
    for (int q = 0; q < nllost; q++) {
        int r = 2 * llost[q].n - 4 + EDGE_LROWX;
        if (nb < MAX_BATCH && *rw + r <= cap && l_took < EDGE_LMAXF) { bt[nb++] = llost[q]; *rw += r; l_took++; }
        else if (keep < 2 * EDGE_N) llost[keep++] = llost[q];
    }
    nllost = keep;
    if (full) {
        int oldest = clones[0].id;
        for (int i = 0; i < EDGE_N && nb < MAX_BATCH; i++) {
            Obs *o = &lines[i].obs;
            if (lines[i].alive && o->n >= EDGE_LMINOBS && o->cid[0] == oldest && *rw + 2 * o->n - 4 + EDGE_LROWX <= cap && l_took < EDGE_LMAXF) {
                l_took++;
                *rw += 2 * o->n - 4 + EDGE_LROWX;
                bt[nb] = *o; bt[nb].tid = -1; bt[nb].edge = 2; nb++;
                int l = o->n - 1;
                o->cid[0] = o->cid[l]; o->x[0] = o->x[l]; o->y[0] = o->y[l]; o->enx[0] = o->enx[l]; o->eny[0] = o->eny[l]; o->ehl[0] = o->ehl[l]; o->n = 1;
            }
        }
    }
    return nb;
}
static int line_take_phb(Obs *bt, int nb, int ph, int nph, int *rw, int cap) {
    int keep = 0, l_took = 0;
    for (int q = 0; q < nllost; q++) {
        int r = 2 * llost[q].n - 4 + EDGE_LROWX;
        if (nb < MAX_BATCH && *rw + r <= cap && l_took < EDGE_LMAXF) { bt[nb++] = llost[q]; *rw += r; l_took++; }
        else if (keep < 2 * EDGE_N) llost[keep++] = llost[q];
    }
    nllost = keep;
    if (nclones == MAX_CLONES) {
        int oldest = clones[0].id;
        for (int i = ph; i < EDGE_N && nb < MAX_BATCH; i += nph) {
            Obs *o = &lines[i].obs;
            if (lines[i].alive && o->n >= EDGE_LMINOBS && o->cid[0] == oldest && *rw + 2 * o->n - 4 + EDGE_LROWX <= cap && l_took < EDGE_LMAXF) {
                l_took++;
                *rw += 2 * o->n - 4 + EDGE_LROWX;
                bt[nb] = *o; bt[nb].tid = -1; bt[nb].edge = 2; nb++;
                int l = o->n - 1;
                o->cid[0] = o->cid[l]; o->x[0] = o->x[l]; o->y[0] = o->y[l]; o->enx[0] = o->enx[l]; o->eny[0] = o->eny[l]; o->ehl[0] = o->ehl[l]; o->n = 1;
            }
        }
    }
    return nb;
}
static void line_drop_clone(int oldest) {
    for (int i = 0; i < EDGE_N; i++) {
        Obs *o = &lines[i].obs; int k = 0;
        for (int j = 0; j < o->n; j++)
            if (o->cid[j] != oldest) { o->cid[k] = o->cid[j]; o->x[k] = o->x[j]; o->y[k] = o->y[j]; o->enx[k] = o->enx[j]; o->eny[k] = o->eny[j]; o->ehl[k] = o->ehl[j]; k++; }
        o->n = k;
    }
}
/* ---- measurement model ---- */
typedef struct { double Q[3], D[3]; } Line3;
#ifndef EDGE_LCACHE
#define EDGE_LCACHE 0      /* 2nd update iteration reuses the 1st pass line fit (no Gauss-Newton / Manhattan refit): ~half the line cost */
#endif
#if EDGE_LCACHE
static Line3 lc_L[MAX_BATCH]; static int lc_type[MAX_BATCH], lc_ok[MAX_BATCH];
#endif
static void lperturb(const Line3 *L, const double *e1, const double *e2, const double *dl, Line3 *out) {
    double d[3];
    for (int i = 0; i < 3; i++) { out->Q[i] = L->Q[i] + dl[0] * e1[i] + dl[1] * e2[i]; d[i] = L->D[i] + dl[2] * e1[i] + dl[3] * e2[i]; }
    double n = sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]); for (int i = 0; i < 3; i++) out->D[i] = d[i] / n;
}
/* h = signed distances (normalized image units) of the 2 endpoints of observation k from the projected line */
static int lres(const Line3 *L, const double *Rwc, const double *pwc, double x, double y, double ex, double ey, double hl, double *h) {
    double dq[3], Qc[3], Dc[3];
    for (int i = 0; i < 3; i++) dq[i] = L->Q[i] - pwc[i];
    m3tvec(Rwc, dq, Qc); m3tvec(Rwc, L->D, Dc);
    double l[3] = {Qc[1] * Dc[2] - Qc[2] * Dc[1], Qc[2] * Dc[0] - Qc[0] * Dc[2], Qc[0] * Dc[1] - Qc[1] * Dc[0]};
    double nn = sqrt(l[0] * l[0] + l[1] * l[1]);
    if (nn < 1e-12) return 0;
    double tx = -ey, ty = ex;
    for (int s = 0; s < 2; s++) { double sg = s ? 1 : -1, px = x + sg * hl * tx, py = y + sg * hl * ty; h[s] = (l[0] * px + l[1] * py + l[2]) / nn; }
    return 1;
}
/* constrained line models (Manhattan): 1 vertical, 2 horizontal; dl = (a, b[, df]) */
static void lmodel(const Line3 *L, int type, const double *dl, Line3 *out) {
    *out = *L;
    if (type == 1) { out->Q[0] += dl[0]; out->Q[1] += dl[1]; return; }
    if (type == 3) { out->Q[0] += -L->D[1] * dl[0]; out->Q[1] += L->D[0] * dl[0]; out->Q[2] += dl[1]; return; }
    double f = atan2(L->D[1], L->D[0]), c = cos(f), sn = sin(f), f2 = f + dl[2];
    out->Q[0] += -sn * dl[0]; out->Q[1] += c * dl[0]; out->Q[2] += dl[1];
    out->D[0] = cos(f2); out->D[1] = sin(f2); out->D[2] = 0;
}
static void lbasis(const double *D, double *e1, double *e2) {
    double a[3] = {1, 0, 0}; if (fabs(D[0]) > 0.6) { a[0] = 0; a[1] = 1; }
    double t = a[0] * D[0] + a[1] * D[1] + a[2] * D[2], nn = 0;
    for (int i = 0; i < 3; i++) { e1[i] = a[i] - t * D[i]; nn += e1[i] * e1[i]; }
    nn = 1 / sqrt(nn); for (int i = 0; i < 3; i++) e1[i] *= nn;
    e2[0] = D[1] * e1[2] - D[2] * e1[1]; e2[1] = D[2] * e1[0] - D[0] * e1[2]; e2[2] = D[0] * e1[1] - D[1] * e1[0];
}
static int line_rows(const Obs *o_in, int *nrows) {
    Obs o; int ci[MAX_OBS]; o.n = 0;
    for (int k = 0; k < o_in->n; k++) {
        int c = clone_index(o_in->cid[k]);
        if (c < 0) continue;
        ci[o.n] = c; o.cid[o.n] = o_in->cid[k]; o.x[o.n] = o_in->x[k]; o.y[o.n] = o_in->y[k]; o.enx[o.n] = o_in->enx[k]; o.eny[o.n] = o_in->eny[k]; o.ehl[o.n] = o_in->ehl[k]; o.n++;
    }
    if (o.n < EDGE_LMINOBS) return 0;
    tc_att++; GSD(g_dx ? 0 : l_att++);
    const int m = o.n, nr = 2 * m;
    double Rwc[MAX_OBS][9], pwc[MAX_OBS][3], Nw[MAX_OBS][3];
    for (int k = 0; k < m; k++) {
        camera_pose(&clones[ci[k]], Rwc[k], pwc[k]);
        double l[3] = {o.enx[k], o.eny[k], -(o.enx[k] * o.x[k] + o.eny[k] * o.y[k])}, nn = 0;
        m3vec(Rwc[k], l, Nw[k]);
        for (int i = 0; i < 3; i++) nn += Nw[k][i] * Nw[k][i];
        nn = 1 / sqrt(nn); for (int i = 0; i < 3; i++) Nw[k][i] *= nn;
    }
    Line3 L; double lb = 0; int type = 0, NP = 4; double h[2 * MAX_OBS], R2 = 0;
#if EDGE_LCACHE
    if (!g_dx) lc_ok[g_cur_b] = 0;
    else if (lc_ok[g_cur_b]) { L = lc_L[g_cur_b]; type = lc_type[g_cur_b]; NP = type == 0 ? 4 : type == 2 ? 3 : 2; goto lc_have; }
#endif
    for (int a = 0; a < m; a++) for (int b = a + 1; b < m; b++) {
        double c3[3] = {Nw[a][1] * Nw[b][2] - Nw[a][2] * Nw[b][1], Nw[a][2] * Nw[b][0] - Nw[a][0] * Nw[b][2], Nw[a][0] * Nw[b][1] - Nw[a][1] * Nw[b][0]};
        double q = c3[0] * c3[0] + c3[1] * c3[1] + c3[2] * c3[2];
        if (q > lb) { lb = q; L.D[0] = c3[0]; L.D[1] = c3[1]; L.D[2] = c3[2]; }
    }
    lb = sqrt(lb);
    if (lb < EDGE_LMIN) { tc_tri++; GSD(g_dx ? 0 : l_tri++); return 0; }
    for (int i = 0; i < 3; i++) L.D[i] /= lb;
    { /* Q: planes N_k . (Q - c_k) = 0 and D . (Q - c_0) = 0, least squares */
        double A[9] = {0}, bb[3] = {0};
        for (int k = 0; k <= m; k++) {
            const double *N = k < m ? Nw[k] : L.D, *c = k < m ? pwc[k] : pwc[0];
            double nc = N[0] * c[0] + N[1] * c[1] + N[2] * c[2];
            for (int i = 0; i < 3; i++) { bb[i] += N[i] * nc; for (int j = 0; j < 3; j++) A[3 * i + j] += N[i] * N[j]; }
        }
        double det = A[0] * (A[4] * A[8] - A[5] * A[7]) - A[1] * (A[3] * A[8] - A[5] * A[6]) + A[2] * (A[3] * A[7] - A[4] * A[6]);
        if (fabs(det) < 1e-12) { tc_tri++; GSD(g_dx ? 0 : l_tri++); return 0; }
        double inv[9] = {A[4] * A[8] - A[5] * A[7], A[2] * A[7] - A[1] * A[8], A[1] * A[5] - A[2] * A[4],
                         A[5] * A[6] - A[3] * A[8], A[0] * A[8] - A[2] * A[6], A[2] * A[3] - A[0] * A[5],
                         A[3] * A[7] - A[4] * A[6], A[1] * A[6] - A[0] * A[7], A[0] * A[4] - A[1] * A[3]};
        for (int i = 0; i < 3; i++) L.Q[i] = (inv[3 * i] * bb[0] + inv[3 * i + 1] * bb[1] + inv[3 * i + 2] * bb[2]) / det;
    }
    /* Gauss-Newton on the 4 line DoF (numeric Jacobian) */
    for (int it = 0; it < 4; it++) {
        double e1[3], e2[3], J[2 * MAX_OBS][4], JtJ[16] = {0}, Jtr[4] = {0};
        lbasis(L.D, e1, e2);
        R2 = 0;
        for (int k = 0; k < m; k++) { if (!lres(&L, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], h + 2 * k)) { tc_tri++; GSD(g_dx ? 0 : l_tri++); return 0; } }
        for (int r = 0; r < nr; r++) R2 += h[r] * h[r];
        if (it == 3) break;
        for (int p = 0; p < 4; p++) {
            double dl[4] = {0, 0, 0, 0}; const double eps = 1e-6; Line3 Lp, Lm; double hp[2], hm[2];
            dl[p] = eps; lperturb(&L, e1, e2, dl, &Lp); dl[p] = -eps; lperturb(&L, e1, e2, dl, &Lm);
            for (int k = 0; k < m; k++) {
                if (!lres(&Lp, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], hp) || !lres(&Lm, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], hm)) { tc_tri++; GSD(g_dx ? 0 : l_tri++); return 0; }
                J[2 * k][p] = (hp[0] - hm[0]) / (2 * eps); J[2 * k + 1][p] = (hp[1] - hm[1]) / (2 * eps);
            }
        }
        for (int r = 0; r < nr; r++) for (int a = 0; a < 4; a++) { Jtr[a] += J[r][a] * h[r]; for (int b = 0; b < 4; b++) JtJ[4 * a + b] += J[r][a] * J[r][b]; }
        for (int a = 0; a < 4; a++) JtJ[5 * a] += 1e-12;
        if (!cholesky(JtJ, 4)) { tc_tri++; GSD(g_dx ? 0 : l_tri++); return 0; }
        double st[4] = {Jtr[0], Jtr[1], Jtr[2], Jtr[3]};
        chol_solve(JtJ, 4, st);
        double dl[4] = {-st[0], -st[1], -st[2], -st[3]};
        Line3 Ln; lperturb(&L, e1, e2, dl, &Ln); L = Ln;
    }
    if (EDGE_RMAX > 0 && sqrt(R2 / nr) * fx > EDGE_RMAX) { tc_gate++; GSD(g_dx ? 0 : l_rmax++); return 0; }
    /* depth: the point of the 3-D line closest to each observation's centroid ray is in front, within range */
    for (int k = 0; k < m; k++) {
        double u[3] = {o.x[k], o.y[k], 1.0}, r[3], w0[3];
        m3vec(Rwc[k], u, r);
        for (int i = 0; i < 3; i++) w0[i] = pwc[k][i] - L.Q[i];
        double a = r[0] * r[0] + r[1] * r[1] + r[2] * r[2], b = r[0] * L.D[0] + r[1] * L.D[1] + r[2] * L.D[2], c = 1.0;
        double d = r[0] * w0[0] + r[1] * w0[1] + r[2] * w0[2], e = L.D[0] * w0[0] + L.D[1] * w0[1] + L.D[2] * w0[2], den = a * c - b * b;
        if (den < 1e-12) { tc_tri++; GSD(g_dx ? 0 : l_tri++); return 0; }
        double s = (b * e - c * d) / den; /* ray parameter = depth (u has z = 1) */
        if (!(s > MIN_DEPTH && s < MAX_DEPTH)) { tc_tri++; GSD(g_dx ? 0 : l_tri++); return 0; }
    }
    /* Manhattan models: 1 = vertical (D = +-z; Q moves in x, y: 2 DoF), 2 = horizontal (D = (cos f, sin f, 0); Q moves along the
       horizontal normal and z, f free: 3 DoF); 0 = free (4 DoF). A class is used when the free fit is within EDGE_VTH / EDGE_HTH deg
       and the constrained refit (Gauss-Newton) stays within EDGE_VRMAX px. */
    {
        double az = fabs(L.D[2]);
        int want = (EDGE_VERT && az > cos(EDGE_VTH * 0.017453292519943295)) ? 1 : (EDGE_HORIZ && az < sin(EDGE_HTH * 0.017453292519943295)) ? 2 : 0;
        if (want) {
            Line3 B = L;
            if (want == 1) { B.D[0] = 0; B.D[1] = 0; B.D[2] = L.D[2] > 0 ? 1 : -1; }
            else { double n2 = sqrt(L.D[0] * L.D[0] + L.D[1] * L.D[1]); B.D[0] = L.D[0] / n2; B.D[1] = L.D[1] / n2; B.D[2] = 0; }
            int np = want == 1 ? 2 : 3, okm = 1; double hv[2 * MAX_OBS], RV = 0;
            for (int it = 0; it < 5 && okm; it++) {
                for (int k = 0; k < m && okm; k++) okm = lres(&B, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], hv + 2 * k);
                if (!okm) break;
                RV = 0; for (int q = 0; q < nr; q++) RV += hv[q] * hv[q];
                if (it == 4) break;
                double J[2 * MAX_OBS][3], JtJ[9] = {0}, Jtr[3] = {0};
                for (int p = 0; p < np; p++) {
                    const double eps = 1e-6; double dl[3] = {0, 0, 0}; Line3 Bp, Bm; double hp[2], hm[2];
                    dl[p] = eps; lmodel(&B, want, dl, &Bp); dl[p] = -eps; lmodel(&B, want, dl, &Bm);
                    for (int k = 0; k < m; k++) { lres(&Bp, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], hp); lres(&Bm, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], hm);
                        J[2 * k][p] = (hp[0] - hm[0]) / (2 * eps); J[2 * k + 1][p] = (hp[1] - hm[1]) / (2 * eps); }
                }
                for (int q = 0; q < nr; q++) for (int a = 0; a < np; a++) { Jtr[a] += J[q][a] * hv[q]; for (int b = 0; b < np; b++) JtJ[np * a + b] += J[q][a] * J[q][b]; }
                for (int a = 0; a < np; a++) JtJ[(np + 1) * a] += 1e-12;
                if (!cholesky(JtJ, np)) { okm = 0; break; }
                double st[3] = {Jtr[0], Jtr[1], Jtr[2]}; chol_solve(JtJ, np, st);
                double dl[3] = {-st[0], -st[1], -st[2]}; Line3 Bn; lmodel(&B, want, dl, &Bn); B = Bn;
            }
            if (okm && sqrt(RV / nr) * fx <= EDGE_VRMAX) { L = B; type = want; NP = np; GSD(want == 1 ? l_vert++ : l_horiz++); }
        }
        if (EDGE_MYAW && type == 2 && my_fixed) { /* snap to the nearest Manhattan direction and refit Q (2 DoF) */
            double f = atan2(L.D[1], L.D[0]), q = 1.5707963267948966, k = floor((f - my_phi0) / q + 0.5), fm = my_phi0 + k * q;
            if (fabs(f - fm) < EDGE_MYTH * 0.017453292519943295) {
                Line3 B = L; B.D[0] = cos(fm); B.D[1] = sin(fm); B.D[2] = 0; int okm = 1; double hv[2 * MAX_OBS], RV = 0;
                for (int it = 0; it < 4 && okm; it++) {
                    for (int k2 = 0; k2 < m && okm; k2++) okm = lres(&B, Rwc[k2], pwc[k2], o.x[k2], o.y[k2], o.enx[k2], o.eny[k2], o.ehl[k2], hv + 2 * k2);
                    if (!okm) break;
                    RV = 0; for (int a = 0; a < nr; a++) RV += hv[a] * hv[a];
                    if (it == 3) break;
                    double J[2 * MAX_OBS][2], A3[3] = {0, 0, 0}, g2[2] = {0, 0};
                    for (int p = 0; p < 2; p++) {
                        const double eps = 1e-6; double dl[3] = {0, 0, 0}; Line3 Bp, Bm; double hp[2], hm[2];
                        dl[p] = eps; lmodel(&B, 3, dl, &Bp); dl[p] = -eps; lmodel(&B, 3, dl, &Bm);
                        for (int k2 = 0; k2 < m; k2++) { lres(&Bp, Rwc[k2], pwc[k2], o.x[k2], o.y[k2], o.enx[k2], o.eny[k2], o.ehl[k2], hp); lres(&Bm, Rwc[k2], pwc[k2], o.x[k2], o.y[k2], o.enx[k2], o.eny[k2], o.ehl[k2], hm);
                            J[2 * k2][p] = (hp[0] - hm[0]) / (2 * eps); J[2 * k2 + 1][p] = (hp[1] - hm[1]) / (2 * eps); }
                    }
                    for (int a = 0; a < nr; a++) { A3[0] += J[a][0] * J[a][0]; A3[1] += J[a][0] * J[a][1]; A3[2] += J[a][1] * J[a][1]; g2[0] += J[a][0] * hv[a]; g2[1] += J[a][1] * hv[a]; }
                    double det = A3[0] * A3[2] - A3[1] * A3[1];
                    if (!(det > 1e-24)) { okm = 0; break; }
                    double dl[3] = {-(A3[2] * g2[0] - A3[1] * g2[1]) / det, -(A3[0] * g2[1] - A3[1] * g2[0]) / det, 0}; Line3 Bn; lmodel(&B, 3, dl, &Bn); B = Bn;
                }
                if (okm && sqrt(RV / nr) * fx <= EDGE_VRMAX) { L = B; type = 3; NP = 2; GSD(l_myaw++); }
            }
        }
    }
#if EDGE_LCACHE
    if (!g_dx) { lc_L[g_cur_b] = L; lc_type[g_cur_b] = type; lc_ok[g_cur_b] = 1; }
lc_have:;
#endif
    double e1[3], e2[3], Hl[2 * MAX_OBS * 4];
    lbasis(L.D, e1, e2);
    /* Jacobians: line (NP, numeric) and clone poses (6 per observation, numeric; H = dh/dx, residual r = -h) */
    for (int k = 0; k < m; k++) lres(&L, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], h + 2 * k);
    for (int p = 0; p < NP; p++) {
        double dl[4] = {0, 0, 0, 0}; const double eps = 1e-6; Line3 Lp, Lm; double hp[2], hm[2];
        if (type) { dl[p] = eps; lmodel(&L, type, dl, &Lp); dl[p] = -eps; lmodel(&L, type, dl, &Lm); }
        else { dl[p] = eps; lperturb(&L, e1, e2, dl, &Lp); dl[p] = -eps; lperturb(&L, e1, e2, dl, &Lm); }
        for (int k = 0; k < m; k++) {
            lres(&Lp, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], hp); lres(&Lm, Rwc[k], pwc[k], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], hm);
            Hl[(2 * k) * 4 + p] = (hp[0] - hm[0]) / (2 * eps); Hl[(2 * k + 1) * 4 + p] = (hp[1] - hm[1]) / (2 * eps);
        }
    }
    memset(Hx, 0, nr * MAXD * sizeof(double));
    for (int k = 0; k < m; k++) {
        rr[2 * k] = -h[2 * k]; rr[2 * k + 1] = -h[2 * k + 1];
        const Clone *c = &clones[ci[k]];
        int off = CORE + 6 * ci[k];
        for (int a = 0; a < 6; a++) {
            const double eps = 1e-6; double hp[2], hm[2], Rp[9], pp[3];
            for (int sg = 0; sg < 2; sg++) {
                Clone cp = *c; double ee = sg ? -eps : eps;
                if (a < 3) { double w[3] = {0, 0, 0}; w[a] = ee; rot_right(cp.R, w); } else cp.p[a - 3] += ee;
                camera_pose(&cp, Rp, pp);
                lres(&L, Rp, pp, o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k], sg ? hm : hp);
            }
            Hx[(2 * k) * MAXD + off + a] = (hp[0] - hm[0]) / (2 * eps); Hx[(2 * k + 1) * MAXD + off + a] = (hp[1] - hm[1]) / (2 * eps);
        }
    }
    int nzc[6 * MAX_OBS], nnz = 0, seen[MAX_CLONES + 1] = {0};
    for (int k = 0; k < m; k++)
        if (!seen[ci[k]]) { seen[ci[k]] = 1; for (int q = 0; q < 6; q++) nzc[nnz++] = CORE + 6 * ci[k] + q; }
    const int NC = NP;
    for (int c = 0; c < NC; c++) {
        double norm = 0, v[2 * MAX_OBS];
        for (int i = c; i < nr; i++) norm += Hl[i * 4 + c] * Hl[i * 4 + c];
        norm = sqrt(norm);
        if (norm < 1e-14) continue;
        double alpha = Hl[c * 4 + c] > 0 ? -norm : norm, vn = 0;
        for (int i = c; i < nr; i++) v[i] = Hl[i * 4 + c];
        v[c] -= alpha;
        for (int i = c; i < nr; i++) vn += v[i] * v[i];
        if (vn < 1e-30) continue;
        for (int j = c; j < NC; j++) {
            double s = 0;
            for (int i = c; i < nr; i++) s += v[i] * Hl[i * 4 + j];
            s *= 2 / vn;
            for (int i = c; i < nr; i++) Hl[i * 4 + j] -= s * v[i];
        }
        for (int jj = 0; jj < nnz; jj++) {
            int j = nzc[jj]; double s = 0;
            for (int i = c; i < nr; i++) s += v[i] * Hx[i * MAXD + j];
            s *= 2 / vn;
            for (int i = c; i < nr; i++) Hx[i * MAXD + j] -= s * v[i];
        }
        double s = 0;
        for (int i = c; i < nr; i++) s += v[i] * rr[i];
        s *= 2 / vn;
        for (int i = c; i < nr; i++) rr[i] -= s * v[i];
    }
    const int k0 = nr - NC;
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
        if (GS_DIAG >= 2 && !g_dx) { fprintf(stderr, "LO f=%d m=%d nis=%.2f rms=%.3f |", frame_no, m, m2 / gq, sqrt(R2 / nr) * fx); for (int k = 0; k < m; k++) fprintf(stderr, " %d %.6f %.6f %.5f %.5f %.6f", e_cfr[o.cid[k] & 4095], o.x[k], o.y[k], o.enx[k], o.eny[k], o.ehl[k]); fprintf(stderr, "\n"); }
        if (m2 > gq) { tc_gate++; GSD(l_gate++); if (GATE2) gflag[g_cur_b] = 0; return 0; }
        if (GATE2) gflag[g_cur_b] = 1;
    }
    if (*nrows + k0 > MAX_ROWS) return 0;
    const double hw = PIXEL_STD / EDGE_PIX;
    for (int a = 0; a < k0; a++) {
        for (int j = 0; j < D; j++) Hbig[(*nrows + a) * MAXD + j] = hw * H0[a * MAXD + j];
        rbig[*nrows + a] = hw * r0[a];
    }
    *nrows += k0; GSD(l_rows += k0); GSD(g_dx ? 0 : l_ok++);
    if (EDGE_MYAW && !g_dx && type == 2 && !my_fixed) {
        double f4 = 4 * atan2(L.D[1], L.D[0]); my_c += cos(f4); my_s += sin(f4); my_n++;
        if (my_n >= EDGE_MYN && sqrt(my_c * my_c + my_s * my_s) >= EDGE_MYR * my_n) { my_phi0 = atan2(my_s, my_c) / 4; my_fixed = 1; }
    }
    return 1;
}
/* hooks: the GOV path calls the edge_* names */
#define edge_track_all line_track_all
#define edge_record line_record
#define edge_detect line_detect
#define edge_take_b line_take_b
#define edge_take_phb line_take_phb
#define edge_drop_clone line_drop_clone
#define edge_alive line_alive
#define edge_reset line_reset
#endif
