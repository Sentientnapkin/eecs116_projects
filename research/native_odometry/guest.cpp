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
    new (&estimator) odo::Estimator;
    estimator.init(&weights, int(camera[0]), int(camera[1]), camera[2], camera[3], camera[4], camera[5], transform);
    ready = true;
    return VIOBENCH_STATUS_OK;
}

extern "C" int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
    if (!ready || !frame || !out || !std::isfinite(t) || (estimator.have_v && t - estimator.time_origin <= estimator.last_t)
            || imu_count < 0 || imu_count > odo::Orientation::MAX_PACKET || (imu_count && !imu))
        return VIOBENCH_STATUS_ERROR;
    estimator.step(t, frame, imu, imu_count, out);
    return VIOBENCH_STATUS_OK;
}
