/* Cheap IMU-only guest for viobench (never reads the image): about 500 fuel per frame.
 *
 * Per frame (fit_cheap.py must match this exactly):
 *   g      = mean of gyro rows GROW_A and GROW_B of the 10, rotated into camera axes (R_ci from T_cam_imu)
 *   q      = q * [1 - |h|^2/2, h], h = g dt / 2, normalised      (camera k in camera 0; no bias, no vision)
 *   e0, e1 = EMAs of g with tau 0.25 s and 1 s, alpha = dt / tau, updated before use
 *   x      = [1, e0, e1, |e1|]                                  (10 features)
 *   v_c    = Wv x                                               (camera-frame velocity, weights.h)
 *   p     += R(q) v_c dt                                        (weights fitted to unaligned ATE)
 * Frame 0 outputs identity. The accelerometer is not used: it added nothing measurable (fit_cheap.py SPEC=ga).
 */
#include "viobench_abi.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#include "weights.h"

#define DT 0.05
#define A025 (DT / 0.25)
#define A1 (DT / 1.0)

static double Rci[9];
static double qw = 1, qx, qy, qz;
static double px, py, pz;
static double e0[3], e1[3];
static int started;

/* ------------------------------------------------------------------ config parsing (only T_cam_imu) */
static char config_text[8192];

static int json_matrix(const char *key, double out[16]) {
    const char *p = strstr(config_text, key);
    if (!p) return 0;
    p = strchr(p, '[');
    for (int i = 0; i < 16; i++) {
        while (p && *p && !(*p == '-' || *p == '+' || *p == '.' || (*p >= '0' && *p <= '9'))) p++;
        if (!p || !*p) return 0;
        char *end;
        out[i] = strtod(p, &end);
        p = end;
    }
    return 1;
}

/* ------------------------------------------------------------------ ABI */
int32_t abi_version(void) { return VIOBENCH_ABI_VERSION; }

void *alloc(uint32_t size) { return malloc(size ? size : 1); }

int32_t frame_width(void) { return 320; }

int32_t init(const char *json, uint32_t length) {
    if (length >= sizeof(config_text)) return VIOBENCH_STATUS_ERROR;
    memcpy(config_text, json, length);
    config_text[length] = 0;
    double T[16];
    if (!json_matrix("T_cam_imu", T)) return VIOBENCH_STATUS_ERROR;
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) Rci[3 * i + j] = 0.5 * T[4 * i + j];  /* 0.5: mean of two rows */
    qw = 1; qx = qy = qz = 0; px = py = pz = 0; started = 0;
    for (int k = 0; k < 3; k++) e0[k] = e1[k] = 0;
    return VIOBENCH_STATUS_OK;
}

int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
    (void)t; (void)frame;
    double g0 = 0, g1 = 0, g2 = 0, v0 = 0, v1 = 0, v2 = 0;
    if (!started || imu_count <= GROW_B) {
        started = 1;
    } else {
        const double *ra = imu + 7 * GROW_A + 4, *rb = imu + 7 * GROW_B + 4;
        const double s0 = ra[0] + rb[0], s1 = ra[1] + rb[1], s2 = ra[2] + rb[2];
        g0 = Rci[0] * s0 + Rci[1] * s1 + Rci[2] * s2;
        g1 = Rci[3] * s0 + Rci[4] * s1 + Rci[5] * s2;
        g2 = Rci[6] * s0 + Rci[7] * s1 + Rci[8] * s2;
        /* attitude: q <- q * dq */
        const double hx = 0.5 * DT * g0, hy = 0.5 * DT * g1, hz = 0.5 * DT * g2;
        const double hw = 1.0 - 0.5 * (hx * hx + hy * hy + hz * hz);
        const double nw = qw * hw - qx * hx - qy * hy - qz * hz;
        const double nx = qw * hx + qx * hw + qy * hz - qz * hy;
        const double ny = qw * hy - qx * hz + qy * hw + qz * hx;
        const double nz = qw * hz + qx * hy - qy * hx + qz * hw;
        const double n = 1.0 / sqrt(nw * nw + nx * nx + ny * ny + nz * nz);
        qw = nw * n; qx = nx * n; qy = ny * n; qz = nz * n;
        /* features and camera-frame velocity */
        e0[0] += A025 * (g0 - e0[0]); e0[1] += A025 * (g1 - e0[1]); e0[2] += A025 * (g2 - e0[2]);
        e1[0] += A1 * (g0 - e1[0]);   e1[1] += A1 * (g1 - e1[1]);   e1[2] += A1 * (g2 - e1[2]);
        const double x[NF] = {1.0, e0[0], e0[1], e0[2], e1[0], e1[1], e1[2], fabs(e1[0]), fabs(e1[1]), fabs(e1[2])};
        for (int j = 0; j < NF; j++) {
            v0 += Wv[0][j] * x[j];
            v1 += Wv[1][j] * x[j];
            v2 += Wv[2][j] * x[j];
        }
        /* p += R(q) v dt, via t = 2 q_v x v, v' = v + w t + q_v x t */
        const double tx = 2 * (qy * v2 - qz * v1), ty = 2 * (qz * v0 - qx * v2), tz = 2 * (qx * v1 - qy * v0);
        px += DT * (v0 + qw * tx + qy * tz - qz * ty);
        py += DT * (v1 + qw * ty + qz * tx - qx * tz);
        pz += DT * (v2 + qw * tz + qx * ty - qy * tx);
        if (!(px == px && py == py && pz == pz && qw == qw)) { /* NaN guard: restart from identity */
            qw = 1; qx = qy = qz = 0; px = py = pz = 0;
        }
    }
    out[0] = px; out[1] = py; out[2] = pz;
    out[3] = qx; out[4] = qy; out[5] = qz; out[6] = qw;
    out[7] = v0; out[8] = v1; out[9] = v2;
    out[10] = g0; out[11] = g1; out[12] = g2;
    return VIOBENCH_STATUS_OK;
}
