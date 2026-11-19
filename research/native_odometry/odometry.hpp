// C++ port of the learned-odometry guest: streaming.Inputs (triple_derot, remap warp, ordered packet),
// orientation.Orientation (rolling calibration), OdometryNet (CNN + correlation + SSM head) and the
// Estimator's position integration. Fixed-size static buffers; nothing is allocated per frame.
// model_config.h (written by export.py) fixes the architecture; weights arrive as one float blob.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>
#include <algorithm>

#include "model_config.h"

#if defined(__wasm_simd128__)
#include <wasm_simd128.h>
#endif

namespace odo {

constexpr int W = ODO_WIDTH, H = ODO_HEIGHT, NB = ODO_BLOCKS, EMB = ODO_EMBEDDING;
constexpr int CH[NB] = {ODO_CHANNELS};
constexpr int STRIDE[NB] = {ODO_STRIDES};
constexpr int RADIUS = ODO_RADIUS, NCORR = ODO_CORRELATION ? 2 * (2 * RADIUS + 1) * (2 * RADIUS + 1) : 0;
constexpr int LAYERS = ODO_LAYERS, STATES = ODO_STATES, IMU = 51, SENSOR = 64;

constexpr int dim_after(int n, int b) { return b == 0 ? n : (dim_after(n, b - 1) - 1) / STRIDE[b - 1] + 1; }
constexpr int HF = dim_after(H, NB), WF = dim_after(W, NB), CF = CH[NB - 1];
constexpr int GY = 3, GX = 4;
constexpr int VCH = 3 * CF + NCORR + 2;            // pooled channels
constexpr int VISUAL = VCH * GY * GX;               // projection input from images
constexpr int MAX_ACT = [] { int m = H * W; for (int b = 0; b < NB; ++b) m = std::max(m, CH[b] * dim_after(H, b + 1) * dim_after(W, b + 1)); return m; }();
constexpr int MAX_COL = [] { int m = 0, cin = 1; for (int b = 0; b < NB; ++b) { int n = dim_after(H, b + 1) * dim_after(W, b + 1); m = std::max(m, std::max(cin, CH[b]) * 9 * n); cin = CH[b]; } return m; }();
static_assert(HF % GY == 0 && WF % GX == 0, "adaptive pooling assumes an even split");

// ---------------------------------------------------------------- weights (fixed order, see export.py)
struct Block { const float *w0, *g1, *b1, *w3, *g4, *b4, *skip; };
struct Ssm { const float *norm_w, *norm_b, *in_w, *in_b, *par_w, *par_b, *log_rate, *skip, *out_w, *out_b; };
struct Weights {
    Block cnn[NB];
    const float *s0w, *s0b, *s2w, *s2b, *pw, *pb, *lnw, *lnb;
    Ssm ssm[LAYERS];
    const float *o0w, *o0b, *o1w, *o1b, *o3w, *o3b;
};

inline long bind(Weights &w, const float *p) {
    const float *start = p;
    auto take = [&](long n) { const float *q = p; p += n; return q; };
    int cin = 1;
    for (int b = 0; b < NB; ++b) {
        int c = CH[b];
        w.cnn[b] = {take(c * cin * 9), take(c), take(c), take(c * c * 9), take(c), take(c),
                    (cin != c || STRIDE[b] != 1) ? take(c * cin) : nullptr};
        cin = c;
    }
    w.s0w = take(SENSOR * IMU); w.s0b = take(SENSOR); w.s2w = take(SENSOR * SENSOR); w.s2b = take(SENSOR);
    w.pw = take(EMB * (VISUAL + SENSOR)); w.pb = take(EMB); w.lnw = take(EMB); w.lnb = take(EMB);
    for (int l = 0; l < LAYERS; ++l) {
        Ssm &s = w.ssm[l];
        s.norm_w = take(EMB); s.norm_b = take(EMB); s.in_w = take(2 * EMB * EMB); s.in_b = take(2 * EMB);
        s.par_w = take((EMB + 2 * STATES) * EMB); s.par_b = take(EMB + 2 * STATES);
        s.log_rate = take(EMB * STATES); s.skip = take(EMB); s.out_w = take(EMB * EMB); s.out_b = take(EMB);
    }
    w.o0w = take(EMB); w.o0b = take(EMB); w.o1w = take(128 * EMB); w.o1b = take(128); w.o3w = take(3 * 128); w.o3b = take(3);
    return p - start;
}

// ---------------------------------------------------------------- numeric kernels
inline float silu(float x) { return x / (1.0f + std::exp(-x)); }

#if defined(__wasm_simd128__) && defined(ODO_WASM_TILE8X32)
// The wider tile shares each weight splat across eight vectors and each
// activation load across eight output channels. Each lane keeps the original
// K accumulation order. The inner I/J loops are fully unrolled into locals.
inline void gemm_8x32(const float *A, const float *B, float *C, int M, int K, int N) {
    constexpr int rows = 8, vectors = 8, lanes = 4;
    for (int m = 0; m < M; m += rows) {
        const float *weights[rows];
#pragma clang loop unroll(full)
        for (int i = 0; i < rows; ++i) weights[i] = A + (m + i) * K;
        for (int n = 0; n < N; n += vectors * lanes) {
            v128_t accum[rows][vectors] = {};
            const float *b = B + n;
#if defined(ODO_WASM_UNROLL_K2)
#pragma clang loop unroll_count(2)
#endif
            for (int k = 0; k < K; ++k, b += N) {
                v128_t input[vectors];
#pragma clang loop unroll(full)
                for (int j = 0; j < vectors; ++j) input[j] = wasm_v128_load(b + lanes * j);
#pragma clang loop unroll(full)
                for (int i = 0; i < rows; ++i) {
                    const v128_t w = wasm_v128_load32_splat(weights[i] + k);
#pragma clang loop unroll(full)
                    for (int j = 0; j < vectors; ++j)
                        accum[i][j] = wasm_f32x4_add(accum[i][j], wasm_f32x4_mul(w, input[j]));
                }
            }
#pragma clang loop unroll(full)
            for (int i = 0; i < rows; ++i) {
#pragma clang loop unroll(full)
                for (int j = 0; j < vectors; ++j)
                    wasm_v128_store(C + (m + i) * N + n + lanes * j, accum[i][j]);
            }
        }
    }
}
#endif

// C[m][n] = sum_k A[m][k] B[k][n]  (A: M x K row-major, B: K x N row-major)
inline void gemm(const float *A, const float *B, float *C, int M, int K, int N) {
#if defined(__wasm_simd128__)
#if defined(ODO_WASM_TILE8X32)
    if (M % 8 == 0 && N % 32 == 0) {
        gemm_8x32(A, B, C, M, K, N);
        return;
    }
#endif
    if (M % 4 == 0 && N % 16 == 0) {
        for (int m = 0; m < M; m += 4) {
            const float *a0 = A + m * K, *a1 = a0 + K, *a2 = a1 + K, *a3 = a2 + K;
            for (int n = 0; n < N; n += 16) {
                v128_t c[4][4];
                for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j) c[i][j] = wasm_f32x4_splat(0.f);
                const float *b = B + n;
                for (int k = 0; k < K; ++k, b += N) {
                    v128_t x0 = wasm_v128_load(b), x1 = wasm_v128_load(b + 4), x2 = wasm_v128_load(b + 8), x3 = wasm_v128_load(b + 12);
                    v128_t w0 = wasm_v128_load32_splat(a0 + k), w1 = wasm_v128_load32_splat(a1 + k);
                    v128_t w2 = wasm_v128_load32_splat(a2 + k), w3 = wasm_v128_load32_splat(a3 + k);
#define ODO_ROW(i, w) c[i][0] = wasm_f32x4_add(c[i][0], wasm_f32x4_mul(w, x0)); c[i][1] = wasm_f32x4_add(c[i][1], wasm_f32x4_mul(w, x1)); \
                      c[i][2] = wasm_f32x4_add(c[i][2], wasm_f32x4_mul(w, x2)); c[i][3] = wasm_f32x4_add(c[i][3], wasm_f32x4_mul(w, x3));
                    ODO_ROW(0, w0) ODO_ROW(1, w1) ODO_ROW(2, w2) ODO_ROW(3, w3)
#undef ODO_ROW
                }
                for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j) wasm_v128_store(C + (m + i) * N + n + 4 * j, c[i][j]);
            }
        }
        return;
    }
#endif
    for (int m = 0; m < M; ++m) {
        float *c = C + (long)m * N;
        for (int n = 0; n < N; ++n) c[n] = 0.f;
        for (int k = 0; k < K; ++k) {
            const float a = A[(long)m * K + k];
            const float *b = B + (long)k * N;
            for (int n = 0; n < N; ++n) c[n] += a * b[n];
        }
    }
}

// y = W x + b  (W: out x in row-major)
inline void dense(const float *Wt, const float *b, const float *x, float *y, int in, int out) {
    for (int o = 0; o < out; ++o) {
        const float *r = Wt + (long)o * in;
        float s = 0.f;
        for (int i = 0; i < in; ++i) s += r[i] * x[i];
        y[o] = s + (b ? b[o] : 0.f);
    }
}

inline void layer_norm(float *x, int n, const float *g, const float *b) {
    double m = 0, v = 0;
    for (int i = 0; i < n; ++i) m += x[i];
    m /= n;
    for (int i = 0; i < n; ++i) v += (x[i] - m) * (x[i] - m);
    float inv = 1.0f / std::sqrt((float)(v / n) + 1e-5f);
    for (int i = 0; i < n; ++i) x[i] = ((float)(x[i] - m)) * inv * g[i] + b[i];
}

// GroupNorm(4 groups) in place on [c][hw], optional SiLU.
inline void group_norm(float *x, int c, int hw, const float *g, const float *b, bool act) {
    const int per = c / 4;
    for (int grp = 0; grp < 4; ++grp) {
        float *p = x + (long)grp * per * hw;
        const long n = (long)per * hw;
        double m = 0, v = 0;
        for (long i = 0; i < n; ++i) m += p[i];
        m /= n;
        for (long i = 0; i < n; ++i) { double d = p[i] - m; v += d * d; }
        const float mean = (float)m, inv = 1.0f / std::sqrt((float)(v / n) + 1e-5f);
        for (int ch = 0; ch < per; ++ch) {
            const float scale = inv * g[grp * per + ch], shift = b[grp * per + ch] - mean * scale;
            float *q = p + (long)ch * hw;
            if (act) for (int i = 0; i < hw; ++i) q[i] = silu(q[i] * scale + shift);
            else for (int i = 0; i < hw; ++i) q[i] = q[i] * scale + shift;
        }
    }
}

// 3x3 conv, padding 1, stride s, via im2col + GEMM. in: [cin][h][w] -> out: [cout][oh][ow]
inline void conv3x3(const float *in, int cin, int h, int w, int s, const float *wt, int cout, float *out, float *col) {
    const int oh = (h - 1) / s + 1, ow = (w - 1) / s + 1, n = oh * ow;
    for (int ic = 0; ic < cin; ++ic)
        for (int ky = 0; ky < 3; ++ky)
            for (int kx = 0; kx < 3; ++kx) {
                float *dst = col + (long)((ic * 3 + ky) * 3 + kx) * n;
                const float *src = in + (long)ic * h * w;
                for (int oy = 0; oy < oh; ++oy) {
                    const int iy = oy * s + ky - 1;
                    float *d = dst + oy * ow;
                    if (iy < 0 || iy >= h) { for (int ox = 0; ox < ow; ++ox) d[ox] = 0.f; continue; }
                    const float *r = src + iy * w;
                    for (int ox = 0; ox < ow; ++ox) {
                        const int ix = ox * s + kx - 1;
                        d[ox] = (ix >= 0 && ix < w) ? r[ix] : 0.f;
                    }
                }
            }
    gemm(wt, col, out, cout, cin * 9, n);
}

inline void conv1x1(const float *in, int cin, int h, int w, int s, const float *wt, int cout, float *out, float *col) {
    const int oh = (h - 1) / s + 1, ow = (w - 1) / s + 1, n = oh * ow;
    const float *src = in;
    if (s != 1) {
        for (int ic = 0; ic < cin; ++ic)
            for (int oy = 0; oy < oh; ++oy)
                for (int ox = 0; ox < ow; ++ox) col[(long)ic * n + oy * ow + ox] = in[(long)ic * h * w + oy * s * w + ox * s];
        src = col;
    }
    gemm(wt, src, out, cout, cin, n);
}

// ---------------------------------------------------------------- network
struct Net {
    const Weights *w = nullptr;
    float act_a[MAX_ACT], act_b[MAX_ACT], act_t[MAX_ACT], act_s[MAX_ACT], col[MAX_COL];
    float feat[3][CF * HF * WF];
    float spatial[VISUAL + SENSOR];
    float h[LAYERS][EMB * STATES];
    float y[EMB], u[2 * EMB], par[EMB + 2 * STATES], tmp[EMB], o1[128];

    void reset() { std::memset(h, 0, sizeof h); }

    // One 1-channel image (uint8) through the residual CNN into dst [CF][HF][WF].
    void cnn(const uint8_t *img, float *dst) {
        for (int i = 0; i < H * W; ++i) act_a[i] = (float)img[i] / 255.0f - 0.5f;
        float *x = act_a;
        int cin = 1, hh = H, ww = W;
        for (int b = 0; b < NB; ++b) {
            const Block &k = w->cnn[b];
            const int c = CH[b], s = STRIDE[b], oh = (hh - 1) / s + 1, ow = (ww - 1) / s + 1, n = oh * ow;
            float *t1 = (x == act_a) ? act_b : act_a;  // free buffer
            conv3x3(x, cin, hh, ww, s, k.w0, c, t1, col);
            group_norm(t1, c, n, k.g1, k.b1, true);
            conv3x3(t1, c, oh, ow, 1, k.w3, c, act_t, col);
            group_norm(act_t, c, n, k.g4, k.b4, false);
            const float *skip = x;
            if (k.skip) { conv1x1(x, cin, hh, ww, s, k.skip, c, act_s, col); skip = act_s; }
            float *out = (b == NB - 1) ? dst : t1;
            for (int i = 0; i < c * n; ++i) out[i] = silu(act_t[i] + skip[i]);
            x = out; cin = c; hh = oh; ww = ow;
        }
    }

    // images: 5 planes [cur, warp_short, warp_long, mask_short, mask_long]; imu: 51 features.
    void step(const uint8_t *images, const float *imu, float *velocity) {
        for (int i = 0; i < 3; ++i) cnn(images + (long)i * H * W, feat[i]);
        constexpr int N = HF * WF, CELL = (HF / GY) * (WF / GX);
        float masks[2][N];
        // bilinear (align_corners=False) downsampling of the masks by H/HF, W/WF
        for (int m = 0; m < 2; ++m) {
            const uint8_t *src = images + (long)(3 + m) * H * W;
            for (int oy = 0; oy < HF; ++oy)
                for (int ox = 0; ox < WF; ++ox) {
                    auto coord = [](int o, int in, int out, int &i0, int &i1, float &l1) {
                        float sc = (float)in / out, s = (o + 0.5f) * sc - 0.5f;
                        if (s < 0) s = 0;
                        i0 = (int)s; i1 = std::min(i0 + 1, in - 1); l1 = s - i0;
                    };
                    int y0, y1, x0, x1; float ly, lx;
                    coord(oy, H, HF, y0, y1, ly); coord(ox, W, WF, x0, x1, lx);
                    auto px = [&](int yy, int xx) { return (float)src[yy * W + xx] / 255.0f; };
                    masks[m][oy * WF + ox] = (1 - ly) * ((1 - lx) * px(y0, x0) + lx * px(y0, x1)) + ly * ((1 - lx) * px(y1, x0) + lx * px(y1, x1));
                }
        }
        // pooled components, channel-major [VCH][GY][GX]
        auto pool = [&](int ch, auto value) {
            for (int gy = 0; gy < GY; ++gy)
                for (int gx = 0; gx < GX; ++gx) {
                    float s = 0.f;
                    for (int yy = 0; yy < HF / GY; ++yy)
                        for (int xx = 0; xx < WF / GX; ++xx) {
                            const int p = (gy * (HF / GY) + yy) * WF + gx * (WF / GX) + xx;
                            s += value(p);
                        }
                    spatial[(ch * GY + gy) * GX + gx] = s / CELL;
                }
        };
        const float *cur = feat[0], *sh = feat[1], *lg = feat[2];
        for (int c = 0; c < CF; ++c) {
            const float *a = cur + c * N, *b = sh + c * N, *d = lg + c * N;
            pool(c, [&](int p) { return a[p]; });
            pool(CF + c, [&](int p) { return (a[p] - b[p]) * masks[0][p]; });
            pool(2 * CF + c, [&](int p) { return (a[p] - d[p]) * masks[1][p]; });
        }
        if (NCORR) {
            // normalized features (F.normalize over channels, eps 1e-12), reuse act buffers
            float *na = act_a, *nb = act_b, *nc = act_t;
            float *norms[3] = {na, nb, nc};
            for (int i = 0; i < 3; ++i)
                for (int p = 0; p < N; ++p) {
                    float s = 0.f;
                    for (int c = 0; c < CF; ++c) s += feat[i][c * N + p] * feat[i][c * N + p];
                    const float inv = 1.0f / std::max(std::sqrt(s), 1e-12f);
                    for (int c = 0; c < CF; ++c) norms[i][c * N + p] = feat[i][c * N + p] * inv;
                }
            const int K = 2 * RADIUS + 1;
            float corr[N];
            for (int hist = 0; hist < 2; ++hist) {
                const float *b = norms[1 + hist];
                for (int oi = 0; oi < K; ++oi)
                    for (int oj = 0; oj < K; ++oj) {
                        for (int y = 0; y < HF; ++y)
                            for (int x = 0; x < WF; ++x) {
                                const int yy = y + oi - RADIUS, xx = x + oj - RADIUS;
                                float s = 0.f;
                                if (yy >= 0 && yy < HF && xx >= 0 && xx < WF)
                                    for (int c = 0; c < CF; ++c) s += na[c * N + y * WF + x] * b[c * N + yy * WF + xx];
                                corr[y * WF + x] = s * masks[hist][y * WF + x];
                            }
                        pool(3 * CF + hist * K * K + oi * K + oj, [&](int p) { return corr[p]; });
                    }
            }
        }
        pool(3 * CF + NCORR, [&](int p) { return masks[0][p]; });
        pool(3 * CF + NCORR + 1, [&](int p) { return masks[1][p]; });
        // sensor branch
        float s1[SENSOR];
        dense(w->s0w, w->s0b, imu, s1, IMU, SENSOR);
        for (float &v : s1) v = silu(v);
        dense(w->s2w, w->s2b, s1, spatial + VISUAL, SENSOR, SENSOR);
        for (int i = 0; i < SENSOR; ++i) spatial[VISUAL + i] = silu(spatial[VISUAL + i]);
        dense(w->pw, w->pb, spatial, y, VISUAL + SENSOR, EMB);
        layer_norm(y, EMB, w->lnw, w->lnb);
        for (float &v : y) v = silu(v);
        // selective SSM blocks
        const float dt = std::max(imu[13], 0.001f);
        for (int l = 0; l < LAYERS; ++l) {
            const Ssm &s = w->ssm[l];
            std::memcpy(tmp, y, sizeof tmp);
            layer_norm(tmp, EMB, s.norm_w, s.norm_b);
            dense(s.in_w, s.in_b, tmp, u, EMB, 2 * EMB);
            for (int i = 0; i < EMB; ++i) u[i] = silu(u[i]);
            dense(s.par_w, s.par_b, u, par, EMB, EMB + 2 * STATES);
            float tb[STATES], tc[STATES];
            for (int j = 0; j < STATES; ++j) { tb[j] = std::tanh(par[EMB + j]); tc[j] = std::tanh(par[EMB + STATES + j]); }
            const float norm = std::sqrt((float)STATES);
            for (int i = 0; i < EMB; ++i) {
                const float sp = par[i] > 20.f ? par[i] : std::log1p(std::exp(par[i]));
                const float delta = std::min(std::max(sp, 0.05f), 5.0f) * dt;
                float *hs = h[l] + i * STATES;
                float acc = 0.f;
                for (int j = 0; j < STATES; ++j) {
                    const float rate = std::exp(std::min(std::max(s.log_rate[i * STATES + j], -4.f), 4.f));
                    const float a = std::exp(-delta * rate);
                    hs[j] = a * hs[j] + (1 - a) * (u[i] * tb[j]);
                    acc += hs[j] * tc[j];
                }
                const float gate = u[EMB + i];
                tmp[i] = (acc / norm + s.skip[i] * u[i]) * silu(gate);
            }
            float o[EMB];
            dense(s.out_w, s.out_b, tmp, o, EMB, EMB);
            for (int i = 0; i < EMB; ++i) y[i] += o[i];
        }
        std::memcpy(tmp, y, sizeof tmp);
        layer_norm(tmp, EMB, w->o0w, w->o0b);
        dense(w->o1w, w->o1b, tmp, o1, EMB, 128);
        for (float &v : o1) v = silu(v);
        dense(w->o3w, w->o3b, o1, velocity, 128, 3);
    }
};

// ---------------------------------------------------------------- small linear algebra (double)
struct M3 {
    double a[9];
    double operator()(int r, int c) const { return a[r * 3 + c]; }
    double &operator()(int r, int c) { return a[r * 3 + c]; }
};
inline M3 eye() { return {{1, 0, 0, 0, 1, 0, 0, 0, 1}}; }
inline M3 mul(const M3 &x, const M3 &y) {
    M3 r;
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j) r(i, j) = x(i, 0) * y(0, j) + x(i, 1) * y(1, j) + x(i, 2) * y(2, j);
    return r;
}
inline M3 tr(const M3 &x) { M3 r; for (int i = 0; i < 3; ++i) for (int j = 0; j < 3; ++j) r(i, j) = x(j, i); return r; }
inline void mv(const M3 &m, const double *v, double *out) {
    for (int i = 0; i < 3; ++i) out[i] = m(i, 0) * v[0] + m(i, 1) * v[1] + m(i, 2) * v[2];
}
inline M3 exp_so3(double x, double y, double z) {
    const double a = std::sqrt(x * x + y * y + z * z);
    M3 k = {{0, -z, y, z, 0, -x, -y, x, 0}}, kk = mul(k, k), r = eye();
    double s1, s2;
    if (a < 1e-8) { s1 = 1; s2 = 0.5; } else { s1 = std::sin(a) / a; s2 = (1 - std::cos(a)) / (a * a); }
    for (int i = 0; i < 9; ++i) r.a[i] += s1 * k.a[i] + s2 * kk.a[i];
    return r;
}

// Linear quantile of n values (sorted copy).
inline double quantile(double *v, int n, double f) {
    std::sort(v, v + n);
    const double rank = f * (n - 1);
    const int left = (int)rank;
    const double frac = rank - left;
    return frac == 0 ? v[left] : v[left] * (1 - frac) + v[left + 1] * frac;
}

// ---------------------------------------------------------------- orientation (policy "rolling")
struct Orientation {
    static constexpr int CAP = 256, MAX_PACKET = 1024;
    M3 R = eye();
    double bias[3] = {0, 0, 0}, learned[3] = {0, 0, 0};
    double previous = 0, origin = 0, last_check = 0;
    bool started = false, activated = false;
    struct Row { double t, g[3], accel, image; } roll[CAP];
    int head = 0, count = 0;

    void rolling_update(double t, const double *packet, int n, double image) {
        if (n) {
            Row r{t, {0, 0, 0}, 0, image};
            for (int k = 0; k < n; ++k) for (int c = 0; c < 3; ++c) r.g[c] += packet[k * 7 + 4 + c];
            for (int c = 0; c < 3; ++c) r.g[c] /= n;
            double dev[MAX_PACKET];
            for (int k = 0; k < n; ++k) {
                const double *p = packet + k * 7;
                dev[k] = std::fabs(std::sqrt(p[1] * p[1] + p[2] * p[2] + p[3] * p[3]) - 9.81);
            }
            r.accel = quantile(dev, n, 0.5);
            if (count == CAP) { head = (head + 1) % CAP; --count; }
            roll[(head + count++) % CAP] = r;
        }
        const double window = ODO_STARTUP_SECONDS;
        while (count && roll[head].t < t - window) { head = (head + 1) % CAP; --count; }
        if (t - last_check < 0.2 || count < 8) return;
        last_check = t;
        if (t - roll[head].t < 0.8 * window) return;
        double col[CAP], center[3];
        for (int c = 0; c < 3; ++c) {
            for (int i = 0; i < count; ++i) col[i] = roll[(head + i) % CAP].g[c];
            center[c] = quantile(col, count, 0.5);
        }
        for (int i = 0; i < count; ++i) {
            const double *g = roll[(head + i) % CAP].g;
            col[i] = std::sqrt((g[0] - center[0]) * (g[0] - center[0]) + (g[1] - center[1]) * (g[1] - center[1]) + (g[2] - center[2]) * (g[2] - center[2]));
        }
        const double spread = quantile(col, count, 0.8);
        for (int i = 0; i < count; ++i) col[i] = roll[(head + i) % CAP].accel;
        const double accel = quantile(col, count, 0.5);
        for (int i = 0; i < count; ++i) col[i] = roll[(head + i) % CAP].image;
        const double image_q = quantile(col, count, 0.8);
        const bool calm = std::sqrt(center[0] * center[0] + center[1] * center[1] + center[2] * center[2]) < 0.10 &&
                          spread < 0.055 && accel < 0.45 && image_q < 0.018;
        if (calm) {
            for (int c = 0; c < 3; ++c) bias[c] = activated ? 0.9 * bias[c] + 0.1 * center[c] : center[c];
            activated = true;
        }
    }

    const M3 &step(double t, const double *packet, int n, double image, double time_origin) {
        if (!started) { started = true; origin = previous = t; return R; }
        if (n) {
            const double *last = packet + 4;
            for (int k = 0; k < n; ++k) {
                const double *row = packet + k * 7;
                const double rt = std::max(previous, std::min(row[0] - time_origin, t)), d = rt - previous;
                R = mul(R, exp_so3((row[4] - bias[0] - learned[0]) * d, (row[5] - bias[1] - learned[1]) * d, (row[6] - bias[2] - learned[2]) * d));
                previous = rt;
                last = row + 4;
            }
            const double d = t - previous;
            R = mul(R, exp_so3((last[0] - bias[0] - learned[0]) * d, (last[1] - bias[1] - learned[1]) * d, (last[2] - bias[2] - learned[2]) * d));
        }
        previous = t;
        rolling_update(t, packet, n, image);
        return R;
    }
};

// ---------------------------------------------------------------- image preprocessing
constexpr int MAX_SRC_W = 640, MAX_SRC_H = 480, HISTORY = 64;

// OpenCV INTER_AREA decimation table (computeResizeAreaTab).
struct AreaTab { int di, si; float alpha; };
inline int area_tab(int ssize, int dsize, double scale, AreaTab *tab) {
    int k = 0;
    for (int dx = 0; dx < dsize; ++dx) {
        const double fsx1 = dx * scale, fsx2 = fsx1 + scale, cell = std::min(scale, ssize - fsx1);
        int sx1 = (int)std::ceil(fsx1), sx2 = (int)std::floor(fsx2);
        sx2 = std::min(sx2, ssize - 1); sx1 = std::min(sx1, sx2);
        if (sx1 - fsx1 > 1e-3) tab[k++] = {dx, sx1 - 1, (float)((sx1 - fsx1) / cell)};
        for (int sx = sx1; sx < sx2; ++sx) tab[k++] = {dx, sx, (float)(1.0 / cell)};
        if (fsx2 - sx2 > 1e-3) tab[k++] = {dx, sx2, (float)(std::min(std::min(fsx2 - sx2, 1.), cell) / cell)};
    }
    return k;
}

struct Inputs {
    double K[9], Kinv[9];
    M3 R_bc;
    int sw = 0, sh = 0;
    AreaTab xtab[MAX_SRC_W * 2], ytab[MAX_SRC_H * 2];
    int nx = 0, ny = 0;
    uint8_t gray[MAX_SRC_W * MAX_SRC_H];
    uint8_t cur[H * W], prev[H * W];
    bool have_prev = false, have_time = false;
    double prev_time = 0;
    struct Hist { double t; M3 R; uint8_t img[H * W]; } hist[HISTORY];
    int hhead = 0, hcount = 0;
    Orientation orient;

    void init(int width, int height, double fx, double fy, double cx, double cy, const M3 &r_bc) {
        sw = width; sh = height; R_bc = r_bc;
        const double sx = (double)W / width, sy = (double)H / height;
        const double kfx = fx * sx, kfy = fy * sy, kcx = (cx + .5) * sx - .5, kcy = (cy + .5) * sy - .5;
        const double k[9] = {kfx, 0, kcx, 0, kfy, kcy, 0, 0, 1};
        std::memcpy(K, k, sizeof K);
        const double ifx = 1.0 / kfx, ify = 1.0 / kfy;
        const double ki[9] = {ifx, 0, -(kcx * ifx), 0, ify, -(kcy * ify), 0, 0, 1};
        std::memcpy(Kinv, ki, sizeof Kinv);
        nx = area_tab(width, W, (double)width / W, xtab);
        ny = area_tab(height, H, (double)height / H, ytab);
    }

    // cv::cvtColor(RGB2GRAY) then cv::resize(INTER_AREA) to W x H
    void resize(const uint8_t *rgb) {
        for (int i = 0, n = sw * sh; i < n; ++i)
            gray[i] = (uint8_t)((rgb[3 * i] * 9798 + rgb[3 * i + 1] * 19235 + rgb[3 * i + 2] * 3735 + (1 << 14)) >> 15);
        float buf[W], sum[W];
        int prev_dy = -1;
        auto flush = [&](int dy) { for (int x = 0; x < W; ++x) { int v = (int)std::lrint(sum[x]); cur[dy * W + x] = (uint8_t)std::min(255, std::max(0, v)); } };
        for (int j = 0; j < ny; ++j) {
            const float beta = ytab[j].alpha;
            const int dy = ytab[j].di;
            const uint8_t *S = gray + ytab[j].si * sw;
            for (int x = 0; x < W; ++x) buf[x] = 0;
            for (int k = 0; k < nx; ++k) buf[xtab[k].di] += S[xtab[k].si] * xtab[k].alpha;
            if (dy != prev_dy) {
                if (prev_dy >= 0) flush(prev_dy);
                for (int x = 0; x < W; ++x) sum[x] = beta * buf[x];
                prev_dy = dy;
            } else {
                for (int x = 0; x < W; ++x) sum[x] += beta * buf[x];
            }
        }
        flush(prev_dy);
    }

    // portable_warp (fast remap path): inverse homography, 1/32-pixel fixed point, zero border.
    static void warp(const uint8_t *frame, const double *inv, uint8_t *image, uint8_t *mask) {
        const double hi = std::max(H, W) + 2;
        for (int y = 0; y < H; ++y)
            for (int x = 0; x < W; ++x) {
                const double sx = inv[0] * x + inv[1] * y + inv[2], sy = inv[3] * x + inv[4] * y + inv[5], sz = inv[6] * x + inv[7] * y + inv[8];
                const double d = std::fabs(sz) > 1e-12 ? sz : 1.0;
                const double px = std::min(std::max(sx / d, -2.0), hi), py = std::min(std::max(sy / d, -2.0), hi);
                const int fx = (int)std::floor(px * 32 + .500000001), fy = (int)std::floor(py * 32 + .500000001);
                const int ix = fx >> 5, iy = fy >> 5, dx = fx & 31, dy = fy & 31;
                const int wts[4] = {(32 - dx) * (32 - dy), dx * (32 - dy), (32 - dx) * dy, dx * dy};
                int value = 0, weight = 0;
                for (int k = 0; k < 4; ++k) {
                    const int u = ix + (k & 1), v = iy + (k >> 1);
                    if (u >= 0 && u < W && v >= 0 && v < H) { value += frame[v * W + u] * wts[k]; weight += wts[k]; }
                }
                image[y * W + x] = (uint8_t)((value + 512) >> 10);
                mask[y * W + x] = ((weight * 255 + 512) >> 10) == 255 ? 255 : 0;
            }
    }

    // images: 5 planes; imu: 51 floats; returns attitude R.
    M3 step(double t, const uint8_t *rgb, const double *packet, int n, uint8_t *images, float *imu, double time_origin) {
        resize(rgb);
        float difference = 0.f;
        if (have_prev) {
            float s = 0.f;
            for (int i = 0; i < H * W; ++i) s += std::fabs((float)cur[i] - (float)prev[i]);
            difference = (s / (float)(H * W)) / 255.0f;
        }
        const double dt = have_time ? t - prev_time : 0.0;
        prev_time = t; have_time = true;
        std::memcpy(prev, cur, sizeof cur); have_prev = true;
        const M3 R = orient.step(t, packet, n, (double)difference, time_origin);
        const double tb[3] = {orient.bias[0] + orient.learned[0], orient.bias[1] + orient.learned[1], orient.bias[2] + orient.learned[2]};
        double mean[6] = {0, 0, 0, 0, 0, 0}, sd[6] = {0, 0, 0, 0, 0, 0};
        for (int k = 0; k < n; ++k) for (int c = 0; c < 6; ++c) mean[c] += packet[k * 7 + 1 + c];
        if (n) for (int c = 0; c < 6; ++c) mean[c] /= n;
        for (int k = 0; k < n; ++k) for (int c = 0; c < 6; ++c) { double d = packet[k * 7 + 1 + c] - mean[c]; sd[c] += d * d; }
        if (n) for (int c = 0; c < 6; ++c) sd[c] = std::sqrt(sd[c] / n);
        int f = 0;
        for (int c = 0; c < 3; ++c) imu[f++] = (float)(n ? mean[c] / 9.81 : 0.0);
        for (int c = 0; c < 3; ++c) imu[f++] = (float)(n ? mean[3 + c] - tb[c] : 0.0);
        for (int c = 0; c < 6; ++c) imu[f++] = (float)sd[c];
        imu[f++] = n ? 1.f : 0.f;
        imu[f++] = (float)dt;
        imu[f++] = (float)(K[0] / W);
        double ends[4];
        for (int i = 0; i < 4; ++i) ends[i] = t - dt + dt * (i + 1) / 4;
        for (int b = 0; b < 4; ++b) {
            double m[6] = {0, 0, 0, 0, 0, 0};
            int cnt = 0;
            for (int k = 0; k < n; ++k) {
                const double key = (packet[k * 7] - time_origin) - 1e-8;
                int bin = 0;
                while (bin < 4 && ends[bin] < key) ++bin;  // np.searchsorted(side="left")
                if (std::min(bin, 3) != b) continue;
                for (int c = 0; c < 6; ++c) m[c] += packet[k * 7 + 1 + c];
                ++cnt;
            }
            if (cnt) {
                for (int c = 0; c < 6; ++c) m[c] /= cnt;
                for (int c = 0; c < 3; ++c) { m[c] /= 9.81; m[3 + c] -= tb[c]; }
            }
            for (int c = 0; c < 6; ++c) imu[f++] = (float)m[c];
            imu[f++] = (float)std::min(cnt / 4.0, 1.0);
        }
        for (int c = 0; c < 3; ++c) imu[f++] = (float)orient.bias[c];
        for (int c = 0; c < 3; ++c) imu[f++] = (float)orient.learned[c];
        imu[f++] = orient.activated ? 1.f : 0.f;
        imu[f++] = 1.f;  // image available (the ABI always delivers one)
        // planes
        std::memcpy(images, cur, H * W);
        std::memset(images + H * W, 0, 4 * H * W);
        const double ages[2] = {ODO_BASELINES};
        for (int idx = 0; idx < 2; ++idx) {
            const Hist *match = nullptr;
            for (int i = hcount - 1; i >= 0; --i) {
                const Hist &r = hist[(hhead + i) % HISTORY];
                if (r.t <= t - ages[idx] + 1e-8) { match = &r; break; }
            }
            if (!match) continue;
            const M3 rot = mul(mul(mul(tr(R_bc), tr(R)), match->R), R_bc);
            M3 k, ki;
            std::memcpy(k.a, K, sizeof K); std::memcpy(ki.a, Kinv, sizeof Kinv);
            const M3 inv = mul(mul(k, tr(rot)), ki);
            warp(match->img, inv.a, images + (long)(1 + idx) * H * W, images + (long)(3 + idx) * H * W);
        }
        if (hcount == HISTORY) { hhead = (hhead + 1) % HISTORY; --hcount; }
        Hist &slot = hist[(hhead + hcount++) % HISTORY];
        slot.t = t; slot.R = R; std::memcpy(slot.img, cur, sizeof cur);
        const double oldest = ages[1];
        while (hcount > 2 && hist[(hhead + 1) % HISTORY].t <= t - oldest + 1e-8) { hhead = (hhead + 1) % HISTORY; --hcount; }
        return R;
    }
};

}  // namespace odo
#ifdef ODO_KF_GRID
#include "kf_grid.hpp"
#endif
#ifdef ODO_INPUT_KF_GRID
#include "new_model_inputs.hpp"
#endif
namespace odo {

// ---------------------------------------------------------------- estimator (streaming.Estimator)
struct Estimator {
    Inputs in;
#ifdef ODO_INPUT_KF_GRID
    NewModelInputs input_policy;
#endif
    Net net;
    M3 R_bc;
    double offset[3], position[3] = {0, 0, 0}, last_v[3] = {0, 0, 0}, last_t = 0, time_origin = 0;
    bool have_v = false;
    uint8_t images[5 * H * W];
    float imu[IMU], vb[3];
    M3 R;
#ifdef ODO_KF_GRID
    GridAttitude att;
    double relative_packet[7 * 256];
#ifdef ODO_VEL_FUSION
    double cam_anchor[3] = {0, 0, 0};
    int fused = 0;
#endif
#endif

    // T_cam_imu: 4x4 row-major
    void init(const Weights *w, int width, int height, double fx, double fy, double cx, double cy, const double *T) {
        M3 Rc = {{T[0], T[1], T[2], T[4], T[5], T[6], T[8], T[9], T[10]}};
        R_bc = tr(Rc);
        const double tvec[3] = {T[3], T[7], T[11]};
        mv(R_bc, tvec, offset);
        for (double &o : offset) o = -o;
        in.init(width, height, fx, fy, cx, cy, R_bc);
#ifdef ODO_INPUT_KF_GRID
        input_policy.init(fx, fy, cx, cy, R_bc);
#endif
#ifdef ODO_KF_GRID
        att.init(fx, fy, cx, cy, R_bc);
#endif
        net.w = w;
        net.reset();
    }

    // out: 13 doubles (pose xyz, quaternion xyzw, camera twist)
    void step(double t, const uint8_t *rgb, const double *packet, int n, double *out) {
        if (!have_v) {
            n = 0;  // The first packet precedes the origin.
            time_origin = t;
        }
        t -= time_origin;
        R = in.step(t, rgb, packet, n, images, imu, time_origin);
#ifdef ODO_INPUT_KF_GRID
        R = input_policy.step(t, rgb, in.sw, in.sh, packet, n, time_origin, R, images, imu, !have_v);
#endif
        net.step(images, imu, vb);
#ifdef ODO_KF_GRID
        // Integrate (and report) with the visual-bias attitude; the network's inputs above are unchanged.
        const int rows = std::min(n, 256);
        for (int i = 0; i < rows; ++i) {
            std::memcpy(relative_packet + 7 * i, packet + 7 * i, 7 * sizeof(double));
            relative_packet[7 * i] -= time_origin;
        }
        R = att.step(t, rgb, in.sw, in.sh, relative_packet, rows, !have_v);
#endif
        const double v64[3] = {vb[0], vb[1], vb[2]};
        double v[3];
        mv(R, v64, v);
        if (have_v) for (int i = 0; i < 3; ++i) position[i] += .5 * (t - last_t) * (v[i] + last_v[i]);
#ifdef ODO_VEL_FUSION
        // vel_fusion.py a_replace (knownrot): at each 0.5 s window end, the window's camera displacement keeps the
        // network's length and takes the visual direction; applied as a causal jump at the window's last frame.
        {
            double ro0[3], cam[3];
            mv(R, offset, ro0);
            for (int i = 0; i < 3; ++i) cam[i] = position[i] + ro0[i];
            if (!have_v) std::memcpy(cam_anchor, cam, sizeof cam);
            if (att.window_done) {
                att.window_done = false;
                double d[3], m = 0;
                for (int i = 0; i < 3; ++i) { d[i] = cam[i] - cam_anchor[i]; m += d[i] * d[i]; }
                m = std::sqrt(m);
                if (att.dir_valid && m >= 0.05) {
                    for (int i = 0; i < 3; ++i) { const double jump = m * att.dir_world[i] - d[i]; position[i] += jump; cam[i] += jump; }
                    ++fused;
                }
                std::memcpy(cam_anchor, cam, sizeof cam);
            }
        }
#endif
        last_t = t; have_v = true;
        std::memcpy(last_v, v, sizeof v);
        double ro[3], p[3];
        mv(R, offset, ro);
        for (int i = 0; i < 3; ++i) p[i] = position[i] + ro[i] - offset[i];
        const M3 Rcb = tr(R_bc);
        mv(Rcb, p, out);
        const M3 q = mul(mul(Rcb, R), R_bc);
        // rotation matrix -> quaternion (x, y, z, w)
        const double trace = q(0, 0) + q(1, 1) + q(2, 2);
        double qx, qy, qz, qw;
        if (trace > 0) { double s = std::sqrt(trace + 1.0) * 2; qw = .25 * s; qx = (q(2, 1) - q(1, 2)) / s; qy = (q(0, 2) - q(2, 0)) / s; qz = (q(1, 0) - q(0, 1)) / s; }
        else if (q(0, 0) > q(1, 1) && q(0, 0) > q(2, 2)) { double s = std::sqrt(1.0 + q(0, 0) - q(1, 1) - q(2, 2)) * 2; qw = (q(2, 1) - q(1, 2)) / s; qx = .25 * s; qy = (q(0, 1) + q(1, 0)) / s; qz = (q(0, 2) + q(2, 0)) / s; }
        else if (q(1, 1) > q(2, 2)) { double s = std::sqrt(1.0 + q(1, 1) - q(0, 0) - q(2, 2)) * 2; qw = (q(0, 2) - q(2, 0)) / s; qx = (q(0, 1) + q(1, 0)) / s; qy = .25 * s; qz = (q(1, 2) + q(2, 1)) / s; }
        else { double s = std::sqrt(1.0 + q(2, 2) - q(0, 0) - q(1, 1)) * 2; qw = (q(1, 0) - q(0, 1)) / s; qx = (q(0, 2) + q(2, 0)) / s; qy = (q(1, 2) + q(2, 1)) / s; qz = .25 * s; }
        out[3] = qx; out[4] = qy; out[5] = qz; out[6] = qw;
        double ang[3] = {0, 0, 0};
#ifdef ODO_INPUT_KF_GRID
        const double *tb = input_policy.att.bias;
#elif defined(ODO_KF_GRID)
        const double *tb = att.bias;
#else
        const double tb[3] = {in.orient.bias[0] + in.orient.learned[0], in.orient.bias[1] + in.orient.learned[1], in.orient.bias[2] + in.orient.learned[2]};
#endif
        if (n) for (int c = 0; c < 3; ++c) ang[c] = packet[(n - 1) * 7 + 4 + c] - tb[c];
        const double lin[3] = {v64[0] + ang[1] * offset[2] - ang[2] * offset[1], v64[1] + ang[2] * offset[0] - ang[0] * offset[2], v64[2] + ang[0] * offset[1] - ang[1] * offset[0]};
        mv(Rcb, lin, out + 7);
        mv(Rcb, ang, out + 10);
    }
};

}  // namespace odo
