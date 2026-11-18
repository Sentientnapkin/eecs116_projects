#ifndef ODOMETRY_REFINE_H
#define ODOMETRY_REFINE_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    size_t context_size, hidden_size, iterations;
    const float *init_weight, *init_bias;
    const float *input_weight, *input_bias;
    const float *weight_ih, *bias_ih, *weight_hh, *bias_hh;
    const float *delta_weight, *delta_bias;
} OdometryRefineWeights;

typedef struct {
    float previous_world[3];
    unsigned seen;
} OdometryRefineState;

/* Reset to zero at the beginning of each stream. R maps body to world, row-major.
   imu uses the existing 51-feature layout. Result may alias initial_velocity. */
void odometry_refine_step(const OdometryRefineWeights *weights, OdometryRefineState *state,
                          const float *context, const float initial_velocity[3],
                          const float imu[51], const float R[9], float result[3]);

#ifdef __cplusplus
}
#endif
#endif
