#include "predictor.hpp"
#include "kinematics.hpp"

#include <cassert>

int main() {
    const float unit[] = {1.f};
    const float projection[] = {2.f, 1.f};
    const float head[] = {1.f, 2.f, 0.f, 1.f, 1.f, 0.f};
    vio::Conv convolution{unit, nullptr, 1, 1, 1, 0};
    vio::Dense encoder{projection, nullptr, 2, 1};
    vio::Dense output{head, nullptr, 2, 3};
    const std::uint8_t white[] = {255}, black[] = {0};
    const float imu[] = {2.f};
    float result[3];

    vio::Predictor model(1, 1, convolution, convolution, encoder, output, false);
    model.step(white, imu, 0.f, result);
    assert(result[0] == 9.f && result[1] == 3.f && result[2] == 3.f);
    model.step(black, imu, 0.5f, result);
    const float expected = 2.f + std::exp(-1.f);
    assert(std::abs(result[1] - expected) < 1e-6f);
    assert(std::abs(result[0] - 2.f - 2.f * expected) < 1e-6f);
    model.reset();
    model.step(black, imu, 0.f, result);
    assert(result[0] == 6.f);

    vio::Predictor zero(1, 1, convolution, convolution, encoder, output, true);
    zero.step(white, imu, 0.f, result);
    assert(result[0] == 3.f && result[1] == 0.f && result[2] == 3.f);

    const vio::Mat3 identity{{{1, 0, 0}, {0, 1, 0}, {0, 0, 1}}};
    const vio::Mat3 turn{{{0, -1, 0}, {1, 0, 0}, {0, 0, 1}}};
    vio::Position lever_arm(identity, {1, 0, 0});
    assert((lever_arm.step(5, identity, {0, 0, 0}) == vio::Vec3{0, 0, 0}));
    assert((lever_arm.step(6, turn, {0, 0, 0}) == vio::Vec3{-1, 1, 0}));

    vio::Position translation(identity, {0, 0, 0});
    translation.step(1, identity, {2, 0, 0});
    assert((translation.step(2, turn, {2, 0, 0}) == vio::Vec3{1, 1, 0}));
}
