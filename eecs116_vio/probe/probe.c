/* probe.c: a diagnostic viobench guest. It scores badly on purpose and reports statistics of the hidden episodes
 * through two side channels (README.md has the full layout; decode.py reverses it):
 *
 *  1. Its outputs are chosen so each server error metric measures one ground-truth quantity:
 *       position     = 0 every frame        -> ate_rmse = RMS distance from start, final_drift = final distance,
 *                                              sim3_ate_rmse = RMS spread about the centroid, rpe_t = RMS 1 s motion
 *       orientation  = raw gyro integration -> rotation_rmse / rotation_max / rpe_rotation = gyro drift (bias)
 *       velocity     = (0,0,VBIG) at frame 0, else 0   -> velocity_rmse gives the true forward speed at frame 0
 *       ang.velocity = gyro (line fit at t) + (0,WBIG,0) -> angular_velocity_rmse gives the mean camera-y gyro bias
 *  2. Fuel. Every frame does the same data-independent work (no data-dependent branches), then burns a chosen
 *     number of loop iterations. Frame groups are set so the reported fuel order statistics (median, p95, p99,
 *     max) and the total each carry a packed integer of quantized statistics of the IMU and the images;
 *     init's fuel carries the camera intrinsics.
 *
 * Build: bash build.sh [NAME]   (DEFS="DEBUGX=1" prints the payloads to stderr, for calibration only).
 */
#include "viobench_abi.h"

#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#ifdef DEBUGX
#include <stdio.h>
#endif

#define IW 320
#define IH 240
#define DT 0.05
#define DTI 0.005 /* IMU row spacing */

/* ---------------------------------------------------------------- frame groups (episodes have 1200 frames) */
#define F_MED 589       /* G1 payload is computed at the end of this frame (stats of frames 0..589) */
#define F_FREEZE 1129   /* G2, G3, G4 and total payloads: end of this frame (stats of frames 0..1129) */
#define G1_FIRST 590    /* G1: frames 590..1129 (540) -> sorted ranks 590..1129, holds the median (599.5) */
#define G2_FIRST 1130   /* G2: frames 1130..1184 (55) -> ranks 1130..1184, holds p95 (1139.05) */
#define G3_FIRST 1185   /* G3: frames 1185..1198 (14) -> ranks 1185..1198, holds p99 (1187.01) */
#define X0_FRAME 1198   /* the top G3 frame also burns the total-channel payload (rank 1198, unused by p99) */
#define G4_FRAME 1199   /* G4: the max */
#define SH 2            /* payload shift: 2 guard bits per channel (decoding checks they are zero) */
#define N1 (1ull << 16)
#define N2 (1ull << 23)
#define N3 (1ull << 26)
#define N4 (1ull << 29)
#define SHI 10          /* init payload shift: tolerates config-parsing fuel variation */
#define NI (1ull << 12)
#define VBIG 1.0e6
#define WBIG 1.0e6

/* ---------------------------------------------------------------- state */
static double Rci[9];
static double fx = 1, fy = 1;
static uint32_t XI, X1, X2, X3, X4, X0;
static int64_t k;   /* frame index */
static double qw = 1, qx, qy, qz;

/* IMU accumulators */
static double sd2g, sd2a, sg2, syaw2, saxy2, sj2, amp[3];
static double sg2s, sas[3], sa2s;
/* image accumulators */
static uint64_t sR, sG, sB, sTop, sBot;
static double stex;
static int64_t dark;
static double sRx[3], sRy[3];
static int64_t cnx[3], cny[3];

/* ---------------------------------------------------------------- helpers (branch-free) */
__attribute__((noinline)) static void burn(uint64_t n) {
    volatile uint64_t c = n;
    while (c) c = c - 1;
}

static inline double sel(int c, double a, double b) { return c ? a : b; }

static double flog2(double x) { /* x > 0 */
    union { double d; uint64_t u; } v = {x};
    const int64_t e = (int64_t)((v.u >> 52) & 0x7ff) - 1023;
    v.u = (v.u & 0x000fffffffffffffull) | 0x3ff0000000000000ull; /* mantissa in [1, 2) */
    const double s = (v.d - 1.0) / (v.d + 1.0), s2 = s * s;
    const double ln = 2.0 * s * (1.0 + s2 * (1.0 / 3 + s2 * (1.0 / 5 + s2 * (1.0 / 7 + s2 * (1.0 / 9 + s2 / 11)))));
    return (double)e + ln * 1.4426950408889634;
}

/* x in [lo, hi] -> round onto 0..levels-1, clamped; NaN -> 0 */
static uint32_t qlin(double x, double lo, double hi, uint32_t levels) {
    double t = (x - lo) / (hi - lo) * (double)(levels - 1) + 0.5;
    t = t > 0 ? t : 0;
    const double top = (double)(levels - 1);
    t = t < top ? t : top;
    return (uint32_t)t;
}

/* log2(x) in [lo2, hi2] -> 0..2^bits-1 */
static uint32_t qlog(double x, double lo2, double hi2, int bits) {
    x = x > 1e-30 ? x : 1e-30;
    x = x < 1e30 ? x : 1e30;
    return qlin(flog2(x), lo2, hi2, 1u << bits);
}

/* mean blur ratio of a bin -> 1..63, or 0 when the bin is empty */
static uint32_t qbin(double s, int64_t n) {
    const double m = s / (double)(n + (n == 0));
    return (uint32_t)(n > 0) * (1u + qlin(m, 0.2, 1.1, 63));
}

/* ---------------------------------------------------------------- config parsing */
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

/* ---------------------------------------------------------------- ABI */
int32_t abi_version(void) { return VIOBENCH_ABI_VERSION; }

void *alloc(uint32_t size) { return malloc(size ? size : 1); }

int32_t frame_width(void) { return IW; }

int32_t init(const char *json, uint32_t length) {
    if (length >= sizeof(config_text)) return VIOBENCH_STATUS_ERROR;
    memcpy(config_text, json, length);
    config_text[length] = 0;
    double T[16], cx = 0, cy = 0, w = 0, h = 0;
    if (!json_matrix("\"T_cam_imu\"", T)) return VIOBENCH_STATUS_ERROR;
    if (!json_number("\"fx\"", &fx) || !json_number("\"fy\"", &fy) || !json_number("\"cx\"", &cx) ||
        !json_number("\"cy\"", &cy) || !json_number("\"width\"", &w) || !json_number("\"height\"", &h))
        return VIOBENCH_STATUS_ERROR;
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) Rci[3 * i + j] = T[4 * i + j];
    static const double Tdef[16] = {0, -1, 0, 0, 0, 0, -1, 0, 1, 0, 0, 0, 0, 0, 0, 1};
    int tdefault = 1;
    for (int i = 0; i < 16; i++) tdefault &= T[i] == Tdef[i];
    const int centred = fabs(cx - 0.5 * (w - 1)) < 0.01 && fabs(cy - 0.5 * (h - 1)) < 0.01 && fabs(fx - fy) < 0.001 &&
                        w == IW && h == IH;
    /* fx at 320 px in 0.01 px from 60 px: 15 bits cover 60..387 px (FoV 135 deg -> 66 px, 75 deg -> 208 px) */
    uint32_t fxq = qlin(fx, 60.0, 60.0 + 32767 * 0.01, 32768);
    XI = fxq | (uint32_t)tdefault << 15 | (uint32_t)centred << 16;
    burn(NI + ((uint64_t)XI << SHI));
    k = 0;
    return VIOBENCH_STATUS_OK;
}

static void image_stats(const uint8_t *f, double *Rx, double *Ry, double *Ymean) {
    uint64_t r = 0, g = 0, b = 0, top = 0, bot = 0, e1x = 0, e2x = 0, e1y = 0, e2y = 0;
    for (int y = 0; y < IH; y++) {
        const uint8_t *row = f + (size_t)y * IW * 3;
        uint32_t rr = 0, gg = 0, bb = 0, a1 = 0, a2 = 0;
        for (int x = 0; x < IW; x++) { rr += row[3 * x]; gg += row[3 * x + 1]; bb += row[3 * x + 2]; }
        for (int x = 0; x < IW - 2; x++) {
            const int d1 = (int)row[3 * x + 4] - (int)row[3 * x + 1];
            const int d2 = (int)row[3 * x + 7] - (int)row[3 * x + 1];
            a1 += (uint32_t)(d1 * d1); a2 += (uint32_t)(d2 * d2);
        }
        r += rr; g += gg; b += bb; e1x += a1; e2x += a2;
        const uint64_t yy = rr + 2ull * gg + bb;
        top += yy * (uint64_t)(y < 60);
        bot += yy * (uint64_t)(y >= IH - 60);
    }
    for (int y = 0; y < IH - 2; y++) {
        const uint8_t *r0 = f + (size_t)y * IW * 3 + 1, *r1 = r0 + IW * 3, *r2 = r1 + IW * 3;
        uint32_t a1 = 0, a2 = 0;
        for (int x = 0; x < IW; x++) {
            const int d1 = (int)r1[3 * x] - (int)r0[3 * x];
            const int d2 = (int)r2[3 * x] - (int)r0[3 * x];
            a1 += (uint32_t)(d1 * d1); a2 += (uint32_t)(d2 * d2);
        }
        e1y += a1; e2y += a2;
    }
    sR += r; sG += g; sB += b; sTop += top; sBot += bot;
    stex += (double)e1x / (double)(IH * (IW - 2));
    *Rx = ((double)e1x + 1.0) / ((double)e2x + 1.0);
    *Ry = ((double)e1y + 1.0) / ((double)e2y + 1.0);
    *Ymean = (double)(r + 2 * g + b) / (4.0 * IW * IH);
}

int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
    (void)imu_count; /* always 10 (docs/ABI.md) */
    /* ---- IMU: frame means, second differences (white noise), line fit of the gyro at t */
    double gm[3] = {0, 0, 0}, am[3] = {0, 0, 0}, tm = 0;
    for (int r = 0; r < 10; r++) {
        tm += imu[7 * r];
        for (int a = 0; a < 3; a++) { am[a] += imu[7 * r + 1 + a]; gm[a] += imu[7 * r + 4 + a]; }
    }
    tm *= 0.1;
    for (int a = 0; a < 3; a++) { am[a] *= 0.1; gm[a] *= 0.1; }
    double d2g = 0, d2a = 0, stt = 0, stg[3] = {0, 0, 0};
    for (int r = 1; r < 9; r++)
        for (int a = 0; a < 3; a++) {
            const double ag = imu[7 * (r + 1) + 4 + a] - 2 * imu[7 * r + 4 + a] + imu[7 * (r - 1) + 4 + a];
            const double aa = imu[7 * (r + 1) + 1 + a] - 2 * imu[7 * r + 1 + a] + imu[7 * (r - 1) + 1 + a];
            d2g += ag * ag; d2a += aa * aa;
        }
    for (int r = 0; r < 10; r++) {
        const double dt = imu[7 * r] - tm;
        stt += dt * dt;
        for (int a = 0; a < 3; a++) stg[a] += dt * imu[7 * r + 4 + a];
    }
    stt = stt > 1e-12 ? stt : 1e-12;
    double gfit[3];
    for (int a = 0; a < 3; a++) gfit[a] = gm[a] + stg[a] / stt * (t - tm);

    sd2g += d2g; sd2a += d2a;
    const double g2 = gm[0] * gm[0] + gm[1] * gm[1] + gm[2] * gm[2];
    sg2 += g2; syaw2 += gm[2] * gm[2];
    saxy2 += am[0] * am[0] + am[1] * am[1];
    const int first = k == 0;
    for (int a = 0; a < 3; a++) {
        const double p = first ? am[a] : amp[a];
        const double d = (am[a] - p) / DT;
        sj2 += d * d;
        amp[a] = am[a];
    }
    const double startw = (double)(k < 20);
    sg2s += startw * g2;
    for (int a = 0; a < 3; a++) sas[a] += startw * am[a];
    sa2s += startw * (am[0] * am[0] + am[1] * am[1] + am[2] * am[2]);

    /* ---- attitude: integrate every raw gyro row in camera axes, camera k in camera 0 (frame 0 is identity) */
    const double wscale = first ? 0.0 : 1.0;
    for (int r = 0; r < 10; r++) {
        const double *g = imu + 7 * r + 4;
        const double c0 = Rci[0] * g[0] + Rci[1] * g[1] + Rci[2] * g[2];
        const double c1 = Rci[3] * g[0] + Rci[4] * g[1] + Rci[5] * g[2];
        const double c2 = Rci[6] * g[0] + Rci[7] * g[1] + Rci[8] * g[2];
        const double hx = 0.5 * DTI * wscale * c0, hy = 0.5 * DTI * wscale * c1, hz = 0.5 * DTI * wscale * c2;
        const double hw = 1.0 - 0.5 * (hx * hx + hy * hy + hz * hz);
        const double nw = qw * hw - qx * hx - qy * hy - qz * hz;
        const double nx = qw * hx + qx * hw + qy * hz - qz * hy;
        const double ny = qw * hy - qx * hz + qy * hw + qz * hx;
        const double nz = qw * hz + qx * hy - qy * hx + qz * hw;
        const double n = 1.0 / sqrt(nw * nw + nx * nx + ny * ny + nz * nz);
        qw = nw * n; qx = nx * n; qy = ny * n; qz = nz * n;
    }
    const int bad = !(qw == qw && qx == qx && qy == qy && qz == qz);
    qw = sel(bad, 1.0, qw); qx = sel(bad, 0.0, qx); qy = sel(bad, 0.0, qy); qz = sel(bad, 0.0, qz);

    /* ---- images: colour, texture, blur ratios binned by the rotational pixel speed */
    double Rx, Ry, Ymean;
    image_stats(frame, &Rx, &Ry, &Ymean);
    dark += Ymean < 8.0;
    const double wc0 = Rci[0] * gm[0] + Rci[1] * gm[1] + Rci[2] * gm[2];
    const double wc1 = Rci[3] * gm[0] + Rci[4] * gm[1] + Rci[5] * gm[2];
    const double u = fx * fabs(wc1), v = fy * fabs(wc0); /* px/s: yaw -> horizontal, pitch -> vertical */
    const int bx = (u >= 60.0) + (u >= 200.0), by = (v >= 60.0) + (v >= 200.0);
    sRx[bx] += Rx; cnx[bx] += 1;
    sRy[by] += Ry; cny[by] += 1;

    /* ---- payloads (frame-index branches only: the same instructions run on every episode) */
    if (k == F_MED) {
        const double n = (double)(F_MED + 1);
        const double sig_g = sqrt(sd2g / (6.0 * 24.0 * n));
        const double gstart = sqrt(sg2s / 20.0);
        const double m0 = sas[0] / 20, m1 = sas[1] / 20, m2 = sas[2] / 20;
        double av = sa2s / 20 - (m0 * m0 + m1 * m1 + m2 * m2);
        av = av > 0 ? av : 0;
        const uint32_t d2 = (uint32_t)(dark > 0) + (uint32_t)(dark > 2) + (uint32_t)(dark > 20);
        X1 = qlog(gstart, -9, 1, 6) | qlog(sqrt(av), -8, 3, 5) << 6 | qlog(sig_g, -11, -1, 7) << 11 | d2 << 18;
    }
    if (k == F_FREEZE) {
        const double n = (double)(F_FREEZE + 1);
        const double npix = n * IW * IH;
        const double sum = (double)(sR + sG + sB) + 1.0;
        const double Y = (double)(sR + 2 * sG + sB) / (4.0 * npix);
        X2 = qlin(Y, 0, 255, 64) | qlin((double)sG / sum, 0.18, 0.50, 32) << 6 |
             qlin((double)sB / sum, 0.18, 0.50, 32) << 11 | qlog(stex / n, -2, 12, 7) << 16;
        const double sig_a = sqrt(sd2a / (6.0 * 24.0 * n));
        X3 = qbin(sRy[0], cny[0]) | qbin(sRy[1], cny[1]) << 6 | qbin(sRy[2], cny[2]) << 12 | qlog(sig_a, -10, 0, 7) << 18;
        X4 = 0xAu | qbin(sRx[0], cnx[0]) << 4 | qbin(sRx[1], cnx[1]) << 10 | qbin(sRx[2], cnx[2]) << 16 |
             qlog(sqrt(sj2 / (3.0 * n)), -1, 9, 6) << 22;
        const double ty = (double)sTop / (4.0 * n * IW * 60), by_ = (double)sBot / (4.0 * n * IW * 60);
        X0 = qlog(sqrt(sg2 / n), -6, 2, 6) | qlog(sqrt(syaw2 / n), -7, 2, 6) << 6 | qlog(sqrt(saxy2 / n), -4, 4, 6) << 12 |
             qlin(ty, 0, 255, 16) << 18 | qlin(by_, 0, 255, 16) << 22;
#ifdef DEBUGX
        fprintf(stderr, "PROBER k=%lld sig_g=%.6g sig_a=%.6g Y=%.4g cg=%.4g cb=%.4g tex=%.5g jerk=%.5g grms=%.5g yaw=%.5g "
                "axy=%.5g top=%.4g bot=%.4g dark=%lld Rx=%.4g,%.4g,%.4g nx=%lld,%lld,%lld Ry=%.4g,%.4g,%.4g ny=%lld,%lld,%lld\n",
                (long long)k, sqrt(sd2g / (6.0 * 24.0 * n)), sig_a, Y, (double)sG / sum, (double)sB / sum, stex / n, sqrt(sj2 / (3.0 * n)),
                sqrt(sg2 / n), sqrt(syaw2 / n), sqrt(saxy2 / n), ty, by_, (long long)dark,
                sRx[0] / (cnx[0] + (cnx[0] == 0)), sRx[1] / (cnx[1] + (cnx[1] == 0)), sRx[2] / (cnx[2] + (cnx[2] == 0)),
                (long long)cnx[0], (long long)cnx[1], (long long)cnx[2],
                sRy[0] / (cny[0] + (cny[0] == 0)), sRy[1] / (cny[1] + (cny[1] == 0)), sRy[2] / (cny[2] + (cny[2] == 0)),
                (long long)cny[0], (long long)cny[1], (long long)cny[2]);
#endif
    }

    /* ---- fuel channel */
    uint64_t n = 0;
    if (k >= G1_FIRST && k < G2_FIRST) n = N1 + ((uint64_t)X1 << SH);
    if (k >= G2_FIRST && k < G3_FIRST) n = N2 + ((uint64_t)X2 << SH);
    if (k >= G3_FIRST && k < G4_FRAME) n = N3 + ((uint64_t)X3 << SH);
    if (k == X0_FRAME) n += (uint64_t)X0 << SH;
    if (k == G4_FRAME) n = N4 + ((uint64_t)X4 << SH);
    burn(n);
#ifdef DEBUGX
    if (k == G4_FRAME) fprintf(stderr, "PROBEX %u %u %u %u %u %u\n", XI, X1, X2, X3, X4, X0);
#endif

    /* ---- outputs */
    out[0] = out[1] = out[2] = 0;
    out[3] = qx; out[4] = qy; out[5] = qz; out[6] = qw;
    out[7] = 0; out[8] = 0; out[9] = first ? VBIG : 0.0;
    for (int a = 0; a < 3; a++)
        out[10 + a] = Rci[3 * a] * gfit[0] + Rci[3 * a + 1] * gfit[1] + Rci[3 * a + 2] * gfit[2];
    out[11] += WBIG;
    k++;
    return VIOBENCH_STATUS_OK;
}
