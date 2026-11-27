// classical/vio: implementation (see vio.h for the design).
#include "vio.h"

#ifndef __wasm__
#include <cstdio>
#endif

namespace vio {

static inline int ia_of(int anchor) { return NC + 6 * anchor; }
static inline int ir_of(int feature) { return NC + 6 * MAXA + feature; }
static inline f4 ld(const float *p) { return *(const f4 *)p; }
static inline void st(float *p, f4 v) { *(f4 *)p = v; }

void Vio::init(double fx_, double fy_, double cx_, double cy_, const double *T) {
    fx = fx_, fy = fy_, cx = cx_, cy = cy_;
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) Rcb(i, j) = T[4 * i + j];
    tcb = {T[3], T[7], T[11]};
    tbc = tmul(Rcb, tcb) * -1.0;
    R = identity();
    p = v = bg = ba = {0, 0, 0};
    g = {0, 0, -G};
    b1 = {1, 0, 0}, b2 = {0, 1, 0};
    std::memset(C, 0, sizeof(C));
    std::memset(dx, 0, sizeof(dx));
    frame = 0, last_anchor_frame = -100, scan_cell = 0, rr = 0, spent = 0;
    for (auto &f : feats) f.alive = false;
    for (auto &a : anchors) a.alive = false, a.count = 0;
    for (int i = 0; i < 13; i++) last_out[i] = 0;
    last_out[6] = 1;
    thrust_sum[0] = thrust_sum[1] = 0, thrust_count[0] = thrust_count[1] = 0;
    thrust_on = true, thrust_checks = thrust_misfits = 0;
    for (int &s : stats) s = 0;
}

// ---------------------------------------------------------------- images
// Level 1 is the 2x2 box mean of the green channel, level 2 the 2x2 box mean of level 1. Both builds average the two
// rows with rounding and then the two columns without, so the wasm and the scalar code give identical bytes.
#if defined(__wasm_simd128__)
static inline v128_t greens16(const uint8_t *p) {  // the 16 green bytes of 16 RGB pixels
    v128_t v0 = wasm_v128_load(p), v1 = wasm_v128_load(p + 16), v2 = wasm_v128_load(p + 32);
    v128_t s = wasm_i8x16_shuffle(v0, v1, 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 0, 0, 0, 0, 0);
    return wasm_i8x16_shuffle(s, v2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 21, 24, 27, 30);
}
#endif

void Vio::build_pyramid(const uint8_t *rgb) {
    green = rgb + 1, l1 = pyr1, l2 = pyr2;
#if defined(__wasm_simd128__)
    {
        const uint8_t *r0 = rgb;
        uint8_t *o = pyr1;
        for (int y = 0; y < H / 2; y++, r0 += 3 * W) {
#pragma clang loop unroll(full)
            for (int x = 0; x < W / 2; x += 16, r0 += 96, o += 16) {
                v128_t va = wasm_u8x16_avgr(greens16(r0), greens16(r0 + 3 * W)), vb = wasm_u8x16_avgr(greens16(r0 + 48), greens16(r0 + 3 * W + 48));
                v128_t ha = wasm_u16x8_shr(wasm_u16x8_extadd_pairwise_u8x16(va), 1), hb = wasm_u16x8_shr(wasm_u16x8_extadd_pairwise_u8x16(vb), 1);
                wasm_v128_store(o, wasm_u8x16_narrow_i16x8(ha, hb));
            }
        }
        const uint8_t *s0 = pyr1;
        o = pyr2;
        for (int y = 0; y < H / 4; y++, s0 += W / 2) {
#pragma clang loop unroll(full)
            for (int x = 0; x < W / 4; x += 16, s0 += 32, o += 16) {
                v128_t va = wasm_u8x16_avgr(wasm_v128_load(s0), wasm_v128_load(s0 + W / 2)), vb = wasm_u8x16_avgr(wasm_v128_load(s0 + 16), wasm_v128_load(s0 + W / 2 + 16));
                v128_t ha = wasm_u16x8_shr(wasm_u16x8_extadd_pairwise_u8x16(va), 1), hb = wasm_u16x8_shr(wasm_u16x8_extadd_pairwise_u8x16(vb), 1);
                wasm_v128_store(o, wasm_u8x16_narrow_i16x8(ha, hb));
            }
        }
    }
#else
    for (int y = 0; y < H / 2; y++) {
        const uint8_t *a = green + 3 * W * 2 * y, *b = a + 3 * W;
        uint8_t *o = pyr1 + y * (W / 2);
        for (int x = 0; x < W / 2; x++) o[x] = (uint8_t)((((a[6 * x] + b[6 * x] + 1) >> 1) + ((a[6 * x + 3] + b[6 * x + 3] + 1) >> 1)) >> 1);
    }
    for (int y = 0; y < H / 4; y++) {
        const uint8_t *a = pyr1 + (W / 2) * 2 * y, *b = a + W / 2;
        uint8_t *o = pyr2 + y * (W / 4);
        for (int x = 0; x < W / 4; x++) o[x] = (uint8_t)((((a[2 * x] + b[2 * x] + 1) >> 1) + ((a[2 * x + 1] + b[2 * x + 1] + 1) >> 1)) >> 1);
    }
#endif
}

// ---------------------------------------------------------------- IMU
void Vio::propagate(const double *imu, int count) {
    // Rows of the error-state transition for attitude (TH), position (PP) and velocity (VV); the other rows are the
    // identity. Only the columns that are not known in advance are carried: attitude, gyro bias, accelerometer bias,
    // gravity (COLS); TH never leaves the attitude and gyro-bias columns. In the others VV has the identity under
    // velocity and PP the identity under position and (elapsed time) x identity under velocity.
    static const int COLS[11] = {0, 1, 2, 9, 10, 11, 12, 13, 14, 15, 16};
    float TH[3][6] = {}, PP[3][11] = {}, VV[3][11] = {};
    for (int i = 0; i < 3; i++) TH[i][i] = 1;
    double total = 0;
    V3 gs{0, 0, 0}, as{0, 0, 0};
    // the state advances per sample, the transition per pair of samples (mean specific force, rotation at mid-pair)
    M3 R0 = R;
    V3 a0{0, 0, 0};
    double dt0 = 0;
    for (int s = 0; s < count; s++) {
        const double *row = imu + 7 * s;
        double dt = row[0] - last_t;
        if (!(dt > 1e-4 && dt < 0.05)) dt = 0.005;
        last_t = row[0];
        total += dt;
        V3 am{row[1], row[2], row[3]}, gm{row[4], row[5], row[6]};
        gs = gs + gm, as = as + am;
        V3 w = gm - bg, a = am - ba;
        M3 Eh = expm(w * (0.5 * dt)), Rm = R * Eh;
        V3 aw = Rm * a + g;
        p = p + v * dt + aw * (0.5 * dt * dt);
        v = v + aw * dt;
        M3 Rn = Rm * Eh;
        bool first = (s & 1) == 0 && s + 1 < count;
        if (first) {
            R0 = R, a0 = a, dt0 = dt, R = Rn;
            continue;
        }
        bool single = (s & 1) == 0;  // an odd sample count leaves the last one alone
        const M3 &Rmid = single ? Rm : R;  // R: the attitude between the two samples of the pair
        double dtp = single ? dt : dt0 + dt;
        V3 ap = single ? a : (a0 * dt0 + a * dt) * (1.0 / dtp);
        M3 E = single ? Eh * Eh : transpose(R0) * Rn, M = Rmid * skew(ap);
        float fdt = (float)dtp, hdt2 = (float)(0.5 * dtp * dtp);
        float D[3][11];
        for (int r = 0; r < 3; r++) {
            float m0 = (float)M(r, 0), m1 = (float)M(r, 1), m2 = (float)M(r, 2);
            for (int k = 0; k < 6; k++) D[r][k] = -(m0 * TH[0][k] + m1 * TH[1][k] + m2 * TH[2][k]);
            for (int k = 0; k < 3; k++) D[r][6 + k] = -(float)Rmid(r, k);
        }
        D[0][9] = (float)(G * b1.x), D[1][9] = (float)(G * b1.y), D[2][9] = (float)(G * b1.z);
        D[0][10] = (float)(G * b2.x), D[1][10] = (float)(G * b2.y), D[2][10] = (float)(G * b2.z);
        for (int r = 0; r < 3; r++)
            for (int c = 0; c < 11; c++) {
                PP[r][c] += fdt * VV[r][c] + hdt2 * D[r][c];
                VV[r][c] += fdt * D[r][c];
            }
        float e[9];
        for (int k = 0; k < 9; k++) e[k] = (float)E.m[k];
        for (int k = 0; k < 6; k++) {
            float t0 = TH[0][k], t1 = TH[1][k], t2 = TH[2][k];
            TH[0][k] = e[0] * t0 + e[3] * t1 + e[6] * t2;
            TH[1][k] = e[1] * t0 + e[4] * t1 + e[7] * t2;
            TH[2][k] = e[2] * t0 + e[5] * t1 + e[8] * t2;
        }
        for (int r = 0; r < 3; r++) TH[r][3 + r] -= fdt;
        R = Rn;
    }
    orthonormalize(R);
    gyro_mean = gs * (1.0 / count), acc_mean = as * (1.0 / count);

    // covariance: rows 0..8 become Phi9 C, the 9x9 corner Phi9 C Phi9^T, and the columns mirror the rows
    float ft = (float)total;
    alignas(16) static float Mx[9][NSP];
    for (int r = 0; r < 3; r++) {
        f4 kt[6], kp[11], kv[11], vt = splat(ft);
        for (int i = 0; i < 6; i++) kt[i] = splat(TH[r][i]);
        for (int i = 0; i < 11; i++) kp[i] = splat(PP[r][i]), kv[i] = splat(VV[r][i]);
#pragma clang loop unroll(full)
        for (int c = 0; c < NSP; c += 4) {
            f4 c0 = ld(C[0] + c), c1 = ld(C[1] + c), c2 = ld(C[2] + c), c9 = ld(C[9] + c), c10 = ld(C[10] + c), c11 = ld(C[11] + c);
            f4 vel = ld(C[6 + r] + c);
            st(Mx[r] + c, kt[0] * c0 + kt[1] * c1 + kt[2] * c2 + kt[3] * c9 + kt[4] * c10 + kt[5] * c11);
            f4 sp = ld(C[3 + r] + c) + vt * vel + kp[0] * c0 + kp[1] * c1 + kp[2] * c2 + kp[3] * c9 + kp[4] * c10 + kp[5] * c11;
            f4 sv = vel + kv[0] * c0 + kv[1] * c1 + kv[2] * c2 + kv[3] * c9 + kv[4] * c10 + kv[5] * c11;
#pragma clang loop unroll(full)
            for (int i = 6; i < 11; i++) {
                f4 q = ld(C[COLS[i]] + c);
                sp += kp[i] * q, sv += kv[i] * q;
            }
            st(Mx[3 + r] + c, sp), st(Mx[6 + r] + c, sv);
        }
    }
    alignas(16) float Phi[9][20] = {};
    for (int r = 0; r < 3; r++) {
        for (int i = 0; i < 6; i++) Phi[r][COLS[i]] = TH[r][i];
        for (int i = 0; i < 11; i++) Phi[3 + r][COLS[i]] = PP[r][i], Phi[6 + r][COLS[i]] = VV[r][i];
        Phi[3 + r][3 + r] = 1, Phi[3 + r][6 + r] = ft, Phi[6 + r][6 + r] = 1;
    }
    float N[9][9];
    for (int r = 0; r < 9; r++)
        for (int c = r; c < 9; c++) {
            // lanes beyond NC of Phi are zero, so the columns of Mx past the core do not contribute
            f4 q = ld(Mx[r]) * ld(Phi[c]) + ld(Mx[r] + 4) * ld(Phi[c] + 4) + ld(Mx[r] + 8) * ld(Phi[c] + 8) + ld(Mx[r] + 12) * ld(Phi[c] + 12) + ld(Mx[r] + 16) * ld(Phi[c] + 16);
            N[r][c] = N[c][r] = hsum(q);
        }
    float qg = (float)(P.sig_g * P.sig_g * total * P.q_scale), qa = (float)(P.sig_a * P.sig_a * total * P.q_scale);
    for (int r = 0; r < 9; r++) {
        std::memcpy(C[r], Mx[r], sizeof(float) * NSP);
        for (int c = 0; c < 9; c++) C[r][c] = N[r][c];
        for (int c = 9; c < NS; c++) C[c][r] = Mx[r][c];
    }
    for (int i = 0; i < 3; i++) {
        C[i][i] += qg;
        C[6 + i][6 + i] += qa;
        C[3 + i][3 + i] += qa * ft * ft / 3;
        C[3 + i][6 + i] += qa * ft / 2;
        C[6 + i][3 + i] += qa * ft / 2;
        C[9 + i][9 + i] += (float)(P.sig_bg * P.sig_bg * total);
        C[12 + i][12 + i] += (float)(P.sig_ba * P.sig_ba * total);
    }
}

// ---------------------------------------------------------------- geometry
// Once per frame: for every anchor the map from its camera to the current one, at the propagated state.
static M3 Mk;  // Rcb R^T of the current frame
void Vio::anchor_frames() {
    Mk = Rcb * transpose(R);
    M3 Rbc = transpose(Rcb);
    for (int j = 0; j < MAXA; j++) {
        Anchor &A = anchors[j];
        if (!A.alive) continue;
        A.Rrel = Mk * A.R * Rbc;
        A.t = Mk * (A.R * tbc + A.p - p) + tcb;
    }
}

// Predicted pixel of a feature, the 2x2 warp of its patch (anchor pixels -> current pixels) and the pixel sigma that
// the uncertainty of its depth causes.
bool Vio::project(const Feature &f, int ir, double &u, double &v_, float *A, double &sigma) const {
    const Anchor &a = anchors[f.anchor];
    const M3 &Q = a.Rrel;
    V3 q{Q.m[0] * f.bx + Q.m[1] * f.by + Q.m[2] + a.t.x * f.rho, Q.m[3] * f.bx + Q.m[4] * f.by + Q.m[5] + a.t.y * f.rho, Q.m[6] * f.bx + Q.m[7] * f.by + Q.m[8] + a.t.z * f.rho};
    if (q.z < 1e-3) return false;
    double iz = 1.0 / q.z, hx = q.x * iz, hy = q.y * iz;
    u = fx * hx + cx, v_ = fy * hy + cy;
    A[0] = (float)((Q.m[0] - hx * Q.m[6]) * iz);
    A[1] = (float)((Q.m[1] - hx * Q.m[7]) * iz * fx / fy);
    A[2] = (float)((Q.m[3] - hy * Q.m[6]) * iz * fy / fx);
    A[3] = (float)((Q.m[4] - hy * Q.m[7]) * iz);
    double du = fx * (a.t.x - hx * a.t.z) * iz * f.rho, dv = fy * (a.t.y - hy * a.t.z) * iz * f.rho;
    double var = C[ir][ir], s2 = (du * du + dv * dv) * (var > 0 ? var : 0);
    if (P.sigma_full > 0.5) {  // plus what the velocity uncertainty moves the point in one frame
        double k = 0.05 * f.rho * iz * fx;
        s2 += (double)(C[6][6] + C[7][7] + C[8][8]) * k * k;
    }
    sigma = std::sqrt(s2);
    return true;
}

typedef short s8v __attribute__((vector_size(16), aligned(2)));
typedef unsigned char u8x8 __attribute__((vector_size(8), aligned(1)));
static inline s8v widen8(const uint8_t *q) {
    u8x8 b;
    std::memcpy(&b, q, 8);
    return __builtin_convertvector(b, s8v);
}
static inline int dot8(s8v a, s8v b) {  // sum of the eight products
#if defined(__wasm_simd128__)
    v128_t d = wasm_i32x4_dot_i16x8((v128_t)a, (v128_t)b);
    return wasm_i32x4_extract_lane(d, 0) + wasm_i32x4_extract_lane(d, 1) + wasm_i32x4_extract_lane(d, 2) + wasm_i32x4_extract_lane(d, 3);
#else
    int s = 0;
    for (int i = 0; i < 8; i++) s += a[i] * b[i];
    return s;
#endif
}
typedef short s4v __attribute__((vector_size(8), aligned(2)));
static inline f4 half_f(s8v v, int hi) {  // lanes 0..3 or 4..7 as floats
    s4v h = hi ? __builtin_shufflevector(v, v, 4, 5, 6, 7) : __builtin_shufflevector(v, v, 0, 1, 2, 3);
    return __builtin_convertvector(__builtin_convertvector(h, i4), f4);
}
static inline int sum8(s8v a) { return ((a[0] + a[1]) + (a[2] + a[3])) + ((a[4] + a[5]) + (a[6] + a[7])); }

// The templates of a new feature. Its centre is the centre of an 8x8 window of level 1 with even coordinates, which
// puts the 8x8 patch (and the ring around it that the gradients need) on whole pixels of all three levels.
// A corner needs two-dimensional structure at every level. A patch that is an edge at some level (aliased wall and
// floor boundaries look like corners at the fine level only) becomes an edge feature if allowed: its alignment and its
// measurement act only along the edge normal, taken from level 1.
bool Vio::make_template(Feature &f, bool allow_edge) {
    s8v tv[LEVELS][8], xv[LEVELS][8], yv[LEVELS][8];
    float mean[LEVELS], mx[LEVELS], my[LEVELS], ga[LEVELS], gb[LEVELS], gc[LEVELS];
    bool corner = true;
    for (int l = 0; l < LEVELS; l++) {
        int w = W >> l, h = H >> l;
        int x0 = (int)std::floor((f.ax + 0.5) / (1 << l) - 0.5 - 4.5 + 0.25), y0 = (int)std::floor((f.ay + 0.5) / (1 << l) - 0.5 - 4.5 + 0.25);  // corner of the 10x10 block
        f.level_ok[l] = x0 >= 0 && y0 >= 0 && x0 + 10 < w && y0 + 10 < h;
        if (!f.level_ok[l]) {
            if (l < 2) return false;
            continue;
        }
        alignas(16) uint8_t blk[10][16];
        if (l == 0) {
            const uint8_t *q = green + 3 * (y0 * W + x0);
#pragma clang loop unroll(full)
            for (int j = 0; j < 10; j++, q += 3 * W)
#pragma clang loop unroll(full)
                for (int i = 0; i < 10; i++) blk[j][i] = q[3 * i];
        } else {
            const uint8_t *q = (l == 1 ? l1 : l2) + y0 * w + x0;
#pragma clang loop unroll(full)
            for (int j = 0; j < 10; j++, q += w) std::memcpy(blk[j], q, 16);
        }
        // sums over the patch of the pixel t, twice its central differences gx, gy, and their products
        s8v st_ = {}, sx_ = {}, sy_ = {};
        int tt = 0, xx = 0, yy = 0, xy = 0;
#pragma clang loop unroll(full)
        for (int j = 0; j < 8; j++) {
            const uint8_t *c = blk[j + 1] + 1;
            s8v t = widen8(c), gx = widen8(c + 1) - widen8(c - 1), gy = widen8(c + 16) - widen8(c - 16);
            tv[l][j] = t, xv[l][j] = gx, yv[l][j] = gy;
            st_ += t, sx_ += gx, sy_ += gy;
            tt += dot8(t, t), xx += dot8(gx, gx), yy += dot8(gy, gy), xy += dot8(gx, gy);
        }
        mean[l] = sum8(st_) * (1.0f / TN), mx[l] = sum8(sx_) * (1.0f / TN), my[l] = sum8(sy_) * (1.0f / TN);
        // structure tensor of the zero-mean gradients (the differences are twice the gradient)
        float a = 0.25f * (xx - TN * mx[l] * mx[l]), b = 0.25f * (xy - TN * mx[l] * my[l]), c = 0.25f * (yy - TN * my[l] * my[l]);
        ga[l] = a, gb[l] = b, gc[l] = c, f.TT[l] = tt - TN * mean[l] * mean[l];
        float det = a * c - b * b, half = 0.5f * (a + c), root = std::sqrt(std::fmax(0.0f, half * half - det)), lmin = half - root, lmax = half + root;
        if (!(lmin > (float)P.min_ratio * lmax && lmin > (float)P.min_eig * TN && det > 0)) corner = false, stats[14 + (l > 0)]++;
    }
    f.edge = !corner || P.force_edge > 0.5;
    if (f.edge) {
        if (!allow_edge && P.force_edge < 0.5) return false;
        // the normal: the eigenvector of the larger eigenvalue at level 1
        float a = ga[1], b = gb[1], c = gc[1], half = 0.5f * (a + c), lmax = half + std::sqrt(std::fmax(0.0f, half * half - (a * c - b * b)));
        float vx = lmax - c, vy = b;
        if (vx * vx + vy * vy < 1e-6f * lmax * lmax) vx = a >= c ? 1.0f : 0.0f, vy = a >= c ? 0.0f : 1.0f;
        float in = 1.0f / std::sqrt(vx * vx + vy * vy);
        f.nx = vx * in, f.ny = vy * in;
    }
    for (int l = 0; l < LEVELS; l++) {
        if (!f.level_ok[l]) continue;
        float g0, g1, g2;
        if (f.edge) {  // the inverse structure tensor restricted to the normal: n n^T / (n^T G n)
            float e = ga[l] * f.nx * f.nx + 2 * gb[l] * f.nx * f.ny + gc[l] * f.ny * f.ny;
            if (!(e > (float)P.edge_min * TN)) {
                if (l < 2) return false;
                f.level_ok[l] = false;
                continue;
            }
            g0 = f.nx * f.nx / e, g1 = f.nx * f.ny / e, g2 = f.ny * f.ny / e;
        } else {
            float det = ga[l] * gc[l] - gb[l] * gb[l];
            g0 = gc[l] / det, g1 = -gb[l] / det, g2 = ga[l] / det;
        }
        f.Gi[l][0] = g0, f.Gi[l][1] = g1, f.Gi[l][2] = g2;
        f4 vm = splat(mean[l]), vmx = splat(mx[l]), vmy = splat(my[l]), h0 = splat(0.5f * g0), h1 = splat(0.5f * g1), h2 = splat(0.5f * g2);
        f4 sx = splat(0), sy = splat(0);
#pragma clang loop unroll(full)
        for (int j = 0; j < 8; j++)
#pragma clang loop unroll(full)
            for (int half_ = 0; half_ < 2; half_++) {
                int k = j * TP + 4 * half_;
                f4 t = half_f(tv[l][j], half_) - vm, gx = half_f(xv[l][j], half_) - vmx, gy = half_f(yv[l][j], half_) - vmy;
                f4 cxv = h0 * gx + h1 * gy, cyv = h1 * gx + h2 * gy;
                st(f.T[l] + k, t), st(f.cx[l] + k, cxv), st(f.cy[l] + k, cyv);
                sx += cxv * t, sy += cyv * t;
            }
        f.cT[l][0] = hsum(sx), f.cT[l][1] = hsum(sy);
    }
    return true;
}

// One inverse-compositional pass: sample the 8x8 patch at (x, y) of an image with the warp (a0..a3), four pixels at a
// time, and return the template-space step (ddx, ddy) that aligns it and its zero-mean correlation with the template.
// STRIDE 3 reads the green bytes of the RGB frame, STRIDE 1 a pyramid level; a 4-byte load fetches both columns.
template <int STRIDE>
static inline void pass_kernel(const uint8_t *base, int w, float x, float y, float a0, float a1, float a2, float a3, const float *T, const float *cxp, const float *cyp,
                               float &sw, float &sww, float &swt, float &sx, float &sy) {
    const f4 lo = {-3.5f, -2.5f, -1.5f, -0.5f}, hi = {0.5f, 1.5f, 2.5f, 3.5f};
    const f4 ax[2] = {lo * splat(a0), hi * splat(a0)}, ay[2] = {lo * splat(a2), hi * splat(a2)};
    const i4 mask = {255, 255, 255, 255};
    const int shift = 8 * STRIDE, down = w * STRIDE;
    f4 vW = splat(0), vWW = splat(0), vWT = splat(0), vX = splat(0), vY = splat(0);
    float xr = x - 3.5f * a1, yr = y - 3.5f * a3;
#pragma clang loop unroll(full)
    for (int j = 0; j < TP; j++, xr += a1, yr += a3) {
#pragma clang loop unroll(full)
        for (int half = 0; half < 2; half++) {
            f4 X = splat(xr) + ax[half], Y = splat(yr) + ay[half];
            i4 Xi = __builtin_convertvector(X, i4), Yi = __builtin_convertvector(Y, i4);
            f4 FX = X - __builtin_convertvector(Xi, f4), FY = Y - __builtin_convertvector(Yi, f4);
            i4 idx = (Yi * w + Xi) * STRIDE;
            i4 top, bot;
            for (int n = 0; n < 4; n++) {
                const uint8_t *q = base + idx[n];
                int t, b;
                std::memcpy(&t, q, 4), std::memcpy(&b, q + down, 4);
                top[n] = t, bot[n] = b;
            }
            f4 p00 = __builtin_convertvector(top & mask, f4), p01 = __builtin_convertvector((top >> shift) & mask, f4);
            f4 p10 = __builtin_convertvector(bot & mask, f4), p11 = __builtin_convertvector((bot >> shift) & mask, f4);
            f4 a = p00 + FX * (p01 - p00), b = p10 + FX * (p11 - p10), V = a + FY * (b - a);
            int k = j * TP + half * 4;
            vW += V, vWW += V * V, vWT += V * ld(T + k), vX += V * ld(cxp + k), vY += V * ld(cyp + k);
        }
    }
    sw = hsum(vW), sww = hsum(vWW), swt = hsum(vWT), sx = hsum(vX), sy = hsum(vY);
}

// (x, y): patch centre in pixels of image level m. A: warp in level-0 units, k: template step in image-level pixels.
bool Vio::pass(int m, float x, float y, const float *A, float k, const Feature &f, int l, float &ddx, float &ddy, float &zncc) const {
    int w = W >> m, h = H >> m;
    float a0 = A[0] * k, a1 = A[1] * k, a2 = A[2] * k, a3 = A[3] * k;
    float ex = 3.5f * (std::fabs(a0) + std::fabs(a1)), ey = 3.5f * (std::fabs(a2) + std::fabs(a3));
    if (!(x - ex >= 0 && y - ey >= 0 && x + ex < w - 2.01f && y + ey < h - 2.01f)) return false;
    float sw, sww, swt, sx, sy;
    if (m == 0)
        pass_kernel<3>(green, w, x, y, a0, a1, a2, a3, f.T[l], f.cx[l], f.cy[l], sw, sww, swt, sx, sy);
    else
        pass_kernel<1>(m == 1 ? l1 : l2, w, x, y, a0, a1, a2, a3, f.T[l], f.cx[l], f.cy[l], sw, sww, swt, sx, sy);
    ddx = sx - f.cT[l][0], ddy = sy - f.cT[l][1];
    float var = sww - sw * sw * (1.0f / TN);
    zncc = swt / std::sqrt(var * f.TT[l] + 1e-6f);
    return true;
}

// ---------------------------------------------------------------- filter
void Vio::kill_feature(int i) {
    Feature &f = feats[i];
    if (!f.alive) return;
    f.alive = false;
    int ir = ir_of(i);
    std::memset(C[ir], 0, sizeof(float) * NSP);
    for (int k = 0; k < NS; k++) C[k][ir] = 0;
    dx[ir] = 0;
    Anchor &A = anchors[f.anchor];
    if (--A.count <= 0) {
        A.alive = false, A.count = 0;
        int ia = ia_of(f.anchor);
        for (int d = 0; d < 6; d++) {
            std::memset(C[ia + d], 0, sizeof(float) * NSP);
            for (int k = 0; k < NS; k++) C[k][ia + d] = 0;
            dx[ia + d] = 0;
        }
    }
}

// The accumulated error state of the frame goes into the nominal state.
void Vio::inject() {
    // a trust region: no single frame may move the state further than this, however large the gain
    static const struct { int at, n; double limit; } CLAMP[6] = {{0, 3, 0.2}, {3, 3, 1.0}, {6, 3, 3.0}, {9, 3, 0.02}, {12, 3, 0.2}, {15, 2, 0.15}};
    for (const auto &c : CLAMP) {
        double n2 = 0;
        for (int k = 0; k < c.n; k++) n2 += (double)dx[c.at + k] * dx[c.at + k];
        if (n2 > c.limit * c.limit) {
            float sc = (float)(c.limit / std::sqrt(n2));
            for (int k = 0; k < c.n; k++) dx[c.at + k] *= sc;
        }
    }
    R = R * expm({dx[0], dx[1], dx[2]});
    p = p + V3{dx[3], dx[4], dx[5]};
    v = v + V3{dx[6], dx[7], dx[8]};
    bg = bg + V3{dx[9], dx[10], dx[11]};
    ba = ba + V3{dx[12], dx[13], dx[14]};
    V3 gn = g + (b1 * dx[15] + b2 * dx[16]) * G;
    g = gn * (G / norm(gn));
    V3 gu = g * (1.0 / G);
    b1 = b1 - gu * dot(gu, b1);
    b1 = b1 * (1.0 / norm(b1));
    b2 = cross(gu, b1);
    for (int j = 0; j < MAXA; j++)
        if (anchors[j].alive) {
            const float *d = dx + ia_of(j);
            anchors[j].R = anchors[j].R * expm({d[0], d[1], d[2]});
            anchors[j].p = anchors[j].p + V3{d[3], d[4], d[5]};
        }
    {
        // the correction common to the depths of the established features is a revision of the map's scale
        float vals[MAXF];
        int nv = 0;
        for (int i = 0; i < MAXF; i++)
            if (feats[i].alive && feats[i].used >= 5) vals[nv++] = dx[ir_of(i)];
        scale_step = 0;
        if (nv >= 4) {
            for (int a = 1; a < nv; a++) {
                float key = vals[a];
                int b = a - 1;
                for (; b >= 0 && vals[b] > key; b--) vals[b + 1] = vals[b];
                vals[b + 1] = key;
            }
            scale_step = -0.5 * (vals[nv / 2] + vals[(nv - 1) / 2]);  // log of the factor on distances
        }
        scale_log += scale_step;
    }
    for (int i = 0; i < MAXF; i++)
        if (feats[i].alive) {
            double dl = dx[ir_of(i)];  // the state is log(rho)
            dl = dl > 1.5 ? 1.5 : (dl < -1.5 ? -1.5 : dl);
            double r = feats[i].rho * exp_small(dl);
            feats[i].rho = r < P.rho_min ? P.rho_min : (r > P.rho_max ? P.rho_max : r);
        }
    std::memset(dx, 0, sizeof(dx));
}

// The linearised measurement of feature i at the propagated state: the two rows of d(normalized image point)/d(state)
// over the 13 states it touches (attitude, position, anchor attitude, anchor position, log inverse depth) and the
// predicted point itself in (r0, r1).
bool Vio::rows_of(int i, float *h0, float *h1, float &r0, float &r1) const {
    const Feature &f = feats[i];
    const Anchor &a = anchors[f.anchor];
    const M3 &Q = a.Rrel;
    V3 q{Q.m[0] * f.bx + Q.m[1] * f.by + Q.m[2] + a.t.x * f.rho, Q.m[3] * f.bx + Q.m[4] * f.by + Q.m[5] + a.t.y * f.rho, Q.m[6] * f.bx + Q.m[7] * f.by + Q.m[8] + a.t.z * f.rho};
    if (q.z < 1e-3) return false;
    double iz = 1.0 / q.z, hx = q.x * iz, hy = q.y * iz;
    M3 Jth = skew(q - tcb * f.rho) * Rcb;
    M3 Jtha = Q * skew(V3{f.bx, f.by, 1.0} - tcb * f.rho) * Rcb;  // negated below
    for (int k = 0; k < 3; k++) {
        double c[4][3] = {{Jth(0, k), Jth(1, k), Jth(2, k)}, {-f.rho * Mk(0, k), -f.rho * Mk(1, k), -f.rho * Mk(2, k)}, {-Jtha(0, k), -Jtha(1, k), -Jtha(2, k)},
                          {f.rho * Mk(0, k), f.rho * Mk(1, k), f.rho * Mk(2, k)}};
        for (int b = 0; b < 4; b++) {
            h0[3 * b + k] = (float)(iz * (c[b][0] - hx * c[b][2]));
            h1[3 * b + k] = (float)(iz * (c[b][1] - hy * c[b][2]));
        }
    }
    h0[12] = (float)(iz * f.rho * (a.t.x - hx * a.t.z));
    h1[12] = (float)(iz * f.rho * (a.t.y - hy * a.t.z));
    r0 = (float)hx, r1 = (float)hy;
    return true;
}

// One gated 2-d EKF update with the measured pixel (zu, zv) of corner feature i, linearised at the propagated state;
// the correction is accumulated in dx. Returns false if the innovation gate rejects the measurement.
bool Vio::update_feature(int i, double zu, double zv) {
    Feature &f = feats[i];
    int ia = ia_of(f.anchor), ir = ir_of(i);
    float h0[13], h1[13], r0, r1;
    if (!rows_of(i, h0, h1, r0, r1)) return false;
    const float *rows[13];
    const float *dxa = dx + ia;
    for (int k = 0; k < 6; k++) rows[k] = C[k], rows[6 + k] = C[ia + k];
    rows[12] = C[ir];
    // innovation at the state corrected by the earlier updates of this frame
    r0 = (float)((zu - cx) / fx) - r0, r1 = (float)((zv - cy) / fy) - r1;
    for (int k = 0; k < 6; k++) r0 -= h0[k] * dx[k] + h0[6 + k] * dxa[k], r1 -= h1[k] * dx[k] + h1[6 + k] * dxa[k];
    r0 -= h0[12] * dx[ir], r1 -= h1[12] * dx[ir];
    // P H^T as two rows, by the symmetry of P a weighted sum of 13 of its rows
    alignas(16) float PH0[NSP], PH1[NSP];
    {
        f4 k0[13], k1[13];
        for (int k = 0; k < 13; k++) k0[k] = splat(h0[k]), k1[k] = splat(h1[k]);
#pragma clang loop unroll(full)
        for (int c = 0; c < NSP; c += 4) {
            f4 r = ld(rows[0] + c);
            f4 s0 = k0[0] * r, s1 = k1[0] * r;
#pragma clang loop unroll(full)
            for (int k = 1; k < 13; k++) {
                r = ld(rows[k] + c);
                s0 += k0[k] * r, s1 += k1[k] * r;
            }
            st(PH0 + c, s0), st(PH1 + c, s1);
        }
    }
    // measurement noise: a floor plus image noise through the template's inverse structure tensor and the patch warp
    double rn = P.px_sigma / fx, n2 = P.img_sigma * P.img_sigma / (fx * fx);
    rn *= rn;
    const float *Gi = f.Gi[0], *A = f.A;
    double t00 = A[0] * Gi[0] + A[1] * Gi[1], t01 = A[0] * Gi[1] + A[1] * Gi[2], t10 = A[2] * Gi[0] + A[3] * Gi[1], t11 = A[2] * Gi[1] + A[3] * Gi[2];
    double S00 = rn + n2 * (t00 * A[0] + t01 * A[1]), S01 = n2 * (t00 * A[2] + t01 * A[3]), S11 = rn + n2 * (t10 * A[2] + t11 * A[3]);
    for (int k = 0; k < 6; k++) {
        S00 += h0[k] * PH0[k] + h0[6 + k] * PH0[ia + k];
        S01 += h0[k] * PH1[k] + h0[6 + k] * PH1[ia + k];
        S11 += h1[k] * PH1[k] + h1[6 + k] * PH1[ia + k];
    }
    S00 += h0[12] * PH0[ir], S01 += h0[12] * PH1[ir], S11 += h1[12] * PH1[ir];
    {
        // Second order in the log depth: the pixel moves with exp(dlambda), the filter models 1 + dlambda. While the
        // depth is very uncertain the remainder dlambda^2 / 2 (mean var / 2, variance var^2 / 2) along the depth
        // direction of the measurement is as large as the measurement noise; ignoring it makes the filter sure of
        // velocity and tilt within half a second of a start in motion.
        double var = C[ir][ir] > 0 ? C[ir][ir] : 0, k = P.second_order;
        double m = 0.5 * k * var, q = 0.5 * k * var * var;
        r0 -= (float)(m * h0[12]), r1 -= (float)(m * h1[12]);
        S00 += q * h0[12] * h0[12], S01 += q * h0[12] * h1[12], S11 += q * h1[12] * h1[12];
    }
    double det = S00 * S11 - S01 * S01;
    if (!(det > 0)) return false;
    double i00 = S11 / det, i01 = -S01 / det, i11 = S00 / det;
    double chi2 = r0 * (i00 * r0 + i01 * r1) + r1 * (i01 * r0 + i11 * r1);
#ifndef __wasm__
    if (P.debug > 0.5)
        std::fprintf(stderr, "  f%02d a%d age %3d used %3d res %6.2f %6.2f px  chi2 %7.2f  S %.2f %.2f px  rho %.3f sr %.2f  z %.1f %.1f\n", i, f.anchor, f.age, f.used, r0 * fx, r1 * fy, chi2,
                     std::sqrt(S00) * fx, std::sqrt(S11) * fy, f.rho, std::sqrt(C[ir][ir]), zu, zv);
#endif
    nis += 0.05 * ((chi2 < P.gate ? 0.5 * chi2 : 0.5 * P.gate) - nis);  // per degree of freedom, rejected ones at the gate
    if (!(chi2 < P.gate)) return false;
    // gain rows K = PH S^-1, dx += K r, P -= K PH^T
    alignas(16) float K0[NSP], K1[NSP];
    {
        f4 a00 = splat((float)i00), a01 = splat((float)i01), a11 = splat((float)i11), v0 = splat(r0), v1 = splat(r1);
#pragma clang loop unroll(full)
        for (int c = 0; c < NSP; c += 4) {
            f4 p0 = ld(PH0 + c), p1 = ld(PH1 + c);
            f4 k0 = p0 * a00 + p1 * a01, k1 = p0 * a01 + p1 * a11;
            st(K0 + c, k0), st(K1 + c, k1);
            st(dx + c, ld(dx + c) + k0 * v0 + k1 * v1);
        }
    }
    for (int r = 0; r < NS; r++) {
        float k0 = K0[r], k1 = K1[r];
        if (k0 == 0 && k1 == 0) continue;
        f4 v0 = splat(k0), v1 = splat(k1);
        float *row = C[r];
#pragma clang loop unroll(full)
        for (int c = 0; c < NSP; c += 4) st(row + c, ld(row + c) - (v0 * ld(PH0 + c) + v1 * ld(PH1 + c)));
    }
    return true;
}

// The same for an edge feature: one scalar update with the offset of the aligned patch across the edge.
bool Vio::update_edge(int i, double zu, double zv) {
    Feature &f = feats[i];
    int ia = ia_of(f.anchor), ir = ir_of(i);
    float h0[13], h1[13], r0, r1;
    if (!rows_of(i, h0, h1, r0, r1)) return false;
    // the edge normal in the current image: the template normal through the inverse transpose of the patch warp
    const float *A = f.A;
    float mx = A[3] * f.nx - A[2] * f.ny, my = -A[1] * f.nx + A[0] * f.ny, in = 1.0f / std::sqrt(mx * mx + my * my + 1e-12f);
    float wx = mx * in * (float)fx, wy = my * in * (float)fy;  // pixels across the edge per unit of normalized coordinates
    float hn[13];
    for (int k = 0; k < 13; k++) hn[k] = wx * h0[k] + wy * h1[k];
    float r = wx * ((float)((zu - cx) / fx) - r0) + wy * ((float)((zv - cy) / fy) - r1);
    const float *dxa = dx + ia;
    for (int k = 0; k < 6; k++) r -= hn[k] * dx[k] + hn[6 + k] * dxa[k];
    r -= hn[12] * dx[ir];
    const float *rows[13];
    for (int k = 0; k < 6; k++) rows[k] = C[k], rows[6 + k] = C[ia + k];
    rows[12] = C[ir];
    alignas(16) float PH[NSP];
    {
        f4 kk[13];
        for (int k = 0; k < 13; k++) kk[k] = splat(hn[k]);
#pragma clang loop unroll(full)
        for (int c = 0; c < NSP; c += 4) {
            f4 s0 = kk[0] * ld(rows[0] + c);
#pragma clang loop unroll(full)
            for (int k = 1; k < 13; k++) s0 += kk[k] * ld(rows[k] + c);
            st(PH + c, s0);
        }
    }
    double S = P.edge_sigma * P.edge_sigma;
    for (int k = 0; k < 6; k++) S += hn[k] * PH[k] + hn[6 + k] * PH[ia + k];
    S += hn[12] * PH[ir];
    {
        double var = C[ir][ir] > 0 ? C[ir][ir] : 0, k = P.second_order;  // second order in the log depth, as for corners
        r -= (float)(0.5 * k * var * hn[12]);
        S += 0.5 * k * var * var * hn[12] * hn[12];
    }
    if (!(S > 0)) return false;
    {
        double c1 = r * r / S, lim = 0.72 * P.gate;  // 0.72: the 1-dof equivalent of the 2-dof gate
        nis += 0.05 * ((c1 < lim ? c1 : lim) - nis);
        if (!(c1 < lim)) return false;
    }
    float is = (float)(1.0 / S);
    f4 vr = splat(r * is);
#pragma clang loop unroll(full)
    for (int c = 0; c < NSP; c += 4) st(dx + c, ld(dx + c) + ld(PH + c) * vr);
    for (int row = 0; row < NS; row++) {
        float k0 = PH[row] * is;
        if (k0 == 0) continue;
        f4 v0 = splat(k0);
        float *q = C[row];
#pragma clang loop unroll(full)
        for (int c = 0; c < NSP; c += 4) st(q + c, ld(q + c) - v0 * ld(PH + c));
    }
    return true;
}

// A scalar update of one state with a direct pseudo-measurement: residual r (before this frame's corrections), variance var.
void Vio::update_state(int k, double r, double var) {
    alignas(16) float PH[NSP];
    std::memcpy(PH, C[k], sizeof(PH));
    float is = (float)(1.0 / (PH[k] + var));
    f4 vr = splat(((float)r - dx[k]) * is);
#pragma clang loop unroll(full)
    for (int c = 0; c < NSP; c += 4) st(dx + c, ld(dx + c) + ld(PH + c) * vr);
    for (int row = 0; row < NS; row++) {
        float k0 = PH[row] * is;
        if (k0 == 0) continue;
        f4 v0 = splat(k0);
        float *q = C[row];
#pragma clang loop unroll(full)
        for (int c = 0; c < NSP; c += 4) st(q + c, ld(q + c) - v0 * ld(PH + c));
    }
}

// Alignment and update of the features, as far as the frame's work budget goes: the young ones first (their depth is
// still converging), then the established ones in turn, starting after the last one served in the previous frame.
void Vio::track_and_update() {
    n_tracked = n_updated = n_passes = n_tried = 0;
    int gated[MAXF], n_gated = 0, meas_i[MAXF];
    double meas_u[MAXF], meas_v[MAXF];
    const int nf = MAXF, young = (int)P.young;
    int free_slots = 0;
    for (int i = 0; i < nf; i++) free_slots += !feats[i].alive;
    // when slots are free, a little is kept back for finding new features
    double limit = budget_now - (free_slots >= P.min_new ? 4 * P.cost_cell + P.reserve_new * P.cost_template + P.cost_anchor : 0.0);
    const int first = rr % nf;  // (fixed for the frame: rr moves on as features are served)
    for (int round = 0; round < 2; round++)
        for (int n = 0; n < nf; n++) {
            int i = round == 0 ? n : (first + n) % nf;
            Feature &f = feats[i];
            if (!f.alive || (round == 0) != (f.used < young)) continue;
            if (spent + (f.edge ? P.cost_edge : P.cost_update) + 3 * P.cost_pass > limit) break;
            if (round == 1) rr = i + 1;
            f.age++;
            double u0, v0, sigma;
            int ir = ir_of(i);
            if (!project(f, ir, u0, v0, f.A, sigma) || u0 < P.border || v0 < P.border || u0 > W - 1 - P.border || v0 > H - 1 - P.border) {
                stats[0]++;
                kill_feature(i);
                continue;
            }
            const float *A = f.A;
            float det = A[0] * A[3] - A[1] * A[2];
            float s = det > 0 ? std::sqrt(det) : 0;
            if (!(s > P.scale_lo && s < P.scale_hi)) {
                stats[1]++;
                kill_feature(i);
                continue;
            }
            int ds = s < 0.7071f ? -1 : (s > 1.4142f ? 1 : 0);
            int start = sigma > P.coarse_sigma ? 2 : (sigma > P.mid_sigma ? 1 : 0);
            double cu = u0, cv = v0;
            bool ok = false;
            float zncc = -1;
            int before = n_passes;
            n_tried++;
            for (int l = start; l >= 0; l--) {
                if (!f.level_ok[l]) continue;
                int m = l + ds;
                m = m < 0 ? 0 : (m > LEVELS - 1 ? LEVELS - 1 : m);
                float k = (float)(1 << l) / (float)(1 << m), sm = (float)(1 << m);
                float x = (float)((cu + 0.5) / sm - 0.5), y = (float)((cv + 0.5) / sm - 0.5);
                float a0 = A[0] * k, a1 = A[1] * k, a2 = A[2] * k, a3 = A[3] * k;
                bool good = true;
                float z = -1, step2 = 100;
                const int passes = l == 0 ? (int)P.passes : (int)P.coarse_passes;
                for (int it = 0; it < passes && good; it++) {
                    float ddx, ddy;
                    n_passes++;
                    good = pass(m, x, y, A, k, f, l, ddx, ddy, z);
                    if (!good) break;
                    step2 = ddx * ddx + ddy * ddy;
                    if (step2 > 9.0f) {  // never more than 3 template pixels at once
                        float sc = 3.0f / std::sqrt(step2);
                        ddx *= sc, ddy *= sc;
                    }
                    x -= a0 * ddx + a1 * ddy, y -= a2 * ddx + a3 * ddy;
                    if (step2 < 0.01f) break;  // within a tenth of a pixel: the step is taken without another look
                }
                if (l == 0) {
                    ok = good && step2 < 1.0f, zncc = z;
                    if (ok) cu = (x + 0.5) * sm - 0.5, cv = (y + 0.5) * sm - 0.5;
                } else if (good && z > 0.5f) {
                    cu = (x + 0.5) * sm - 0.5, cv = (y + 0.5) * sm - 0.5;
                }
            }
            spent += P.cost_pass * (n_passes - before);
            if (!ok || zncc < P.zncc_min) {
                stats[ok ? 3 : 2]++;
                if (++f.fails > P.max_fail) stats[5]++, kill_feature(i);
                continue;
            }
            spent += f.edge ? P.cost_edge : P.cost_update;
            if (n_tracked < MAXF) meas_i[n_tracked] = i, meas_u[n_tracked] = cu, meas_v[n_tracked] = cv, n_tracked++;
        }
    // Start-up (the velocity is still unknown, at the start of a flight or after a restart): the propagated position
    // is a poor linearisation point. At zero displacement the depth of a feature has no influence on its predicted
    // pixel, so features at different depths contradict each other and are gated. The position that the aligned
    // corners agree on at their current depths (a 3-dof robust least squares with the prior as regulariser) becomes
    // the linearisation point, the velocity follows through the prior correlation, and the update then runs as one
    // relinearised (iterated-EKF) step: dx starts at minus the shift.
    const bool startup = P.seed > 0.5 && C[6][6] + C[7][7] + C[8][8] > (float)P.seed_var;
    if (startup && n_tracked >= 4) {
        double J[MAXF][2][3], r[MAXF][2];
        int nj = 0;
        for (int n = 0; n < n_tracked; n++) {
            const Feature &f = feats[meas_i[n]];
            float h0[13], h1[13], r0, r1;
            if (f.edge || !rows_of(meas_i[n], h0, h1, r0, r1)) continue;
            for (int k = 0; k < 3; k++) J[nj][0][k] = h0[3 + k], J[nj][1][k] = h1[3 + k];
            r[nj][0] = (meas_u[n] - cx) / fx - r0, r[nj][1] = (meas_v[n] - cy) / fy - r1;
            nj++;
        }
        if (nj >= 4) {
            double Ppp[9], Pvp[9];
            for (int a = 0; a < 3; a++)
                for (int b = 0; b < 3; b++) Ppp[3 * a + b] = C[3 + a][3 + b], Pvp[3 * a + b] = C[6 + a][3 + b];
            // inverse of the prior position covariance
            double det = Ppp[0] * (Ppp[4] * Ppp[8] - Ppp[5] * Ppp[7]) - Ppp[1] * (Ppp[3] * Ppp[8] - Ppp[5] * Ppp[6]) + Ppp[2] * (Ppp[3] * Ppp[7] - Ppp[4] * Ppp[6]);
            if (det > 1e-18) {
                double Pi[9] = {(Ppp[4] * Ppp[8] - Ppp[5] * Ppp[7]) / det, (Ppp[2] * Ppp[7] - Ppp[1] * Ppp[8]) / det, (Ppp[1] * Ppp[5] - Ppp[2] * Ppp[4]) / det,
                                (Ppp[5] * Ppp[6] - Ppp[3] * Ppp[8]) / det, (Ppp[0] * Ppp[8] - Ppp[2] * Ppp[6]) / det, (Ppp[2] * Ppp[3] - Ppp[0] * Ppp[5]) / det,
                                (Ppp[3] * Ppp[7] - Ppp[4] * Ppp[6]) / det, (Ppp[1] * Ppp[6] - Ppp[0] * Ppp[7]) / det, (Ppp[0] * Ppp[4] - Ppp[1] * Ppp[3]) / det};
                double sig = P.seed_px / fx, iw = 1.0 / (sig * sig), huber = 2.0 * sig;
                double dp[3] = {0, 0, 0};
                for (int it = 0; it < 3; it++) {
                    double A[9], b[3] = {0, 0, 0};
                    for (int k = 0; k < 9; k++) A[k] = Pi[k];
                    for (int n = 0; n < nj; n++) {
                        double e0 = r[n][0] - (J[n][0][0] * dp[0] + J[n][0][1] * dp[1] + J[n][0][2] * dp[2]), e1 = r[n][1] - (J[n][1][0] * dp[0] + J[n][1][1] * dp[1] + J[n][1][2] * dp[2]);
                        double en = std::sqrt(e0 * e0 + e1 * e1), w = iw * (it == 0 || en < huber ? 1.0 : huber / en);
                        for (int a = 0; a < 3; a++) {
                            b[a] += w * (J[n][0][a] * r[n][0] + J[n][1][a] * r[n][1]);
                            for (int c = 0; c < 3; c++) A[3 * a + c] += w * (J[n][0][a] * J[n][0][c] + J[n][1][a] * J[n][1][c]);
                        }
                    }
                    double d = A[0] * (A[4] * A[8] - A[5] * A[7]) - A[1] * (A[3] * A[8] - A[5] * A[6]) + A[2] * (A[3] * A[7] - A[4] * A[6]);
                    if (!(std::fabs(d) > 1e-30)) break;
                    dp[0] = (b[0] * (A[4] * A[8] - A[5] * A[7]) - A[1] * (b[1] * A[8] - A[5] * b[2]) + A[2] * (b[1] * A[7] - A[4] * b[2])) / d;
                    dp[1] = (A[0] * (b[1] * A[8] - A[5] * b[2]) - b[0] * (A[3] * A[8] - A[5] * A[6]) + A[2] * (A[3] * b[2] - b[1] * A[6])) / d;
                    dp[2] = (A[0] * (A[4] * b[2] - b[1] * A[7]) - A[1] * (A[3] * b[2] - b[1] * A[6]) + b[0] * (A[3] * A[7] - A[4] * A[6])) / d;
                }
                double n2 = dp[0] * dp[0] + dp[1] * dp[1] + dp[2] * dp[2];
                if (std::isfinite(n2) && n2 < 1.0) {
                    double q[3] = {Pi[0] * dp[0] + Pi[1] * dp[1] + Pi[2] * dp[2], Pi[3] * dp[0] + Pi[4] * dp[1] + Pi[5] * dp[2], Pi[6] * dp[0] + Pi[7] * dp[1] + Pi[8] * dp[2]};
                    double dv[3] = {Pvp[0] * q[0] + Pvp[1] * q[1] + Pvp[2] * q[2], Pvp[3] * q[0] + Pvp[4] * q[1] + Pvp[5] * q[2], Pvp[6] * q[0] + Pvp[7] * q[1] + Pvp[8] * q[2]};
                    p = p + V3{dp[0], dp[1], dp[2]}, v = v + V3{dv[0], dv[1], dv[2]};
                    for (int k = 0; k < 3; k++) dx[3 + k] -= (float)dp[k], dx[6 + k] -= (float)dv[k];
                    anchor_frames();
                    stats[17]++;
                }
            }
        }
    }
    int aligned = n_tracked;
    for (int n = 0; n < aligned; n++) {
        int i = meas_i[n];
        Feature &f = feats[i];
        if (!f.alive) continue;
        if (f.edge ? update_edge(i, meas_u[n], meas_v[n]) : update_feature(i, meas_u[n], meas_v[n])) {
            f.fails = 0, f.used++, f.px = meas_u[n], f.py = meas_v[n];
            n_updated++;
        } else {
            stats[4]++;
            if (!startup) gated[n_gated < MAXF ? n_gated++ : 0] = i;  // during start-up a gated feature is not held against it
        }
    }
    // A gated measurement of a well-aligned patch is an outlier if most of the others agree with the state. If most
    // are gated, the state is what is wrong (typically the velocity after a stretch without features): the velocity
    // uncertainty is reopened and the features are kept, so that the next frame can pull the state back.
    bool state_wrong = P.rescue > 0 && n_gated >= 2 && 2 * n_gated >= n_tracked;
    if (state_wrong) {
        float add = (float)(P.rescue * P.rescue);
        for (int k = 6; k < 9; k++) C[k][k] += add;
        stats[7]++;
    } else {
        for (int n = 0; n < n_gated; n++)
            if (++feats[gated[n]].fails > P.max_fail) stats[6]++, kill_feature(gated[n]);
    }
}

// Structure tensors of two adjacent 4x4 level-1 windows (columns 0..3 and 4..7 from q, four rows; central differences):
// sums of gx^2, gy^2, gx gy for each. A 4x4 window of level 1 is exactly the footprint of the 8x8 level-0 template.
static inline void tile_tensors(const uint8_t *q, int w, int *s) {
#if defined(__wasm_simd128__)
    v128_t a = wasm_i32x4_const(0, 0, 0, 0), b = a, c = a;
#pragma clang loop unroll(full)
    for (int j = 0; j < 4; j++, q += w) {
        v128_t gx = wasm_i16x8_sub(wasm_u16x8_load8x8(q + 1), wasm_u16x8_load8x8(q - 1));
        v128_t gy = wasm_i16x8_sub(wasm_u16x8_load8x8(q + w), wasm_u16x8_load8x8(q - w));
        a = wasm_i32x4_add(a, wasm_i32x4_dot_i16x8(gx, gx));
        b = wasm_i32x4_add(b, wasm_i32x4_dot_i16x8(gy, gy));
        c = wasm_i32x4_add(c, wasm_i32x4_dot_i16x8(gx, gy));
    }
    s[0] = wasm_i32x4_extract_lane(a, 0) + wasm_i32x4_extract_lane(a, 1), s[3] = wasm_i32x4_extract_lane(a, 2) + wasm_i32x4_extract_lane(a, 3);
    s[1] = wasm_i32x4_extract_lane(b, 0) + wasm_i32x4_extract_lane(b, 1), s[4] = wasm_i32x4_extract_lane(b, 2) + wasm_i32x4_extract_lane(b, 3);
    s[2] = wasm_i32x4_extract_lane(c, 0) + wasm_i32x4_extract_lane(c, 1), s[5] = wasm_i32x4_extract_lane(c, 2) + wasm_i32x4_extract_lane(c, 3);
#else
    for (int k = 0; k < 6; k++) s[k] = 0;
    for (int j = 0; j < 4; j++, q += w)
        for (int i = 0; i < 8; i++) {
            int gx = q[i + 1] - q[i - 1], gy = q[i + w] - q[i - w], o = i < 4 ? 0 : 3;
            s[o] += gx * gx, s[o + 1] += gy * gy, s[o + 2] += gx * gy;
        }
#endif
}

// Anchor `slot` becomes a clone of the current body pose: its rows and columns are copies of the pose's.
void Vio::clone_anchor(int slot) {
    Anchor &A = anchors[slot];
    A.alive = true, A.R = R, A.p = p, A.count = 0;
    A.Rrel = identity(), A.t = {0, 0, 0};
    int ia = ia_of(slot);
    for (int d = 0; d < 6; d++) std::memcpy(C[ia + d], C[d], sizeof(float) * NSP);
    for (int k = 0; k < NS; k++)
        for (int d = 0; d < 6; d++) C[k][ia + d] = C[k][d];
}

// The median inverse depth, in the current frame, of the established features, and which feature has it.
void Vio::scene_median() {
    // prior inverse depth: the median over established features of the inverse depth in the current frame
    const int nf = MAXF;
    int ref = -1;  // the established feature with the median depth: the reference of the new features' prior
    {
        double vals[MAXF];
        int who[MAXF], nv = 0;
        for (int i = 0; i < nf; i++) {
            const Feature &f = feats[i];
            if (!f.alive || f.used < 5) continue;
            const Anchor &a = anchors[f.anchor];
            double qz = a.Rrel.m[6] * f.bx + a.Rrel.m[7] * f.by + a.Rrel.m[8] + a.t.z * f.rho;
            if (qz > 1e-3) vals[nv] = f.rho / qz, who[nv] = i, nv++;
        }
        if (nv >= 3) {
            for (int a = 1; a < nv; a++) {  // insertion sort
                double key = vals[a];
                int kw = who[a], b = a - 1;
                for (; b >= 0 && vals[b] > key; b--) vals[b + 1] = vals[b], who[b + 1] = who[b];
                vals[b + 1] = key, who[b + 1] = kw;
            }
            rho_med = vals[nv / 2], ref = who[nv / 2];
        }
    }
    scene_ref = ref;
}

// New features on a new anchor (a clone of the current pose). Detection looks at a few grid cells without a feature,
// in an order that hops across the image, and scores a small lattice of 8x8 level-1 windows in each.
void Vio::add_features() {
    const int nf = (int)P.nfeat < MAXF ? (int)P.nfeat : MAXF, na = (int)P.nanchor < MAXA ? (int)P.nanchor : MAXA;
    int alive = 0;
    for (int i = 0; i < nf; i++) alive += feats[i].alive;
    n_alive = alive, n_new = 0;
    int free_slots = nf - alive;
    if (free_slots < P.min_new) return;
    if (frame - last_anchor_frame < P.anchor_gap && alive > nf / 3) return;
    int slot = -1;
    for (int j = 0; j < na; j++)
        if (!anchors[j].alive) {
            slot = j;
            break;
        }
    if (slot < 0) {  // no free anchor: only a nearly empty one may be evicted
        int worst = 0;
        for (int j = 1; j < na; j++)
            if (anchors[j].count < anchors[worst].count) worst = j;
        if (anchors[worst].count > P.evict_max && alive > nf / 3) return;
        slot = -2 - worst;
    }
    const int GW = 8, GH = 6, CELL = 20;  // 40-pixel cells at level 0, 20 at level 1
    bool occupied[GW * GH] = {};
    for (int i = 0; i < nf; i++)
        if (feats[i].alive) {
            int gx_ = (int)(feats[i].px * (1.0 / 40)), gy_ = (int)(feats[i].py * (1.0 / 40));
            gx_ = gx_ < 0 ? 0 : (gx_ > GW - 1 ? GW - 1 : gx_), gy_ = gy_ < 0 ? 0 : (gy_ > GH - 1 ? GH - 1 : gy_);
            occupied[gy_ * GW + gx_] = true;
        }
    const int w1 = W / 2, h1 = H / 2;
    const int margin = ((int)P.border + 8) / 2;  // level-1 pixels between a window centre and the image border
    int px_ = 2 * (frame & 1), py_ = (frame & 2);  // the tiling shifts by half a window from frame to frame; even: see make_template
    int cand_x[GW * GH], cand_y[GW * GH], ncand = 0;
    bool cand_edge[GW * GH];
    const bool edges = alive < P.edge_fill;
    int max_new = (int)P.max_new < free_slots ? (int)P.max_new : free_slots, examined = 0;
    for (int n = 0; n < GW * GH && examined < P.max_cells && ncand < max_new; n++) {
        if (spent + P.cost_cell + (ncand + 1) * P.cost_template + P.cost_anchor > budget_now) break;
        int cell = scan_cell;
        scan_cell = (scan_cell + 19) % (GW * GH);
        if (occupied[cell]) continue;
        examined++, stats[8]++;
        spent += P.cost_cell;
        int x0 = (cell % GW) * CELL, y0 = (cell / GW) * CELL;
        float best = (float)P.det_thresh, best_edge = (float)P.edge_thresh;
        int bx_ = -1, by_ = 0, ex_ = -1, ey_ = 0;
        // the cell is tiled with 4x4 windows, two per call (the third call of a row overlaps the second by a window)
        static const int XS[3] = {0, 8, 12};
        for (int j = 0; j < 5; j++)
            for (int i = 0; i < 3; i++) {
                int xa = x0 + px_ + XS[i], y = y0 + py_ + 4 * j;
                if (xa < margin || y < margin || xa + 8 > w1 - margin || y + 4 > h1 - margin) continue;
                int t[6];
                tile_tensors(l1 + y * w1 + xa, w1, t);
                for (int k = 0; k < 2; k++) {
                    float a = (float)t[3 * k], c = (float)t[3 * k + 1], b = (float)t[3 * k + 2];
                    float root = std::sqrt((a - c) * (a - c) + 4 * b * b), lam = 0.5f * ((a + c) - root) * (1.0f / 64.0f), big = 0.5f * ((a + c) + root) * (1.0f / 64.0f);
                    int x = xa + 4 * k + 2;  // the window covers x-2..x+1: its centre, and the template's, is x - 0.5
                    if (lam > best) best = lam, bx_ = x, by_ = y + 2;
                    if (big > best_edge) best_edge = big, ex_ = x, ey_ = y + 2;
                }
            }
        if (bx_ >= 0)
            cand_x[ncand] = bx_, cand_y[ncand] = by_, cand_edge[ncand] = false, ncand++, stats[9]++;
        else if (edges && ex_ >= 0)
            cand_x[ncand] = ex_, cand_y[ncand] = ey_, cand_edge[ncand] = true, ncand++;
    }
    if (ncand == 0) return;
    double rho_prior = P.rho0;
    int ref = scene_ref;
    if (ref >= 0) rho_prior = rho_med * std::pow(P.rho0 / rho_med, P.rho_pull);
    // Templates first: the anchor is only made if the batch is worth one of the few anchor slots. A new anchor
    // with one or two features is the next one to be evicted, and evictions take established features with them.
    int made_idx[MAXF], created = 0, taken = 0;
    for (int i = 0; i < nf && taken < ncand; i++) {
        if (feats[i].alive) continue;
        Feature &f = feats[i];
        bool made = false;
        while (taken < ncand && !made) {
            f.ax = 2 * cand_x[taken] - 0.5, f.ay = 2 * cand_y[taken] - 0.5;  // level-1 window centre x - 0.5 in level-0 pixels
            spent += P.cost_template;
            made = make_template(f, edges);
            taken++;
            stats[made ? 11 : 10]++;
        }
        if (!made) break;
        made_idx[created++] = i;
    }
    if (created == 0 || (created < P.min_batch && alive > nf / 3)) return;
    stats[12]++;
    spent += P.cost_anchor;
    if (slot < 0) {
        int worst = -2 - slot;
        for (int k = 0; k < MAXF; k++)
            if (feats[k].alive && feats[k].anchor == worst) stats[16]++, kill_feature(k);
        slot = worst;
    }
    clone_anchor(slot);
    bool fresh[MAXF] = {};  // made in this batch
    for (int n = 0; n < created; n++) {
        int i = made_idx[n];
        Feature &f = feats[i];
        f.alive = true, f.anchor = slot, f.age = 0, f.fails = 0, f.used = 0;
        f.bx = (f.ax - cx) / fx, f.by = (f.ay - cy) / fy;
        f.px = f.ax, f.py = f.ay;
        f.rho = rho_prior;
        int ir = ir_of(i);
        std::memset(C[ir], 0, sizeof(float) * NSP);
        for (int k = 0; k < NS; k++) C[k][ir] = 0;
        C[ir][ir] = (float)(P.rho_log_sigma * P.rho_log_sigma);
        if (P.rho_corr > 0.5) {
            // The depth priors of features are not independent pieces of information: their errors share the unknown
            // scale of the scene (and of the map built so far). Independent priors make the filter sure of the scale
            // at once (fifteen priors of sigma 0.7 "know" it to 18 %), and every new batch confirms the scale the map
            // happens to have, so the accelerometer can no longer move it and nothing is corrected in retrospect.
            // The reference: the feature with the median depth, else (none established yet) the most used live one.
            // Without any live feature the batch itself shares the scene's part of the prior.
            int from = ref >= 0 && feats[ref].alive ? ref : -1;
            if (from < 0) {
                for (int k = 0; k < MAXF; k++)
                    if (k != i && feats[k].alive && !fresh[k] && (from < 0 || feats[k].used > feats[from].used)) from = k;
            }
            if (from >= 0) {
                // "as deep as the reference feature, give or take": the reference's covariance with every state,
                // plus the spread of scene depths around it (a valid joint covariance by construction)
                int irr = ir_of(from);
                std::memcpy(C[ir], C[irr], sizeof(float) * NSP);
                for (int k = 0; k < NS; k++) C[k][ir] = C[k][irr];
                C[ir][ir] = C[irr][irr] + (float)(P.rho_ind * P.rho_ind);
            } else {
                float common = (float)(P.rho_common * P.rho_common);
                C[ir][ir] = common + (float)(P.rho_ind * P.rho_ind);
                for (int m = 0; m < n; m++) {
                    int ik = ir_of(made_idx[m]);
                    C[ir][ik] = C[ik][ir] = common;
                }
            }
            fresh[i] = true;
        }
        anchors[slot].count++;
    }
    last_anchor_frame = frame;
    n_new = created, n_alive = alive + created;
}

void Vio::output(double *out) {
    M3 Rc = Rcb * R * transpose(Rcb);
    V3 pc = Rcb * (p + R * tbc - tbc);
    V3 wb = gyro_mean - bg;
    V3 wc = Rcb * wb;
    V3 vc = Rcb * (tmul(R, v) + cross(wb, tbc));
    double o[13] = {pc.x, pc.y, pc.z, 0, 0, 0, 1, vc.x, vc.y, vc.z, wc.x, wc.y, wc.z};
    to_quaternion(Rc, o + 3);
    bool finite = true;
    for (int i = 0; i < 13; i++) finite = finite && std::isfinite(o[i]);
    if (finite) std::memcpy(last_out, o, sizeof(o));
    std::memcpy(out, last_out, sizeof(last_out));
#ifdef VIO_PROFILE  // work counters of this frame in place of the twist (for the fuel model, never in a submission)
    out[7] = n_passes, out[8] = n_tracked, out[9] = n_updated, out[10] = stats[8], out[11] = stats[10] + stats[11], out[12] = stats[12];
#endif
}

// A scalar measurement of the attitude error along h (body axes): h . dtheta = r, variance var. The correction goes
// into dx like every other update of the frame.
void Vio::update_att(const double *h, double r, double var) {
    alignas(16) float PH[NSP];
    f4 h0 = splat((float)h[0]), h1 = splat((float)h[1]), h2 = splat((float)h[2]);
#pragma clang loop unroll(full)
    for (int c = 0; c < NSP; c += 4) st(PH + c, h0 * ld(C[0] + c) + h1 * ld(C[1] + c) + h2 * ld(C[2] + c));
    double S = var + h[0] * PH[0] + h[1] * PH[1] + h[2] * PH[2];
    float is = (float)(1.0 / S);
    f4 vr = splat((float)(r - (h[0] * dx[0] + h[1] * dx[1] + h[2] * dx[2])) * is);
#pragma clang loop unroll(full)
    for (int c = 0; c < NSP; c += 4) st(dx + c, ld(dx + c) + ld(PH + c) * vr);
    for (int row = 0; row < NS; row++) {
        float k0 = PH[row] * is;
        if (k0 == 0) continue;
        f4 v0 = splat(k0);
        float *q = C[row];
#pragma clang loop unroll(full)
        for (int c = 0; c < NSP; c += 4) st(q + c, ld(q + c) - v0 * ld(PH + c));
    }
}

// Uncertainty along the scale gauge: a common factor (1 + s) on the displacement from the origin of the scale (the
// position at the last (re)start), the velocity, the anchor positions and every depth changes no predicted pixel, so
// vision cannot observe it and only the accelerometer can. The EKF, linearising the product of velocity and inverse
// depth, becomes sure of the scale within the first second of a start in motion; adding variance sigma^2 along this
// one direction keeps the scale (and with it the position, which is fully correlated) correctable, and leaves the
// well-observed image geometry alone.
void Vio::inflate_scale(double sigma) {
    alignas(16) float u[NSP] = {};
    V3 d = p - scale_origin;
    u[3] = (float)d.x, u[4] = (float)d.y, u[5] = (float)d.z, u[6] = (float)v.x, u[7] = (float)v.y, u[8] = (float)v.z;
    for (int j = 0; j < MAXA; j++)
        if (anchors[j].alive) {
            V3 a = anchors[j].p - scale_origin;
            int ia = ia_of(j);
            u[ia + 3] = (float)a.x, u[ia + 4] = (float)a.y, u[ia + 5] = (float)a.z;
        }
    for (int i = 0; i < MAXF; i++)
        if (feats[i].alive) u[ir_of(i)] = -1.0f;
    float q = (float)(sigma * sigma);
    for (int r = 0; r < NS; r++) {
        if (u[r] == 0) continue;
        f4 k = splat(q * u[r]);
        float *row = C[r];
#pragma clang loop unroll(full)
        for (int c = 0; c < NSP; c += 4) st(row + c, ld(row + c) + k * ld(u + c));
    }
}

// (Re)start the filter at the current pose: no anchors or features, and the prior uncertainty for velocity, biases
// and gravity. Used at frame 0 and by the watchdog; the pose itself is kept.
void Vio::restart(bool first) {
    for (auto &f : feats) f.alive = false;
    for (auto &a : anchors) a.alive = false, a.count = 0;
    std::memset(C, 0, sizeof(C));
    std::memset(dx, 0, sizeof(dx));
    if (!first) {
        // gravity: opposite to the mean specific force of the last seconds (a drone's velocity is bounded, so its
        // mean acceleration is small); the velocity is unknown, the accelerometer bias starts over
        double n = norm(up_lp);
        g = n > 0.5 * G ? up_lp * (-G / n) : R * V3{0, 0, -G};
        v = v * 0.0, ba = {0, 0, 0};
        double nb = norm(bg);
        if (!(nb < 0.04)) bg = {0, 0, 0};
        thrust_sum[0] = thrust_sum[1] = 0, thrust_count[0] = thrust_count[1] = 0;
    }
    V3 gu = g * (1.0 / G);
    V3 e = std::fabs(gu.x) < 0.9 ? V3{1, 0, 0} : V3{0, 1, 0};
    b1 = e - gu * dot(gu, e);
    b1 = b1 * (1.0 / norm(b1));
    b2 = cross(gu, b1);
    // The biases start with a fraction of their prior uncertainty and get the rest once the velocity has converged:
    // in the first second they cannot matter (0.012 rad/s is a pixel), but a filter that does not know its velocity
    // yet readily explains image motion with a gyro bias and then sits in that wrong solution.
    for (int i = 0; i < 3; i++) {
        C[6 + i][6 + i] = (float)(P.init_v * P.init_v);
        C[9 + i][9 + i] = (float)(P.init_bg * P.init_bg * P.stage * P.stage);
        C[12 + i][12 + i] = (float)(P.init_ba * P.init_ba * (i < 2 ? 1.0 : P.stage * P.stage));  // x, y are observed directly (thrust)
    }
    C[15][15] = C[16][16] = (float)(P.init_tilt * P.init_tilt);
    staged = true, restart_frame = frame, scale_origin = p;
    last_anchor_frame = -100, streak = 0, far = 0, nis = 1.0, rho_med = P.rho0, scene_ref = -1;
}

void Vio::step(double t, const uint8_t *rgb, const double *imu, int count, double *out, const Vio *pyramid_of) {
    if (pyramid_of)  // another instance has built the pyramid of this frame (the depth hypotheses of the start)
        green = rgb + 1, l1 = pyramid_of->pyr1, l2 = pyramid_of->pyr2;
    else
        build_pyramid(rgb);
    spent = 0;
    budget_now = frame < P.bank_frames ? P.bank_budget : P.budget;  // (several depth hypotheses share the first seconds: see solution.cpp)
    if (frame == 0) {
        V3 as{0, 0, 0};
        for (int s = 0; s < count; s++) as = as + V3{imu[7 * s + 1], imu[7 * s + 2], imu[7 * s + 3]};
        // Without drag the specific force is the thrust, along body z whatever the drone does, so its measured
        // direction says nothing about gravity beyond "roughly body z" and is off by the accelerometer bias. Gravity
        // starts along body z (exact for a hover); the measured direction is the fallback for another mounting.
        double an = norm(as);
        if (P.g_body > 0.5 && as.z > 0.5 * an)
            g = {0, 0, -G};
        else if (an > 1.0)
            g = as * (-G / an);
        restart(true);
        thrust_sum[0] = as.x / count, thrust_sum[1] = as.y / count, thrust_count[0] = thrust_count[1] = 1;
        up_lp = g * -1.0;
        last_t = t;
        gyro_mean = acc_mean = {0, 0, 0};
    } else {
        propagate(imu, count);
#ifndef __wasm__
        if (P.debug > 0.5) std::fprintf(stderr, "frame %d  v %.3f %.3f %.3f  g %.2f %.2f %.2f  p %.3f %.3f %.3f\n", frame, v.x, v.y, v.z, g.x, g.y, g.z, p.x, p.y, p.z);
#endif
        anchor_frames();
        // the specific force in world axes, low-passed over a few seconds: minus gravity up to the mean acceleration
        up_lp = up_lp + (R * (acc_mean - ba) - up_lp) * (0.05 / P.up_tau);
        thrust_sum[0] += acc_mean.x, thrust_sum[1] += acc_mean.y, thrust_count[0]++, thrust_count[1]++;
        // One pseudo-measurement every other frame, in turn over a 2 s cycle (in the first frames every frame: the
        // tilt estimate of a hover depends on the accelerometer bias):
        //   accelerometer bias x, y: without drag the specific force is along body z, so its body x/y components are
        //     bias plus noise (their mean since the last turn is used);
        //   gravity direction, once per cycle: weakly towards minus the low-passed specific force;
        //   velocity, per axis: a weak prior of zero, which only matters when nothing else observes it.
        if (P.scene_sigma > 0 && frame % 40 == 21 && scene_ref >= 0 && feats[scene_ref].alive && feats[scene_ref].used >= 5) {
            // the scene prior, as a measurement once in two seconds: the median depth of the tracked features is
            // around 1 / rho0 (this is what keeps the scale from wandering off in gentle flight)
            update_state(ir_of(scene_ref), std::log(P.rho0 / rho_med), P.scene_sigma * P.scene_sigma), spent += 8.5;
        }
        if ((frame & 1) == 0 || frame < 8) {
            int slot = (frame >> 1) % 20, turn = frame < 8 ? (frame & 1) : (slot & 1);
            if (frame >= 40 && slot < 2 && P.gprior > 0) {
                double n = norm(up_lp);
                if (n > 0.5 * G) {
                    V3 d = (up_lp * (-1.0 / n)) - g * (1.0 / G);
                    update_state(15 + slot, dot(slot == 0 ? b1 : b2, d), P.gprior * P.gprior), spent += 8.5;
                }
            } else if (frame >= 8 && slot >= 2 && slot < 5 && P.vprior > 0) {
                update_state(4 + slot, -(slot == 2 ? v.x : (slot == 3 ? v.y : v.z)), P.vprior * P.vprior), spent += 8.5;
            } else if (P.thrust_sigma > 0 && thrust_on && thrust_count[turn] > 0) {
                double z = thrust_sum[turn] / thrust_count[turn], var = P.thrust_sigma * P.thrust_sigma + P.sig_a * P.sig_a * 200.0 / (10.0 * thrust_count[turn]);
                thrust_sum[turn] = 0, thrust_count[turn] = 0;
                double r = z - (turn == 0 ? ba.x : ba.y);
                // the model checks itself: residuals far beyond bias and noise mean the specific force is not along
                // body z (drag), and after too many of them the constraint is dropped for the rest of the flight
                bool fits = r * r < 9.0 * (var + C[12 + turn][12 + turn]);
                thrust_checks++, thrust_misfits += !fits;
                if (thrust_checks >= 20 && thrust_misfits * 4 > thrust_checks) thrust_on = false;
                if (fits) update_state(12 + turn, r, var), spent += 8.5;
            }
        }
        {
            // scale uncertainty per frame: more during the first seconds after a (re)start, fading to a small constant
            int since = frame - restart_frame;
            double sq = since < P.scale_frames ? P.scale_q0 + (P.scale_q - P.scale_q0) * since / P.scale_frames : P.scale_q;
            if (sq > 0) inflate_scale(sq), spent += 6.5;
        }
        track_and_update();
        inject();
#ifdef VIO_DIAG
        if (n_updated == 0) {
            diag.blackout++, diag.run++;
            if (diag.run > diag.longest) diag.longest = diag.run, diag.longest_start = frame - diag.run + 1;
        } else {
            diag.run = 0;
        }
        if (frame == 10) diag.speed10 = norm(v);
        if (frame == 40) diag.speed40 = norm(v), diag.rho2 = rho_med;
        if (scene_ref >= 0) {
            diag.lrho += std::log(rho_med), diag.nrho++;
            if (frame < 200) diag.lrho10 += std::log(rho_med), diag.nrho10++;
        }
#endif
        // Watchdog: a state that cannot be (speed, biases far outside what the sensor has) or a filter that keeps
        // rejecting well-aligned features has diverged, typically from a start in mid-flight. It starts over from
        // the current pose rather than integrating a wrong velocity for the rest of the flight.
        // (health: the running normalised innovation squared is about 0.4 in a consistent filter, with short peaks;
        // in a wrong basin it stays near 3. A frame above the limit counts once against the filter, any other
        // frame twice for it.)
        streak = nis > P.nis_bad ? streak + 1 : (streak > 2 ? streak - 2 : 0);
        // (scale: the median depth of the tracked features is 1.5 to 3 m in these scenes and stays under 10 m
        // through whole flights; far beyond that, sustained, is the monocular scale running away with the velocity)
        far = (n_updated >= 3 && rho_med < P.rho_floor) ? far + 1 : 0;
        double sp = norm(v);
        bool sane = std::isfinite(sp) && std::isfinite(p.x + p.y + p.z) && sp < P.max_speed && std::fabs(ba.x) < P.ba_max && std::fabs(ba.y) < P.ba_max && std::fabs(ba.z) < P.ba_max &&
                    norm(bg) < P.bg_max && streak <= P.max_streak && far <= P.max_far;
        if (!sane && P.watchdog > 0.5) {
            if (!std::isfinite(p.x + p.y + p.z)) p = {last_out[0], last_out[1], last_out[2]}, R = identity();  // last resort
            if (!std::isfinite(sp)) v = {0, 0, 0};
            if (streak > P.max_streak) stats[7]++;  // (counted apart from the restarts for an impossible state)
#ifdef VIO_DIAG
            {
                bool ba_out = !(std::fabs(ba.x) < P.ba_max && std::fabs(ba.y) < P.ba_max && std::fabs(ba.z) < P.ba_max);
                int why = streak > P.max_streak ? 0 : (far > P.max_far ? 1 : (!(sp < P.max_speed) ? 2 : (ba_out ? 3 : 4)));
                if (diag.restarts[why] < 9) diag.restarts[why]++;
                if (diag.first_restart < 0) diag.first_restart = frame;
            }
#endif
            restart(false);
            stats[13]++;
        }
        if (staged && (C[6][6] + C[7][7] + C[8][8] < (float)P.seed_var || frame - restart_frame > 60)) {
            float rest = (float)(1.0 - P.stage * P.stage);
            for (int i = 0; i < 3; i++) C[9 + i][9 + i] += (float)(P.init_bg * P.init_bg) * rest;
            C[14][14] += (float)(P.init_ba * P.init_ba) * rest;
            staged = false;
        }
        anchor_frames();  // new features use the corrected state for their depth prior
    }
    scene_median();
    add_features();
    output(out);
#ifdef VIO_DIAG
    // Diagnostics build (classical/vio_diag): the pose is the submission's, unchanged. The twist is not part of the
    // score, and the server reports its RMSE per flight, so on the last frame of a 60 s flight the two twist vectors
    // carry counters as decimal digits (decoded by classical/vio_diag/decode.py).
    diag.alive_sum += n_alive;
    if (frame == 1199) {
        auto cap = [](double x, double hi) { return x < 0 ? 0.0 : (x > hi ? hi : std::floor(x)); };
        double first = diag.first_restart < 0 ? 999 : cap(diag.first_restart / 10.0, 998);
        // version 2 of the layout: restart causes (consistency, scale, speed, accelerometer bias, gyro bias) and the
        // scene's inverse depth (median of the tracked features: at 2 s, mean over the first 10 s, over the flight)
        double rho_all = diag.nrho ? std::exp(diag.lrho / diag.nrho) : 0, rho_10 = diag.nrho10 ? std::exp(diag.lrho10 / diag.nrho10) : 0;
        double pv = diag.restarts[0] * 1e10 + diag.restarts[1] * 1e9 + diag.restarts[2] * 1e8 + first * 1e5 + diag.restarts[3] * 1e4 + diag.restarts[4] * 1e3 + cap(diag.rho2 * 50 + 0.5, 99) * 1e1 + diag.hypothesis;
        double pw = cap(diag.speed10 * 10 + 0.5, 99) * 1e9 + cap(diag.speed40 * 10 + 0.5, 99) * 1e7 + (thrust_on ? 1e6 : 0) + cap(rho_all * 50 + 0.5, 99) * 1e4 + cap(diag.alive_sum / 1200.0 + 0.5, 99) * 1e2 +
                    cap(rho_10 * 50 + 0.5, 99);
        out[7] = pv * 1e4, out[8] = 0, out[9] = 0, out[10] = pw * 1e4, out[11] = 0, out[12] = 0;
    }
#endif
    frame++;
}

}  // namespace vio
