#include "odometry.hpp"
#include "viobench_abi.h"

#include <cstdlib>
#include <new>

namespace {

odo::Estimator estimator;
odo::Weights weights;
bool ready = false;

// The runner passes a length-delimited flat object with six numeric fields
// and one row-major 4x4 array. Keys can appear in any order.
const char *field(const char *json, const char *name) {
    const char *at = std::strstr(json, name);
    if (!at) return nullptr;
    at += std::strlen(name);
    while (*at == ' ' || *at == '\n' || *at == '\r' || *at == '\t') ++at;
    return *at == ':' ? at + 1 : nullptr;
}

bool read_number(const char *&at, double &value) {
    if (!at) return false;
    char *end;
    value = std::strtod(at, &end);
    if (end == at || !std::isfinite(value)) return false;
    at = end;
    return true;
}

bool token(const char *&at, char expected) {
    if (!at) return false;
    while (*at == ' ' || *at == '\n' || *at == '\r' || *at == '\t') ++at;
    if (*at != expected) return false;
    ++at;
    return true;
}

}  // namespace

#ifdef __wasm__
extern "C" const float odo_weights[ODO_WEIGHTS];
#else
static const float *odo_weights = nullptr;

extern "C" void host_weights(const float *data) {
    odo_weights = data;
}

extern "C" void host_features(uint8_t *images, float *imu, double *rotation) {
    std::memcpy(images, estimator.images, sizeof estimator.images);
    std::memcpy(imu, estimator.imu, sizeof estimator.imu);
    std::memcpy(rotation, estimator.R.a, sizeof estimator.R.a);
}

extern "C" void host_reset_net() {
    estimator.net.w = &weights;
    estimator.net.reset();
}

extern "C" void host_net_step(const uint8_t *images, const float *imu, float *velocity) {
    estimator.net.step(images, imu, velocity);
}
#endif

#ifdef ODO_INPUT_KF_GRID
#ifdef __wasm__
#define ODO_INPUT_EXPORT(name) __attribute__((export_name(name)))
#else
#define ODO_INPUT_EXPORT(name)
#endif
// Read-only debug export. It accepts no reference/truth data and is never called
// by the benchmark runner; the same binary can be checked without tracing edits.
extern "C" ODO_INPUT_EXPORT("input_features") void input_features(
        uint8_t *images, float *imu, double *rotation, double *state) {
    std::memcpy(images, estimator.images, sizeof estimator.images);
    std::memcpy(imu, estimator.imu, sizeof estimator.imu);
    std::memcpy(rotation, estimator.R.a, sizeof estimator.R.a);
    const auto &att = estimator.input_policy.att;
    for (int c = 0; c < 3; ++c) { state[c] = att.bias[c]; state[3 + c] = att.P[c]; }
    state[6] = att.decided; state[7] = att.accepted; state[8] = att.rejected;
    state[9] = estimator.input_policy.pooled_decided;
    for (int c = 0; c < 3; ++c) state[10 + c] = estimator.vb[c];
}
#undef ODO_INPUT_EXPORT
#endif

extern "C" int32_t abi_version() { return VIOBENCH_ABI_VERSION; }
extern "C" void *alloc(uint32_t size) { return std::malloc(size); }
extern "C" int32_t frame_width() { return 320; }

extern "C" int32_t init(const char *config_json, uint32_t length) {
    ready = false;
    char json[2048];
    if (!config_json || length >= sizeof json) return VIOBENCH_STATUS_ERROR;
    std::memcpy(json, config_json, length);
    json[length] = '\0';
    const char *keys[] = {"\"width\"", "\"height\"", "\"fx\"", "\"fy\"", "\"cx\"", "\"cy\""};
    double camera[6];
    for (int i = 0; i < 6; ++i) {
        const char *at = field(json, keys[i]);
        if (!read_number(at, camera[i])) return VIOBENCH_STATUS_ERROR;
    }
    if (camera[0] != frame_width() || camera[1] != 240 || camera[2] <= 0 || camera[3] <= 0)
        return VIOBENCH_STATUS_ERROR;
    const char *at = field(json, "\"T_cam_imu\"");
    double transform[16];
    if (!token(at, '[')) return VIOBENCH_STATUS_ERROR;
    for (int row = 0; row < 4; ++row) {
        if (row && !token(at, ',')) return VIOBENCH_STATUS_ERROR;
        if (!token(at, '[')) return VIOBENCH_STATUS_ERROR;
        for (int col = 0; col < 4; ++col) {
            if (col && !token(at, ',')) return VIOBENCH_STATUS_ERROR;
            if (!read_number(at, transform[row * 4 + col])) return VIOBENCH_STATUS_ERROR;
        }
        if (!token(at, ']')) return VIOBENCH_STATUS_ERROR;
    }
    if (!token(at, ']')) return VIOBENCH_STATUS_ERROR;
#ifndef __wasm__
    if (!odo_weights) return VIOBENCH_STATUS_ERROR;
#endif
    if (odo::bind(weights, odo_weights) != ODO_WEIGHTS) return VIOBENCH_STATUS_ERROR;
#ifdef ODO_INPUT_KF_GRID
    estimator.~Estimator();
#endif
    new (&estimator) odo::Estimator;
    estimator.init(&weights, int(camera[0]), int(camera[1]), camera[2], camera[3], camera[4], camera[5], transform);
    ready = true;
    return VIOBENCH_STATUS_OK;
}

extern "C" int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
    if (!ready || !frame || !out || !std::isfinite(t) || (estimator.have_v && t - estimator.time_origin <= estimator.last_t)
            || imu_count < 0 || imu_count > odo::Orientation::MAX_PACKET || (imu_count && !imu))
        return VIOBENCH_STATUS_ERROR;
#ifdef ODO_INPUT_KF_GRID
    try {
        estimator.step(t, frame, imu, imu_count, out);
    } catch (const std::exception &) {
        return VIOBENCH_STATUS_ERROR;
    }
#else
    estimator.step(t, frame, imu, imu_count, out);
#endif
    return VIOBENCH_STATUS_OK;
}
