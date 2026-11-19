#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace vio {

struct Dense {
    const float* weights;
    const float* bias;
    int inputs;
    int outputs;

    void apply(const float* input, float* output, bool relu = false) const {
        for (int i = 0; i < outputs; ++i) {
            const float* row = weights + static_cast<std::size_t>(i) * inputs;
            float value = bias ? bias[i] : 0.0f;
            for (int j = 0; j < inputs; ++j) {
                value += row[j] * input[j];
            }
            output[i] = relu ? std::max(0.0f, value) : value;
        }
    }
};

struct Conv {
    const float* weights;
    const float* bias;
    int inputs;
    int outputs;
    int kernel;
    int padding;

    int extent(int n) const { return (n + 2 * padding - kernel) / 2 + 1; }

    void apply(const float* src, int height, int width, float* dst) const {
        const int out_height = extent(height);
        const int out_width = extent(width);
        for (int oc = 0; oc < outputs; ++oc) {
            for (int y = 0; y < out_height; ++y) {
                for (int x = 0; x < out_width; ++x) {
                    float value = bias ? bias[oc] : 0.0f;
                    for (int ic = 0; ic < inputs; ++ic) {
                        for (int ky = 0; ky < kernel; ++ky) {
                            const int iy = 2 * y - padding + ky;
                            if (iy < 0 || iy >= height) continue;
                            for (int kx = 0; kx < kernel; ++kx) {
                                const int ix = 2 * x - padding + kx;
                                if (ix < 0 || ix >= width) continue;
                                const auto weight = ((oc * inputs + ic) * kernel + ky) * kernel + kx;
                                value += src[(ic * height + iy) * width + ix] * weights[weight];
                            }
                        }
                    }
                    dst[(oc * out_height + y) * out_width + x] = std::max(0.0f, value);
                }
            }
        }
    }
};

// CNN plus fixed EMA. The caller supplies preprocessed CHW images and the selected
// IMU feature vector. Model weights must outlive the predictor.
class Predictor {
public:
    Predictor(int height, int width, Conv first, Conv second, Dense projection,
              Dense output, bool zero_initial_state)
        : height_(height), width_(width), first_(first), second_(second),
          projection_(projection), output_(output), zero_initial_state_(zero_initial_state),
          pixels_(first.inputs * height * width),
          intermediate_(first.outputs * first.extent(height) * first.extent(width)),
          features_(projection.inputs), head_input_(2 * projection.outputs) {}

    void reset() { initialized_ = false; }

    void step(const std::uint8_t* images, const float* sensors, float dt, float* velocity) {
        for (std::size_t i = 0; i < pixels_.size(); ++i) {
            pixels_[i] = static_cast<float>(images[i]) / 255.0f - 0.5f;
        }
        first_.apply(pixels_.data(), height_, width_, intermediate_.data());
        const int height = first_.extent(height_);
        const int width = first_.extent(width_);
        second_.apply(intermediate_.data(), height, width, features_.data());
        const int visual = second_.outputs * second_.extent(height) * second_.extent(width);
        std::copy_n(sensors, projection_.inputs - visual, features_.data() + visual);
        projection_.apply(features_.data(), head_input_.data(), true);
        float* state = head_input_.data() + projection_.outputs;
        if (!initialized_) {
            if (zero_initial_state_) {
                std::fill_n(state, projection_.outputs, 0.0f);
            } else {
                std::copy_n(head_input_.data(), projection_.outputs, state);
            }
            initialized_ = true;
        } else {
            const float decay = std::exp(-2.0f * dt);
            for (int i = 0; i < projection_.outputs; ++i) {
                state[i] = decay * state[i] + (1.0f - decay) * head_input_[i];
            }
        }
        output_.apply(head_input_.data(), velocity);
    }

private:
    int height_, width_;
    Conv first_, second_;
    Dense projection_, output_;
    bool zero_initial_state_, initialized_ = false;
    std::vector<float> pixels_, intermediate_, features_, head_input_;
};

}  // namespace vio
