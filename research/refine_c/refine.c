#include "refine.h"

#include <math.h>

static void linear(size_t rows, size_t cols, const float *weight, const float *bias,
                   const float *input, float *output) {
    for (size_t i = 0; i < rows; ++i) {
        float sum = bias[i];
        for (size_t j = 0; j < cols; ++j)
            sum += weight[i * cols + j] * input[j];
        output[i] = sum;
    }
}

static float sigmoid(float x) {
    return 1.0f / (1.0f + expf(-x));
}

void odometry_refine_step(const OdometryRefineWeights *w, OdometryRefineState *state,
                          const float *context, const float initial_velocity[3],
                          const float imu[51], const float R[9], float result[3]) {
    const size_t h = w->hidden_size, in = w->context_size + 8;
    float hidden[h], features[in], projected[h], input_gates[3*h], hidden_gates[3*h];
    float predicted[3], velocity[3], delta[3];
    for (size_t i = 0; i < 3; ++i) {
        float previous_body = 0.0f;
        for (size_t j = 0; j < 3; ++j)
            previous_body += state->previous_world[j] * R[3*j + i];
        predicted[i] = previous_body + (9.81f * imu[i] - 9.81f * R[6 + i]) * (imu[12] * imu[13]);
        velocity[i] = initial_velocity[i];
    }
    features[3] = imu[12];
    features[4] = (float)state->seen;
    for (size_t i = 0; i < w->context_size; ++i)
        features[i + 8] = context[i];

    linear(h, w->context_size, w->init_weight, w->init_bias, context, hidden);
    for (size_t i = 0; i < h; ++i)
        hidden[i] = tanhf(hidden[i]);
    for (size_t k = 0; k < w->iterations; ++k) {
        for (size_t i = 0; i < 3; ++i) {
            features[i] = velocity[i];
            float residual = (predicted[i] - velocity[i]) * features[4];
            features[i + 5] = fmaxf(-3.0f, fminf(3.0f, residual));
        }
        linear(h, in, w->input_weight, w->input_bias, features, projected);
        for (size_t i = 0; i < h; ++i)
            projected[i] *= sigmoid(projected[i]);

        linear(3*h, h, w->weight_ih, w->bias_ih, projected, input_gates);
        linear(3*h, h, w->weight_hh, w->bias_hh, hidden, hidden_gates);
        for (size_t i = 0; i < h; ++i) {
            float reset = sigmoid(input_gates[i] + hidden_gates[i]);
            float update = sigmoid(input_gates[h + i] + hidden_gates[h + i]);
            float candidate = tanhf(input_gates[2*h + i] + reset * hidden_gates[2*h + i]);
            hidden[i] = candidate + update * (hidden[i] - candidate);
        }
        linear(3, h, w->delta_weight, w->delta_bias, hidden, delta);
        for (size_t i = 0; i < 3; ++i)
            velocity[i] += delta[i];
    }
    for (size_t i = 0; i < 3; ++i) {
        state->previous_world[i] = (R[3*i] * velocity[0] + R[3*i + 1] * velocity[1]) + R[3*i + 2] * velocity[2];
        result[i] = velocity[i];
    }
    state->seen = 1;
}
