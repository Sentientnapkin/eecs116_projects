#pragma once

#include <array>

namespace vio {

using Vec3 = std::array<double, 3>;
using Mat3 = std::array<Vec3, 3>;

inline Vec3 transform(const Mat3& r, const Vec3& v) {
    Vec3 result{};
    for (int i = 0; i < 3; ++i) {
        result[i] = r[i][0] * v[0] + r[i][1] * v[1] + r[i][2] * v[2];
    }
    return result;
}

inline Vec3 transform_transposed(const Mat3& r, const Vec3& v) {
    Vec3 result{};
    for (int i = 0; i < 3; ++i) {
        result[i] = r[0][i] * v[0] + r[1][i] * v[1] + r[2][i] * v[2];
    }
    return result;
}

class Position {
public:
    Position(Mat3 camera_to_body, Vec3 camera_in_body)
        : camera_to_body_(camera_to_body), camera_in_body_(camera_in_body) {}

    Vec3 step(double t, const Mat3& body_to_initial_body, const Vec3& body_velocity) {
        const auto world_velocity = transform(body_to_initial_body, body_velocity);
        auto camera = transform(body_to_initial_body, camera_in_body_);
        for (int i = 0; i < 3; ++i) {
            if (initialized_) {
                body_[i] += 0.5 * (t - t_) * (last_velocity_[i] + world_velocity[i]);
            }
            camera[i] += body_[i] - camera_in_body_[i];
        }
        t_ = t;
        last_velocity_ = world_velocity;
        initialized_ = true;
        return transform_transposed(camera_to_body_, camera);
    }

private:
    Mat3 camera_to_body_;
    Vec3 camera_in_body_, body_{}, last_velocity_{};
    double t_ = 0;
    bool initialized_ = false;
};

}  // namespace vio
