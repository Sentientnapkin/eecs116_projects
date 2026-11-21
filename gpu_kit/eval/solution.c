/* Visual-inertial odometry for viobench, in plain C (port of proto/solution/solution.py, configuration FINAL).
 *
 * Per frame:
 *   IMU core   integrate the 10 gyro samples (minus the estimated bias) for attitude; gravity from the first half
 *              second; slow accelerometer tilt correction.
 *   velocity   = direction of travel (from the camera, kept in camera axes so it turns with the drone) x speed,
 *              zero while the camera sees no motion, fading to zero when vision has been silent for 2.5 s.
 *   vision     ~40 corners picked on a grid at the start of a 1 s window, followed frame to frame with a two-level
 *              Lucas-Kanade tracker on 9x9 patches (only pixels near the corners are read), predicted by the gyro.
 *              At the window end: rotation correction + direction of travel (epipolar fit with a cheirality sign
 *              check), stop/go from the left-over parallax, speed = sqrt(0.35 m/s x flow speed), and the window's
 *              movement is redone with the measured direction.
 * Nothing is allocated per frame; all state is static.
 */
#include "viobench_abi.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------------ configuration (FINAL in solution.py) */
#define GRAVITY 9.81
#define GRAVITY_TOLERANCE (0.1 * GRAVITY)
#define CALIBRATION_SECONDS 0.5
#define REST_ACCEL_STD 1.0
#define REST_GYRO_STD 0.2
#define MAX_GYRO_BIAS_AT_REST 0.05
#define TILT_SECONDS 2.0

#ifndef WINDOW_FRAMES
#define WINDOW_FRAMES 20
#endif
#ifndef MIN_WINDOW_FRAMES
#define MIN_WINDOW_FRAMES 8
#endif
#ifndef MAX_POINTS
#define MAX_POINTS 40
#endif
#ifndef DEFER_START
#define DEFER_START 1  /* start the next window one frame after the last one closed */
#endif
#ifndef KEEP_FRACTION
#define KEEP_FRACTION 0.0  /* >0: finish a window early once fewer than this share of its corners survive */
#endif
#ifndef MIN_POINTS
#define MIN_POINTS 10
#endif
#ifndef FINISH_BELOW
#define FINISH_BELOW MIN_POINTS  /* a window closes once fewer than this many points survive; above MIN_POINTS it is still used */
#endif
#ifndef BIAS_GAIN
#define BIAS_GAIN 0.05
#endif
#define MAX_BIAS 0.06
#define MAX_ROT_CORRECTION 0.08
#ifndef ROT_APPLY
#define ROT_APPLY 0.5
#endif
#define PURE_ROTATION_PARALLAX 0.004
#ifndef MOVING_PARALLAX
#define MOVING_PARALLAX 0.008
#endif
#ifndef FIXED_SPEED
#define FIXED_SPEED 0.35
#endif
#ifndef TYPICAL_DEPTH
#define TYPICAL_DEPTH 3.0
#endif
#ifndef SPEED_SMOOTHING
#define SPEED_SMOOTHING 0.6  /* weight of the newest flow speed (0.3 -> 0.6: 1.10 -> 1.05 m) */
#endif
#ifndef RETRO_RAW
#define RETRO_RAW 1      /* redo a window with its own speed measurement (1.10 -> 1.02 m on tuning runs) */
#endif
#ifndef SPEED_WEIGHT
#define SPEED_WEIGHT 0.5
#endif
#ifndef SCALE_TAU
#define SCALE_TAU 0        /* >0: correct the camera speed's scale (the unknown scene depth) with the accelerometer,
                              remembering about this many seconds of evidence; 0 = off */
#endif
#ifndef SCALE_PRIOR
#define SCALE_PRIOR 2.0    /* (m/s)^2 of "the 3 m depth guess is right" evidence the correction starts from */
#endif
#ifndef SCALE_RMA
#define SCALE_RMA 0        /* 1: symmetric fit sqrt(sum|dA|^2 / sum|du|^2) (both sides noisy) instead of least squares,
                              which shrinks the scale when the camera velocities are noisy */
#endif
#define SCALE_MIN 0.33
#define SCALE_MAX 3.0
#ifndef VEL_KF
#define VEL_KF 0           /* 1: velocity from a Kalman filter: accelerometer prediction, camera-window corrections, outlier gate */
#endif
#ifndef KF_Q
#define KF_Q 1.0           /* (m/s)^2 per second the velocity uncertainty grows between camera updates */
#endif
#ifndef KF_R_REL
#define KF_R_REL 0.3       /* camera velocity noise: this fraction of its speed ... */
#endif
#ifndef KF_R_ABS
#define KF_R_ABS 0.1       /* ... plus this many m/s */
#endif
#ifndef KF_STILL_R
#define KF_STILL_R 0.05    /* m/s noise of a "standing still" window */
#endif
#ifndef KF_GATE
#define KF_GATE 3.0        /* reject a camera velocity this many standard deviations away from the prediction */
#endif
#ifndef KF_BLEND
#define KF_BLEND 1         /* 1: the camera measurement uses the blended speed (pulled toward FIXED_SPEED); 0: camera speed alone */
#endif
#ifndef CONF_BLEND
#define CONF_BLEND 0       /* 1: the camera weight of the speed blend depends on the window's confidence (points kept,
                              movement seen): from W_LO for a shaky window up to W_HI for a clear one */
#endif
#ifndef W_LO
#define W_LO 0.4
#endif
#ifndef W_HI
#define W_HI 1.0
#endif
#ifndef CONF_POINTS
#define CONF_POINTS 20     /* this many points kept = full confidence from the points */
#endif
#ifndef CONF_PARALLAX
#define CONF_PARALLAX 0.03 /* this much parallax (rad) = full confidence from the movement */
#endif
#ifndef FLOW_LOST
#define FLOW_LOST 0        /* 1: points lost mid-window still count for the speed, over the frames they survived
                              (the nearest, fastest-moving points are the ones lost first) */
#endif
#ifndef SPEED_PRIOR_SECONDS
#define SPEED_PRIOR_SECONDS 0  /* >0: the speed is pulled toward this flight's own average camera speed over about this many
                                  seconds (starting at FIXED_SPEED) instead of toward the fixed FIXED_SPEED */
#endif
#ifndef MAX_SPEED
#define MAX_SPEED 4.0
#endif
#ifndef STALE_SECONDS
#define STALE_SECONDS 2.5
#endif
#ifndef STALE_DECAY_SECONDS
#define STALE_DECAY_SECONDS 1.0
#endif

/* tracker (each can be overridden with -D for experiments) */
#ifndef HALF
#define HALF 6                  /* 11x11 patch (9x9: 1.38 m, 11x11: 1.10 m on the tuning runs) */
#endif
#define SIDE (2 * HALF + 1)
#define TSIDE (SIDE + 2)        /* template with a one-sample border for gradients */
#ifndef LEVELS
#define LEVELS 4                /* image pyramid levels: 320, 160, 80, 40 px wide */
#endif
#ifndef LK_ITERATIONS
#define LK_ITERATIONS 5
#endif
#ifndef COARSE_ITERATIONS
#define COARSE_ITERATIONS 3     /* refinement steps on the smaller pyramid levels ... */
#endif
#ifndef COARSE_EPS
#define COARSE_EPS 0.01f        /* ... which stop once a step is under 0.1 px (squared) */
#endif
#ifndef BACK_LEVELS
#define BACK_LEVELS 4           /* levels used by the backward check (all: fewer let bad points through, 2.07 -> 3.12 m) */
#endif
#ifndef MAX_RESIDUAL
#define MAX_RESIDUAL 30.0f      /* gray levels RMS: worse matches are dropped */
#endif
#ifndef FB_CHECK
#define FB_CHECK 1              /* track back to the previous frame; must land within FB_TOLERANCE px */
#endif
#ifndef FB_TOLERANCE
#define FB_TOLERANCE 1.0f
#endif
#ifndef MAX_JUMP
#define MAX_JUMP 25.0f          /* pixels from the gyro prediction */
#endif
#define BORDER 3
#define MAX_W 320
#define MAX_H 240

/* corner grid */
#define CELL_W 32
#define CELL_H 30
#define CANDIDATE_STRIDE 5
#define CORNER_BORDER 10
#define MAX_CELLS 128

/* ------------------------------------------------------------------ small linear algebra (row-major 3x3) */
typedef struct { double m[9]; } M3;

static M3 m3_eye(void) { M3 r = {{1, 0, 0, 0, 1, 0, 0, 0, 1}}; return r; }

static M3 m3_mul(M3 a, M3 b) {
    M3 r;
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++)
            r.m[3 * i + j] = a.m[3 * i] * b.m[j] + a.m[3 * i + 1] * b.m[3 + j] + a.m[3 * i + 2] * b.m[6 + j];
    return r;
}

static M3 m3_t(M3 a) {
    M3 r;
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) r.m[3 * i + j] = a.m[3 * j + i];
    return r;
}

static void m3_apply(const M3 *a, const double v[3], double out[3]) {
    double x = v[0], y = v[1], z = v[2];
    out[0] = a->m[0] * x + a->m[1] * y + a->m[2] * z;
    out[1] = a->m[3] * x + a->m[4] * y + a->m[5] * z;
    out[2] = a->m[6] * x + a->m[7] * y + a->m[8] * z;
}

static void m3_apply_t(const M3 *a, const double v[3], double out[3]) { /* a^T v */
    double x = v[0], y = v[1], z = v[2];
    out[0] = a->m[0] * x + a->m[3] * y + a->m[6] * z;
    out[1] = a->m[1] * x + a->m[4] * y + a->m[7] * z;
    out[2] = a->m[2] * x + a->m[5] * y + a->m[8] * z;
}

static double dot3(const double a[3], const double b[3]) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
static double norm3(const double a[3]) { return sqrt(dot3(a, a)); }
static void cross3(const double a[3], const double b[3], double out[3]) {
    double x = a[1] * b[2] - a[2] * b[1], y = a[2] * b[0] - a[0] * b[2], z = a[0] * b[1] - a[1] * b[0];
    out[0] = x; out[1] = y; out[2] = z;
}

static M3 skew(const double v[3]) { M3 r = {{0, -v[2], v[1], v[2], 0, -v[0], -v[1], v[0], 0}}; return r; }

static M3 exp_so3(const double w[3]) {
    double angle = norm3(w);
    M3 r = m3_eye();
    if (angle < 1e-12) {
        M3 k = skew(w);
        for (int i = 0; i < 9; i++) r.m[i] += k.m[i];
        return r;
    }
    double u[3] = {w[0] / angle, w[1] / angle, w[2] / angle};
    M3 k = skew(u), k2 = m3_mul(k, k);
    double s = sin(angle), c = 1.0 - cos(angle);
    for (int i = 0; i < 9; i++) r.m[i] += s * k.m[i] + c * k2.m[i];
    return r;
}

static M3 orthonormalize(M3 a) { /* Gram-Schmidt on the rows */
    double *r0 = a.m, *r1 = a.m + 3, *r2 = a.m + 6;
    double n = norm3(r0);
    for (int i = 0; i < 3; i++) r0[i] /= n;
    double d = dot3(r0, r1);
    for (int i = 0; i < 3; i++) r1[i] -= d * r0[i];
    n = norm3(r1);
    for (int i = 0; i < 3; i++) r1[i] /= n;
    cross3(r0, r1, r2);
    return a;
}

/* solve the symmetric positive 3x3 system a x = b (Cramer) */
static int solve3(const double a[9], const double b[3], double x[3]) {
    double c0 = a[4] * a[8] - a[5] * a[7], c1 = a[5] * a[6] - a[3] * a[8], c2 = a[3] * a[7] - a[4] * a[6];
    double det = a[0] * c0 + a[1] * c1 + a[2] * c2;
    if (!(fabs(det) > 1e-300)) return 0;
    double inv[9] = {c0, a[2] * a[7] - a[1] * a[8], a[1] * a[5] - a[2] * a[4],
                     c1, a[0] * a[8] - a[2] * a[6], a[2] * a[3] - a[0] * a[5],
                     c2, a[1] * a[6] - a[0] * a[7], a[0] * a[4] - a[1] * a[3]};
    for (int i = 0; i < 3; i++) x[i] = (inv[3 * i] * b[0] + inv[3 * i + 1] * b[1] + inv[3 * i + 2] * b[2]) / det;
    return 1;
}

/* eigenvector of the smallest eigenvalue of a symmetric 3x3 matrix (cyclic Jacobi) */
static void smallest_eigenvector(const double s[9], double out[3]) {
    double a[9], v[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};
    memcpy(a, s, sizeof(a));
    for (int sweep = 0; sweep < 8; sweep++) {
        double off = a[1] * a[1] + a[2] * a[2] + a[5] * a[5];
        if (off < 1e-30) break;
        for (int p = 0; p < 2; p++)
            for (int q = p + 1; q < 3; q++) {
                double apq = a[3 * p + q];
                if (fabs(apq) < 1e-300) continue;
                double theta = (a[3 * q + q] - a[3 * p + p]) / (2 * apq);
                double t = (theta >= 0 ? 1.0 : -1.0) / (fabs(theta) + sqrt(theta * theta + 1));
                double c = 1 / sqrt(t * t + 1), sn = t * c;
                for (int k = 0; k < 3; k++) { /* a = J^T a J */
                    double akp = a[3 * k + p], akq = a[3 * k + q];
                    a[3 * k + p] = c * akp - sn * akq;
                    a[3 * k + q] = sn * akp + c * akq;
                }
                for (int k = 0; k < 3; k++) {
                    double apk = a[3 * p + k], aqk = a[3 * q + k];
                    a[3 * p + k] = c * apk - sn * aqk;
                    a[3 * q + k] = sn * apk + c * aqk;
                }
                for (int k = 0; k < 3; k++) {
                    double vkp = v[3 * k + p], vkq = v[3 * k + q];
                    v[3 * k + p] = c * vkp - sn * vkq;
                    v[3 * k + q] = sn * vkp + c * vkq;
                }
            }
    }
    int m = 0;
    if (a[4] < a[0]) m = 1;
    if (a[8] < a[3 * m + m]) m = 2;
    out[0] = v[m]; out[1] = v[3 + m]; out[2] = v[6 + m];
    double n = norm3(out);
    for (int i = 0; i < 3; i++) out[i] /= n;
}

/* median of n values (n <= MAX_POINTS), destroys the scratch copy */
static double median(const double *values, int n) {
    double s[2 * MAX_POINTS];
    if (n <= 0) return 0;
    if (n > 2 * MAX_POINTS) n = 2 * MAX_POINTS;
    memcpy(s, values, n * sizeof(double));
    for (int i = 1; i < n; i++) { /* insertion sort: n is tiny */
        double x = s[i];
        int j = i - 1;
        while (j >= 0 && s[j] > x) { s[j + 1] = s[j]; j--; }
        s[j + 1] = x;
    }
    return (n & 1) ? s[n / 2] : 0.5 * (s[n / 2 - 1] + s[n / 2]);
}

static void huber(const double *res, int n, double scale, double *w) {
    if (scale < 1e-9) scale = 1e-9;
    for (int i = 0; i < n; i++) {
        double r = fabs(res[i]) / scale;
        w[i] = r <= 1.0 ? 1.0 : 1.0 / r;
    }
}

/* ------------------------------------------------------------------ state */
static int W = 320, H = 240;
static double FX, FY, CX, CY;
static M3 R_ci, R_ic;            /* camera <- IMU, IMU <- camera */
static double t_ci[3], t_ic[3];  /* translations of T_cam_imu and T_imu_cam */

static M3 R_wb;                  /* world = IMU frame at the first camera timestamp */
static double vel[3], pos[3], omega[3], gyro_bias[3], gravity_w[3];
static int have_gravity, started;
static double last_t, now_t;

static double cal_force[3], cal_time, cal_g_sum[3], cal_g_sq[3], cal_a_sum[3], cal_a_sq[3];
static int cal_n;

static double direction_cam[3];
static int have_direction, moving;
static double direction_time = -1e9;
#ifdef __wasm__
static double flow_speed, prior_speed;
#endif

typedef struct {
    float x, y;                      /* current position */
    float sx, sy;                    /* position at the window start */
    float tmpl[LEVELS][TSIDE * TSIDE];
    float gx[LEVELS][SIDE * SIDE], gy[LEVELS][SIDE * SIDE];
    float hinv[LEVELS][3];           /* inverse of [[a, b], [b, c]] as (a, b, c) */
    int good;
} Track;

static Track tracks[MAX_POINTS];
/* points lost mid-window: start and last good position, the camera rotation at that frame, and how long they lasted */
static float lost_sx[MAX_POINTS], lost_sy[MAX_POINTS], lost_x[MAX_POINTS], lost_y[MAX_POINTS];
static double lost_dt[MAX_POINTS];
static int n_lost;
static double prev_frame_t;
static int n_tracks, initial_tracks, window_active, window_frames;
static M3 window_R;
/* accelerometer scale: accA = integral of the world acceleration since the start; winA = its sum over the open window */
static double accA[3], winA[3], sc_N, sc_D, sc_A, prev_u[3], prev_Abar[3], prev_end;
static int winA_n, have_prev_u;
static double kv[3], kP;
static int kf_init, kf_rejects;
static void window_Abar(double out[3]) {
    for (int k = 0; k < 3; k++) out[k] = winA_n > 0 ? winA[k] / winA_n : accA[k];
}
static double speed_scale(void) {
    if (SCALE_TAU <= 0) return 1.0;
    double s = (sc_N + SCALE_PRIOR) / (sc_D + SCALE_PRIOR);
    if (SCALE_RMA) s = sc_N > 0 ? sqrt((sc_A + SCALE_PRIOR) / (sc_D + SCALE_PRIOR)) : SCALE_MIN;
    return s < SCALE_MIN ? SCALE_MIN : (s > SCALE_MAX ? SCALE_MAX : s);
}
/* mean velocity of window k = v0 + mean of accA over its frames, so for two windows (camera velocity u, unknown scale s):
   s (u_k - u_j) = Abar_k - Abar_j. Least squares with forgetting; a standing window (u = 0) is an exact anchor. */
static void scale_update(int ok, const double u[3], double t_start, double t_end) {
    if (SCALE_TAU <= 0) return;
    double Abar[3];
    for (int k = 0; k < 3; k++) Abar[k] = winA_n > 0 ? winA[k] / winA_n : accA[k];
    if (ok && have_prev_u && t_start - prev_end < 1.5) {
        double f = exp(-(t_end - prev_end) / (SCALE_TAU > 0 ? SCALE_TAU : 1)), du[3], dA[3];
        for (int k = 0; k < 3; k++) { du[k] = u[k] - prev_u[k]; dA[k] = Abar[k] - prev_Abar[k]; }
        sc_N = sc_N * f + (du[0] * dA[0] + du[1] * dA[1] + du[2] * dA[2]);
        sc_D = sc_D * f + (du[0] * du[0] + du[1] * du[1] + du[2] * du[2]);
        sc_A = sc_A * f + (dA[0] * dA[0] + dA[1] * dA[1] + dA[2] * dA[2]);
    }
    if (ok) {
        memcpy(prev_u, u, sizeof(prev_u)); memcpy(prev_Abar, Abar, sizeof(prev_Abar));
        prev_end = t_end; have_prev_u = 1;
    } else {
        have_prev_u = 0;
    }
}
static double window_p[3], window_t;
static M3 prev_R;
/* image pyramids (green channel as gray, each level a 2x2-averaged half of the one above) of the current and the
   previous frame; LK runs coarse to fine on them like OpenCV's calcOpticalFlowPyrLK */
/* each level carries a PAD-pixel border of copied edge pixels, so patches near the edge stay on the fast path */
typedef struct { const uint8_t *p; int w, h, s; } Img; /* p: pixel (0, 0); s: row stride including the border */
#define PAD 16
#define PYRAMID_BYTES 160000
static uint8_t pyramid_store[2][PYRAMID_BYTES];
static Img pyramids[2][LEVELS];
static int cur_index;
static int have_prev_gray;
#define CUR (pyramids[cur_index])
#define PREV (pyramids[cur_index ^ 1])

/* ------------------------------------------------------------------ host-only diagnostics (not in the wasm) */
#ifndef __wasm__
#define DEBUG_MAX_WINDOWS 4000
static int debug_windows;
static double debug_record[DEBUG_MAX_WINDOWS][12]; /* t0, t1, points, parallax, d[3], t_cam[3], used, moving */
static void debug_window(double t0, double t1, int n, double parallax, const double d[3], const double tc[3], int used) {
    if (debug_windows >= DEBUG_MAX_WINDOWS) return;
    double *r = debug_record[debug_windows++];
    r[0] = t0; r[1] = t1; r[2] = n; r[3] = parallax;
    for (int k = 0; k < 3; k++) { r[4 + k] = d[k]; r[7 + k] = tc ? tc[k] : 0; }
    r[10] = used; r[11] = moving;
}
int debug_window_count(void) { return debug_windows; }
static double flow_speed, prior_speed;
double debug_flow_speed(void) { return flow_speed; }
int debug_moving(void) { return moving; }
const double *debug_window_data(void) { return &debug_record[0][0]; }
#else
#define debug_window(...) ((void)0)
#endif

/* ------------------------------------------------------------------ pixels (green channel as gray) */
/* copy the edge pixels of a level outwards into its PAD-pixel border (equivalent to clamping coordinates) */
static void pad_level(uint8_t *p, int w, int h, int s) {
    for (int y = 0; y < h; y++) {
        uint8_t *row = p + y * s;
        memset(row - PAD, row[0], PAD);
        memset(row + w, row[w - 1], PAD);
    }
    for (int k = 1; k <= PAD; k++) {
        memcpy(p - k * s - PAD, p - PAD, w + 2 * PAD);
        memcpy(p + (h - 1 + k) * s - PAD, p + (h - 1) * s - PAD, w + 2 * PAD);
    }
}

static void load_gray(const uint8_t *frame) {
    cur_index ^= 1;
    uint8_t *store = pyramid_store[cur_index];
    Img *pyr = pyramids[cur_index];
    int s = W + 2 * PAD;
    uint8_t *g = store + PAD * s + PAD;
    const uint8_t *src = frame + 1;
    for (int y = 0; y < H; y++) {
        uint8_t *row = g + y * s;
        const uint8_t *in = src + 3 * y * W;
        for (int x = 0; x < W; x++) row[x] = in[3 * x];
    }
    pad_level(g, W, H, s);
    pyr[0].p = g; pyr[0].w = W; pyr[0].h = H; pyr[0].s = s;
    uint8_t *next = store + (H + 2 * PAD) * s;
    for (int L = 1; L < LEVELS; L++) {
        const Img *up = &pyr[L - 1];
        int w = up->w / 2, h = up->h / 2, ls = w + 2 * PAD;
        uint8_t *o = next + PAD * ls + PAD;
        for (int y = 0; y < h; y++) {
            const uint8_t *r0 = up->p + (2 * y) * up->s, *r1 = r0 + up->s;
            uint8_t *out = o + y * ls;
            for (int x = 0; x < w; x++)
                out[x] = (uint8_t)((r0[2 * x] + r0[2 * x + 1] + r1[2 * x] + r1[2 * x + 1] + 2) >> 2);
        }
        pad_level(o, w, h, ls);
        pyr[L].p = o; pyr[L].w = w; pyr[L].h = h; pyr[L].s = ls;
        next += (h + 2 * PAD) * ls;
    }
}

static inline float pix(int x, int y) { return (float)CUR[0].p[y * CUR[0].s + x]; }

static inline float sample(const Img *im, float x, float y) {
    const int w = im->w, h = im->h, s = im->s;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x > w - 1.001f) x = w - 1.001f;
    if (y > h - 1.001f) y = h - 1.001f;
    int x0 = (int)x, y0 = (int)y;
    float ax = x - x0, ay = y - y0;
    const uint8_t *p = im->p + y0 * s + x0;
    float top = p[0] + ax * ((float)p[1] - p[0]);
    float bottom = p[s] + ax * ((float)p[s + 1] - p[s]);
    return top + ay * (bottom - top);
}

/* n x n samples of im at (x + j, y + i): all share one sub-pixel offset, so the bilinear weights are computed once
   and the inner loop is four loads and four multiply-adds; the padded border keeps nearly every patch on this path */
static void patch(const Img *im, float x, float y, int n, float *out) {
    float fx = floorf(x), fy = floorf(y);
    int x0 = (int)fx, y0 = (int)fy, s = im->s;
    if (x0 >= -PAD && y0 >= -PAD && x0 + n < im->w + PAD - 1 && y0 + n < im->h + PAD - 1) {
        float ax = x - fx, ay = y - fy;
        float w00 = (1 - ax) * (1 - ay), w01 = ax * (1 - ay), w10 = (1 - ax) * ay, w11 = ax * ay;
        for (int i = 0; i < n; i++) {
            const uint8_t *r0 = im->p + (y0 + i) * s + x0, *r1 = r0 + s;
            float *o = out + i * n;
            for (int j = 0; j < n; j++) o[j] = w00 * r0[j] + w01 * r0[j + 1] + w10 * r1[j] + w11 * r1[j + 1];
        }
    } else {
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) out[i * n + j] = sample(im, x + j, y + i);
    }
}

/* tracker level l runs coarse to fine on pyramid level L = LEVELS-1-l; a full-resolution pixel coordinate c maps to
   (c + 0.5) / 2^L - 0.5 there (pixel centres) */
static inline float to_level(float c, int L) { return (c + 0.5f) / (float)(1 << L) - 0.5f; }
static inline float from_level(float c, int L) { return (c + 0.5f) * (float)(1 << L) - 0.5f; }

/* template, gradients and inverse Hessian of a track at its current position in pyramid pyr */
static int make_template(Track *tr, const Img *pyr) {
    for (int l = 0; l < LEVELS; l++) {
        int L = LEVELS - 1 - l;
        float cx = to_level(tr->x, L), cy = to_level(tr->y, L);
        float *T = tr->tmpl[l];
        patch(&pyr[L], cx - HALF - 1, cy - HALF - 1, TSIDE, T);
        float a = 0, b = 0, c = 0, inv2s = 0.5f;
        for (int i = 0; i < SIDE; i++)
            for (int j = 0; j < SIDE; j++) {
                int k = (i + 1) * TSIDE + (j + 1);
                float gx = (T[k + 1] - T[k - 1]) * inv2s, gy = (T[k + TSIDE] - T[k - TSIDE]) * inv2s;
                tr->gx[l][i * SIDE + j] = gx;
                tr->gy[l][i * SIDE + j] = gy;
                a += gx * gx; b += gx * gy; c += gy * gy;
            }
        float det = a * c - b * b;
        if (!(det > 1e-3f)) return 0;
        tr->hinv[l][0] = c / det; tr->hinv[l][1] = -b / det; tr->hinv[l][2] = a / det;
    }
    return 1;
}

/* inverse-compositional Lucas-Kanade: where does tr's template sit in image img, starting the search at (ux, uy)? */
static int lk(const Track *tr, const Img *pyr, float ux, float uy, float *ox, float *oy, int first_level) {
    float px = ux, py = uy;
    for (int l = first_level; l < LEVELS; l++) {
        int L = LEVELS - 1 - l;
        const Img *im = &pyr[L];
        float qx = to_level(px, L), qy = to_level(py, L);
        const float *T = tr->tmpl[l], *GX = tr->gx[l], *GY = tr->gy[l], *Hi = tr->hinv[l];
        float P[SIDE * SIDE];
        int iterations = L == 0 ? LK_ITERATIONS : COARSE_ITERATIONS;
        float eps = L == 0 ? 0.0009f : COARSE_EPS;
        for (int it = 0; it < iterations; it++) {
            float bx = 0, by = 0;
            patch(im, qx - HALF, qy - HALF, SIDE, P);
            for (int i = 0; i < SIDE; i++) {
                const float *Ti = T + (i + 1) * TSIDE + 1, *Pi = P + i * SIDE, *Gx = GX + i * SIDE, *Gy = GY + i * SIDE;
                for (int j = 0; j < SIDE; j++) {
                    float e = Pi[j] - Ti[j];
                    bx += Gx[j] * e;
                    by += Gy[j] * e;
                }
            }
            float dx = Hi[0] * bx + Hi[1] * by, dy = Hi[1] * bx + Hi[2] * by;
            qx -= dx; qy -= dy;
            if (dx * dx + dy * dy < eps) break;
        }
        px = from_level(qx, L); py = from_level(qy, L);
    }
    const float *T = tr->tmpl[LEVELS - 1]; /* residual at the final position, full resolution */
    float e2 = 0, P[SIDE * SIDE];
    patch(&pyr[0], px - HALF, py - HALF, SIDE, P);
    for (int i = 0; i < SIDE; i++)
        for (int j = 0; j < SIDE; j++) {
            float e = P[i * SIDE + j] - T[(i + 1) * TSIDE + (j + 1)];
            e2 += e * e;
        }
    if (!(sqrtf(e2 / (SIDE * SIDE)) < MAX_RESIDUAL)) return 0;
    if ((px - ux) * (px - ux) + (py - uy) * (py - uy) > MAX_JUMP * MAX_JUMP) return 0;
    if (px < BORDER || py < BORDER || px > W - 1 - BORDER || py > H - 1 - BORDER) return 0;
    *ox = px; *oy = py;
    return 1;
}

/* ------------------------------------------------------------------ corners on a grid (Shi-Tomasi, sparse) */
static float corner_score(int x, int y) {
    float sxx = 0, syy = 0, sxy = 0;
    for (int dy = -3; dy <= 3; dy += 2)
        for (int dx = -3; dx <= 3; dx += 2) {
            int u = x + dx, v = y + dy;
            float gx = pix(u + 1, v) - pix(u - 1, v), gy = pix(u, v + 1) - pix(u, v - 1);
            sxx += gx * gx; syy += gy * gy; sxy += gx * gy;
        }
    float half = 0.5f * (sxx + syy), diff = 0.5f * (sxx - syy);
    return half - sqrtf(diff * diff + sxy * sxy);
}

static void start_window(double t) {
    float best_score[MAX_CELLS];
    int best_x[MAX_CELLS], best_y[MAX_CELLS], cells = 0;
    float top = 0;
    for (int cy = 0; cy + CELL_H <= H; cy += CELL_H)
        for (int cx = 0; cx + CELL_W <= W; cx += CELL_W) {
            if (cells >= MAX_CELLS) break;
            float bs = 0;
            int bx = -1, by = -1;
            for (int y = cy + 2; y < cy + CELL_H - 1; y += CANDIDATE_STRIDE) {
                if (y < CORNER_BORDER || y >= H - CORNER_BORDER) continue;
                for (int x = cx + 2; x < cx + CELL_W - 1; x += CANDIDATE_STRIDE) {
                    if (x < CORNER_BORDER || x >= W - CORNER_BORDER) continue;
                    float s = corner_score(x, y);
                    if (s > bs) { bs = s; bx = x; by = y; }
                }
            }
            if (bx >= 0) {
                best_score[cells] = bs; best_x[cells] = bx; best_y[cells] = by; cells++;
                if (bs > top) top = bs;
            }
        }
    /* keep the strongest cells, above a small fraction of the best (like qualityLevel = 0.001) */
    n_tracks = 0;
    float floor_score = top * 0.001f > 1.0f ? top * 0.001f : 1.0f;
    while (n_tracks < MAX_POINTS) {
        int m = -1;
        for (int c = 0; c < cells; c++)
            if (best_score[c] > floor_score && (m < 0 || best_score[c] > best_score[m])) m = c;
        if (m < 0) break;
        Track *tr = &tracks[n_tracks];
        tr->x = tr->sx = (float)best_x[m];
        tr->y = tr->sy = (float)best_y[m];
        best_score[m] = -1;
        if (make_template(tr, CUR)) n_tracks++;
    }
    if (n_tracks < MIN_POINTS) {
        window_active = 0;
        return;
    }
    initial_tracks = n_tracks;
    window_active = 1;
    window_frames = 0;
    window_R = R_wb;
    memcpy(window_p, pos, sizeof(pos));
    window_t = t;
    memcpy(winA, accA, sizeof(accA));
    winA_n = 1;
    n_lost = 0;
}

static void bearing(float x, float y, double out[3]) {
    out[0] = (x - CX) / FX; out[1] = (y - CY) / FY; out[2] = 1.0;
    double n = norm3(out);
    out[0] /= n; out[1] /= n; out[2] /= n;
}

static M3 lost_R[MAX_POINTS];
static void record_lost(const Track *tr, float x, float y) {
    if (!FLOW_LOST || n_lost >= MAX_POINTS || window_frames < 2) return;
    lost_sx[n_lost] = tr->sx; lost_sy[n_lost] = tr->sy; lost_x[n_lost] = x; lost_y[n_lost] = y;
    lost_R[n_lost] = m3_mul(m3_mul(R_ci, m3_t(window_R)), m3_mul(prev_R, R_ic)); /* that frame's camera in window-start axes */
    lost_dt[n_lost] = prev_frame_t - window_t;
    n_lost++;
}
static void track_all(void) {
    M3 R_prev_cur = m3_mul(m3_mul(R_ci, m3_t(prev_R)), m3_mul(R_wb, R_ic));
    int kept = 0;
    for (int i = 0; i < n_tracks; i++) {
        Track *tr = &tracks[i];
        const float lx = tr->x, ly = tr->y;
        double f[3], g[3];
        bearing(tr->x, tr->y, f);
        m3_apply_t(&R_prev_cur, f, g); /* a far point keeps its world bearing: f_cur = R_prev_cur^T f_prev */
        if (g[2] <= 0.1) { record_lost(tr, lx, ly); continue; }
        float ux = (float)(FX * g[0] / g[2] + CX), uy = (float)(FY * g[1] / g[2] + CY), nx, ny;
        if (!lk(tr, CUR, ux, uy, &nx, &ny, 0)) { record_lost(tr, lx, ly); continue; }
        float old_x = tr->x, old_y = tr->y;
        tr->x = nx; tr->y = ny;
        if (!make_template(tr, CUR)) { record_lost(tr, lx, ly); continue; } /* the next frame tracks against this one */
#if FB_CHECK
        float bx, by; /* the match must also hold backwards: from here into the previous frame */
        if (!lk(tr, PREV, old_x, old_y, &bx, &by, LEVELS - BACK_LEVELS)) { record_lost(tr, lx, ly); continue; }
        if ((bx - old_x) * (bx - old_x) + (by - old_y) * (by - old_y) > FB_TOLERANCE * FB_TOLERANCE) { record_lost(tr, lx, ly); continue; }
#else
        (void)old_x; (void)old_y;
#endif
        if (kept != i) tracks[kept] = *tr;
        kept++;
    }
    n_tracks = kept;
    window_frames++;
}

/* ------------------------------------------------------------------ two-view geometry */
static int g_n;
static double g_f0[MAX_POINTS][3], g_f1[MAX_POINTS][3];

static void rotation_only(const M3 *R, double d[3], double *parallax) {
    double A[MAX_POINTS][9], b[MAX_POINTS][3], res[MAX_POINTS], w[MAX_POINTS];
    for (int i = 0; i < g_n; i++) {
        double g[3];
        m3_apply(R, g_f1[i], g);
        M3 a = m3_mul(*R, skew(g_f1[i]));
        for (int k = 0; k < 9; k++) A[i][k] = -a.m[k];
        for (int k = 0; k < 3; k++) b[i][k] = g_f0[i][k] - g[k];
        w[i] = 1;
    }
    d[0] = d[1] = d[2] = 0;
    for (int it = 0; it < 4; it++) {
        double AtA[9] = {1e-6, 0, 0, 0, 1e-6, 0, 0, 0, 1e-6}, Atb[3] = {0, 0, 0};
        for (int i = 0; i < g_n; i++)
            for (int r = 0; r < 3; r++) {
                for (int c = 0; c < 3; c++) {
                    double s = 0;
                    for (int k = 0; k < 3; k++) s += A[i][3 * k + r] * A[i][3 * k + c];
                    AtA[3 * r + c] += w[i] * s;
                }
                double s = 0;
                for (int k = 0; k < 3; k++) s += A[i][3 * k + r] * b[i][k];
                Atb[r] += w[i] * s;
            }
        if (!solve3(AtA, Atb, d)) { d[0] = d[1] = d[2] = 0; }
        for (int i = 0; i < g_n; i++) {
            double e[3];
            for (int k = 0; k < 3; k++) e[k] = b[i][k] - (A[i][3 * k] * d[0] + A[i][3 * k + 1] * d[1] + A[i][3 * k + 2] * d[2]);
            res[i] = norm3(e);
        }
        huber(res, g_n, 1.5 * median(res, g_n), w);
    }
    *parallax = median(res, g_n);
}

static void epipolar(const M3 *R, const double t_init[3], double d[3], double t[3]) {
    double w[MAX_POINTS], r[MAX_POINTS], g[MAX_POINTS][3];
    double n0 = norm3(t_init);
    for (int k = 0; k < 3; k++) t[k] = t_init[k] / n0;
    d[0] = d[1] = d[2] = 0;
    for (int i = 0; i < g_n; i++) w[i] = 1;
    for (int it = 0; it < 6; it++) {
        M3 Rd = m3_mul(*R, exp_so3(d));
        double S[9] = {0};
        for (int i = 0; i < g_n; i++) {
            double h[3];
            m3_apply(&Rd, g_f1[i], g[i]);
            cross3(g[i], g_f0[i], h);
            double ww = w[i] * w[i];
            for (int a = 0; a < 3; a++)
                for (int c = 0; c < 3; c++) S[3 * a + c] += ww * h[a] * h[c];
        }
        double tn[3];
        smallest_eigenvector(S, tn);
        if (dot3(tn, t) < 0) for (int k = 0; k < 3; k++) tn[k] = -tn[k];
        memcpy(t, tn, sizeof(tn));
        double AtA[9] = {1e-4, 0, 0, 0, 1e-4, 0, 0, 0, 1e-4}, Atb[3] = {0, 0, 0}, absr[MAX_POINTS];
        for (int i = 0; i < g_n; i++) {
            double n[3], a[3], tmp[3];
            cross3(g_f0[i], t, n);
            r[i] = dot3(n, g[i]);
            /* a = n^T Rd [f1]x  (row vector) = ([f1]x^T Rd^T n)^T = -(f1 x (Rd^T n)) */
            m3_apply_t(&Rd, n, tmp);
            cross3(g_f1[i], tmp, a);
            for (int k = 0; k < 3; k++) a[k] = -a[k];
            for (int p = 0; p < 3; p++) {
                for (int q = 0; q < 3; q++) AtA[3 * p + q] += w[i] * a[p] * a[q];
                Atb[p] += w[i] * a[p] * r[i];
            }
            absr[i] = fabs(r[i]);
        }
        double e[3];
        if (solve3(AtA, Atb, e)) for (int k = 0; k < 3; k++) d[k] += e[k];
        huber(r, g_n, 1.5 * median(absr, g_n) + 1e-9, w);
    }
    /* cheirality: Z1 = -(f0 x t).(f0 x g) / |f0 x g|^2 must be positive for most points */
    M3 Rd = m3_mul(*R, exp_so3(d));
    int positive = 0, negative = 0;
    for (int i = 0; i < g_n; i++) {
        double gi[3], cg[3], ft[3];
        m3_apply(&Rd, g_f1[i], gi);
        cross3(g_f0[i], gi, cg);
        if (dot3(cg, cg) <= 1e-6) continue;
        cross3(g_f0[i], t, ft);
        double s = -dot3(ft, cg);
        if (s > 0) positive++; else if (s < 0) negative++;
    }
    if (positive + negative >= 3 && positive < negative) for (int k = 0; k < 3; k++) t[k] = -t[k];
}

/* speed = FIXED_SPEED^(1 - w) x flow_speed^w: w = 0 is the fixed guess, 1 the camera alone, 0.5 the geometric middle */
static double speed_prior(void) { return SPEED_PRIOR_SECONDS > 0 ? prior_speed : FIXED_SPEED; }
static double speed_weight = SPEED_WEIGHT;  /* CONF_BLEND: set per window from its confidence */
static double current_speed(void) {
    double flow = flow_speed > 1e-3 ? flow_speed : 1e-3;
    return pow(speed_prior(), 1.0 - speed_weight) * pow(flow, speed_weight);
}

static void finish_window(double t) {
    if (n_tracks < MIN_POINTS || window_frames < MIN_WINDOW_FRAMES) return;
    g_n = n_tracks;
    for (int i = 0; i < g_n; i++) {
        bearing(tracks[i].sx, tracks[i].sy, g_f0[i]);
        bearing(tracks[i].x, tracks[i].y, g_f1[i]);
    }
    M3 R_pred = m3_mul(m3_mul(R_ci, m3_t(window_R)), m3_mul(R_wb, R_ic)); /* camera k1 in camera k0 */
    double d[3], parallax, t_cam[3];
    int have_t = 0;
    rotation_only(&R_pred, d, &parallax);
    if (parallax >= PURE_ROTATION_PARALLAX) {
        double t_init[3];
        if (have_direction) {
            m3_apply(&R_pred, direction_cam, t_init);
        } else {
            double dp[3] = {pos[0] - window_p[0], pos[1] - window_p[1], pos[2] - window_p[2]}, tmp[3];
            m3_apply_t(&window_R, dp, tmp);
            m3_apply(&R_ci, tmp, t_init);
            if (norm3(t_init) <= 1e-3) { t_init[0] = 0; t_init[1] = 0; t_init[2] = 1; }
        }
        epipolar(&R_pred, t_init, d, t_cam);
        have_t = isfinite(t_cam[0]) && isfinite(t_cam[1]) && isfinite(t_cam[2]);
    }
    moving = parallax >= MOVING_PARALLAX;
    double u_cam[3] = {0, 0, 0}, z_mean[3] = {0, 0, 0}, z_quality = 1;
    int u_ok = !moving;  /* a standing window has velocity 0 */
    int z_ok = !moving;  /* Kalman measurement available (a standing window counts) */
    if (have_t) {
        M3 Rd = m3_mul(R_pred, exp_so3(d));
        /* flow speed: a point at angle a from the direction of travel shifts by about |t| sin(a) / Z */
        double ratios[2 * MAX_POINTS];
        int usable = 0;
        double elapsed = t - window_t > 1e-3 ? t - window_t : 1e-3;
        for (int i = 0; i < g_n; i++) {
            double gi[3], c[3];
            m3_apply(&Rd, g_f1[i], gi);
            double cs = dot3(g_f0[i], gi);
            if (cs > 1) cs = 1;
            if (cs < -1) cs = -1;
            cross3(g_f0[i], t_cam, c);
            double sin_a = norm3(c);
            if (sin_a > 0.2) ratios[usable++] = acos(cs) / sin_a / elapsed;
        }
        for (int i = 0; FLOW_LOST && i < n_lost; i++) {
            double f0[3], f1[3], gi[3], c[3];
            bearing(lost_sx[i], lost_sy[i], f0);
            bearing(lost_x[i], lost_y[i], f1);
            m3_apply(&lost_R[i], f1, gi);
            double cs = dot3(f0, gi);
            if (cs > 1) cs = 1;
            if (cs < -1) cs = -1;
            cross3(f0, t_cam, c);
            double sin_a = norm3(c);
            if (sin_a > 0.2 && lost_dt[i] > 1e-3) ratios[usable++] = acos(cs) / sin_a / lost_dt[i];
        }
        double window_speed = -1;
        if (usable >= 5) {
            double raw = TYPICAL_DEPTH * median(ratios, usable);
            double measured = raw * speed_scale();
            if (CONF_BLEND) {
                double cp = (double)(g_n - MIN_POINTS) / (CONF_POINTS - MIN_POINTS);
                double cm = (parallax - MOVING_PARALLAX) / (CONF_PARALLAX - MOVING_PARALLAX);
                cp = cp < 0 ? 0 : (cp > 1 ? 1 : cp);
                cm = cm < 0 ? 0 : (cm > 1 ? 1 : cm);
                speed_weight = W_LO + (W_HI - W_LO) * cp * cm;
            }
            if (moving) {
                double tmp0[3], tw0[3];
                m3_apply(&R_ic, t_cam, tmp0);
                m3_apply(&window_R, tmp0, tw0);
                for (int k = 0; k < 3; k++) u_cam[k] = raw * tw0[k];
                u_ok = 1;
            }
            flow_speed = (1 - SPEED_SMOOTHING) * flow_speed + SPEED_SMOOTHING * measured;
            window_speed = pow(speed_prior(), 1.0 - speed_weight) * pow(measured > 1e-3 ? measured : 1e-3, speed_weight);
            if (SPEED_PRIOR_SECONDS > 0 && parallax >= MOVING_PARALLAX) {
                double m = measured < 0.05 ? 0.05 : (measured > MAX_SPEED ? MAX_SPEED : measured);
                prior_speed += (m - prior_speed) * -expm1(-elapsed / (SPEED_PRIOR_SECONDS > 0 ? SPEED_PRIOR_SECONDS : 1));
            }
        }
        double camera_only = window_speed >= 0 ? pow(window_speed / pow(speed_prior(), 1.0 - speed_weight), 1.0 / speed_weight) : -1;
        int measured_here = window_speed >= 0;
        if (!RETRO_RAW || window_speed < 0) window_speed = current_speed();
        if (window_speed > MAX_SPEED) window_speed = MAX_SPEED;
        /* redo the window's movement with the direction just measured */
        double travelled = moving ? window_speed * (t - window_t) : 0.0, tw[3], tmp[3];
        m3_apply(&R_ic, t_cam, tmp);
        m3_apply(&window_R, tmp, tw);
        if (moving && measured_here) {
            double sp = KF_BLEND ? window_speed : (camera_only > MAX_SPEED ? MAX_SPEED : camera_only);
            for (int k = 0; k < 3; k++) z_mean[k] = sp * tw[k];
            z_quality = (double)MAX_POINTS / (g_n > 1 ? g_n : 1);  /* fewer surviving points: noisier */
            z_ok = 1;
        }
        for (int k = 0; k < 3; k++) pos[k] = window_p[k] + tw[k] * travelled;
        /* the direction in current-camera axes */
        double dc[3];
        m3_apply_t(&Rd, t_cam, dc);
        double n = norm3(dc);
        for (int k = 0; k < 3; k++) direction_cam[k] = dc[k] / n;
        have_direction = 1;
        direction_time = t;
    } else if (!moving) {
        direction_time = t;
    }
    scale_update(u_ok, u_cam, window_t, t);
#if !VEL_KF
    (void)z_ok; (void)z_quality; (void)z_mean;
#else
    if (z_ok) {
        /* the window gives its MEAN velocity; the filter's state is the velocity now: add the change measured since */
        double Abar[3], z[3], y[3], zn = norm3(z_mean);
        window_Abar(Abar);
        for (int k = 0; k < 3; k++) z[k] = z_mean[k] + (accA[k] - Abar[k]);
        double sd = moving ? (KF_R_REL * zn + KF_R_ABS) : KF_STILL_R, R = sd * sd * (moving ? z_quality : 1.0);
        if (!kf_init) {
            memcpy(kv, z, sizeof(z)); kP = R; kf_init = 1; kf_rejects = 0;
        } else {
            for (int k = 0; k < 3; k++) y[k] = z[k] - kv[k];
            double S = kP + R, d2 = (y[0] * y[0] + y[1] * y[1] + y[2] * y[2]) / (3 * S);
            if (d2 > KF_GATE * KF_GATE && kf_rejects < 2) {
                kf_rejects++;  /* outlier: keep the prediction */
            } else if (d2 > KF_GATE * KF_GATE) {
                memcpy(kv, z, sizeof(z)); kP = R; kf_rejects = 0;  /* three disagreements in a row: trust the camera again */
            } else {
                double K = kP / S;
                for (int k = 0; k < 3; k++) kv[k] += K * y[k];
                kP *= 1 - K;
                kf_rejects = 0;
            }
        }
        /* the window's movement again, from the filtered velocity */
        for (int k = 0; k < 3; k++) pos[k] = window_p[k] + (kv[k] - (accA[k] - Abar[k])) * (t - window_t);
        direction_time = t;
    }
#endif
    int accept = isfinite(d[0]) && isfinite(d[1]) && isfinite(d[2]) && norm3(d) <= MAX_ROT_CORRECTION;
    debug_window(window_t, t, g_n, parallax, d, have_t ? t_cam : 0, accept);
    if (!accept) return;
    double d_imu[3], half[3];
    m3_apply(&R_ic, d, d_imu);
    double elapsed = t - window_t > 1e-3 ? t - window_t : 1e-3;
    for (int k = 0; k < 3; k++) half[k] = ROT_APPLY * d_imu[k];
    R_wb = orthonormalize(m3_mul(R_wb, exp_so3(half)));
    for (int k = 0; k < 3; k++) gyro_bias[k] -= BIAS_GAIN * d_imu[k] / elapsed;
    double nb = norm3(gyro_bias);
    if (nb > MAX_BIAS) for (int k = 0; k < 3; k++) gyro_bias[k] *= MAX_BIAS / nb;
}

static void vision(double t, const uint8_t *frame) {
    load_gray(frame);
    int finished = 0;
    if (window_active && have_prev_gray) {
        track_all();
        for (int k = 0; k < 3; k++) winA[k] += accA[k];
        winA_n++;
        int losing = KEEP_FRACTION > 0 && n_tracks < KEEP_FRACTION * initial_tracks && window_frames >= MIN_WINDOW_FRAMES;
        if (n_tracks < FINISH_BELOW || window_frames >= WINDOW_FRAMES || losing) {
            finish_window(t);
            window_active = 0;
            finished = 1;
        }
    }
    /* the corner search waits for the next frame when this one already closed a window (flattens the worst frame) */
    if (!window_active && !(DEFER_START && finished)) start_window(t);
    prev_R = R_wb;
    prev_frame_t = t;
    have_prev_gray = 1;
}

/* ------------------------------------------------------------------ IMU core */
static void calibrate(const double *imu, int count, const double force[3], double dt) {
    for (int i = 0; i < count; i++) {
        const double *row = imu + 7 * i;
        for (int k = 0; k < 3; k++) {
            cal_a_sum[k] += row[1 + k]; cal_a_sq[k] += row[1 + k] * row[1 + k];
            cal_g_sum[k] += row[4 + k]; cal_g_sq[k] += row[4 + k] * row[4 + k];
        }
        cal_n++;
    }
    for (int k = 0; k < 3; k++) cal_force[k] += force[k] * dt;
    cal_time += dt;
    if (cal_time < CALIBRATION_SECONDS) return;
    double mean_force[3], magnitude;
    for (int k = 0; k < 3; k++) mean_force[k] = cal_force[k] / cal_time;
    magnitude = norm3(mean_force);
    if (fabs(magnitude - GRAVITY) < GRAVITY_TOLERANCE) {
        for (int k = 0; k < 3; k++) gravity_w[k] = mean_force[k] * GRAVITY / magnitude;
        have_gravity = 1;
        double mg[3], sg[3], sa[3];
        for (int k = 0; k < 3; k++) {
            mg[k] = cal_g_sum[k] / cal_n;
            double ma = cal_a_sum[k] / cal_n;
            sg[k] = sqrt(fmax(cal_g_sq[k] / cal_n - mg[k] * mg[k], 0));
            sa[k] = sqrt(fmax(cal_a_sq[k] / cal_n - ma * ma, 0));
        }
        if (norm3(mg) < MAX_GYRO_BIAS_AT_REST && norm3(sg) < REST_GYRO_STD && norm3(sa) < REST_ACCEL_STD) {
            memcpy(gyro_bias, mg, sizeof(mg));
            memcpy(gravity_w, mean_force, sizeof(mean_force));
        }
    }
    memset(cal_force, 0, sizeof(cal_force));
    memset(cal_a_sum, 0, sizeof(cal_a_sum)); memset(cal_a_sq, 0, sizeof(cal_a_sq));
    memset(cal_g_sum, 0, sizeof(cal_g_sum)); memset(cal_g_sq, 0, sizeof(cal_g_sq));
    cal_time = 0;
    cal_n = 0;
}

static void integrate(const double *imu, int count) {
    double start = last_t, force[3] = {0, 0, 0};
    for (int i = 0; i < count; i++) {
        const double *row = imu + 7 * i;
        double dt = row[0] - last_t;
        if (dt <= 0) continue;
        last_t = row[0];
        double w[3];
        for (int k = 0; k < 3; k++) { omega[k] = row[4 + k] - gyro_bias[k]; w[k] = omega[k] * dt; }
        R_wb = m3_mul(R_wb, exp_so3(w));
        double f[3];
        m3_apply(&R_wb, row + 1, f);
        for (int k = 0; k < 3; k++) force[k] += f[k] * dt;
    }
    double dt = last_t - start;
    if (dt <= 0) return;
    for (int k = 0; k < 3; k++) force[k] /= dt;
    if (!have_gravity) {
        calibrate(imu, count, force, dt);
        return;
    }
    double magnitude = norm3(force);
    if (fabs(magnitude - GRAVITY) < GRAVITY_TOLERANCE) {
        double a[3], gn[3], axis[3], gnorm = norm3(gravity_w);
        for (int k = 0; k < 3; k++) { a[k] = force[k] / magnitude; gn[k] = gravity_w[k] / gnorm; }
        cross3(a, gn, axis);
        double gain = -expm1(-dt / TILT_SECONDS);
        for (int k = 0; k < 3; k++) axis[k] *= gain;
        R_wb = orthonormalize(m3_mul(exp_so3(axis), R_wb));
    }
    for (int k = 0; k < 3; k++) accA[k] += (force[k] - gravity_w[k]) * dt;
    /* velocity: camera direction x speed while moving, zero when standing, fading when vision is silent */
    double next_v[3];
#if VEL_KF
    if (kf_init) {
        for (int k = 0; k < 3; k++) kv[k] += (force[k] - gravity_w[k]) * dt;
        kP += KF_Q * dt;
        if (now_t - direction_time > STALE_SECONDS) {
            double decay = exp(-dt / STALE_DECAY_SECONDS);
            for (int k = 0; k < 3; k++) kv[k] *= decay;
        }
        memcpy(next_v, kv, sizeof(kv));
    } else {
        next_v[0] = next_v[1] = next_v[2] = 0;
    }
#else
    if (now_t - direction_time > STALE_SECONDS) {
        double decay = exp(-dt / STALE_DECAY_SECONDS);
        for (int k = 0; k < 3; k++) next_v[k] = vel[k] * decay;
    } else if (moving && have_direction) {
        double tmp[3], dw[3], speed = current_speed();
        if (speed > MAX_SPEED) speed = MAX_SPEED;
        m3_apply(&R_ic, direction_cam, tmp);
        m3_apply(&R_wb, tmp, dw);
        for (int k = 0; k < 3; k++) next_v[k] = dw[k] * speed;
    } else {
        next_v[0] = next_v[1] = next_v[2] = 0;
    }
#endif
    for (int k = 0; k < 3; k++) {
        pos[k] += 0.5 * dt * (vel[k] + next_v[k]);
        vel[k] = next_v[k];
    }
}

/* ------------------------------------------------------------------ output */
static void quaternion(const M3 *R, double q[4]) { /* [x, y, z, w] */
    const double *m = R->m;
    double trace = m[0] + m[4] + m[8];
    if (trace > 0) {
        double s = sqrt(trace + 1.0) * 2;
        q[0] = (m[7] - m[5]) / s; q[1] = (m[2] - m[6]) / s; q[2] = (m[3] - m[1]) / s; q[3] = 0.25 * s;
    } else {
        int i = (m[4] > m[0]) ? 1 : 0;
        if (m[8] > m[4 * i]) i = 2;
        int j = (i + 1) % 3, k = (i + 2) % 3;
        double s = sqrt(1.0 + m[4 * i] - m[4 * j] - m[4 * k]) * 2;
        q[i] = 0.25 * s;
        q[j] = (m[3 * j + i] + m[3 * i + j]) / s;
        q[k] = (m[3 * k + i] + m[3 * i + k]) / s;
        q[3] = (m[3 * k + j] - m[3 * j + k]) / s;
    }
    double n = sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
    for (int i = 0; i < 4; i++) q[i] /= n;
}

static void write_identity(double *out) {
    for (int i = 0; i < VIOBENCH_STATE_VALUES; i++) out[i] = 0.0;
    out[6] = 1.0;
}

static void write_state(double *out) {
    /* T_c0_c = T_cam_imu T_wb T_imu_cam */
    M3 Rc = m3_mul(m3_mul(R_ci, R_wb), R_ic);
    double a[3], b[3];
    m3_apply(&R_wb, t_ic, a);
    for (int k = 0; k < 3; k++) a[k] += pos[k];
    m3_apply(&R_ci, a, b);
    for (int k = 0; k < 3; k++) out[k] = b[k] + t_ci[k];
    quaternion(&Rc, out + 3);
    double v_b[3], wr[3], vc[3];
    m3_apply_t(&R_wb, vel, v_b);
    cross3(omega, t_ic, wr);
    for (int k = 0; k < 3; k++) v_b[k] += wr[k];
    m3_apply(&R_ci, v_b, vc);
    for (int k = 0; k < 3; k++) out[7 + k] = vc[k];
    m3_apply(&R_ci, omega, out + 10);
    for (int i = 0; i < VIOBENCH_STATE_VALUES; i++)
        if (!isfinite(out[i])) { write_identity(out); return; }
}

/* ------------------------------------------------------------------ config parsing (tiny, for our known keys) */
static char config_text[4096];

static double json_number(const char *key, double fallback) {
    char pattern[64];
    size_t n = strlen(key);
    pattern[0] = '"';
    memcpy(pattern + 1, key, n);
    pattern[n + 1] = '"';
    pattern[n + 2] = 0;
    const char *p = strstr(config_text, pattern);
    if (!p) return fallback;
    p = strchr(p + n + 2, ':');
    return p ? strtod(p + 1, NULL) : fallback;
}

static int json_matrix(const char *key, double out[16]) {
    const char *p = strstr(config_text, key);
    if (!p) return 0;
    p = strchr(p, '[');
    for (int i = 0; i < 16; i++) {
        while (p && *p && !(*p == '-' || *p == '+' || *p == '.' || (*p >= '0' && *p <= '9'))) p++;
        if (!p || !*p) return 0;
        char *end;
        out[i] = strtod(p, &end);
        p = end;
    }
    return 1;
}

/* ------------------------------------------------------------------ ABI */
int32_t abi_version(void) { return VIOBENCH_ABI_VERSION; }

void *alloc(uint32_t size) { return malloc(size ? size : 1); }

int32_t frame_width(void) { return 320; }

int32_t init(const char *json, uint32_t length) {
    if (length >= sizeof(config_text)) return VIOBENCH_STATUS_ERROR;
    memcpy(config_text, json, length);
    config_text[length] = 0;
    W = (int)json_number("width", 320);
    H = (int)json_number("height", 240);
    FX = json_number("fx", 0); FY = json_number("fy", 0);
    CX = json_number("cx", 0); CY = json_number("cy", 0);
    double T[16];
    if (!(FX > 0) || !(FY > 0) || !json_matrix("T_cam_imu", T)) return VIOBENCH_STATUS_ERROR;
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) R_ci.m[3 * i + j] = T[4 * i + j];
        t_ci[i] = T[4 * i + 3];
    }
    R_ic = m3_t(R_ci);
    m3_apply(&R_ic, t_ci, t_ic);
    for (int k = 0; k < 3; k++) t_ic[k] = -t_ic[k];
    R_wb = m3_eye();
    prev_R = R_wb;
    flow_speed = FIXED_SPEED;
    prior_speed = FIXED_SPEED;
    return VIOBENCH_STATUS_OK;
}

int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
    if (!started) {
        started = 1;
        last_t = t;
        now_t = t;
        vision(t, frame);
        write_identity(out);
        return VIOBENCH_STATUS_OK;
    }
    now_t = t;
    integrate(imu, imu_count);
    if (have_gravity) vision(t, frame);
    write_state(out);
    return VIOBENCH_STATUS_OK;
}
