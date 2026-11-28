/* cheap_vis.c: low-fuel stage-3 guest = cheap.c's gyro attitude + IMU velocity model, plus the direction of travel from
 * a few rotation-compensated image patches. 1:1 port of vis3.py (features) and s3vis_fit.py (velocity model):
 *
 *   per frame k >= 1:
 *     g, q, e0, e1, x            as cheap.c (gyro rows GROW_A/GROW_B, camera axes, 10 features)
 *     vision (vis3.features_for) GAP trackers take turns; tracker k%GAP matches frame k against its template from k-GAP:
 *                                rotation prediction from the attitude, ITERS inverse-compositional LK steps on NP patches,
 *                                translational flow -> normal equations A (EMA), direction d (power iteration), sign,
 *                                flow magnitude q (EMA); then it re-selects its points and template on frame k
 *     v_c = Wv x + (WS . phi) d  phi = [1, q/Q0, (q/Q0)^2, nv/16, nv >= 4]   (vis_weights.h, from s3vis_fit.py)
 *     p  += R(q) v_c dt
 * Gray = (R + 2G + B) >> 2, read only at the sampled pixels.
 */
#include "viobench_abi.h"

#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "vis_weights.h"

#define DT 0.05
#define A025 (DT / 0.25)
#define A1 (DT / 1.0)
#define IW 320
#define IH 240

#ifndef GAP
#define GAP 3
#endif
#define GX 10
#define GY 8
#define NC (GX * GY)
#define NP 16
#define PATCH 5
#define STRIDE 3
#define NS (PATCH * PATCH)
#define CP 3
#define CS 4
#define ITERS 2
#define TAU 0.3
#define MIN_EIG 1.0
#define MAX_RES 25.0
#define Q0 0.02

static double Rci[9];
static double qw = 1, qx, qy, qz;
static double px, py, pz;
static double e0[3], e1[3];
static int64_t k;
static double fx, fy, cx, cy;

/* attitude history for the GAP-frame rotation (rotation matrices of frames k-GAP..k) */
static double Rhist[GAP + 1][9];

typedef struct {
    double P[NP][2];
    int Pi[NP];                /* green-channel byte offset of (int)P */
    double T[NP][NS], gx[NP][NS], gy[NP][NS];
    double hxx[NP], hxy[NP], hyy[NP], det[NP], mineig[NP];
} Tracker;
static Tracker trk[GAP];
static double A[9], dvec[3] = {0, 0, 1}, qflow;
static double CAND[NC][2];
static int CANDI[NC][2];   /* (int)CAND: candidate / template sampling is on the integer grid */
static int CANDO[NC];      /* green-channel byte offset of CANDI */
static int OFFC[CP * CP], OFFP[NS];   /* byte offsets of the texture-test and patch samples */
static int last_nv;

static char config_text[8192];

static const char *after_key(const char *key) {
    const char *p = strstr(config_text, key);
    if (!p) return 0;
    p += strlen(key);
    while (*p && !(*p == '-' || *p == '+' || *p == '.' || (*p >= '0' && *p <= '9'))) p++;
    return *p ? p : 0;
}

static int json_number(const char *key, double *out) {
    const char *p = after_key(key);
    if (!p) return 0;
    *out = strtod(p, 0);
    return 1;
}

static int json_matrix(const char *key, double out[16]) {
    const char *p = after_key(key);
    for (int i = 0; i < 16; i++) {
        while (p && *p && !(*p == '-' || *p == '+' || *p == '.' || (*p >= '0' && *p <= '9'))) p++;
        if (!p || !*p) return 0;
        char *end;
        out[i] = strtod(p, &end);
        p = end;
    }
    return 1;
}

/* v2 gray: the green channel */
static inline double gray(const uint8_t *f, int x, int y) { return (double)f[3 * (y * IW + x) + 1]; }

#define R0 (STRIDE * (PATCH / 2))

/* e[s] = I(x + o_s) - T[s] with one bilinear weight set for the whole patch (vis3 v2: the patch lies inside the image) */
/* r2 = sum e^2, (bx, by) = sum (gx, gy) e with e = I(x + o_s) - T[s]; one bilinear weight set per patch */
static double patch_error(const uint8_t *f, double x, double y, const double *T, const double *gx, const double *gy,
                          double *bx, double *by) {
    const int x0 = (int)floor(x), y0 = (int)floor(y);
    const double ax = x - x0, ay = y - y0;
    const double w00 = (1 - ay) * (1 - ax), w01 = (1 - ay) * ax, w10 = ay * (1 - ax), w11 = ay * ax;
    const uint8_t *base = f + 3 * (y0 * IW + x0) + 1;
    double r2 = 0, sx = 0, sy = 0;
    for (int s = 0; s < NS; s++) {
        const uint8_t *p = base + OFFP[s];
        const double d = w00 * p[0] + w01 * p[3] + w10 * p[3 * IW] + w11 * p[3 * IW + 3] - T[s];
        r2 += d * d; sx += gx[s] * d; sy += gy[s] * d;
    }
    *bx = sx; *by = sy;
    return r2;
}

static void select_points(Tracker *t, const uint8_t *f) {
#ifdef PROF_NOSELECT
    for (int n = 0; n < NP; n++) { t->P[n][0] = CAND[n][0]; t->P[n][1] = CAND[n][1]; } return;
#endif
    double top[NP]; int idx[NP], m = 0;
    for (int c = 0; c < NC; c++) {
        int a = 0, b = 0, d = 0;
        const uint8_t *base = f + CANDO[c];
        for (int s = 0; s < CP * CP; s++) {
            const uint8_t *p = base + OFFC[s];
            const int gx = (int)p[3] - (int)p[-3], gy = (int)p[3 * IW] - (int)p[-3 * IW];
            a += gx * gx; b += gx * gy; d += gy * gy;
        }
        const double da = a, db = b, dd = d;
        const double sc = (da + dd - sqrt((da - dd) * (da - dd) + 4 * db * db)) / 2;
        /* keep the NP largest, ties to the lower index (numpy argsort(-score, kind="stable")) */
        if (m == NP && !(sc > top[NP - 1])) continue;
        int pos = m < NP ? m++ : NP - 1;
        while (pos > 0 && sc > top[pos - 1]) { top[pos] = top[pos - 1]; idx[pos] = idx[pos - 1]; pos--; }
        top[pos] = sc; idx[pos] = c;
    }
    for (int n = 0; n < NP; n++) {
        const int c = idx[n];
        t->P[n][0] = CAND[c][0]; t->P[n][1] = CAND[c][1]; t->Pi[n] = CANDO[c];
    }
}

static void set_template(Tracker *t, const uint8_t *f) {
    select_points(t, f);
    for (int n = 0; n < NP; n++) {
        double *T = t->T[n], *gx = t->gx[n], *gy = t->gy[n];
        const uint8_t *base = f + t->Pi[n];
        for (int s = 0; s < NS; s++) T[s] = base[OFFP[s]];
        double hxx = 0, hxy = 0, hyy = 0;
        for (int j = 0; j < PATCH; j++)
            for (int i = 0; i < PATCH; i++) {
                const int s = j * PATCH + i;
                gx[s] = (i > 0 && i < PATCH - 1) ? (T[s + 1] - T[s - 1]) / (2 * STRIDE) : 0;
                gy[s] = (j > 0 && j < PATCH - 1) ? (T[s + PATCH] - T[s - PATCH]) / (2 * STRIDE) : 0;
                hxx += gx[s] * gx[s]; hxy += gx[s] * gy[s]; hyy += gy[s] * gy[s];
            }
        const double det = hxx * hyy - hxy * hxy, tr = hxx + hyy, disc = tr * tr - 4 * det;
        t->hxx[n] = hxx; t->hxy[n] = hxy; t->hyy[n] = hyy; t->det[n] = det;
        t->mineig[n] = (tr - sqrt(disc > 0 ? disc : 0)) / 2 / NS;
    }
}

/* dR = R_{k-GAP}^T R_k (row-major); bearings in frame k = dR^T bearings in frame k-GAP */
static int track_step(Tracker *t, const uint8_t *f, const double dR[9]) {
#ifdef PROF_NOTRACK
    set_template(t, f); return 0;
#endif
    double nA[9] = {0}, xp[NP][2], u[NP][2], mnx[NP], mny[NP];
    int ok[NP], nv = 0;
    for (int n = 0; n < NP; n++) {
        const double m0x = (t->P[n][0] - cx) / fx, m0y = (t->P[n][1] - cy) / fy;
        const double m1[3] = {dR[0] * m0x + dR[3] * m0y + dR[6], dR[1] * m0x + dR[4] * m0y + dR[7], dR[2] * m0x + dR[5] * m0y + dR[8]};
        xp[n][0] = fx * m1[0] / m1[2] + cx; xp[n][1] = fy * m1[1] / m1[2] + cy;
        double x = xp[n][0], y = xp[n][1];
        ok[n] = t->mineig[n] > MIN_EIG && t->det[n] > 1e-9;
        double r2 = 0;
        for (int it = 0; it < ITERS && ok[n]; it++) {
            ok[n] = x - R0 >= 0 && x + R0 < IW - 1 && y - R0 >= 0 && y + R0 < IH - 1;
            if (!ok[n]) break;
            double bx, by;
            r2 = patch_error(f, x, y, t->T[n], t->gx[n], t->gy[n], &bx, &by);   /* residual before the last update */
            x -= (t->hyy[n] * bx - t->hxy[n] * by) / t->det[n];
            y -= (t->hxx[n] * by - t->hxy[n] * bx) / t->det[n];
        }
        const double mx = fabs(x - xp[n][0]) > fabs(y - xp[n][1]) ? fabs(x - xp[n][0]) : fabs(y - xp[n][1]);
        ok[n] = ok[n] && sqrt(r2 / NS) < MAX_RES && mx < 12;
        u[n][0] = (x - xp[n][0]) / fx; u[n][1] = (y - xp[n][1]) / fx;   /* vis3 normalises both by f = K[0,0] */
        mnx[n] = (xp[n][0] - cx) / fx; mny[n] = (xp[n][1] - cy) / fy;
        if (ok[n]) {
            const double nn[3] = {u[n][1], -u[n][0], u[n][0] * mny[n] - u[n][1] * mnx[n]};
            for (int a = 0; a < 3; a++)
                for (int b = 0; b < 3; b++) nA[3 * a + b] += nn[a] * nn[b];
            nv++;
        }
    }
    const double al = DT / TAU;
    for (int i = 0; i < 9; i++) A[i] = (1 - al) * A[i] + al * nA[i];
    const double tr = A[0] + A[4] + A[8];
    double d[3] = {dvec[0], dvec[1], dvec[2]};
    for (int it = 0; it < 4; it++) {
        const double nd[3] = {tr * d[0] - (A[0] * d[0] + A[1] * d[1] + A[2] * d[2]),
                              tr * d[1] - (A[3] * d[0] + A[4] * d[1] + A[5] * d[2]),
                              tr * d[2] - (A[6] * d[0] + A[7] * d[1] + A[8] * d[2])};
        const double nrm = sqrt(nd[0] * nd[0] + nd[1] * nd[1] + nd[2] * nd[2]) + 1e-30;
        d[0] = nd[0] / nrm; d[1] = nd[1] / nrm; d[2] = nd[2] / nrm;
    }
    double agree = 0, qs = 0;
    for (int n = 0; n < NP; n++) {
        if (!ok[n]) continue;
        agree += (mnx[n] * d[2] - d[0]) * u[n][0] + (mny[n] * d[2] - d[1]) * u[n][1];
        qs += sqrt(u[n][0] * u[n][0] + u[n][1] * u[n][1]);
    }
    if (agree < 0) { d[0] = -d[0]; d[1] = -d[1]; d[2] = -d[2]; }
    dvec[0] = d[0]; dvec[1] = d[1]; dvec[2] = d[2];
    qflow = (1 - al) * qflow + al * (nv ? qs / nv : 0.0);
    set_template(t, f);
    return nv;
}

static void quat_to_R(double R[9]) {
    R[0] = 1 - 2 * (qy * qy + qz * qz); R[1] = 2 * (qx * qy - qw * qz); R[2] = 2 * (qx * qz + qw * qy);
    R[3] = 2 * (qx * qy + qw * qz); R[4] = 1 - 2 * (qx * qx + qz * qz); R[5] = 2 * (qy * qz - qw * qx);
    R[6] = 2 * (qx * qz - qw * qy); R[7] = 2 * (qy * qz + qw * qx); R[8] = 1 - 2 * (qx * qx + qy * qy);
}

/* ------------------------------------------------------------------ ABI */
int32_t abi_version(void) { return VIOBENCH_ABI_VERSION; }

void *alloc(uint32_t size) { return malloc(size ? size : 1); }

int32_t frame_width(void) { return IW; }

int32_t init(const char *json, uint32_t length) {
    if (length >= sizeof(config_text)) return VIOBENCH_STATUS_ERROR;
    memcpy(config_text, json, length);
    config_text[length] = 0;
    double T[16];
    if (!json_matrix("\"T_cam_imu\"", T) || !json_number("\"fx\"", &fx) || !json_number("\"fy\"", &fy) ||
        !json_number("\"cx\"", &cx) || !json_number("\"cy\"", &cy))
        return VIOBENCH_STATUS_ERROR;
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) Rci[3 * i + j] = 0.5 * T[4 * i + j];  /* 0.5: mean of two rows */
    const double m = STRIDE * (PATCH / 2) + 8;
    for (int j = 0; j < GY; j++)
        for (int i = 0; i < GX; i++) {
            CAND[j * GX + i][0] = m + (IW - 1 - 2 * m) * i / (GX - 1);
            CAND[j * GX + i][1] = m + (IH - 1 - 2 * m) * j / (GY - 1);
            CANDI[j * GX + i][0] = (int)CAND[j * GX + i][0]; CANDI[j * GX + i][1] = (int)CAND[j * GX + i][1];
            CANDO[j * GX + i] = 3 * (CANDI[j * GX + i][1] * IW + CANDI[j * GX + i][0]) + 1;
        }
    for (int j = 0; j < CP; j++)
        for (int i = 0; i < CP; i++) OFFC[j * CP + i] = 3 * ((j - CP / 2) * CS * IW + (i - CP / 2) * CS);
    for (int j = 0; j < PATCH; j++)
        for (int i = 0; i < PATCH; i++) OFFP[j * PATCH + i] = 3 * ((j - PATCH / 2) * STRIDE * IW + (i - PATCH / 2) * STRIDE);
    qw = 1; qx = qy = qz = 0; px = py = pz = 0; k = 0;
    for (int a = 0; a < 3; a++) e0[a] = e1[a] = 0;
    memset(A, 0, sizeof A); dvec[0] = dvec[1] = 0; dvec[2] = 1; qflow = 0; last_nv = 0;
    return VIOBENCH_STATUS_OK;
}

int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
    (void)t;
    double g0 = 0, g1 = 0, g2 = 0, v0 = 0, v1 = 0, v2 = 0;
    if (k == 0 || imu_count <= GROW_B) {
        for (int i = 0; i < 9; i++) Rhist[GAP][i] = (i % 4 == 0);
        for (int g = 0; g < GAP; g++) set_template(&trk[g], frame);   /* trackers g < GAP start on frames g: see below */
    } else {
        const double *ra = imu + 7 * GROW_A + 4, *rb = imu + 7 * GROW_B + 4;
        const double s0 = ra[0] + rb[0], s1 = ra[1] + rb[1], s2 = ra[2] + rb[2];
        g0 = Rci[0] * s0 + Rci[1] * s1 + Rci[2] * s2;
        g1 = Rci[3] * s0 + Rci[4] * s1 + Rci[5] * s2;
        g2 = Rci[6] * s0 + Rci[7] * s1 + Rci[8] * s2;
        const double hx = 0.5 * DT * g0, hy = 0.5 * DT * g1, hz = 0.5 * DT * g2;
        const double hw = 1.0 - 0.5 * (hx * hx + hy * hy + hz * hz);
        const double nw = qw * hw - qx * hx - qy * hy - qz * hz;
        const double nx = qw * hx + qx * hw + qy * hz - qz * hy;
        const double ny = qw * hy - qx * hz + qy * hw + qz * hx;
        const double nz = qw * hz + qx * hy - qy * hx + qz * hw;
        const double n = 1.0 / sqrt(nw * nw + nx * nx + ny * ny + nz * nz);
        qw = nw * n; qx = nx * n; qy = ny * n; qz = nz * n;
        e0[0] += A025 * (g0 - e0[0]); e0[1] += A025 * (g1 - e0[1]); e0[2] += A025 * (g2 - e0[2]);
        e1[0] += A1 * (g0 - e1[0]);   e1[1] += A1 * (g1 - e1[1]);   e1[2] += A1 * (g2 - e1[2]);
        const double x[NF] = {1.0, e0[0], e0[1], e0[2], e1[0], e1[1], e1[2], fabs(e1[0]), fabs(e1[1]), fabs(e1[2])};
        for (int j = 0; j < NF; j++) { v0 += Wv[0][j] * x[j]; v1 += Wv[1][j] * x[j]; v2 += Wv[2][j] * x[j]; }
        /* attitude history: Rhist[GAP] = R_k, Rhist[GAP - g] = R_{k-g} */
        for (int g = 0; g < GAP; g++) memcpy(Rhist[g], Rhist[g + 1], sizeof Rhist[0]);
        quat_to_R(Rhist[GAP]);
        if (k < GAP) {
            set_template(&trk[k % GAP], frame);      /* vis3: trs[g].set_template(frames[g]) for g < GAP */
        } else {
            double dR[9];                             /* R_{k-GAP}^T R_k */
            const double *Ra = Rhist[0], *Rb = Rhist[GAP];
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++) dR[3 * i + j] = Ra[i] * Rb[j] + Ra[3 + i] * Rb[3 + j] + Ra[6 + i] * Rb[6 + j];
            last_nv = track_step(&trk[k % GAP], frame, dR);
        }
        const double qq = qflow / Q0;
        const double phi[5] = {1.0, qq, qq * qq, last_nv / 16.0, last_nv >= 4 ? 1.0 : 0.0};
        double s = 0;
        for (int j = 0; j < 5; j++) s += WS[j] * phi[j];
        v0 += s * dvec[0]; v1 += s * dvec[1]; v2 += s * dvec[2];
        const double tx = 2 * (qy * v2 - qz * v1), ty = 2 * (qz * v0 - qx * v2), tz = 2 * (qx * v1 - qy * v0);
        px += DT * (v0 + qw * tx + qy * tz - qz * ty);
        py += DT * (v1 + qw * ty + qz * tx - qx * tz);
        pz += DT * (v2 + qw * tz + qx * ty - qy * tx);
        if (!(px == px && py == py && pz == pz && qw == qw)) { qw = 1; qx = qy = qz = 0; px = py = pz = 0; }
    }
    out[0] = px; out[1] = py; out[2] = pz;
    out[3] = qx; out[4] = qy; out[5] = qz; out[6] = qw;
    out[7] = v0; out[8] = v1; out[9] = v2;
    out[10] = g0; out[11] = g1; out[12] = g2;
    k++;
    return VIOBENCH_STATUS_OK;
}
