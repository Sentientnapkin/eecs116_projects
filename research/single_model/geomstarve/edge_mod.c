/* ===================================================================================================================
 * atepush EDGE: edgelets for vision-starved scenes (untextured ProcTHOR walls: few corners, long straight polygon edges).
 * An edgelet is a point on an image edge, tracked every frame by a 1-D search along the edge normal (gyro de-rotated
 * prediction); the along-edge position is free (aperture). Its clone observations are used in the MSCKF as a POINT ON
 * A 3-D LINE with one residual per observation, n_k . (z_k - pi_k(P)): P is anchored on the first observation's ray
 * (any point of the 3-D line is consistent with all observations, the ray picks one), the feature is removed by the left
 * null space of d r / d P restricted to the 2 directions orthogonal to the line (the line direction is unobservable).
 * Spawned only while the corner tracks are few (EDGE_LIVE), so textured flights are (nearly) unchanged.
 * =================================================================================================================== */
#ifndef EDGE_N
#define EDGE_N 32         /* max edgelets */
#endif
#ifndef EDGE_LIVE
#define EDGE_LIVE 30      /* spawn edgelets while fewer live corner tracks than this */
#endif
#ifndef EDGE_E
#define EDGE_E 25.0       /* min sqrt(structure-tensor trace), 5x5 central differences (~ step contrast 8) */
#endif
#ifndef EDGE_COH
#define EDGE_COH 0.80     /* min coherence (l1 - l2) / (l1 + l2): an edge, not a corner / noise */
#endif
#ifndef EDGE_C
#define EDGE_C 8.0        /* min step contrast along the normal while tracking */
#endif
#ifndef EDGE_S
#define EDGE_S 4.0        /* px search half range along the normal per frame */
#endif
#ifndef EDGE_PIX
#define EDGE_PIX 1.0      /* px noise of the normal-direction residual */
#endif
#ifndef EDGE_MINOBS
#define EDGE_MINOBS 4
#endif
#ifndef EDGE_ANG
#define EDGE_ANG 0.94     /* min |cos| between consecutive normals */
#endif
#ifndef EDGE_AMB
#define EDGE_AMB 0.75     /* a second peak above this fraction of the best (>= 2 px away) => ambiguous, drop */
#endif
#ifndef EDGE_DREL
#define EDGE_DREL 0.3     /* max relative depth sd at triangulation */
#endif
#ifndef EDGE_LMIN
#define EDGE_LMIN 0.05    /* min |N_0 x N_k| (normalized plane normals) */
#endif
#ifndef EDGE_RMAX
#define EDGE_RMAX 0.0     /* px: reject features whose rms normal residual after the depth fit exceeds this (0: off) */
#endif
#ifndef EDGE_SANG
#define EDGE_SANG 0.0     /* rad: normal-direction sd; row noise^2 += (slide along the edge * EDGE_SANG)^2 */
#endif
#ifndef EDGE_NS3
#define EDGE_NS3 0        /* eliminate all 3 point directions (P free along the line too): m-3 rows */
#endif
#ifndef EDGE_GCDET
#define EDGE_GCDET 400000.0 /* GOV: budget reserved for one edgelet detection pass */
#endif
#ifndef EDGE_GX
#define EDGE_GX 8
#endif
#ifndef EDGE_GY
#define EDGE_GY 6
#endif
#ifndef EDGE_CAPU
#define EDGE_CAPU 64      /* max edgelet features per update */
#endif
typedef struct { int alive; double x, y, nx, ny, con; int pol; Obs obs; } Edgelet;
static Edgelet edges[EDGE_N];
static Obs elost[2 * EDGE_N];
static int nelost;
static long e_spawn, e_rows; static int e_cfr[4096];
#if GS_DIAG
#define GSD(x) (x)
#else
#define GSD(x) ((void)0)
#endif
static long ek[10]; static int es_why; /* diag: kill reasons 0 border 1 nopeak 2 ambig 3 coh 4 en 5 ang 6 con 7 spawn-try 8 spawn-coh 9 spawn-search */
static int e_dcur;
static void edge_reset(void) { memset(edges, 0, sizeof edges); nelost = 0; e_spawn = e_rows = 0; e_dcur = 0; }
static inline double ebil(const uint8_t *I, double x, double y) {
    int x0 = (int)x, y0 = (int)y; double ax = x - x0, ay = y - y0; const uint8_t *p = I + y0 * IMG_W + x0;
    return (1 - ay) * ((1 - ax) * p[0] + ax * p[1]) + ay * ((1 - ax) * p[IMG_W] + ax * p[IMG_W + 1]);
}
/* structure tensor 5x5 at an integer pixel: unit normal (dominant gradient direction), coherence, energy */
static void etensor(const uint8_t *I, int xi, int yi, double *nx, double *ny, double *coh, double *en) {
    double sxx = 0, syy = 0, sxy = 0;
    for (int v = -2; v <= 2; v++)
        for (int u = -2; u <= 2; u++) {
            const uint8_t *p = I + (yi + v) * IMG_W + xi + u;
            int gx = p[1] - p[-1], gy = p[IMG_W] - p[-IMG_W];
            sxx += gx * gx; syy += gy * gy; sxy += gx * gy;
        }
    double tr = sxx + syy, df = sqrt((sxx - syy) * (sxx - syy) + 4 * sxy * sxy);
    double th = 0.5 * atan2(2 * sxy, sxx - syy);
    *nx = cos(th); *ny = sin(th); *coh = tr > 1e-9 ? df / tr : 0; *en = sqrt(tr);
}
/* 1-D search along n around (x, y): best s in [-S, S] (step 0.5) of pol * (I(q + n) - I(q - n)); returns 0 if none/ambiguous */
static int esearch(const uint8_t *I, double x, double y, double nx, double ny, double S, int pol, double *s_out, double *c_out) {
    double g[64]; int ns = (int)(2 * S / 0.5) + 1; if (ns > 63) ns = 63;
    const double lo = 3, hx = IMG_W - 4, hy = IMG_H - 4;
    int bi = -1; double best = -1e9;
    for (int i = 0; i < ns; i++) {
        double s = -S + 0.5 * i, qx = x + s * nx, qy = y + s * ny;
        double ax = qx + nx, ay = qy + ny, bx = qx - nx, by = qy - ny;
        if (ax < lo || ay < lo || bx < lo || by < lo || ax > hx || ay > hy || bx > hx || by > hy) { g[i] = -1e9; continue; }
        g[i] = pol * (ebil(I, ax, ay) - ebil(I, bx, by));
        if (g[i] > best) { best = g[i]; bi = i; }
    }
    if (bi < 0 || best < EDGE_C) { GSD(es_why = 1); return 0; }
    for (int i = 0; i < ns; i++)
        if (abs(i - bi) >= 4 && g[i] > EDGE_AMB * best && (i == 0 || g[i] >= g[i - 1]) && (i == ns - 1 || g[i] >= g[i + 1])) { GSD(es_why = 2); return 0; }
    double sb = -S + 0.5 * bi;
    if (bi > 0 && bi < ns - 1 && g[bi - 1] > -1e8 && g[bi + 1] > -1e8) {
        double d2 = g[bi - 1] - 2 * g[bi] + g[bi + 1];
        if (d2 < -1e-9) { double o = 0.5 * (g[bi - 1] - g[bi + 1]) / d2; if (o > 0.5) o = 0.5; if (o < -0.5) o = -0.5; sb += 0.5 * o; }
    }
    *s_out = sb; *c_out = best;
    return 1;
}
static void edge_kill(Edgelet *e) {
    e->alive = 0;
    if (e->obs.n >= EDGE_MINOBS && nelost < 2 * EDGE_N) { elost[nelost] = e->obs; elost[nelost].tid = -1; elost[nelost].edge = 1; nelost++; }
}
/* every frame: track edgelets from the previous image into image `cur` (rotation-predicted, search along the normal) */
static void edge_track_all(int cur, const double *Rrel) {
    const uint8_t *I = pyr[cur][0];
    for (int i = 0; i < EDGE_N; i++) {
        Edgelet *e = &edges[i];
        if (!e->alive) continue;
        double ray[3] = {(e->x - cx) / fx, (e->y - cy) / fy, 1.0}, rp[3];
        m3vec(Rrel, ray, rp);
        double gx = e->x, gy = e->y;
        if (rp[2] > 1e-3) { gx = fx * rp[0] / rp[2] + cx; gy = fy * rp[1] / rp[2] + cy; }
        double s, c, nx, ny, coh, en;
        if (gx < 8 || gy < 8 || gx > IMG_W - 9 || gy > IMG_H - 9) { GSD(ek[0]++); edge_kill(e); continue; }
        if (!esearch(I, gx, gy, e->nx, e->ny, EDGE_S, e->pol, &s, &c)) { GSD(ek[es_why]++); edge_kill(e); continue; }
        double px = gx + s * e->nx, py = gy + s * e->ny;
        if (px < 8 || py < 8 || px > IMG_W - 9 || py > IMG_H - 9) { GSD(ek[0]++); edge_kill(e); continue; }
        etensor(I, (int)floor(px + 0.5), (int)floor(py + 0.5), &nx, &ny, &coh, &en);
        double dt = nx * e->nx + ny * e->ny;
        if (coh < EDGE_COH || en < EDGE_E || fabs(dt) < EDGE_ANG || c < 0.5 * e->con) { GSD(ek[coh < EDGE_COH ? 3 : en < EDGE_E ? 4 : fabs(dt) < EDGE_ANG ? 5 : 6]++); edge_kill(e); continue; }
        if (dt < 0) { nx = -nx; ny = -ny; }
        e->x = px; e->y = py; e->nx = nx; e->ny = ny; e->con = c;
    }
}
static void edge_record(void) {
    int cid = clones[nclones - 1].id;
    e_cfr[cid & 4095] = frame_no;
    for (int i = 0; i < EDGE_N; i++) {
        Edgelet *e = &edges[i];
        if (!e->alive) continue;
        Obs *o = &e->obs;
        if (o->n == MAX_OBS) {
            memmove(o->cid, o->cid + 1, (MAX_OBS - 1) * sizeof(int)); memmove(o->x, o->x + 1, (MAX_OBS - 1) * sizeof(double));
            memmove(o->y, o->y + 1, (MAX_OBS - 1) * sizeof(double)); memmove(o->enx, o->enx + 1, (MAX_OBS - 1) * sizeof(float));
            memmove(o->eny, o->eny + 1, (MAX_OBS - 1) * sizeof(float)); o->n--;
        }
        double ax = e->nx * fx, ay = e->ny * fy, nn = sqrt(ax * ax + ay * ay);
        o->cid[o->n] = cid; o->x[o->n] = (e->x - cx) / fx; o->y[o->n] = (e->y - cy) / fy;
        o->enx[o->n] = (float)(ax / nn); o->eny[o->n] = (float)(ay / nn); o->n++;
    }
}
/* clone frames, while starved: new edgelets in grid cells free of corner tracks and edgelets (max-gradient pixel, stride 2) */
#ifndef EDGE_DEVERY
#define EDGE_DEVERY 0     /* 1: spawn pass on every vision frame (use with EDGE_DMAX to spread the cost) */
#endif
#ifndef EDGE_DSTR
#define EDGE_DSTR 2       /* spawn scan stride (px) */
#endif
#ifndef EDGE_DMAX
#define EDGE_DMAX 100000  /* max free cells scanned per detection call (round robin); default all */
#endif
static void edge_detect(int cur) {
    int live = 0; for (int i = 0; i < MAX_TRACKS; i++) live += tracks[i].alive;
    if (live >= EDGE_LIVE) return;
    const uint8_t *I = pyr[cur][0];
    int occ[EDGE_GX * EDGE_GY] = {0};
    const int cw = IMG_W / EDGE_GX, ch = IMG_H / EDGE_GY;
    for (int i = 0; i < MAX_TRACKS; i++) if (tracks[i].alive) { int a = (int)(tracks[i].x / cw), b = (int)(tracks[i].y / ch); if (a >= 0 && a < EDGE_GX && b >= 0 && b < EDGE_GY) occ[b * EDGE_GX + a] = 1; }
    for (int i = 0; i < EDGE_N; i++) if (edges[i].alive) { int a = (int)(edges[i].x / cw), b = (int)(edges[i].y / ch); if (a >= 0 && a < EDGE_GX && b >= 0 && b < EDGE_GY) occ[b * EDGE_GX + a] = 1; }
    int slot = 0, ncell = 0;
    for (int kk = 0; kk < EDGE_GX * EDGE_GY; kk++) {
        int cell = EDGE_DMAX < 100000 ? (e_dcur + kk) % (EDGE_GX * EDGE_GY) : kk;
        if (occ[cell]) continue;
        if (ncell >= EDGE_DMAX) { e_dcur = cell; return; }
        ncell++;
        while (slot < EDGE_N && edges[slot].alive) slot++;
        if (slot >= EDGE_N) { if (EDGE_DMAX < 100000) e_dcur = cell; return; }
        int x0 = (cell % EDGE_GX) * cw, y0 = (cell / EDGE_GX) * ch, bx = -1, by = -1, bm = 0;
        int xa = x0 < 10 ? 10 : x0, ya = y0 < 10 ? 10 : y0, xb = x0 + cw > IMG_W - 10 ? IMG_W - 10 : x0 + cw, yb = y0 + ch > IMG_H - 10 ? IMG_H - 10 : y0 + ch;
        for (int y = ya; y < yb; y += EDGE_DSTR)
            for (int x = xa; x < xb; x += EDGE_DSTR) {
                const uint8_t *p = I + y * IMG_W + x;
                int m = abs(p[1] - p[-1]) + abs(p[IMG_W] - p[-IMG_W]);
                if (m > bm) { bm = m; bx = x; by = y; }
            }
        if (bx < 0 || bm < EDGE_C) continue;
        GSD(ek[7]++);
        double nx, ny, coh, en, s, c;
        etensor(I, bx, by, &nx, &ny, &coh, &en);
        if (coh < EDGE_COH || en < EDGE_E) { GSD(ek[8]++); continue; }
        { /* not next to a corner track */
            int near = 0;
            for (int i = 0; i < MAX_TRACKS; i++) if (tracks[i].alive && fabs(tracks[i].x - bx) < 8 && fabs(tracks[i].y - by) < 8) { near = 1; break; }
            if (near) continue;
        }
        const uint8_t *p = I + by * IMG_W + bx;
        double gn = nx * (p[1] - p[-1]) + ny * (p[IMG_W] - p[-IMG_W]);
        int pol = gn >= 0 ? 1 : -1;
        if (!esearch(I, bx, by, nx, ny, 2.0, pol, &s, &c)) { GSD(ek[9]++); continue; }
        Edgelet *e = &edges[slot];
        memset(e, 0, sizeof *e);
        e->alive = 1; e->x = bx + s * nx; e->y = by + s * ny; e->nx = nx; e->ny = ny; e->pol = pol; e->con = c;
        e->obs.edge = 1; e->obs.tid = -1;
        e_spawn++;
    }
}
/* append edgelet features to an update batch: ended ones, and (window full) the ones observed in the oldest clone */
static int edge_take(Obs *bt, int nb, int full) {
    int take = 0;
    while (nelost > 0 && nb < MAX_BATCH && take < EDGE_CAPU) { bt[nb++] = elost[--nelost]; take++; }
    nelost = 0;
    if (full) {
        int oldest = clones[0].id;
        for (int i = 0; i < EDGE_N && nb < MAX_BATCH && take < EDGE_CAPU; i++) {
            Obs *o = &edges[i].obs;
            if (edges[i].alive && o->n >= EDGE_MINOBS && o->cid[0] == oldest) {
                bt[nb] = *o; bt[nb].tid = -1; bt[nb].edge = 1; nb++; take++;
                o->cid[0] = o->cid[o->n - 1]; o->x[0] = o->x[o->n - 1]; o->y[0] = o->y[o->n - 1];
                o->enx[0] = o->enx[o->n - 1]; o->eny[0] = o->eny[o->n - 1]; o->n = 1;
            }
        }
    }
    return nb;
}
static void edge_drop_clone(int oldest) {
    for (int i = 0; i < EDGE_N; i++) {
        Obs *o = &edges[i].obs; int k = 0;
        for (int j = 0; j < o->n; j++)
            if (o->cid[j] != oldest) { o->cid[k] = o->cid[j]; o->x[k] = o->x[j]; o->y[k] = o->y[j]; o->enx[k] = o->enx[j]; o->eny[k] = o->eny[j]; k++; }
        o->n = k;
    }
}
/* GOV (T4uB) variant of edge_take: ended / oldest-clone edgelet features within the row budget (m-3 rows each) */
#ifndef GC_EDGE
#define GC_EDGE 12000     /* instructions per tracked edgelet per frame (estimate) */
#endif
static int edge_take_b(Obs *bt, int nb, int full, int *rw, int cap) {
    int keep = 0;
    for (int q = 0; q < nelost; q++) {
        int r = elost[q].n - 3;
        if (nb < MAX_BATCH && *rw + r <= cap) { bt[nb++] = elost[q]; *rw += r; }
        else if (keep < 2 * EDGE_N) elost[keep++] = elost[q];
    }
    nelost = keep;
    if (full) {
        int oldest = clones[0].id;
        for (int i = 0; i < EDGE_N && nb < MAX_BATCH; i++) {
            Obs *o = &edges[i].obs;
            if (edges[i].alive && o->n >= EDGE_MINOBS && o->cid[0] == oldest && *rw + o->n - 3 <= cap) {
                *rw += o->n - 3;
                bt[nb] = *o; bt[nb].tid = -1; bt[nb].edge = 1; nb++;
                o->cid[0] = o->cid[o->n - 1]; o->x[0] = o->x[o->n - 1]; o->y[0] = o->y[o->n - 1];
                o->enx[0] = o->enx[o->n - 1]; o->eny[0] = o->eny[o->n - 1]; o->n = 1;
            }
        }
    }
    return nb;
}
static int edge_alive(void) { int n = 0; for (int i = 0; i < EDGE_N; i++) n += edges[i].alive; return n; }
/* EDGE_SPREAD: in-between frames take ended edgelet features and 1/nph of the edgelets observed in the clone that the next
   clone frame marginalizes (as the corner tracks), so the clone frame's update is not inflated by all edgelets at once */
#ifndef EDGE_SPREAD
#define EDGE_SPREAD 0
#endif
static int edge_take_ph(Obs *bt, int nb, int ph, int nph) {
    while (nelost > 0 && nb < MAX_BATCH) bt[nb++] = elost[--nelost];
    if (nclones == MAX_CLONES) {
        int oldest = clones[0].id;
        for (int i = ph; i < EDGE_N && nb < MAX_BATCH; i += nph) {
            Obs *o = &edges[i].obs;
            if (edges[i].alive && o->n >= EDGE_MINOBS && o->cid[0] == oldest) {
                bt[nb] = *o; bt[nb].tid = -1; bt[nb].edge = 1; nb++;
                o->cid[0] = o->cid[o->n - 1]; o->x[0] = o->x[o->n - 1]; o->y[0] = o->y[o->n - 1];
                o->enx[0] = o->enx[o->n - 1]; o->eny[0] = o->eny[o->n - 1]; o->n = 1;
            }
        }
    }
    return nb;
}
/* geomstarve: edgelet machinery runs only while it can matter (EDGE_ON_LIVE: live corner tracks below this, or edgelets alive) */
#ifndef EDGE_ON_LIVE
#define EDGE_ON_LIVE 1000
#endif
#if EDGE_LINE
static int line_alive(void);
#endif
static int edge_on(void) {
    if (EDGE_ON_LIVE >= 1000) return 1;
    int live = 0; for (int i = 0; i < MAX_TRACKS; i++) live += tracks[i].alive;
    if (live < EDGE_ON_LIVE) return 1;
    for (int i = 0; i < EDGE_N; i++) if (edges[i].alive) return 1;
#if EDGE_LINE
    if (line_alive()) return 1;
#endif
    return 0;
}

/* geomstarve EDGE_GSPREAD (GOV path): ended edgelet features and 1/nph of the edgelets observed in the oldest clone are taken on the
   in-between frames (as the corner tracks), so the clone frame does not carry all edge rows at once */
#ifndef EDGE_GSPREAD
#define EDGE_GSPREAD 0
#endif
static int edge_take_phb(Obs *bt, int nb, int ph, int nph, int *rw, int cap) {
    int keep = 0;
    for (int q = 0; q < nelost; q++) {
        int r = elost[q].n - 3;
        if (nb < MAX_BATCH && *rw + r <= cap) { bt[nb++] = elost[q]; *rw += r; }
        else if (keep < 2 * EDGE_N) elost[keep++] = elost[q];
    }
    nelost = keep;
    if (nclones == MAX_CLONES) {
        int oldest = clones[0].id;
        for (int i = ph; i < EDGE_N && nb < MAX_BATCH; i += nph) {
            Obs *o = &edges[i].obs;
            if (edges[i].alive && o->n >= EDGE_MINOBS && o->cid[0] == oldest && *rw + o->n - 3 <= cap) {
                *rw += o->n - 3;
                bt[nb] = *o; bt[nb].tid = -1; bt[nb].edge = 1; nb++;
                o->cid[0] = o->cid[o->n - 1]; o->x[0] = o->x[o->n - 1]; o->y[0] = o->y[o->n - 1];
                o->enx[0] = o->enx[o->n - 1]; o->eny[0] = o->eny[o->n - 1]; o->n = 1;
            }
        }
    }
    return nb;
}
