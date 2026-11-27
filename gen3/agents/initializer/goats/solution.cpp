// classical/vio: the viobench ABI around vio::Vio (one translation unit: vio.cpp is included below).
// wasm:  viobench bundle classical/vio -o classical/output/vio.wasm
// host:  classical/vio/build_host.sh  ->  build-host/libvio.dylib, driven by classical/vio/lab.py (ctypes)
#include "viobench_abi.h"

#include <cstdlib>
#include <cstring>

#include "vio.cpp"
#include "parameters.h"

#ifndef VIO_BANK
#define VIO_BANK 3
#endif

namespace {
// A start in motion leaves the scale of the scene unknown: the first velocity is image motion times an ASSUMED depth,
// and the offset picked up before the accelerometer has sorted that out stays for the whole flight. So the first
// seconds are run under several depth assumptions side by side (same frames, one shared pyramid), and the filter
// whose innovations were the most consistent carries on alone. Until then the output is the current leader's.
vio::Vio *bank[VIO_BANK] = {};
double bank_score[VIO_BANK];
int bank_live = 0;  // hypotheses still running (0 or 1: the bank is over or off)
vio::Vio *S = nullptr;
vio::Params pending;

// The number after "key": in a flat JSON text (the config has unique key names).
bool number_after(const char *json, uint32_t length, const char *key, int skip, double *out) {
    size_t kl = std::strlen(key);
    for (uint32_t i = 0; i + kl + 2 < length; i++) {
        if (json[i] == '"' && !std::strncmp(json + i + 1, key, kl) && json[i + 1 + kl] == '"') {
            const char *s = json + i + kl + 2, *end = json + length;
            for (int k = 0; k <= skip; k++) {
                while (s < end && !((*s >= '0' && *s <= '9') || *s == '-' || *s == '.')) s++;
                if (s >= end) return false;
                char buffer[40];
                int n = 0;
                while (s < end && n < 39 && ((*s >= '0' && *s <= '9') || *s == '-' || *s == '.' || *s == 'e' || *s == 'E' || *s == '+')) buffer[n++] = *s++;
                buffer[n] = 0;
                if (k == skip) {
                    *out = std::strtod(buffer, nullptr);
                    return true;
                }
            }
        }
    }
    return false;
}
}  // namespace

extern "C" {
int32_t abi_version(void) { return VIOBENCH_ABI_VERSION; }
void *alloc(uint32_t size) { return std::malloc(size); }
int32_t frame_width(void) { return 320; }

int32_t init(const char *json, uint32_t length) {
    double fx, fy, cx, cy, T[16];
    if (!number_after(json, length, "fx", 0, &fx) || !number_after(json, length, "fy", 0, &fy) || !number_after(json, length, "cx", 0, &cx) ||
        !number_after(json, length, "cy", 0, &cy))
        return VIOBENCH_STATUS_ERROR;
    for (int i = 0; i < 16; i++)
        if (!number_after(json, length, "T_cam_imu", i, &T[i])) return VIOBENCH_STATUS_ERROR;
    for (auto &b : bank)
        if (!b) b = new vio::Vio();
#ifdef VIO_SET  // compile-time overrides of tunables, e.g. -DVIO_SET="p.update_stride=3;p.gate=12;"
    {
        vio::Params &p = pending;
        VIO_SET
    }
#endif
    bank_live = pending.bank_frames > 0 ? VIO_BANK : 0;
    S = bank[bank_live ? VIO_BANK / 2 : 0];
    for (int i = 0; i < VIO_BANK; i++) {
        bank[i]->P = pending;
        if (bank_live) {  // inverse depths a factor bank_spread apart, centred on rho0; no pull towards the prior
            bank[i]->P.rho0 = pending.rho0 * std::pow(pending.bank_spread, i - 0.5 * (VIO_BANK - 1));
            bank[i]->P.rho_pull = 0;
        }
        bank_score[i] = 0;
        if (bank_live || i == 0) bank[i]->init(fx, fy, cx, cy, T);
    }
    return VIOBENCH_STATUS_OK;
}

#ifdef VIO_BENCH
static const uint8_t *bench_rgb;
static const double *bench_imu;
#endif

int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
    if (!S) return VIOBENCH_STATUS_ERROR;
#ifdef VIO_BENCH
    bench_rgb = frame, bench_imu = imu;
#endif
    if (bank_live > 1) {
        double o[VIO_BANK][13];
        for (int i = 0; i < VIO_BANK; i++) bank[i]->step(t, frame, imu, imu_count, o[i], i ? bank[0] : nullptr);
        int k = bank[0]->frame - 1, lead = VIO_BANK / 2;  // k: index of the frame just processed
        if (k >= 5) {
            for (int i = 0; i < VIO_BANK; i++) bank_score[i] += bank[i]->nis;
            for (int i = 0; i < VIO_BANK; i++)
                if (bank_score[i] < bank_score[lead]) lead = i;
        }
        S = bank[lead];
        std::memcpy(out, o[lead], sizeof(o[lead]));
        if (k >= (int)S->P.bank_frames) {
            bank_live = 1;
#ifdef VIO_DIAG
            S->diag.hypothesis = lead + 1;
#endif
        }
        return VIOBENCH_STATUS_OK;
    }
    S->step(t, frame, imu, imu_count, out);
    return VIOBENCH_STATUS_OK;
}

#ifdef VIO_BENCH
// Fuel of one kernel on a copy of the live state (classical/vio/bench.py subtracts kind 1, the copy alone).
__attribute__((export_name("bench"))) int32_t bench(int32_t kind, int32_t arg) {
    static vio::Vio T;
    static vio::Feature F;
    if (kind == 0) return 0;
    T = *S;
    int i = 0;
    for (int k = 0; k < vio::MAXF; k++)
        if (T.feats[k].alive && T.feats[k].used > 3) i = k;
    double out[13];
    float ddx, ddy, z;
    T.P.gate = 1e9;
    switch (kind) {
    case 2: T.build_pyramid(bench_rgb); break;
    case 3: T.propagate(bench_imu, 10); break;
    case 4: T.anchor_frames(); break;
    case 5: T.update_state(12, 0.01, 0.01); break;
    case 6: return T.update_feature(i, T.feats[i].px, T.feats[i].py);
    case 7: F = T.feats[i], F.ax = 4 * (int)(F.px / 4) - 0.5, F.ay = 4 * (int)(F.py / 4) - 0.5; return T.make_template(F, true);
    case 15: return T.update_edge(i, T.feats[i].px, T.feats[i].py);
    case 8: return T.pass(arg, (float)((T.feats[i].px + 0.5) / (1 << arg) - 0.5), (float)((T.feats[i].py + 0.5) / (1 << arg) - 0.5), T.feats[i].A, 1.0f, T.feats[i], 0, ddx, ddy, z);
    case 9: T.clone_anchor(0); break;
    case 10: T.inject(); break;
    case 11: T.kill_feature(i); break;
    case 12: T.output(out); break;
    case 13: T.P.budget = 0, T.track_and_update(); break;
    case 14:
        for (auto &f : T.feats) f.alive = false;
        T.spent = 0, T.P.budget = 1e9, T.P.edge_fill = 0, T.P.max_cells = arg, T.P.max_new = 1000, T.P.min_new = 0, T.P.anchor_gap = 0, T.P.det_thresh = 1e9, T.add_features();
        break;
    }
    return 0;
}
#endif

#ifndef __wasm__
// host only: tunables by name before init(), and diagnostics after a step
int32_t vio_set(const char *name, double value) {
#define X(n, d) \
    if (!std::strcmp(name, #n)) { \
        pending.n = value; \
        return 0; \
    }
    VIO_PARAMS(X)
#undef X
    return -1;
}
void vio_reset_params(void) { pending = vio::Params(); }
// oracle for upper-bound experiments (lab.py, VIO_ORACLE with "y"): the true body attitude Rgt (world <- body, row-major)
// gives the heading error about gravity, used as a measurement with the given sigma and added noise
void vio_oracle_yaw(const double *Rgt, double sigma, double noise) {
    using namespace vio;
    M3 Rt;
    for (int i = 0; i < 9; i++) Rt.m[i] = Rgt[i];
    M3 D = transpose(S->R) * Rt;
    V3 dth{0.5 * (D(2, 1) - D(1, 2)), 0.5 * (D(0, 2) - D(2, 0)), 0.5 * (D(1, 0) - D(0, 1))};
    V3 ub = tmul(S->R, S->g * (1.0 / G));
    double h[3] = {ub.x, ub.y, ub.z};
    S->update_att(h, dot(ub, dth) + noise, sigma * sigma);
    S->inject();
}
// oracle for upper-bound experiments (classical/vio/lab.py, VIO_ORACLE): after frame 0, the true velocity and/or gravity
void vio_seed(const double *v, const double *g, int mode) {
    using namespace vio;
    if (mode & 1) {
        S->v = {v[0], v[1], v[2]};
        for (int i = 6; i < 9; i++) S->C[i][i] = 0.05f * 0.05f;
    }
    if (mode & 2) {
        S->g = {g[0], g[1], g[2]};
        V3 gu = S->g * (1.0 / G);
        V3 e = std::fabs(gu.x) < 0.9 ? V3{1, 0, 0} : V3{0, 1, 0};
        S->b1 = e - gu * dot(gu, e);
        S->b1 = S->b1 * (1.0 / norm(S->b1));
        S->b2 = cross(gu, S->b1);
        S->C[15][15] = S->C[16][16] = 0.01f * 0.01f;
        S->up_lp = S->g * -1.0;
    }
}
void vio_debug(double *o) {
    o[0] = S->n_alive, o[1] = S->n_tracked, o[2] = S->n_updated, o[3] = S->n_new;
    o[4] = S->bg.x, o[5] = S->bg.y, o[6] = S->bg.z, o[7] = S->ba.x, o[8] = S->ba.y, o[9] = S->ba.z;
    o[10] = S->g.x, o[11] = S->g.y, o[12] = S->g.z, o[13] = S->v.x, o[14] = S->v.y, o[15] = S->v.z;
    int na = 0;
    for (auto &a : S->anchors) na += a.alive;
    o[16] = na;
    o[17] = S->n_passes;
    for (int i = 0; i < 16; i++) o[18 + i] = S->stats[i];
    o[34] = S->nis, o[35] = S->n_tried, o[36] = S->streak, o[37] = S->stats[16], o[38] = S->rho_med, o[39] = S->scale_log;
    for (int i = 0; i < 6; i++) o[40 + i] = S->C[3 + i][3 + i];  // position and velocity variances
    o[46] = S->C[15][15] + S->C[16][16];
}
int32_t vio_features(double *o, int32_t max) {  // rows [px, py, rho, anchor, used]
    int n = 0;
    for (int i = 0; i < vio::MAXF && n < max; i++)
        if (S->feats[i].alive) {
            const auto &f = S->feats[i];
            o[5 * n] = f.px, o[5 * n + 1] = f.py, o[5 * n + 2] = f.rho, o[5 * n + 3] = f.anchor, o[5 * n + 4] = f.used;
            n++;
        }
    return n;
}
#endif
}
