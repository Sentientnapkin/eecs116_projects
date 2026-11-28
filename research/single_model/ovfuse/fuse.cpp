// B16 + OpenVINS in one reactor. Both estimators get every frame; FUSE_MODE picks what is reported.
//   FUSE_MODE 0: B16 only (OpenVINS still runs: fuel/parity check)   1: OpenVINS only (= the provided example)
//   FUSE_MODE 2: switch: B16 until OpenVINS has initialized and has run FUSE_WARM frames, then OpenVINS;
//                back to B16 for good if OpenVINS errors, outputs non-finite values, or runs away (speed > FUSE_VMAX m/s,
//                or position more than FUSE_DMAX m from B16 for FUSE_DFRAMES consecutive frames).
// Positions of both are camera k in camera 0 (the ABI convention), so the switch needs no frame change.
#include "viobench_abi.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#ifndef FUSE_MODE
#define FUSE_MODE 2
#endif
#ifndef FUSE_WARM
#define FUSE_WARM 20
#endif
#ifndef FUSE_VMAX
#define FUSE_VMAX 12.0
#endif
#ifndef FUSE_DMAX
#define FUSE_DMAX 1e9
#endif
#ifndef FUSE_DFRAMES
#define FUSE_DFRAMES 40
#endif
#ifndef FUSE_BLEND
#define FUSE_BLEND 0 /* frames over which the reported position moves linearly from B16 to OpenVINS at the switch */
#endif

extern "C" {
int32_t b16_init(const char* json, uint32_t length);
int32_t b16_step(double t, const uint8_t* frame, const double* imu, int32_t imu_count, double* out);
}
int32_t ovx_init(const char* json, uint32_t length);
int32_t ovx_step(double t, const uint8_t* frame, const double* imu, int32_t imu_count, double* out);
bool ovx_started();

namespace {
bool ov_dead = false, use_ov = false;
long frame_no = 0, ov_run = 0, far_run = 0, switch_frame = -1;

bool finite(const double* v, int n) {
    for (int i = 0; i < n; i++)
        if (!std::isfinite(v[i])) return false;
    return true;
}
}  // namespace

extern "C" {
VIOBENCH_EXPORT(abi_version) int32_t abi_version() { return VIOBENCH_ABI_VERSION; }
VIOBENCH_EXPORT(alloc) void* alloc(uint32_t size) { return std::malloc(size ? size : 1); }
VIOBENCH_EXPORT(frame_width) int32_t frame_width() { return 320; }

VIOBENCH_EXPORT(init) int32_t init(const char* json, uint32_t length) {
    ov_dead = use_ov = false;
    frame_no = ov_run = far_run = 0;
    switch_frame = -1;
    if (b16_init(json, length) != VIOBENCH_STATUS_OK) return VIOBENCH_STATUS_ERROR;
    if (ovx_init(json, length) != VIOBENCH_STATUS_OK) {
        if (FUSE_MODE == 1) return VIOBENCH_STATUS_ERROR;
        ov_dead = true;
        std::fprintf(stderr, "fuse: OpenVINS init failed, B16 only\n");
    }
    return VIOBENCH_STATUS_OK;
}

VIOBENCH_EXPORT(step) int32_t step(double t, const uint8_t* frame, const double* imu, int32_t imu_count, double* out) {
    double b[VIOBENCH_STATE_VALUES], o[VIOBENCH_STATE_VALUES];
    for (int i = 0; i < VIOBENCH_STATE_VALUES; i++) b[i] = o[i] = NAN;
    const int32_t bs = b16_step(t, frame, imu, imu_count, b);
    bool ov_ok = false;
    if (!ov_dead) {
        if (ovx_step(t, frame, imu, imu_count, o) == VIOBENCH_STATUS_OK && finite(o, VIOBENCH_STATE_VALUES)) {
            ov_ok = true;
        } else {
            ov_dead = true;
            std::fprintf(stderr, "fuse: OpenVINS failed at t=%.3f (frame %ld)%s\n", t, frame_no, use_ov ? ", back to B16" : "");
            use_ov = false;
        }
    }
    frame_no++;
    if (FUSE_MODE == 1) {
        if (!ov_ok) return VIOBENCH_STATUS_ERROR;
        std::memcpy(out, o, sizeof o);
        return VIOBENCH_STATUS_OK;
    }
    const bool b_ok = bs == VIOBENCH_STATUS_OK && finite(b, VIOBENCH_STATE_VALUES);
    if (FUSE_MODE == 2 && ov_ok) {
        ov_run = ovx_started() ? ov_run + 1 : 0;
        const double speed = std::sqrt(o[7] * o[7] + o[8] * o[8] + o[9] * o[9]);
        double d = 0;
        if (b_ok)
            for (int i = 0; i < 3; i++) d += (o[i] - b[i]) * (o[i] - b[i]);
        far_run = (b_ok && std::sqrt(d) > FUSE_DMAX) ? far_run + 1 : 0;
        if (use_ov && (speed > FUSE_VMAX || far_run >= FUSE_DFRAMES)) {
            std::fprintf(stderr, "fuse: OpenVINS rejected at t=%.3f (|v| %.2f, |p_ov-p_b16| %.2f), B16 for good\n", t, speed, std::sqrt(d));
            ov_dead = true;
            use_ov = false;
        } else if (!use_ov && ov_run >= FUSE_WARM && speed <= FUSE_VMAX) {
            use_ov = true;
            switch_frame = frame_no;
            std::printf("fuse: switched to OpenVINS at t=%.3f (frame %ld), |p_ov-p_b16| %.3f m\n", t, frame_no, std::sqrt(d));
        }
    }
    if (use_ov) {
        std::memcpy(out, o, sizeof o);
        if (FUSE_BLEND > 0 && b_ok && frame_no - switch_frame < FUSE_BLEND) {
            const double w = double(frame_no - switch_frame) / FUSE_BLEND;
            for (int i = 0; i < 3; i++) out[i] = (1 - w) * b[i] + w * o[i];
        }
        return VIOBENCH_STATUS_OK;
    }
    if (!b_ok) return VIOBENCH_STATUS_ERROR;
    std::memcpy(out, b, sizeof b);
    return VIOBENCH_STATUS_OK;
}
}
