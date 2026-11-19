#pragma once
// Exact changed-input policy of input_attitude.derive(..., external=raw_kf_grid).
// The original rolling Inputs remains a parallel source of quantized sufficient
// statistics. Raw KF supplies current attitude/bias; pooled startup statistics
// separately repropagate only the historical attitudes used by future warps.
#include "input_grid_attitude.hpp"
#include <stdexcept>

namespace odo {

struct NewModelInputs {
    InputGridAttitude att;
    double packet_relative[7 * Orientation::MAX_PACKET];
    struct Start {
        double t, dt, before[3];
        M3 increment;
        float imu[IMU];
    } startup[HISTORY];
    struct History { double t; M3 R; uint8_t image[H * W]; } hist[HISTORY];
    int startup_count = 0, head = 0, count = 0;
    bool pooled_decided = false, started = false;
    double previous_t = 0, previous_bias[3] = {0, 0, 0};
    M3 previous_old = eye(), K = eye(), Kinv = eye(), R_bc = eye();

    void init(double fx, double fy, double cx, double cy, const M3 &body_from_camera) {
        R_bc = body_from_camera;
        att.init(fx, fy, cx, cy, body_from_camera);
    }

    static double samples(const float *imu) {
        double n = 0;
        for (int b = 0; b < 4; ++b) n += std::nearbyint(double(imu[21 + 7 * b]) * 4);
        return n * double(imu[12]);
    }

    void decide_history() {
        pooled_decided = true;
        double n = 0, gm[3] = {}, gs[3] = {}, am[3] = {}, as[3] = {}, norm_mean = 0;
        for (int j = 1; j < startup_count; ++j) {
            const float *imu = startup[j].imu;
            const double weight = samples(imu);
            n += weight;
            double accel_norm = 0;
            for (int c = 0; c < 3; ++c) {
                const double gyro = double(imu[3 + c]) + double(imu[43 + c]) + double(imu[46 + c]);
                const double accel = double(imu[c]) * 9.81;
                gm[c] += weight * gyro;
                gs[c] += weight * (double(imu[9 + c]) * imu[9 + c] + gyro * gyro);
                am[c] += weight * accel;
                as[c] += weight * (double(imu[6 + c]) * imu[6 + c] + accel * accel);
                accel_norm += accel * accel;
            }
            norm_mean += weight * std::sqrt(accel_norm);
        }
        if (n <= 40) return;
        double gyro_norm = 0, gyro_sd = 0, accel_norm = 0;
        for (int c = 0; c < 3; ++c) {
            gm[c] /= n;
            am[c] /= n;
            gs[c] = std::max(0.0, gs[c] / n - gm[c] * gm[c]);
            as[c] = as[c] / n - am[c] * am[c];
            gyro_norm += gm[c] * gm[c];
            gyro_sd = std::max(gyro_sd, std::sqrt(gs[c]));
            accel_norm += am[c] * am[c];
        }
        accel_norm = std::max(std::sqrt(accel_norm), 1e-9);
        double variance = 0;
        for (int c = 0; c < 3; ++c) variance += (am[c] / accel_norm) * (am[c] / accel_norm) * as[c];
        if (!(std::sqrt(gyro_norm) < .1 && gyro_sd < .12 &&
              std::fabs(norm_mean / n - 9.81) < .3 && std::sqrt(std::max(variance, 0.0)) < .5)) return;
        M3 revised = eye();
        for (int j = 1; j < startup_count; ++j) {
            const Start &s = startup[j];
            M3 increment = s.increment;
            if (s.imu[12] > 0) increment = mul(increment, exp_so3(
                (s.before[0] - gm[0]) * s.dt, (s.before[1] - gm[1]) * s.dt, (s.before[2] - gm[2]) * s.dt));
            revised = mul(revised, increment);
            for (int h = 0; h < count; ++h) {
                History &entry = hist[(head + h) % HISTORY];
                if (entry.t == s.t) entry.R = revised;
            }
        }
    }

    M3 step(double t, const uint8_t *rgb, int width, int height, const double *packet, int n,
            double origin, const M3 &old_R, uint8_t *images, float *imu, bool first) {
        if (n > Orientation::MAX_PACKET) throw std::runtime_error("Input IMU packet capacity exceeded");
        float old_imu[IMU];
        std::memcpy(old_imu, imu, sizeof old_imu);
        if (!started) {
            // Training reconstructs a centered, square-pixel K from its FP32 focal feature.
            const double focal = double(old_imu[14]) * W;
            K = {{focal, 0, (W - 1) / 2.0, 0, focal, (H - 1) / 2.0, 0, 0, 1}};
            Kinv = {{1 / focal, 0, -(W - 1) / (2.0 * focal), 0, 1 / focal, -(H - 1) / (2.0 * focal), 0, 0, 1}};
            started = true;
        }
        if (!first && !pooled_decided && (old_imu[12] <= 0 || previous_t >= .8 - 1e-6)) decide_history();
        if (!pooled_decided) {
            if (startup_count == HISTORY) throw std::runtime_error("Input startup history capacity exceeded");
            Start &s = startup[startup_count++];
            s.t = t; s.dt = first ? 0 : t - previous_t;
            s.increment = first ? eye() : mul(tr(previous_old), old_R);
            for (int c = 0; c < 3; ++c) s.before[c] = previous_bias[c];
            std::memcpy(s.imu, old_imu, sizeof old_imu);
        }
        for (int i = 0; i < n; ++i) {
            std::memcpy(packet_relative + 7 * i, packet + 7 * i, 7 * sizeof(double));
            packet_relative[7 * i] -= origin;
        }
        const M3 R = att.step(t, rgb, width, height, packet_relative, n, first);
        for (int c = 0; c < 3; ++c) {
            const double old_bias = double(old_imu[43 + c]) + double(old_imu[46 + c]);
            const double shift = old_bias - att.bias[c];
            imu[3 + c] = float(double(old_imu[3 + c]) + shift * double(old_imu[12] > 0));
            for (int b = 0; b < 4; ++b) {
                const int column = 18 + b * 7 + c;
                imu[column] = float(double(old_imu[column]) + shift * double(old_imu[21 + b * 7] > 0));
            }
            imu[43 + c] = float(att.bias[c]);
            previous_bias[c] = old_bias;
        }
        imu[49] = pooled_decided && (att.bias[0] != 0 || att.bias[1] != 0 || att.bias[2] != 0) ? 1.f : 0.f;
        std::memset(images + H * W, 0, 4 * H * W);
        const double ages[2] = {ODO_BASELINES};
        for (int b = 0; b < 2; ++b) {
            const History *match = nullptr;
            for (int j = count - 1; j >= 0; --j) {
                const History &entry = hist[(head + j) % HISTORY];
                if (entry.t <= t - ages[b] + 1e-8) { match = &entry; break; }
            }
            if (!match) continue;
            const M3 rotation = mul(mul(mul(tr(R_bc), tr(R)), match->R), R_bc);
            const M3 inverse = mul(mul(K, tr(rotation)), Kinv);
            Inputs::warp(match->image, inverse.a, images + (1 + b) * H * W, images + (3 + b) * H * W);
        }
        if (count == HISTORY) { head = (head + 1) % HISTORY; --count; }
        History &entry = hist[(head + count++) % HISTORY];
        entry.t = t; entry.R = R; std::memcpy(entry.image, images, H * W);
        while (count > 2 && hist[(head + 1) % HISTORY].t <= t - ages[1] + 1e-8) { head = (head + 1) % HISTORY; --count; }
        previous_old = old_R; previous_t = t;
        return R;
    }
};

}  // namespace odo
