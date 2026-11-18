/* Bridge used only to exercise the same C kernel on a host and in Wasm. */
#include "weights.h"

static float frame[REFINE_CONTEXT_SIZE + 3 + 51 + 9 + 3];
static OdometryRefineState state;

float *refine_frame(void) {
    return frame;
}

void refine_reset(void) {
    state = (OdometryRefineState){0};
}

void refine_frame_step(void) {
    float *initial = frame + REFINE_CONTEXT_SIZE;
    float *imu = initial + 3;
    float *R = imu + 51;
    odometry_refine_step(&odometry_refine_weights, &state, frame, initial, imu, R, R + 9);
}
