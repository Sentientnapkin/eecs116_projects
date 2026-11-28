/* Cheap IMU-only guest for viobench (no image access): a few hundred fuel per frame.
 *
 * Per frame (fit_cheap.py must match this exactly):
 *   g, a   = mean of the 10 gyro / accel rows, rotated into camera axes (R_ci from T_cam_imu)
 *   q      = q * [1 - |h|^2/2, h], h = g dt / 2, normalised      (camera k in camera 0; no bias, no vision)
 *   e1..e4 = EMAs of g (0.25 s, 1 s) and a (0.25 s, 1 s), alpha = dt / tau, updated before use
 *   x      = [1, e_g.25, e_g1, |e_g1|, e_a.25, e_a1]           (16 features)
 *   v_c    = Wv x                                               (camera-frame velocity, weights.h)
 *   p     += R(q) v_c dt                                        (weights fitted to unaligned ATE)
 * Frame 0 outputs identity.
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
static double eg0[3], eg1[3], ea0[3], ea1[3];
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
        for (int j = 0; j < 3; j++) Rci[3 * i + j] = T[4 * i + j];
    qw = 1; qx = qy = qz = 0; px = py = pz = 0; started = 0;
    for (int k = 0; k < 3; k++) eg0[k] = eg1[k] = ea0[k] = ea1[k] = 0;
    return VIOBENCH_STATUS_OK;
}

int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
    (void)t; (void)frame;
    double gc[3] = {0, 0, 0}, vc[3] = {0, 0, 0};
#ifndef CUT
#define CUT 9
#endif
    if (CUT==0 || !started || imu_count <= 0) {
        started = 1;
    } else {
        /* frame means, body axes */
        double sa0 = 0, sa1 = 0, sa2 = 0, sg0 = 0, sg1 = 0, sg2 = 0;
        for (int i = 0; i < imu_count; i++) {
            const double *r = imu + 7 * i;
            sa0 += r[1]; sa1 += r[2]; sa2 += r[3];
            sg0 += r[4]; sg1 += r[5]; sg2 += r[6];
        }
        const double inv = 1.0 / imu_count;
        sa0 *= inv; sa1 *= inv; sa2 *= inv; sg0 *= inv; sg1 *= inv; sg2 *= inv;
        if (CUT==1) { out[0]=sa0+sg0; out[1]=sa1+sg1; out[2]=sa2+sg2; for(int i=3;i<13;i++) out[i]=0; out[6]=1; return 0; }
        double ac[3];
        for (int k = 0; k < 3; k++) {
            gc[k] = Rci[3 * k] * sg0 + Rci[3 * k + 1] * sg1 + Rci[3 * k + 2] * sg2;
            ac[k] = Rci[3 * k] * sa0 + Rci[3 * k + 1] * sa1 + Rci[3 * k + 2] * sa2;
        }
        /* attitude: q <- q * dq */
        const double hx = 0.5 * DT * gc[0], hy = 0.5 * DT * gc[1], hz = 0.5 * DT * gc[2];
        const double hw = 1.0 - 0.5 * (hx * hx + hy * hy + hz * hz);
        double nw = qw * hw - qx * hx - qy * hy - qz * hz;
        double nx = qw * hx + qx * hw + qy * hz - qz * hy;
        double ny = qw * hy - qx * hz + qy * hw + qz * hx;
        double nz = qw * hz + qx * hy - qy * hx + qz * hw;
        const double n = 1.0 / sqrt(nw * nw + nx * nx + ny * ny + nz * nz);
        qw = nw * n; qx = nx * n; qy = ny * n; qz = nz * n;
        if (CUT==2) { out[0]=qx+ac[0]; out[1]=qy+ac[1]; out[2]=qz+ac[2]; for(int i=3;i<13;i++) out[i]=0; out[6]=1; return 0; }
        /* features */
        double x[NF];
        x[0] = 1.0;
        for (int k = 0; k < 3; k++) {
            eg0[k] += A025 * (gc[k] - eg0[k]);
            eg1[k] += A1 * (gc[k] - eg1[k]);
            ea0[k] += A025 * (ac[k] - ea0[k]);
            ea1[k] += A1 * (ac[k] - ea1[k]);
            x[1 + k] = eg0[k];
            x[4 + k] = eg1[k];
            x[7 + k] = fabs(eg1[k]);
            x[10 + k] = ea0[k];
            x[13 + k] = ea1[k];
        }
        if (CUT==3) { out[0]=x[3]+x[9]; out[1]=x[12]+x[15]; out[2]=x[6]; for(int i=3;i<13;i++) out[i]=0; out[6]=1; return 0; }
        for (int m = 0; m < 3; m++) {
            double s = 0;
            for (int j = 0; j < NF; j++) s += Wv[m][j] * x[j];
            vc[m] = s;
        }
        if (CUT==4) { out[0]=vc[0]; out[1]=vc[1]; out[2]=vc[2]; for(int i=3;i<13;i++) out[i]=0; out[6]=1; return 0; }
        /* p += R(q) v_c dt */
        const double xx = qx * qx, yy = qy * qy, zz = qz * qz, xy = qx * qy, xz = qx * qz, yz = qy * qz;
        const double wx = qw * qx, wy = qw * qy, wz = qw * qz;
        px += DT * ((1 - 2 * (yy + zz)) * vc[0] + 2 * (xy - wz) * vc[1] + 2 * (xz + wy) * vc[2]);
        py += DT * (2 * (xy + wz) * vc[0] + (1 - 2 * (xx + zz)) * vc[1] + 2 * (yz - wx) * vc[2]);
        pz += DT * (2 * (xz - wy) * vc[0] + 2 * (yz + wx) * vc[1] + (1 - 2 * (xx + yy)) * vc[2]);
        if (!(px == px && py == py && pz == pz && qw == qw)) { /* NaN guard: restart from identity */
            qw = 1; qx = qy = qz = 0; px = py = pz = 0;
        }
    }
    out[0] = px; out[1] = py; out[2] = pz;
    out[3] = qx; out[4] = qy; out[5] = qz; out[6] = qw;
    out[7] = vc[0]; out[8] = vc[1]; out[9] = vc[2];
    out[10] = gc[0]; out[11] = gc[1]; out[12] = gc[2];
    return VIOBENCH_STATUS_OK;
}
