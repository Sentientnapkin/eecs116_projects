/* =====================================================================================================================
 * gp_msckf: visual-inertial MSCKF with Gaussian-process IMU bias states (viobench submission, milestone m7)
 * =====================================================================================================================
 *
 * A wasm32-wasip1 reactor implementing the viobench ABI v1 (viobench/solution/runtime/native/viobench_abi.h). For every
 * frame it returns the pose of the camera in the first camera frame and its twist. Plain C, no libraries beyond libc
 * and libm, fixed-size static memory, flat cost per frame (max ~21 M fuel, median ~9.6 M on the public set).
 *
 * Pipeline per step (frame + 10 IMU samples, 20 Hz / 200 Hz):
 *
 *   1. IMU propagation (every sample)   error-state EKF, strapdown integration with bias-corrected readings;
 *                                       covariance propagated block-sparsely (F = I except 5 blocks).
 *   2. IMU pseudo-measurements          thrust model: a quadrotor's body x/y specific force is zero, so its frame mean
 *                                       measures the accelerometer bias b_a,x/y; velocity prior (see VELOCITY PRIOR).
 *   3. Image front end                  gray -> 2-level pyramid -> KLT tracking from the gyro-predicted position ->
 *                                       Shi-Tomasi corners topping up a 10x6 grid (one feature per cell).
 *   4. Clones (every 4th frame)         the IMU pose is cloned into the state; a window of 6 clones (~1.2 s).
 *   5. Vision ZUPT                      no translation between the last two clones (de-rotated disparity < 0.4 px)
 *                                       -> zero-velocity update. Cannot fire in steady flight (flight makes parallax).
 *   6. MSCKF feature updates            a track seen in >= 3 clones is used once: triangulate, project the
 *                                       reprojection residuals onto the left null space of the feature Jacobian,
 *                                       chi^2-gate, stack, QR-compress, one EKF update. Spread over the frames
 *                                       between clones so no single frame carries the whole batch (max fuel).
 *   7. Output                           pose of camera k in camera 0, velocity and angular rate in camera k axes.
 *
 * State. Nominal: orientation R (world <- body), velocity v, position p (world), gyro bias b_g, accel bias b_a, R0 (a
 * copy of the frame-0 orientation, refined with the rest so the output stays relative to frame 0), and up to 7 clones
 * (R_c, p_c). The world is gravity-aligned, origin at the IMU at frame 0, yaw = body yaw at frame 0. Error state:
 * [dtheta, dv, dp, db_g, db_a, dtheta0 | dtheta_c, dp_c per clone], orientation errors on the right (R = R^ Exp(dth)).
 *
 * IMU biases are Gaussian processes: kernel s0^2 + s_rw^2 min(t, t') (constant offset + Wiener process), which in
 * state-space form is a random-walk state with initial variance s0^2 and process noise s_rw^2 dt: exact and constant
 * cost per step. s0 = max / sqrt(3) for the simulator's uniform initial bias.
 *
 * Development history, measurements and every design decision: JOURNAL.md (m1 ... m7).
 * Build: viobench bundle gp_msckf -o build/gp_msckf.wasm   (wasi-sdk via VIOBench; see README.md)
 * ===================================================================================================================== */
#include "viobench_abi.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* =====================================================================================================================
 * Parameters
 * ===================================================================================================================== */

/* IMU noise model: HyperDrone x500_fpv_imu preset (viobench/tools/abi/config.py), confirmed by the episode configs */
#define GRAVITY 9.81
#define GYRO_NOISE 0.07        /* rad/s, white noise per 200 Hz sample */
#define ACCEL_NOISE 0.28       /* m/s^2, white noise per sample */
#define GYRO_BIAS_MAX 0.02     /* initial bias ~ uniform(-max, max) per axis */
#define ACCEL_BIAS_MAX 0.2
#define GYRO_BIAS_WALK 0.0006  /* random walk per sqrt(s) (the measured drift supports this reading) */
#define ACCEL_BIAS_WALK 0.001

/* initial uncertainty: roll/pitch from the first IMU window; the episode may start in flight */
#define INIT_TILT_STD 0.05     /* rad */
#define INIT_VELOCITY_STD 1.0  /* m/s */

/* thrust model: body x/y specific force = b_a,x/y + noise (no rotor drag in the simulator) */
#define THRUST_MODEL_STD 0.05  /* m/s^2, unmodelled x/y force */
#define THRUST_GATE 9.21       /* chi^2, 2 dof, 99 % */

/* VELOCITY PRIOR. Velocity is unobservable from the IMU alone, so a weak prior "speed per axis ~ SPEED_STD, correlated
 * over SPEED_TAU" keeps it bounded while vision locks on or drops out. It is applied every frame with variance
 * SPEED_STD^2 * SPEED_TAU / FRAME_DT: the frames within one correlation time together carry the information of a
 * single SPEED_STD measurement (applying sigma directly at 20 Hz would make it ~20x stronger than stated).
 * 0.5 m/s per axis (~0.9 m/s total) is a physical bound for an indoor quadrotor, not a fitted value; confirmed on
 * held-out windows, and it holds on server-like flights 3x faster (JOURNAL m7 and "External check"). */
#define SPEED_STD 0.5          /* m/s per axis */
#define SPEED_TAU 2.0          /* s */
#define FRAME_DT 0.05          /* s, 20 Hz */

/* MSCKF */
#ifndef CLONE_EVERY
#define CLONE_EVERY 4          /* frames between clones */
#endif
#ifndef MAX_CLONES
#define MAX_CLONES 6           /* window ~ MAX_CLONES * CLONE_EVERY frames = 1.2 s */
#endif
#ifndef MIN_OBS
#define MIN_OBS 3              /* clone observations a feature needs */
#endif
#ifndef MAX_OBS
#define MAX_OBS 8
#endif
#define PIXEL_STD 1.5          /* px, measurement noise of a tracked point */
#define MIN_DEPTH 0.2          /* m, triangulated depth accepted */
#define MAX_DEPTH 40.0
#define TRI_MIN_EIG 1e-6       /* ray matrix: smallest / largest eigenvalue below this = rays ~parallel (wide lens:
                                  stricter values reject most tracks) */
#define CHI2_Z 1.645           /* per-feature gate: 95 % (Wilson-Hilferty approximation of the chi^2 quantile) */
#ifndef MAX_UPDATE_FEATURES
#define MAX_UPDATE_FEATURES 20 /* ended tracks processed per in-between frame */
#endif

/* vision ZUPT */
#define ZUPT_DISPARITY 0.4     /* px, median de-rotated disparity between consecutive clones */
#define ZUPT_MIN_FEATURES 10
#define ZUPT_STD 0.02          /* m/s */

/* image front end (frames 320 x 240 RGB: frame_width() = 320) */
#if PROFILE_TIMERS && !defined(__wasm__)
#include <time.h>
#include <stdio.h>
enum { T_PROP, T_IMUMEAS, T_PYR, T_TRACK, T_DETECT, T_CLONE, T_ZUPT, T_FROWS, T_COMPRESS, T_UPDATE, T_REST, T_N };
static const char *T_NAMES[T_N] = {"propagate", "imu_meas", "pyramid", "track", "detect", "clone", "zupt", "feature_rows", "compress", "final_update", "rest"};
static double t_frame[T_N], t_worst[T_N], t_sum[T_N], t_worst_total; static long t_frames;
static double t_now(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec * 1e6 + ts.tv_nsec * 1e-3; }
#define TSTART(id) double _t_##id = t_now()
#define TSTOP(id, sec) t_frame[sec] += t_now() - _t_##id
static void t_end_frame(void) {
    double tot = 0; for (int i = 0; i < T_N; i++) { tot += t_frame[i]; t_sum[i] += t_frame[i]; }
    if (tot > t_worst_total) { t_worst_total = tot; memcpy(t_worst, t_frame, sizeof t_worst); }
    memset(t_frame, 0, sizeof t_frame); t_frames++;
}
void prof_report(void) {
    t_sum[T_COMPRESS] -= t_sum[T_FROWS] + t_sum[T_UPDATE]; t_worst[T_COMPRESS] -= t_worst[T_FROWS] + t_worst[T_UPDATE];
    double ts = 0; for (int i = 0; i < T_N; i++) ts += t_sum[i];
    fprintf(stderr, "PROF mean frame %.0f us, worst frame %.0f us\n", ts / t_frames, t_worst_total);
    for (int i = 0; i < T_N; i++) fprintf(stderr, "PROF %-13s mean %7.1f us (%4.1f%%)   worst frame %7.1f us\n", T_NAMES[i], t_sum[i] / t_frames, 100 * t_sum[i] / ts, t_worst[i]);
}
#else
#define TSTART(id) ((void)0)
#define TSTOP(id, sec) ((void)0)
#define t_end_frame() ((void)0)
#endif
#if WORK_LOG
#include <stdio.h>
static int w_tracks, w_cells, w_feats, w_ok, w_k, w_clone, w_nclones, w_alive;
#define WL(x) (x)
#else
#define WL(x) ((void)0)
#endif
#ifndef FAST_UPDATE
#define FAST_UPDATE 0  /* row-wise (vectorizable) EKF update */
#endif
#ifndef COMPRESS_INFO
#define COMPRESS_INFO 0 /* batch information + Cholesky instead of stacked rows + QR */
#endif
#ifndef FAST_FROWS
#define FAST_FROWS 0 /* compact-block feature residuals (needs COMPRESS_INFO) */
#endif
#ifndef FAST_KLT
#define FAST_KLT 0 /* fixed-point SIMD KLT (wasm only) */
#endif
#ifndef GRAY_GREEN
#define GRAY_GREEN 0 /* gray image = green channel (cheaper than luminance) */
#endif
#ifndef INT_CORNER
#define INT_CORNER 0
#endif
#ifndef CLONE_BATCH_MAX
#define CLONE_BATCH_MAX 1000 /* features updated on a clone frame (rest queued) */
#endif
#ifndef PROP_EVERY
#define PROP_EVERY 1 /* covariance propagation every N IMU samples (nominal state every sample) */
#endif
#ifndef FRAME_BATCH_MAX
#define FRAME_BATCH_MAX 1000 /* features updated on an in-between frame, in all */
#endif
#ifndef UPDATE_ROWS_MAX
#define UPDATE_ROWS_MAX 0 /* >0: at most this many MSCKF rows per frame, the rest applied over the next frames */
#endif
#ifndef DETECT_STRIDE
#define DETECT_STRIDE 2 /* corner candidates every this many pixels */
#endif
#ifndef FAST_DETECT
#define FAST_DETECT 0 /* shared gradient products + box sums: same corner scores */
#endif
#ifndef CHEAP_GATE
#define CHEAP_GATE 0 /* >0: per-feature gate on the residual vs pixel noise only (this factor x chi2), no covariance */
#endif
#ifndef UPDATE_F32
#define UPDATE_F32 0 /* float32 SIMD for the gain and covariance-correction products (P stays double) */
#endif
#ifndef FAST_PYR
#define FAST_PYR 1  /* SIMD pyramid, same values */
#endif
#define IMG_W 320
#define IMG_H 240
#ifndef LEVELS
#define LEVELS 2               /* pyramid levels (2x2 means) */
#endif
#ifndef KLT_R
#define KLT_R 4                /* 9 x 9 window */
#endif
#define KLT_N ((2 * KLT_R + 1) * (2 * KLT_R + 1))
#ifndef KLT_ITERS
#define KLT_ITERS 5            /* per level */
#endif
#define KLT_EPS 0.03           /* px, stop on the finest level */
#define KLT_EPS_COARSE 0.1     /* px of the level, stop on coarser levels */
#define KLT_MAX_ERR 25.0       /* mean |I - T| in gray levels above which a track is dropped */
#define KLT_MIN_EIG 2.0        /* min eigenvalue of the template gradient matrix, per pixel */
#ifndef DETECT_MAX_CELLS
#define DETECT_MAX_CELLS 1000 /* empty cells scored per frame (spreads detection over frames) */
#endif
#ifndef GRID_X
#define GRID_X 10              /* detection grid: one feature per cell */
#endif
#ifndef GRID_Y
#define GRID_Y 6
#endif
#define CELL_W (IMG_W / GRID_X)
#define CELL_H (IMG_H / GRID_Y)
#define MAX_TRACKS (GRID_X * GRID_Y)
#define DETECT_MIN_SCORE 1000.0 /* Shi-Tomasi score; ~ OpenCV goodFeaturesToTrack quality 0.01 on these frames */
#define BORDER (KLT_R + 3)

/* error-state layout */
#define CORE 18
#define MAXD (CORE + 6 * (MAX_CLONES + 1))
enum { TH = 0, V = 3, P = 6, BG = 9, BA = 12, TH0 = 15 };

/* =====================================================================================================================
 * State
 * ===================================================================================================================== */

/* calibration (from the config) */
static double T_cam_imu[16], T_imu_cam[16], R_bc[9], p_bc[3]; /* 4x4 row-major; R_bc, p_bc: camera -> body */
static double fx, fy, cx, cy;

/* filter */
static double R[9], R0[9], vel[3], pos[3], bg[3], ba[3], omega[3];
static double Pm[MAXD * MAXD]; /* covariance, leading dimension MAXD, active size D */
static int D = CORE;
static double last_t;
static int initialized;

typedef struct { int id; double R[9], p[3]; } Clone;
static Clone clones[MAX_CLONES + 1];
static int nclones, clone_counter, frames_since_clone;

/* a feature's observations at clone frames (normalized image coordinates) */
typedef struct { int n; int cid[MAX_OBS]; double x[MAX_OBS], y[MAX_OBS]; } Obs;
typedef struct { int alive; double x, y; Obs obs; } Track;
static Track tracks[MAX_TRACKS];
#define MAX_BATCH (3 * MAX_TRACKS)
static Obs lost[2 * MAX_TRACKS]; /* ended tracks waiting for their update */
static int nlost;
static int detect_cursor;

/* images: two pyramids (previous, current) */
static uint8_t pyr[2][LEVELS][IMG_W * IMG_H + 64]; /* +64: SIMD loads may read past a row end */
static int cur_pyr;
static double Rwc_prev[9]; /* camera orientation at the previous frame (gyro prediction for KLT) */

/* =====================================================================================================================
 * Small linear algebra (3x3 row-major) and rotations
 * ===================================================================================================================== */

static const double I3[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};

static void m3mul(const double *a, const double *b, double *c) { /* c = a b */
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) c[3 * i + j] = a[3 * i] * b[j] + a[3 * i + 1] * b[3 + j] + a[3 * i + 2] * b[6 + j];
}
static void m3tmul(const double *a, const double *b, double *c) { /* c = a^T b */
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) c[3 * i + j] = a[i] * b[j] + a[3 + i] * b[3 + j] + a[6 + i] * b[6 + j];
}
static void m3vec(const double *a, const double *x, double *y) { /* y = a x */
    for (int i = 0; i < 3; i++) y[i] = a[3 * i] * x[0] + a[3 * i + 1] * x[1] + a[3 * i + 2] * x[2];
}
static void m3tvec(const double *a, const double *x, double *y) { /* y = a^T x */
    for (int i = 0; i < 3; i++) y[i] = a[i] * x[0] + a[3 + i] * x[1] + a[6 + i] * x[2];
}
static void skew(const double *w, double *k) { /* [w]x */
    k[0] = 0; k[1] = -w[2]; k[2] = w[1]; k[3] = w[2]; k[4] = 0; k[5] = -w[0]; k[6] = -w[1]; k[7] = w[0]; k[8] = 0;
}
static void exp_so3(const double *w, double *r) { /* Rodrigues */
    double angle = sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2]), k[9], kk[9];
    if (angle < 1e-12) {
        skew(w, k);
        for (int i = 0; i < 9; i++) r[i] = k[i] + (i % 4 == 0);
        return;
    }
    double u[3] = {w[0] / angle, w[1] / angle, w[2] / angle};
    skew(u, k);
    m3mul(k, k, kk);
    double s = sin(angle), c = 1 - cos(angle);
    for (int i = 0; i < 9; i++) r[i] = (i % 4 == 0) + s * k[i] + c * kk[i];
}
static void rot_right(double *Rm, const double *w) { /* Rm <- Rm Exp(w) */
    double e[9], t[9];
    exp_so3(w, e);
    m3mul(Rm, e, t);
    memcpy(Rm, t, sizeof t);
}
static void align_to_z(const double *f_in, double *r) { /* minimal rotation with r f_hat = +z (keeps yaw) */
    double n = sqrt(f_in[0] * f_in[0] + f_in[1] * f_in[1] + f_in[2] * f_in[2]);
    double f[3] = {f_in[0] / n, f_in[1] / n, f_in[2] / n}, axis[3] = {f[1], -f[0], 0.0};
    double s = sqrt(axis[0] * axis[0] + axis[1] * axis[1]), c = f[2];
    if (s < 1e-9) {
        memset(r, 0, 9 * sizeof(double));
        r[0] = 1; r[4] = c > 0 ? 1 : -1; r[8] = c > 0 ? 1 : -1;
        return;
    }
    double a = atan2(s, c), w[3] = {axis[0] / s * a, axis[1] / s * a, 0.0};
    exp_so3(w, r);
}
static void matrix_to_quaternion(const double *m, double *q) { /* q = [x, y, z, w], unit */
    double tr = m[0] + m[4] + m[8];
    if (tr > 0) {
        double s = sqrt(tr + 1.0) * 2;
        q[0] = (m[7] - m[5]) / s; q[1] = (m[2] - m[6]) / s; q[2] = (m[3] - m[1]) / s; q[3] = 0.25 * s;
    } else {
        int i = 0;
        if (m[4] > m[0]) i = 1;
        if (m[8] > m[3 * i + i]) i = 2;
        int j = (i + 1) % 3, k = (i + 2) % 3;
        double s = sqrt(1.0 + m[3 * i + i] - m[3 * j + j] - m[3 * k + k]) * 2;
        q[i] = 0.25 * s;
        q[j] = (m[3 * j + i] + m[3 * i + j]) / s;
        q[k] = (m[3 * k + i] + m[3 * i + k]) / s;
        q[3] = (m[3 * k + j] - m[3 * j + k]) / s;
    }
    double n = sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
    for (int i = 0; i < 4; i++) q[i] /= n;
}
static int solve3(const double *A, const double *b, double *x) { /* x = A^-1 b by the adjugate */
    double det = A[0] * (A[4] * A[8] - A[5] * A[7]) - A[1] * (A[3] * A[8] - A[5] * A[6]) + A[2] * (A[3] * A[7] - A[4] * A[6]);
    if (fabs(det) < 1e-300) return 0;
    double inv[9] = {(A[4] * A[8] - A[5] * A[7]) / det, (A[2] * A[7] - A[1] * A[8]) / det, (A[1] * A[5] - A[2] * A[4]) / det,
                     (A[5] * A[6] - A[3] * A[8]) / det, (A[0] * A[8] - A[2] * A[6]) / det, (A[2] * A[3] - A[0] * A[5]) / det,
                     (A[3] * A[7] - A[4] * A[6]) / det, (A[1] * A[6] - A[0] * A[7]) / det, (A[0] * A[4] - A[1] * A[3]) / det};
    m3vec(inv, b, x);
    return 1;
}
static void sym3_eig_minmax(const double *A, double *lmin, double *lmax) { /* closed form, symmetric 3x3 */
    double p1 = A[1] * A[1] + A[2] * A[2] + A[5] * A[5];
    double q = (A[0] + A[4] + A[8]) / 3;
    if (p1 < 1e-300) {
        double a = A[0], b = A[4], c = A[8];
        *lmin = fmin(a, fmin(b, c)); *lmax = fmax(a, fmax(b, c));
        return;
    }
    double p2 = (A[0] - q) * (A[0] - q) + (A[4] - q) * (A[4] - q) + (A[8] - q) * (A[8] - q) + 2 * p1;
    double p = sqrt(p2 / 6), B[9];
    for (int i = 0; i < 9; i++) B[i] = (A[i] - (i % 4 == 0 ? q : 0)) / p;
    double r = (B[0] * (B[4] * B[8] - B[5] * B[7]) - B[1] * (B[3] * B[8] - B[5] * B[6]) + B[2] * (B[3] * B[7] - B[4] * B[6])) / 2;
    double phi = r <= -1 ? M_PI / 3 : r >= 1 ? 0 : acos(r) / 3;
    *lmax = q + 2 * p * cos(phi);
    *lmin = q + 2 * p * cos(phi + 2 * M_PI / 3);
}

/* =====================================================================================================================
 * Generic EKF update
 * ===================================================================================================================== */

#define MAXK MAXD
static double HP[MAXK * MAXD], Kt[MAXK * MAXD], Sm[MAXK * MAXK];

static int cholesky(double *A, int n) { /* in place, lower triangle; 0 if not positive definite */
    for (int j = 0; j < n; j++) {
        double s = A[j * n + j];
        for (int k = 0; k < j; k++) s -= A[j * n + k] * A[j * n + k];
        if (s <= 1e-300) return 0;
        s = sqrt(s);
        A[j * n + j] = s;
        for (int i = j + 1; i < n; i++) {
            double t = A[i * n + j];
            for (int k = 0; k < j; k++) t -= A[i * n + k] * A[j * n + k];
            A[i * n + j] = t / s;
        }
    }
    return 1;
}
static void chol_solve(const double *L, int n, double *b) { /* L L^T x = b, in place */
    for (int i = 0; i < n; i++) {
        double s = b[i];
        for (int k = 0; k < i; k++) s -= L[i * n + k] * b[k];
        b[i] = s / L[i * n + i];
    }
    for (int i = n - 1; i >= 0; i--) {
        double s = b[i];
        for (int k = i + 1; k < n; k++) s -= L[k * n + i] * b[k];
        b[i] = s / L[i * n + i];
    }
}

/* apply an error-state correction to the nominal state (orientation errors on the right) */
static void inject(const double *dx) {
    rot_right(R, dx + TH);
    for (int i = 0; i < 3; i++) { vel[i] += dx[V + i]; pos[i] += dx[P + i]; bg[i] += dx[BG + i]; ba[i] += dx[BA + i]; }
    rot_right(R0, dx + TH0);
    for (int c = 0; c < nclones; c++) {
        int o = CORE + 6 * c;
        rot_right(clones[c].R, dx + o);
        for (int i = 0; i < 3; i++) clones[c].p[i] += dx[o + 3 + i];
    }
}

/* EKF update with residual r (k), Jacobian H (k x D, row-major, leading dimension MAXD) and isotropic noise variance.
 * Rejected (returns 0) if r^T S^-1 r > gate. Sums run only over the columns where H is nonzero.
 * P <- P - (HP)^T S^-1 HP, written symmetrically. */
#if FAST_UPDATE
/* y[0..n) -= a x[0..n)  /  y += a x  /  y *= a: wasm SIMD, two doubles per instruction, bit-identical to scalar */
#if defined(__wasm_simd128__)
#include <wasm_simd128.h>
static inline void vsub_ax(double *restrict y, const double *restrict x, double a, int n) {
    v128_t va = wasm_f64x2_splat(a);
    int j = 0;
    for (; j + 4 <= n; j += 4) {
        v128_t y0 = wasm_v128_load(y + j), y1 = wasm_v128_load(y + j + 2);
        y0 = wasm_f64x2_sub(y0, wasm_f64x2_mul(va, wasm_v128_load(x + j)));
        y1 = wasm_f64x2_sub(y1, wasm_f64x2_mul(va, wasm_v128_load(x + j + 2)));
        wasm_v128_store(y + j, y0); wasm_v128_store(y + j + 2, y1);
    }
    for (; j < n; j++) y[j] -= a * x[j];
}
static inline void vadd_ax(double *restrict y, const double *restrict x, double a, int n) {
    v128_t va = wasm_f64x2_splat(a);
    int j = 0;
    for (; j + 4 <= n; j += 4) {
        v128_t y0 = wasm_v128_load(y + j), y1 = wasm_v128_load(y + j + 2);
        y0 = wasm_f64x2_add(y0, wasm_f64x2_mul(va, wasm_v128_load(x + j)));
        y1 = wasm_f64x2_add(y1, wasm_f64x2_mul(va, wasm_v128_load(x + j + 2)));
        wasm_v128_store(y + j, y0); wasm_v128_store(y + j + 2, y1);
    }
    for (; j < n; j++) y[j] += a * x[j];
}
static inline void fsub_ax(float *restrict y, const float *restrict x, float a, int n) {
    v128_t va = wasm_f32x4_splat(a);
    int j = 0;
    for (; j + 8 <= n; j += 8) {
        v128_t y0 = wasm_v128_load(y + j), y1 = wasm_v128_load(y + j + 4);
        y0 = wasm_f32x4_sub(y0, wasm_f32x4_mul(va, wasm_v128_load(x + j)));
        y1 = wasm_f32x4_sub(y1, wasm_f32x4_mul(va, wasm_v128_load(x + j + 4)));
        wasm_v128_store(y + j, y0); wasm_v128_store(y + j + 4, y1);
    }
    for (; j < n; j++) y[j] -= a * x[j];
}
static inline void fadd_ax(float *restrict y, const float *restrict x, float a, int n) {
    v128_t va = wasm_f32x4_splat(a);
    int j = 0;
    for (; j + 8 <= n; j += 8) {
        v128_t y0 = wasm_v128_load(y + j), y1 = wasm_v128_load(y + j + 4);
        y0 = wasm_f32x4_add(y0, wasm_f32x4_mul(va, wasm_v128_load(x + j)));
        y1 = wasm_f32x4_add(y1, wasm_f32x4_mul(va, wasm_v128_load(x + j + 4)));
        wasm_v128_store(y + j, y0); wasm_v128_store(y + j + 4, y1);
    }
    for (; j < n; j++) y[j] += a * x[j];
}
static inline void vscale(double *restrict y, double a, int n) {
    v128_t va = wasm_f64x2_splat(a);
    int j = 0;
    for (; j + 2 <= n; j += 2) wasm_v128_store(y + j, wasm_f64x2_mul(wasm_v128_load(y + j), va));
    for (; j < n; j++) y[j] *= a;
}
#else
static inline void vsub_ax(double *restrict y, const double *restrict x, double a, int n) { for (int j = 0; j < n; j++) y[j] -= a * x[j]; }
static inline void vadd_ax(double *restrict y, const double *restrict x, double a, int n) { for (int j = 0; j < n; j++) y[j] += a * x[j]; }
static inline void vscale(double *restrict y, double a, int n) { for (int j = 0; j < n; j++) y[j] *= a; }
static inline void fsub_ax(float *restrict y, const float *restrict x, float a, int n) { for (int j = 0; j < n; j++) y[j] -= a * x[j]; }
static inline void fadd_ax(float *restrict y, const float *restrict x, float a, int n) { for (int j = 0; j < n; j++) y[j] += a * x[j]; }
#endif
#endif
#if UPDATE_ROWS_MAX
/* rows of an MSCKF update not applied yet (they involve clone states only): row i over the clone columns, residual */
#define PEND_MAX (6 * (MAX_CLONES + 1))
static double pend_H[PEND_MAX][6 * (MAX_CLONES + 1)], pend_r[PEND_MAX];
static int pend_n, updated_rows_this_frame;
/* the state just moved by dx: a pending residual r = z - h(x) becomes r - H dx (linear in the clone states) */
static void pending_correct(const double *dx) {
    for (int i = 0; i < pend_n; i++) {
        double t = 0;
        for (int c = 0; c < D - CORE; c++) t += pend_H[i][c] * dx[CORE + c];
        pend_r[i] -= t;
    }
}
#else
#define pending_correct(dx) ((void)0)
#endif
#if FAST_UPDATE
/* same EKF update, loops ordered so the inner loop runs along a row of length D (vectorizable, no strided sums) */
static int update(const double *r, const double *H, int k, double noise, double gate) {
    int nz[MAXD], nnz = 0;
    for (int i = 0; i < D; i++) {
        int any = 0;
        for (int a = 0; a < k && !any; a++) any = H[a * MAXD + i] != 0;
        if (any) nz[nnz++] = i;
    }
    for (int a = 0; a < k; a++) { /* HP = H P, row by row: HP_a = sum_q H[a][q] P_q */
        double *restrict hp = HP + a * MAXD;
        const double *h = H + a * MAXD;
        memset(hp, 0, D * sizeof(double));
        for (int q = 0; q < nnz; q++) {
            double hq = h[nz[q]];
            if (hq == 0) continue;
            const double *restrict pr = Pm + nz[q] * MAXD;
            vadd_ax(hp, pr, hq, D);
        }
    }
    for (int b = 0; b < k; b++) { /* S = H P H^T + noise I, over the nonzeros of row b of H */
        const double *hb = H + b * MAXD;
        int bq[MAXD], nb = 0;
        for (int q = 0; q < nnz; q++) if (hb[nz[q]] != 0) bq[nb++] = nz[q];
        for (int a = b; a < k; a++) {
            const double *hp = HP + a * MAXD;
            double s = 0;
            for (int q = 0; q < nb; q++) s += hp[bq[q]] * hb[bq[q]];
            Sm[a * k + b] = Sm[b * k + a] = s + (a == b ? noise : 0);
        }
    }
    if (!cholesky(Sm, k)) return 0;
    /* whitened form: y = L^-1 r, W = L^-1 HP (S = L L^T); then r^T S^-1 r = |y|^2, dx = W^T y, P -= W^T W */
    double y[MAXK];
    for (int i = 0; i < k; i++) {
        double t = r[i];
        for (int m = 0; m < i; m++) t -= Sm[i * k + m] * y[m];
        y[i] = t / Sm[i * k + i];
    }
    double m2 = 0;
    for (int a = 0; a < k; a++) m2 += y[a] * y[a];
    if (m2 > gate) return 0;
#if UPDATE_F32
    /* the big products in float32 (4 lanes): W = L^-1 HP and C = W^T W; dx and P stay double */
    static float Wf[MAXK * MAXD], Cf[MAXD * MAXD];
    for (int i = 0; i < k; i++) {
        float *restrict wi = Wf + i * MAXD;
        for (int j = 0; j < D; j++) wi[j] = (float)HP[i * MAXD + j];
        for (int m = 0; m < i; m++) fsub_ax(wi, Wf + m * MAXD, (float)Sm[i * k + m], D);
        float inv = (float)(1 / Sm[i * k + i]);
        for (int j = 0; j < D; j++) wi[j] *= inv;
    }
    for (int i = 0; i < k; i++)
        for (int j = 0; j < D; j++) Kt[i * MAXD + j] = Wf[i * MAXD + j];
#else
    for (int i = 0; i < k; i++) {
        double *restrict wi = Kt + i * MAXD;
        memcpy(wi, HP + i * MAXD, D * sizeof(double));
        for (int m = 0; m < i; m++) {
            double l = Sm[i * k + m];
            const double *restrict wm = Kt + m * MAXD;
            vsub_ax(wi, wm, l, D);
        }
        double inv = 1 / Sm[i * k + i];
        vscale(wi, inv, D);
    }
#endif
    double dx[MAXD];
    memset(dx, 0, D * sizeof(double));
    for (int a = 0; a < k; a++) {
        const double *wa = Kt + a * MAXD;
        vadd_ax(dx, wa, y[a], D);
    }
#if UPDATE_F32
    for (int i = 0; i < D; i++) memset(Cf + i * MAXD + i, 0, (D - i) * sizeof(float));
    for (int a = 0; a < k; a++) {
        const float *restrict wa = Wf + a * MAXD;
        for (int i = 0; i < D; i++) {
            float h = wa[i];
            if (h == 0) continue;
            fadd_ax(Cf + i * MAXD + i, wa + i, h, D - i);
        }
    }
    for (int i = 0; i < D; i++) {
        double *restrict pi = Pm + i * MAXD;
        const float *ci = Cf + i * MAXD;
        for (int j = i; j < D; j++) pi[j] -= ci[j];
    }
#else
    for (int a = 0; a < k; a++) {
        const double *restrict wa = Kt + a * MAXD;
        for (int i = 0; i < D; i++) {
            double h = wa[i];
            if (h == 0) continue;
            double *restrict pi = Pm + i * MAXD;
            vsub_ax(pi + i, wa + i, h, D - i);
        }
    }
#endif
    for (int i = 0; i < D; i++)
        for (int j = i + 1; j < D; j++) Pm[j * MAXD + i] = Pm[i * MAXD + j];
    pending_correct(dx);
    inject(dx);
    return 1;
}
#else
static int update(const double *r, const double *H, int k, double noise, double gate) {
    int nz[MAXD], nnz = 0;
    for (int i = 0; i < D; i++) {
        int any = 0;
        for (int a = 0; a < k && !any; a++) any = H[a * MAXD + i] != 0;
        if (any) nz[nnz++] = i;
    }
    for (int a = 0; a < k; a++) /* HP = H P */
        for (int j = 0; j < D; j++) {
            double s = 0;
            const double *h = H + a * MAXD;
            for (int q = 0; q < nnz; q++) s += h[nz[q]] * Pm[nz[q] * MAXD + j];
            HP[a * MAXD + j] = s;
        }
    for (int a = 0; a < k; a++) /* S = H P H^T + noise I */
        for (int b = 0; b <= a; b++) {
            double s = 0;
            for (int q = 0; q < nnz; q++) s += HP[a * MAXD + nz[q]] * H[b * MAXD + nz[q]];
            Sm[a * k + b] = Sm[b * k + a] = s + (a == b ? noise : 0);
        }
    if (!cholesky(Sm, k)) return 0;
    double y[MAXK];
    memcpy(y, r, k * sizeof(double));
    chol_solve(Sm, k, y); /* y = S^-1 r */
    double m2 = 0;
    for (int a = 0; a < k; a++) m2 += r[a] * y[a];
    if (m2 > gate) return 0;
    double col[MAXK];
    for (int j = 0; j < D; j++) { /* Kt = S^-1 HP (the transposed gain), column by column */
        for (int a = 0; a < k; a++) col[a] = HP[a * MAXD + j];
        chol_solve(Sm, k, col);
        for (int a = 0; a < k; a++) Kt[a * MAXD + j] = col[a];
    }
    double dx[MAXD];
    for (int j = 0; j < D; j++) {
        double s = 0;
        for (int a = 0; a < k; a++) s += Kt[a * MAXD + j] * r[a];
        dx[j] = s;
    }
    for (int i = 0; i < D; i++)
        for (int j = i; j < D; j++) {
            double s = 0;
            for (int a = 0; a < k; a++) s += HP[a * MAXD + i] * Kt[a * MAXD + j];
            double v = Pm[i * MAXD + j] - s;
            Pm[i * MAXD + j] = Pm[j * MAXD + i] = v;
        }
    inject(dx);
    return 1;
}
#endif

/* =====================================================================================================================
 * IMU: initialization, propagation, pseudo-measurements
 * ===================================================================================================================== */

static void set_block(int r, int c, const double *b, double scale) {
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) Pm[(r + i) * MAXD + c + j] = scale * b[3 * i + j];
}

/* frame 0: roll/pitch from the mean specific force (exact at hover; for a quadrotor in flight it points along the
   thrust axis, hence the tilt uncertainty), zero velocity with a wide prior, biases at their GP prior */
static void initialize(const double *imu, int count, double t) {
    double f[3] = {0, 0, 0};
    for (int r = 0; r < count; r++)
        for (int i = 0; i < 3; i++) f[i] += imu[7 * r + 1 + i] / count;
    align_to_z(f, R);
    memcpy(R0, R, sizeof R);
    memset(vel, 0, sizeof vel); memset(pos, 0, sizeof pos);
    memset(bg, 0, sizeof bg); memset(ba, 0, sizeof ba);
    memset(Pm, 0, sizeof Pm);
    D = CORE;
    double tilt[9] = {INIT_TILT_STD * INIT_TILT_STD, 0, 0, 0, INIT_TILT_STD * INIT_TILT_STD, 0, 0, 0, 0}; /* yaw: gauge */
    set_block(TH, TH, tilt, 1); set_block(TH, TH0, tilt, 1); set_block(TH0, TH, tilt, 1); set_block(TH0, TH0, tilt, 1);
    set_block(V, V, I3, INIT_VELOCITY_STD * INIT_VELOCITY_STD);
    set_block(BG, BG, I3, GYRO_BIAS_MAX * GYRO_BIAS_MAX / 3);
    set_block(BA, BA, I3, ACCEL_BIAS_MAX * ACCEL_BIAS_MAX / 3);
    for (int i = 0; i < 3; i++) omega[i] = imu[7 * (count - 1) + 4 + i];
    last_t = t;
}

/* one IMU sample [t, ax, ay, az, gx, gy, gz]: nominal strapdown + covariance P <- F P F^T + Q.
 * F = I except   TH<-TH = dR^T, TH<-BG = -dt I, V<-TH = -dt R [a]x, V<-BA = -dt R, P<-V = dt I,
 * so F P F^T is a row pass then a column pass over the TH, V, P blocks only (clones are untouched by F). */
static void propagate(const double *row) {
    double dt = row[0] - last_t;
    if (dt <= 0) return;
    last_t = row[0];
    const double dt_sample = dt;
    (void)dt_sample;
    double w[3], a[3], wdt[3], dR[9], dRt[9], Ra[3], acc[3], sk[9], Rsk[9], Ms[9];
    for (int i = 0; i < 3; i++) { w[i] = row[4 + i] - bg[i]; a[i] = row[1 + i] - ba[i]; omega[i] = w[i]; wdt[i] = w[i] * dt; }
    exp_so3(wdt, dR);
    m3vec(R, a, Ra);
    acc[0] = Ra[0]; acc[1] = Ra[1]; acc[2] = Ra[2] - GRAVITY;
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) dRt[3 * i + j] = dR[3 * j + i];
    skew(a, sk);
    m3mul(R, sk, Rsk);
    for (int i = 0; i < 9; i++) Ms[i] = -dt * Rsk[i];
#if PROP_EVERY > 1
    { /* covariance: one step over the accumulated interval, linearized at this sample */
        static int nacc; static double dtacc, dRacc[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};
        double t9[9];
        m3mul(dRacc, dR, t9); memcpy(dRacc, t9, sizeof t9);
        dtacc += dt;
        if (++nacc < PROP_EVERY) goto nominal;
        dt = dtacc;
        for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) dRt[3 * i + j] = dRacc[3 * j + i];
        for (int i = 0; i < 9; i++) Ms[i] = -dt * Rsk[i];
        nacc = 0; dtacc = 0;
        memcpy(dRacc, I3, sizeof dRacc);
    }
#endif
    for (int pass = 0; pass < 2; pass++) { /* pass 0: rows (F P), pass 1: columns ((F P) F^T) */
        int rs = pass == 0 ? MAXD : 1, cs = pass == 0 ? 1 : MAXD;
        for (int c = 0; c < D; c++) {
            double th[3], v[3], p[3], gb[3], ab[3];
            for (int i = 0; i < 3; i++) {
                th[i] = Pm[(TH + i) * rs + c * cs]; v[i] = Pm[(V + i) * rs + c * cs]; p[i] = Pm[(P + i) * rs + c * cs];
                gb[i] = Pm[(BG + i) * rs + c * cs]; ab[i] = Pm[(BA + i) * rs + c * cs];
            }
            for (int i = 0; i < 3; i++) {
                Pm[(TH + i) * rs + c * cs] = dRt[3 * i] * th[0] + dRt[3 * i + 1] * th[1] + dRt[3 * i + 2] * th[2] - dt * gb[i];
                Pm[(V + i) * rs + c * cs] = v[i] + Ms[3 * i] * th[0] + Ms[3 * i + 1] * th[1] + Ms[3 * i + 2] * th[2]
                                             - dt * (R[3 * i] * ab[0] + R[3 * i + 1] * ab[1] + R[3 * i + 2] * ab[2]);
                Pm[(P + i) * rs + c * cs] = p[i] + dt * v[i];
            }
        }
    }
    /* Q: white noise on orientation and velocity; the GP bias kernels' random-walk increments */
    double q_th = (GYRO_NOISE * dt) * (GYRO_NOISE * dt), q_v = (ACCEL_NOISE * dt) * (ACCEL_NOISE * dt);
    double q_bg = GYRO_BIAS_WALK * GYRO_BIAS_WALK * dt, q_ba = ACCEL_BIAS_WALK * ACCEL_BIAS_WALK * dt;
    for (int i = 0; i < 3; i++) {
        Pm[(TH + i) * MAXD + TH + i] += q_th; Pm[(V + i) * MAXD + V + i] += q_v;
        Pm[(BG + i) * MAXD + BG + i] += q_bg; Pm[(BA + i) * MAXD + BA + i] += q_ba;
    }
#if PROP_EVERY > 1
nominal:
    dt = dt_sample;
#endif
    for (int i = 0; i < 3; i++) { pos[i] += vel[i] * dt + 0.5 * acc[i] * dt * dt; vel[i] += acc[i] * dt; }
    double Rn[9];
    m3mul(R, dR, Rn);
    memcpy(R, Rn, sizeof R);
}

static double Hs[3 * MAXD]; /* Jacobian rows of the small updates */

/* per frame: thrust model (frame-mean body x/y specific force = b_a,x/y), then the velocity prior */
static void imu_measurements(const double *imu, int n) {
    double mean[2] = {0, 0}, r[3];
    for (int k = 0; k < n; k++) { mean[0] += imu[7 * k + 1] / n; mean[1] += imu[7 * k + 2] / n; }
    memset(Hs, 0, sizeof Hs);
    Hs[BA] = 1; Hs[MAXD + BA + 1] = 1;
    r[0] = mean[0] - ba[0]; r[1] = mean[1] - ba[1];
    update(r, Hs, 2, ACCEL_NOISE * ACCEL_NOISE / n + THRUST_MODEL_STD * THRUST_MODEL_STD, THRUST_GATE);
    double std = SPEED_STD * sqrt(SPEED_TAU / FRAME_DT);
    memset(Hs, 0, sizeof Hs);
    for (int i = 0; i < 3; i++) { Hs[i * MAXD + V + i] = 1; r[i] = -vel[i]; }
    update(r, Hs, 3, std * std, INFINITY);
}

/* =====================================================================================================================
 * Clones
 * ===================================================================================================================== */

/* clone the current IMU pose: the new block copies the TH and P rows/columns (J = [I on dtheta; I on dp]) */
static void add_clone(void) {
    int d = D;
    for (int j = 0; j < d; j++)
        for (int i = 0; i < 3; i++) {
            Pm[(d + i) * MAXD + j] = Pm[(TH + i) * MAXD + j];
            Pm[(d + 3 + i) * MAXD + j] = Pm[(P + i) * MAXD + j];
        }
    for (int i = 0; i < 6; i++) {
        for (int j = 0; j < d; j++) Pm[j * MAXD + d + i] = Pm[(d + i) * MAXD + j];
        int src_i = i < 3 ? TH + i : P + i - 3;
        for (int j = 0; j < 6; j++) {
            int src_j = j < 3 ? TH + j : P + j - 3;
            Pm[(d + i) * MAXD + d + j] = Pm[src_i * MAXD + src_j];
        }
    }
    D += 6;
    clones[nclones].id = clone_counter++;
    memcpy(clones[nclones].R, R, sizeof R);
    memcpy(clones[nclones].p, pos, sizeof pos);
    nclones++;
}

/* marginalize the oldest clone: drop its 6 rows and columns (in place, reading only ahead of the writes) */
#if UPDATE_ROWS_MAX
static double Hpend_rows[PEND_MAX * MAXD];
/* apply pending rows: those touching the oldest clone (oldest_only) or up to `limit` rows from the front */
static void apply_pending(int oldest_only, int limit) {
    int n = 0;
    while (n < pend_n && n < limit) {
        if (oldest_only) {
            int touches = 0;
            for (int c = 0; c < 6; c++) touches |= pend_H[n][c] != 0;
            if (!touches) break;
        }
        n++;
    }
    if (!n) return;
    int nc = D - CORE;
    double rr_[PEND_MAX];
    for (int r = 0; r < n; r++) {
        double *row = Hpend_rows + r * MAXD;
        memset(row, 0, D * sizeof(double));
        memcpy(row + CORE, pend_H[r], nc * sizeof(double));
        rr_[r] = pend_r[r];
    }
    /* drop them from the queue first: update() corrects the residuals of what stays pending */
    memmove(pend_H[0], pend_H[n], (pend_n - n) * sizeof(pend_H[0]));
    memmove(pend_r, pend_r + n, (pend_n - n) * sizeof(double));
    pend_n -= n;
    update(rr_, Hpend_rows, n, (PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY);
}
#endif
static void remove_oldest_clone(void) {
#if UPDATE_ROWS_MAX
    apply_pending(1, PEND_MAX);
    for (int r = 0; r < pend_n; r++) { /* the remaining rows do not involve the oldest clone: shift the columns */
        memmove(pend_H[r], pend_H[r] + 6, (D - CORE - 6) * sizeof(double));
        for (int c = D - CORE - 6; c < 6 * (MAX_CLONES + 1); c++) pend_H[r][c] = 0;
    }
#endif
    int newD = D - 6;
    for (int i = 0; i < newD; i++) {
        int si = i < CORE ? i : i + 6;
        for (int j = 0; j < newD; j++) {
            int sj = j < CORE ? j : j + 6;
            Pm[i * MAXD + j] = Pm[si * MAXD + sj];
        }
    }
    D = newD;
    memmove(clones, clones + 1, (nclones - 1) * sizeof(Clone));
    nclones--;
}

static int clone_index(int id) {
    for (int c = 0; c < nclones; c++) if (clones[c].id == id) return c;
    return -1;
}

static void camera_pose(const Clone *c, double *Rwc, double *pwc) { /* camera pose of a clone in the world */
    double t[3];
    m3mul(c->R, R_bc, Rwc);
    m3vec(c->R, p_bc, t);
    for (int i = 0; i < 3; i++) pwc[i] = c->p[i] + t[i];
}

/* =====================================================================================================================
 * MSCKF feature update
 * ===================================================================================================================== */

static double chi2_quantile(int dof) { /* Wilson-Hilferty */
    double a = 2.0 / (9.0 * dof), b = 1 - a + CHI2_Z * sqrt(a);
    return dof * b * b * b;
}

/* feature position from its clone observations: linear (sum of ray-orthogonal projectors), then 3 Gauss-Newton steps
   on the reprojection error; rejected if the rays are ~parallel or a depth is outside [MIN_DEPTH, MAX_DEPTH] */
static int triangulate(const Obs *o, const int *ci, double *pf) {
    double A[9] = {0}, b[3] = {0}, Rwc[MAX_OBS][9], pwc[MAX_OBS][3];
    for (int k = 0; k < o->n; k++) {
        camera_pose(&clones[ci[k]], Rwc[k], pwc[k]);
        double u[3] = {o->x[k], o->y[k], 1.0}, d[3];
        m3vec(Rwc[k], u, d);
        double n = sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
        for (int i = 0; i < 3; i++) d[i] /= n;
        for (int i = 0; i < 3; i++)
            for (int j = 0; j < 3; j++) {
                double m = (i == j) - d[i] * d[j];
                A[3 * i + j] += m;
                b[i] += m * pwc[k][j];
            }
    }
    double lmin, lmax;
    sym3_eig_minmax(A, &lmin, &lmax);
    if (lmin < TRI_MIN_EIG * lmax) return 0;
    if (!solve3(A, b, pf)) return 0;
    for (int it = 0; it < 3; it++) {
        double JtJ[9] = {0}, Jtr[3] = {0};
        for (int k = 0; k < o->n; k++) {
            double dpt[3] = {pf[0] - pwc[k][0], pf[1] - pwc[k][1], pf[2] - pwc[k][2]}, pc[3];
            m3tvec(Rwc[k], dpt, pc);
            if (pc[2] < 1e-3) return 0;
            double iz = 1 / pc[2], J[6]; /* J = Jpi Rwc^T, Jpi = d(projection)/d(point in camera) */
            double jp[6] = {iz, 0, -pc[0] * iz * iz, 0, iz, -pc[1] * iz * iz};
            for (int r = 0; r < 2; r++)
                for (int c = 0; c < 3; c++)
                    J[3 * r + c] = jp[3 * r] * Rwc[k][3 * c] + jp[3 * r + 1] * Rwc[k][3 * c + 1] + jp[3 * r + 2] * Rwc[k][3 * c + 2];
            double res[2] = {o->x[k] - pc[0] * iz, o->y[k] - pc[1] * iz};
            for (int i = 0; i < 3; i++) {
                for (int j = 0; j < 3; j++) JtJ[3 * i + j] += J[i] * J[j] + J[3 + i] * J[3 + j];
                Jtr[i] += J[i] * res[0] + J[3 + i] * res[1];
            }
        }
        for (int i = 0; i < 3; i++) JtJ[4 * i] += 1e-9;
        double step[3];
        if (!solve3(JtJ, Jtr, step)) return 0;
        for (int i = 0; i < 3; i++) pf[i] += step[i];
    }
    for (int k = 0; k < o->n; k++) {
        double dpt[3] = {pf[0] - pwc[k][0], pf[1] - pwc[k][1], pf[2] - pwc[k][2]}, pc[3];
        m3tvec(Rwc[k], dpt, pc);
        if (!(pc[2] > MIN_DEPTH && pc[2] < MAX_DEPTH)) return 0;
    }
    return 1;
}

#define MAX_ROWS (MAX_BATCH * (2 * MAX_OBS - 3))
static double Hbig[MAX_ROWS * MAXD], rbig[MAX_ROWS]; /* stacked rows of one update */
static double Hx[2 * MAX_OBS * MAXD], rr[2 * MAX_OBS], Hf[2 * MAX_OBS * 3];
static double H0P[(2 * MAX_OBS) * MAXD];
#define NCMAX (MAXD - CORE)
static double Ainf[NCMAX * NCMAX], binf[NCMAX]; /* COMPRESS_INFO: lower triangle of sum H^T H, and sum H^T r (clone columns) */

/* Rows of one feature, appended to Hbig at *nrows if it passes the gate. For each observation in clone c:
 *   residual  z - pi(R_wc^T (p_f - p_wc))
 *   d/d dtheta_c = Jpi R_bc^T [R_c^T (p_f - p_c)]x,   d/d dp_c = -Jpi R_bc^T R_c^T,   d/d p_f = Jpi R_bc^T R_c^T.
 * The feature position is removed by projecting onto the left null space of d/d p_f (3 Householder reflections on
 * [Hf | Hx | r], keeping rows 3..2m-1), so the feature never enters the state. Gate: chi^2 at CHI2_Z. */
static int feature_rows(const Obs *o_in, int *nrows) {
    Obs o = {0};
    int ci[MAX_OBS];
    for (int k = 0; k < o_in->n; k++) { /* keep the observations whose clone is still in the window */
        int c = clone_index(o_in->cid[k]);
        if (c < 0) continue;
        ci[o.n] = c; o.cid[o.n] = o_in->cid[k]; o.x[o.n] = o_in->x[k]; o.y[o.n] = o_in->y[k]; o.n++;
    }
    if (o.n < MIN_OBS) return 0;
    double pf[3];
    if (!triangulate(&o, ci, pf)) return 0;
    int m = 2 * o.n;
    double RbcT[9];
    m3tmul(R_bc, I3, RbcT); /* R_bc^T */
    memset(Hx, 0, m * MAXD * sizeof(double));
    for (int k = 0; k < o.n; k++) {
        const Clone *c = &clones[ci[k]];
        double Rwc[9], pwc[3], dpt[3], pc[3], u[3], tmp[3];
        camera_pose(c, Rwc, pwc);
        for (int i = 0; i < 3; i++) dpt[i] = pf[i] - pwc[i];
        m3tvec(Rwc, dpt, pc);
        double iz = 1 / pc[2];
        double jp[6] = {iz, 0, -pc[0] * iz * iz, 0, iz, -pc[1] * iz * iz};
        rr[2 * k] = o.x[k] - pc[0] * iz;
        rr[2 * k + 1] = o.y[k] - pc[1] * iz;
        for (int i = 0; i < 3; i++) tmp[i] = pf[i] - c->p[i];
        m3tvec(c->R, tmp, u); /* the feature in the clone's body frame */
        double A[6], sku[9]; /* A = Jpi R_bc^T (2x3) */
        for (int r2 = 0; r2 < 2; r2++)
            for (int cc = 0; cc < 3; cc++) A[3 * r2 + cc] = jp[3 * r2] * RbcT[cc] + jp[3 * r2 + 1] * RbcT[3 + cc] + jp[3 * r2 + 2] * RbcT[6 + cc];
        skew(u, sku);
        int off = CORE + 6 * ci[k];
        for (int r2 = 0; r2 < 2; r2++)
            for (int cc = 0; cc < 3; cc++) {
                double s_th = 0, s_p = 0;
                for (int t = 0; t < 3; t++) {
                    s_th += A[3 * r2 + t] * sku[3 * t + cc];
                    s_p += A[3 * r2 + t] * c->R[3 * cc + t]; /* (A R_c^T)[r2][cc] */
                }
                Hx[(2 * k + r2) * MAXD + off + cc] = s_th;
                Hx[(2 * k + r2) * MAXD + off + 3 + cc] = -s_p;
                Hf[(2 * k + r2) * 3 + cc] = s_p;
            }
    }
    for (int c = 0; c < 3; c++) { /* left null space of Hf */
        double norm = 0, v[2 * MAX_OBS];
        for (int i = c; i < m; i++) norm += Hf[i * 3 + c] * Hf[i * 3 + c];
        norm = sqrt(norm);
        if (norm < 1e-14) continue;
        double alpha = Hf[c * 3 + c] > 0 ? -norm : norm, vn = 0;
        for (int i = c; i < m; i++) v[i] = Hf[i * 3 + c];
        v[c] -= alpha;
        for (int i = c; i < m; i++) vn += v[i] * v[i];
        if (vn < 1e-30) continue;
        for (int j = c; j < 3; j++) {
            double s = 0;
            for (int i = c; i < m; i++) s += v[i] * Hf[i * 3 + j];
            s *= 2 / vn;
            for (int i = c; i < m; i++) Hf[i * 3 + j] -= s * v[i];
        }
        for (int j = 0; j < D; j++) {
            double s = 0;
            for (int i = c; i < m; i++) s += v[i] * Hx[i * MAXD + j];
            if (s == 0) continue;
            s *= 2 / vn;
            for (int i = c; i < m; i++) Hx[i * MAXD + j] -= s * v[i];
        }
        double s = 0;
        for (int i = c; i < m; i++) s += v[i] * rr[i];
        s *= 2 / vn;
        for (int i = c; i < m; i++) rr[i] -= s * v[i];
    }
    int k0 = m - 3;
    const double *H0 = Hx + 3 * MAXD, *r0 = rr + 3;
    /* gate on r0^T (H0 P H0^T + s^2 I)^-1 r0, over the observing clones' columns only (H0 is zero elsewhere) */
    double sigma2 = (PIXEL_STD / fx) * (PIXEL_STD / fx);
    int nzc[6 * MAX_OBS], nnz = 0, seen[MAX_CLONES + 1] = {0};
    for (int k = 0; k < o.n; k++)
        if (!seen[ci[k]]) {
            seen[ci[k]] = 1;
            for (int q = 0; q < 6; q++) nzc[nnz++] = CORE + 6 * ci[k] + q;
        }
#if PROF == 6
    nnz = 0; /* fuel profiling: skip the gate's covariance */
#endif
    for (int a = 0; a < k0; a++)
        for (int jj = 0; jj < nnz; jj++) {
            int j = nzc[jj];
            double s = 0;
            for (int q = 0; q < nnz; q++) s += H0[a * MAXD + nzc[q]] * Pm[nzc[q] * MAXD + j];
            H0P[a * MAXD + j] = s;
        }
    for (int a = 0; a < k0; a++)
        for (int b = 0; b <= a; b++) {
            double s = 0;
            for (int q = 0; q < nnz; q++) s += H0P[a * MAXD + nzc[q]] * H0[b * MAXD + nzc[q]];
            Sm[a * k0 + b] = Sm[b * k0 + a] = s + (a == b ? sigma2 : 0);
        }
#if PROF == 6
    if (*nrows + k0 > MAX_ROWS) return 0;
    for (int a = 0; a < k0; a++) { memcpy(Hbig + (*nrows + a) * MAXD, H0 + a * MAXD, D * sizeof(double)); rbig[*nrows + a] = r0[a]; }
    *nrows += k0; return 1;
#endif
    if (!cholesky(Sm, k0)) return 0;
    double y[2 * MAX_OBS];
    memcpy(y, r0, k0 * sizeof(double));
    chol_solve(Sm, k0, y);
    double m2 = 0;
    for (int a = 0; a < k0; a++) m2 += r0[a] * y[a];
    if (m2 > chi2_quantile(k0)) return 0;
#if COMPRESS_INFO
    /* add this feature's H0^T H0 and H0^T r0 (its clones' columns only) to the batch information */
    for (int a = 0; a < k0; a++) {
        const double *h = H0 + a * MAXD;
        for (int ii = 0; ii < nnz; ii++) {
            double hi = h[nzc[ii]];
            if (hi == 0) continue;
            int gi = nzc[ii] - CORE;
            double *ai = Ainf + gi * NCMAX;
            for (int jj = 0; jj < nnz; jj++) {
                int gj = nzc[jj] - CORE;
                if (gj <= gi) ai[gj] += hi * h[nzc[jj]]; /* lower triangle (gi >= gj) */
            }
            binf[gi] += hi * r0[a];
        }
    }
    *nrows += k0;
    return 1;
#else
    if (*nrows + k0 > MAX_ROWS) return 0;
    for (int a = 0; a < k0; a++) {
        memcpy(Hbig + (*nrows + a) * MAXD, H0 + a * MAXD, D * sizeof(double));
        rbig[*nrows + a] = r0[a];
    }
    *nrows += k0;
    return 1;
#endif
}

#if FAST_FROWS && COMPRESS_INFO
/* FAST_FROWS: the same feature residual, gate and information as feature_rows, from compact 2x6 Jacobian blocks:
 *   gate S = (Q B Q^T)[3:, 3:] + s^2 I with B = Hx P Hx^T built from the observing clones 6x6 covariance blocks;
 *   information H0^T H0 = Hx^T Hx - H3^T H3 and H0^T r0 = Hx^T r - H3^T r3 (Q orthogonal; H3 = first 3 rows of Q Hx). */
static int feature_rows_fast(const Obs *o_in, int *nrows) {
    WL(w_feats++);
    Obs o = {0};
    int ci[MAX_OBS];
    for (int k = 0; k < o_in->n; k++) {
        int c = clone_index(o_in->cid[k]);
        if (c < 0) continue;
        ci[o.n] = c; o.cid[o.n] = o_in->cid[k]; o.x[o.n] = o_in->x[k]; o.y[o.n] = o_in->y[k]; o.n++;
    }
    if (o.n < MIN_OBS) return 0;
    double pf[3];
    if (!triangulate(&o, ci, pf)) return 0;
    const int n = o.n, m = 2 * n;
    double RbcT[9];
    m3tmul(R_bc, I3, RbcT);
    double Hk[MAX_OBS][2][6], hf[2 * MAX_OBS][3], rv[2 * MAX_OBS], rv0[2 * MAX_OBS];
    for (int k = 0; k < n; k++) {
        const Clone *c = &clones[ci[k]];
        double Rwc[9], pwc[3], dpt[3], pc[3], u[3], tmp[3];
        camera_pose(c, Rwc, pwc);
        for (int i = 0; i < 3; i++) dpt[i] = pf[i] - pwc[i];
        m3tvec(Rwc, dpt, pc);
        double iz = 1 / pc[2];
        double jp[6] = {iz, 0, -pc[0] * iz * iz, 0, iz, -pc[1] * iz * iz};
        rv[2 * k] = o.x[k] - pc[0] * iz;
        rv[2 * k + 1] = o.y[k] - pc[1] * iz;
        for (int i = 0; i < 3; i++) tmp[i] = pf[i] - c->p[i];
        m3tvec(c->R, tmp, u);
        double A[6], sku[9];
        for (int r2 = 0; r2 < 2; r2++)
            for (int cc = 0; cc < 3; cc++) A[3 * r2 + cc] = jp[3 * r2] * RbcT[cc] + jp[3 * r2 + 1] * RbcT[3 + cc] + jp[3 * r2 + 2] * RbcT[6 + cc];
        skew(u, sku);
        for (int r2 = 0; r2 < 2; r2++)
            for (int cc = 0; cc < 3; cc++) {
                double s_th = 0, s_p = 0;
                for (int t = 0; t < 3; t++) {
                    s_th += A[3 * r2 + t] * sku[3 * t + cc];
                    s_p += A[3 * r2 + t] * c->R[3 * cc + t];
                }
                Hk[k][r2][cc] = s_th;
                Hk[k][r2][3 + cc] = -s_p;
                hf[2 * k + r2][cc] = s_p;
            }
    }
    memcpy(rv0, rv, m * sizeof(double));
    /* B = Hx P Hx^T: 2x2 blocks Hk P_kl Hl^T */
    static double B[2 * MAX_OBS][2 * MAX_OBS];
    for (int k = 0; k < n && !CHEAP_GATE; k++) {
        const int ok = CORE + 6 * ci[k];
        for (int l = 0; l <= k; l++) {
            const int ol = CORE + 6 * ci[l];
            double T[2][6];
            for (int r2 = 0; r2 < 2; r2++)
                for (int j = 0; j < 6; j++) {
                    double s = 0;
                    for (int i = 0; i < 6; i++) s += Hk[k][r2][i] * Pm[(ok + i) * MAXD + ol + j];
                    T[r2][j] = s;
                }
            for (int r2 = 0; r2 < 2; r2++)
                for (int s2 = 0; s2 < 2; s2++) {
                    double s = 0;
                    for (int j = 0; j < 6; j++) s += T[r2][j] * Hk[l][s2][j];
                    B[2 * k + r2][2 * l + s2] = s;
                    B[2 * l + s2][2 * k + r2] = s;
                }
        }
    }
    /* Householder reflections annihilating hf (the left null space), applied to r and to B on both sides */
    double vs[3][2 * MAX_OBS], vns[3];
    int used[3] = {0, 0, 0};
    for (int c = 0; c < 3; c++) {
        double norm = 0, *v = vs[c];
        for (int i = c; i < m; i++) norm += hf[i][c] * hf[i][c];
        norm = sqrt(norm);
        if (norm < 1e-14) continue;
        double alpha = hf[c][c] > 0 ? -norm : norm, vn = 0;
        for (int i = 0; i < c; i++) v[i] = 0;
        for (int i = c; i < m; i++) v[i] = hf[i][c];
        v[c] -= alpha;
        for (int i = c; i < m; i++) vn += v[i] * v[i];
        if (vn < 1e-30) continue;
        used[c] = 1; vns[c] = vn;
        for (int j = c; j < 3; j++) {
            double s = 0;
            for (int i = c; i < m; i++) s += v[i] * hf[i][j];
            s *= 2 / vn;
            for (int i = c; i < m; i++) hf[i][j] -= s * v[i];
        }
        double s = 0;
        for (int i = c; i < m; i++) s += v[i] * rv[i];
        s *= 2 / vn;
        for (int i = c; i < m; i++) rv[i] -= s * v[i];
        for (int j = 0; j < m && !CHEAP_GATE; j++) { /* rows: B <- R B */
            double t = 0;
            for (int i = c; i < m; i++) t += v[i] * B[i][j];
            t *= 2 / vn;
            for (int i = c; i < m; i++) B[i][j] -= t * v[i];
        }
        for (int i = 0; i < m && !CHEAP_GATE; i++) { /* columns: B <- B R */
            double t = 0;
            for (int j = c; j < m; j++) t += B[i][j] * v[j];
            t *= 2 / vn;
            for (int j = c; j < m; j++) B[i][j] -= t * v[j];
        }
    }
    const int k0 = m - 3;
    const double *r0 = rv + 3;
    double sigma2 = (PIXEL_STD / fx) * (PIXEL_STD / fx);
#if CHEAP_GATE
    { /* outlier test on the null-space residual against pixel noise x CHEAP_GATE (no state covariance) */
        double e2 = 0;
        for (int a = 0; a < k0; a++) e2 += r0[a] * r0[a];
        if (e2 / sigma2 > CHEAP_GATE * chi2_quantile(k0)) return 0;
    }
#else
    for (int a = 0; a < k0; a++)
        for (int b = 0; b <= a; b++) Sm[a * k0 + b] = Sm[b * k0 + a] = B[3 + a][3 + b] + (a == b ? sigma2 : 0);
    if (!cholesky(Sm, k0)) return 0;
    double y[2 * MAX_OBS];
    memcpy(y, r0, k0 * sizeof(double));
    chol_solve(Sm, k0, y);
    double m2 = 0;
    for (int a = 0; a < k0; a++) m2 += r0[a] * y[a];
    if (m2 > chi2_quantile(k0)) return 0;
#endif
    /* information: + Hx^T Hx (block diagonal: one observation per clone) and Hx^T r */
    for (int k = 0; k < n; k++) {
        const int g = 6 * ci[k];
        for (int i = 0; i < 6; i++) {
            double *ai = Ainf + (g + i) * NCMAX + g;
            for (int j = 0; j <= i; j++) ai[j] += Hk[k][0][i] * Hk[k][0][j] + Hk[k][1][i] * Hk[k][1][j];
            binf[g + i] += Hk[k][0][i] * rv0[2 * k] + Hk[k][1][i] * rv0[2 * k + 1];
        }
    }
    /* - H3^T H3 and - H3^T r3: row i of Q Hx is w_i^T Hx with w_i = Q^T e_i (reflections in reverse order) */
    double H3[3][6 * MAX_OBS];
    for (int i = 0; i < 3; i++) {
        double w[2 * MAX_OBS];
        for (int a = 0; a < m; a++) w[a] = a == i;
        for (int c = 2; c >= 0; c--) {
            if (!used[c]) continue;
            double s = 0;
            for (int a = c; a < m; a++) s += vs[c][a] * w[a];
            s *= 2 / vns[c];
            for (int a = c; a < m; a++) w[a] -= s * vs[c][a];
        }
        for (int k = 0; k < n; k++)
            for (int j = 0; j < 6; j++) H3[i][6 * k + j] = w[2 * k] * Hk[k][0][j] + w[2 * k + 1] * Hk[k][1][j];
    }
    for (int p = 0; p < 6 * n; p++) {
        const int gp = 6 * ci[p / 6] + p % 6;
        for (int q = 0; q < 6 * n; q++) {
            const int gq = 6 * ci[q / 6] + q % 6;
            if (gq > gp) continue;
            Ainf[gp * NCMAX + gq] -= H3[0][p] * H3[0][q] + H3[1][p] * H3[1][q] + H3[2][p] * H3[2][q];
        }
        binf[gp] -= H3[0][p] * rv[0] + H3[1][p] * rv[1] + H3[2][p] * rv[2];
    }
    *nrows += k0;
    WL(w_ok++);
    return 1;
}
#define feature_rows feature_rows_fast
#endif

/* one EKF update for a batch of features. The stacked rows are zero on the 18 core columns, so a stack taller than
   the clone columns is QR-compressed (Householder on [H | r]) over those columns only: same information, fewer rows */
static void msckf_update(Obs *batch, int nbatch) {
    int nrows = 0;
#if COMPRESS_INFO
    int nc = D - CORE;
    for (int i = 0; i < nc; i++) { memset(Ainf + i * NCMAX, 0, nc * sizeof(double)); binf[i] = 0; }
#if PROF == 9
    return;
#endif
    { TSTART(fr); for (int b = 0; b < nbatch; b++) feature_rows(&batch[b], &nrows); TSTOP(fr, T_FROWS); }
#if UPDATE_ROWS_MAX
    for (int r = 0; r < pend_n; r++) { /* fold the pending rows back in: + h^T h, + h^T r */
        const double *h = pend_H[r];
        for (int i = 0; i < nc; i++) {
            if (h[i] == 0) continue;
            double *ai = Ainf + i * NCMAX;
            for (int j = 0; j <= i; j++) ai[j] += h[i] * h[j];
            binf[i] += h[i] * pend_r[r];
        }
        nrows++;
    }
    pend_n = 0;
#endif
    if (!nrows) return;
    /* Cholesky A = L L^T (skipping directions without information); rows L^T and residual L^-1 b carry the same
       information as the QR-compressed stack (R^T R = H^T H, Q^T r = R^-T H^T r) */
    double maxd = 0;
    for (int i = 0; i < nc; i++) if (Ainf[i * NCMAX + i] > maxd) maxd = Ainf[i * NCMAX + i];
    if (maxd <= 0) return;
    int keep[NCMAX];
    for (int j = 0; j < nc; j++) {
        double *aj = Ainf + j * NCMAX;
        double d = aj[j];
        for (int m = 0; m < j; m++) d -= aj[m] * aj[m];
        if (d <= 1e-10 * maxd) { /* no information left in this direction */
            keep[j] = 0;
            for (int i = j; i < nc; i++) Ainf[i * NCMAX + j] = 0;
            continue;
        }
        keep[j] = 1;
        d = sqrt(d);
        aj[j] = d;
        for (int i = j + 1; i < nc; i++) {
            double *ai = Ainf + i * NCMAX;
            double t = ai[j];
            for (int m = 0; m < j; m++) t -= ai[m] * aj[m];
            ai[j] = t / d;
        }
    }
    double yb[NCMAX];
    for (int i = 0; i < nc; i++) { /* y = L^-1 b over the kept pivots */
        if (!keep[i]) { yb[i] = 0; continue; }
        double t = binf[i];
        for (int m = 0; m < i; m++) t -= Ainf[i * NCMAX + m] * yb[m];
        yb[i] = t / Ainf[i * NCMAX + i];
    }
    int k = 0;
    for (int j = 0; j < nc; j++) {
        if (!keep[j]) continue;
        double *row = Hbig + k * MAXD;
        memset(row, 0, D * sizeof(double));
        for (int i = j; i < nc; i++) row[CORE + i] = Ainf[i * NCMAX + j];
        rbig[k] = yb[j];
        k++;
    }
#if PROF == 8
    k = 0;
#endif
#if UPDATE_ROWS_MAX
    if (k > UPDATE_ROWS_MAX) { /* keep the rows past the cap (newer clones) for the next frames */
        for (int r = UPDATE_ROWS_MAX; r < k; r++) {
            memcpy(pend_H[pend_n], Hbig + r * MAXD + CORE, nc * sizeof(double));
            for (int c = nc; c < 6 * (MAX_CLONES + 1); c++) pend_H[pend_n][c] = 0;
            pend_r[pend_n] = rbig[r];
            pend_n++;
        }
        k = UPDATE_ROWS_MAX;
    }
#endif
    WL(w_k += k);
#if UPDATE_ROWS_MAX
    updated_rows_this_frame = k;
#endif
    { TSTART(up); if (k) update(rbig, Hbig, k, (PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY); TSTOP(up, T_UPDATE); }
    return;
#endif
    { TSTART(fr); for (int b = 0; b < nbatch; b++) feature_rows(&batch[b], &nrows); TSTOP(fr, T_FROWS); }
    if (!nrows) return;
#if PROF == 5
    return; /* fuel profiling: rows only, no compression or update */
#endif
    int nclone_cols = D - CORE;
    if (nrows > nclone_cols) {
        for (int c = CORE; c < D; c++) {
            int pr = c - CORE; /* pivot row */
            double norm = 0;
            for (int i = pr; i < nrows; i++) norm += Hbig[i * MAXD + c] * Hbig[i * MAXD + c];
            norm = sqrt(norm);
            if (norm < 1e-14) continue;
            double alpha = Hbig[pr * MAXD + c] > 0 ? -norm : norm;
            static double v[MAX_ROWS];
            double vn = 0;
            for (int i = pr; i < nrows; i++) v[i] = Hbig[i * MAXD + c];
            v[pr] -= alpha;
            for (int i = pr; i < nrows; i++) vn += v[i] * v[i];
            if (vn < 1e-30) continue;
            for (int j = c; j < D; j++) {
                double s = 0;
                for (int i = pr; i < nrows; i++) s += v[i] * Hbig[i * MAXD + j];
                s *= 2 / vn;
                for (int i = pr; i < nrows; i++) Hbig[i * MAXD + j] -= s * v[i];
            }
            double s = 0;
            for (int i = pr; i < nrows; i++) s += v[i] * rbig[i];
            s *= 2 / vn;
            for (int i = pr; i < nrows; i++) rbig[i] -= s * v[i];
        }
        nrows = nclone_cols;
    }
    { TSTART(up); update(rbig, Hbig, nrows, (PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY); TSTOP(up, T_UPDATE); }
}

/* =====================================================================================================================
 * Image front end
 * ===================================================================================================================== */

/* gray (77 R + 150 G + 29 B + 128) >> 8, then LEVELS - 1 halvings by 2x2 means */
#if defined(__wasm_simd128__) && FAST_PYR
#include <wasm_simd128.h>
/* identical arithmetic to the scalar version, 16 pixels per step: deinterleave RGB with shuffles, 16-bit products */
static void build_pyramid(const uint8_t *rgb, int which) {
    uint8_t *g = pyr[which][0];
    const v128_t k77 = wasm_i16x8_splat(77), k150 = wasm_i16x8_splat(150), k29 = wasm_i16x8_splat(29), k128 = wasm_i16x8_splat(128);
#if GRAY_GREEN == 2
    for (int i = 0; i < IMG_W * IMG_H; i += 16) { /* gray = avg(avg(R, B), G) ~ (R + 2G + B) / 4 */
        const uint8_t *p = rgb + 3 * i;
        v128_t v0 = wasm_v128_load(p), v1 = wasm_v128_load(p + 16), v2 = wasm_v128_load(p + 32);
        v128_t r = wasm_i8x16_shuffle(wasm_i8x16_shuffle(v0, v1, 0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 0, 0, 0, 0, 0), v2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 20, 23, 26, 29);
        v128_t gg = wasm_i8x16_shuffle(wasm_i8x16_shuffle(v0, v1, 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 0, 0, 0, 0, 0), v2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 21, 24, 27, 30);
        v128_t b = wasm_i8x16_shuffle(wasm_i8x16_shuffle(v0, v1, 2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 0, 0, 0, 0, 0, 0), v2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 19, 22, 25, 28, 31);
        wasm_v128_store(g + i, wasm_u8x16_avgr(wasm_u8x16_avgr(r, b), gg));
    }
    (void)k77; (void)k150; (void)k29; (void)k128;
    for (int i = 0; i < 0; i += 16) {
#elif GRAY_GREEN
    for (int i = 0; i < IMG_W * IMG_H; i += 16) { /* gray = green */
        const uint8_t *p = rgb + 3 * i;
        v128_t gg = wasm_i8x16_shuffle(wasm_v128_load(p), wasm_v128_load(p + 16), 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 0, 0, 0, 0, 0);
        wasm_v128_store(g + i, wasm_i8x16_shuffle(gg, wasm_v128_load(p + 32), 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 21, 24, 27, 30));
    }
    (void)k77; (void)k150; (void)k29; (void)k128;
    for (int i = 0; i < 0; i += 16) {
#else
    for (int i = 0; i < IMG_W * IMG_H; i += 16) {
#endif
        const uint8_t *p = rgb + 3 * i;
        v128_t v0 = wasm_v128_load(p), v1 = wasm_v128_load(p + 16), v2 = wasm_v128_load(p + 32);
        v128_t r = wasm_i8x16_shuffle(v0, v1, 0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 0, 0, 0, 0, 0);
        r = wasm_i8x16_shuffle(r, v2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 20, 23, 26, 29);
        v128_t gg = wasm_i8x16_shuffle(v0, v1, 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 0, 0, 0, 0, 0);
        gg = wasm_i8x16_shuffle(gg, v2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 21, 24, 27, 30);
        v128_t b = wasm_i8x16_shuffle(v0, v1, 2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 0, 0, 0, 0, 0, 0);
        b = wasm_i8x16_shuffle(b, v2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 19, 22, 25, 28, 31);
        v128_t lo = wasm_i16x8_add(wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_low_u8x16(r), k77),
                                                  wasm_i16x8_mul(wasm_u16x8_extend_low_u8x16(gg), k150)),
                                   wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_low_u8x16(b), k29), k128));
        v128_t hi = wasm_i16x8_add(wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_high_u8x16(r), k77),
                                                  wasm_i16x8_mul(wasm_u16x8_extend_high_u8x16(gg), k150)),
                                   wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_high_u8x16(b), k29), k128));
        wasm_v128_store(g + i, wasm_u8x16_narrow_i16x8(wasm_u16x8_shr(lo, 8), wasm_u16x8_shr(hi, 8)));
    }
    for (int L = 1; L < LEVELS; L++) {
        int w = IMG_W >> L, h = IMG_H >> L, ws = IMG_W >> (L - 1);
        const uint8_t *s = pyr[which][L - 1];
        uint8_t *d = pyr[which][L];
        const v128_t two = wasm_i16x8_splat(2);
        for (int y = 0; y < h; y++) {
            const uint8_t *r0 = s + 2 * y * ws, *r1 = r0 + ws;
            int x = 0;
            for (; x + 16 <= w; x += 16) {
                v128_t a0 = wasm_u16x8_extadd_pairwise_u8x16(wasm_v128_load(r0 + 2 * x));
                v128_t a1 = wasm_u16x8_extadd_pairwise_u8x16(wasm_v128_load(r0 + 2 * x + 16));
                v128_t b0 = wasm_u16x8_extadd_pairwise_u8x16(wasm_v128_load(r1 + 2 * x));
                v128_t b1 = wasm_u16x8_extadd_pairwise_u8x16(wasm_v128_load(r1 + 2 * x + 16));
                v128_t lo = wasm_u16x8_shr(wasm_i16x8_add(wasm_i16x8_add(a0, b0), two), 2);
                v128_t hi = wasm_u16x8_shr(wasm_i16x8_add(wasm_i16x8_add(a1, b1), two), 2);
                wasm_v128_store(d + y * w + x, wasm_u8x16_narrow_i16x8(lo, hi));
            }
            for (; x < w; x++)
                d[y * w + x] = (uint8_t)((r0[2 * x] + r0[2 * x + 1] + r1[2 * x] + r1[2 * x + 1] + 2) >> 2);
        }
    }
}
#else
static void build_pyramid(const uint8_t *rgb, int which) {
    uint8_t *g = pyr[which][0];
#if GRAY_GREEN == 2
    for (int i = 0; i < IMG_W * IMG_H; i++) g[i] = (uint8_t)((((rgb[3 * i] + rgb[3 * i + 2] + 1) >> 1) + rgb[3 * i + 1] + 1) >> 1);
#elif GRAY_GREEN
    for (int i = 0; i < IMG_W * IMG_H; i++) g[i] = rgb[3 * i + 1];
#else
    for (int i = 0; i < IMG_W * IMG_H; i++) g[i] = (uint8_t)((77 * rgb[3 * i] + 150 * rgb[3 * i + 1] + 29 * rgb[3 * i + 2] + 128) >> 8);
#endif
    for (int L = 1; L < LEVELS; L++) {
        int w = IMG_W >> L, h = IMG_H >> L, ws = IMG_W >> (L - 1);
        const uint8_t *s = pyr[which][L - 1];
        uint8_t *d = pyr[which][L];
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
                d[y * w + x] = (uint8_t)((s[2 * y * ws + 2 * x] + s[2 * y * ws + 2 * x + 1] + s[(2 * y + 1) * ws + 2 * x] + s[(2 * y + 1) * ws + 2 * x + 1] + 2) >> 2);
    }
}
#endif

/* (2r+1)^2 bilinear samples centred at (x, y); all share one sub-pixel offset, so one set of weights */
static void extract(const uint8_t *I, int w, double x, double y, int r, double *out) {
    int x0 = (int)x, y0 = (int)y, n = 2 * r + 1;
    double ax = x - x0, ay = y - y0;
    double w00 = (1 - ax) * (1 - ay), w01 = ax * (1 - ay), w10 = (1 - ax) * ay, w11 = ax * ay;
    for (int v = 0; v < n; v++) {
        const uint8_t *p = I + (y0 - r + v) * w + x0 - r;
        double *o = out + v * n;
        for (int u = 0; u < n; u++) o[u] = w00 * p[u] + w01 * p[u + 1] + w10 * p[u + w] + w11 * p[u + w + 1];
    }
}

/* pyramidal inverse-compositional Lucas-Kanade (translation) from (x0, y0) in image `prev` to image `cur`, starting
   at the guess (gx, gy). The template and its gradients (central differences inside one patch with a 1-pixel ring)
   are fixed per level, so the Hessian is computed once. Returns 0 if the track is lost. */
#if FAST_KLT
#define klt klt_scalar
#endif
static int klt(int prev, int cur, double x0, double y0, double gx, double gy, double *ox, double *oy) {
    static double T[KLT_N], GX[KLT_N], GY[KLT_N], patch[(2 * KLT_R + 3) * (2 * KLT_R + 3)], cur_patch[KLT_N];
    double dx = gx - x0, dy = gy - y0, err = 1e9;
    for (int L = LEVELS - 1; L >= 0; L--) {
        double s = 1.0 / (1 << L);
        int w = IMG_W >> L, h = IMG_H >> L;
        const uint8_t *I0 = pyr[prev][L], *I1 = pyr[cur][L];
        double px = x0 * s, py = y0 * s, ddx = dx * s, ddy = dy * s;
        if (px < KLT_R + 2 || py < KLT_R + 2 || px > w - KLT_R - 3 || py > h - KLT_R - 3) {
            if (L == 0) return 0;
            continue;
        }
        double hxx = 0, hxy = 0, hyy = 0;
        const int pw = 2 * KLT_R + 3;
        extract(I0, w, px, py, KLT_R + 1, patch);
        int n = 0;
        for (int v = 1; v < pw - 1; v++)
            for (int u = 1; u < pw - 1; u++, n++) {
                const double *q = patch + v * pw + u;
                T[n] = q[0];
                GX[n] = 0.5 * (q[1] - q[-1]);
                GY[n] = 0.5 * (q[pw] - q[-pw]);
                hxx += GX[n] * GX[n]; hxy += GX[n] * GY[n]; hyy += GY[n] * GY[n];
            }
        double det = hxx * hyy - hxy * hxy;
        double mineig = 0.5 * (hxx + hyy) - sqrt(0.25 * (hxx - hyy) * (hxx - hyy) + hxy * hxy);
        if (mineig < KLT_MIN_EIG * KLT_N || det <= 0) { /* no texture at this level */
            if (L == 0) return 0;
            dx = ddx / s; dy = ddy / s;
            continue;
        }
        for (int it = 0; it < KLT_ITERS; it++) {
            double qx = px + ddx, qy = py + ddy;
            if (qx < KLT_R + 1 || qy < KLT_R + 1 || qx > w - KLT_R - 2 || qy > h - KLT_R - 2) {
                if (L == 0) return 0;
                break;
            }
            double bx = 0, by = 0, esum = 0;
            extract(I1, w, qx, qy, KLT_R, cur_patch);
            for (n = 0; n < KLT_N; n++) {
                double e = cur_patch[n] - T[n];
                bx += GX[n] * e; by += GY[n] * e;
                esum += fabs(e);
            }
            err = esum / KLT_N;
            double ux = (hyy * bx - hxy * by) / det, uy = (hxx * by - hxy * bx) / det;
            ddx -= ux; ddy -= uy;
            double eps = L == 0 ? KLT_EPS : KLT_EPS_COARSE;
            if (ux * ux + uy * uy < eps * eps) break;
        }
        dx = ddx / s; dy = ddy / s;
    }
    if (err > KLT_MAX_ERR) return 0;
    *ox = x0 + dx; *oy = y0 + dy;
    return 1;
}

#if FAST_KLT
/* FAST_KLT: the same pyramidal inverse-compositional KLT in 16-bit fixed point, 8 lanes per instruction.
 * Patch values are gray x 8 (bilinear weights quantized to 1/16 px, sum 256, then >> 5); a row of up to 16 samples is
 * two i16x8 vectors; lanes past the patch width get zero gradient so they never contribute. */
#undef klt
#if !defined(__wasm_simd128__)
/* host twin of the fixed-point SIMD KLT: the same integer arithmetic (no overflow anywhere), so identical results */
static void extract_fx_s(const uint8_t *I, int w, double x, double y, int r, int n, int out[][16]) {
    int x0 = (int)x, y0 = (int)y;
    int ax = (int)((x - x0) * 16 + 0.5), ay = (int)((y - y0) * 16 + 0.5);
    if (ax > 16) ax = 16;
    if (ay > 16) ay = 16;
    int w00 = (16 - ax) * (16 - ay), w01 = ax * (16 - ay), w10 = (16 - ax) * ay, w11 = ax * ay;
    for (int v = 0; v < n; v++) {
        const uint8_t *p = I + (y0 - r + v) * w + x0 - r;
        for (int j = 0; j < 16; j++)
            out[v][j] = ((w00 * p[j] + w01 * p[j + 1] + w10 * p[j + w] + w11 * p[j + w + 1]) & 0xffff) >> 5;
    }
}
static int klt(int prev, int cur, double x0, double y0, double gx, double gy, double *ox, double *oy) {
    const int N = 2 * KLT_R + 1;
    double dx = gx - x0, dy = gy - y0, err = 1e9;
    for (int L = LEVELS - 1; L >= 0; L--) {
        double s = 1.0 / (1 << L);
        int w = IMG_W >> L, h = IMG_H >> L;
        const uint8_t *I0 = pyr[prev][L], *I1 = pyr[cur][L];
        double px = x0 * s, py = y0 * s, ddx = dx * s, ddy = dy * s;
        if (px < KLT_R + 2 || py < KLT_R + 2 || px > w - KLT_R - 3 || py > h - KLT_R - 3) {
            if (L == 0) return 0;
            continue;
        }
        int P[2 * KLT_R + 3][16], T[2 * KLT_R + 1][16], GX[2 * KLT_R + 1][16], GY[2 * KLT_R + 1][16];
        extract_fx_s(I0, w, px, py, KLT_R + 1, 2 * KLT_R + 3, P);
        long long hxx = 0, hxy = 0, hyy = 0;
        for (int v = 0; v < N; v++)
            for (int j = 0; j < 16; j++) {
                int in = j < N;
                T[v][j] = j < 15 ? P[v + 1][j + 1] : P[v + 1][15];
                int rgt = j < 14 ? P[v + 1][j + 2] : P[v + 1][15];
                int lft = P[v + 1][j];
                int up = j < 15 ? P[v][j + 1] : P[v][15], dn = j < 15 ? P[v + 2][j + 1] : P[v + 2][15];
                GX[v][j] = in ? rgt - lft : 0;
                GY[v][j] = in ? dn - up : 0;
                hxx += GX[v][j] * GX[v][j]; hxy += GX[v][j] * GY[v][j]; hyy += GY[v][j] * GY[v][j];
            }
        double Hxx = hxx / 256.0, Hxy = hxy / 256.0, Hyy = hyy / 256.0;
        double det = Hxx * Hyy - Hxy * Hxy;
        double mineig = 0.5 * (Hxx + Hyy) - sqrt(0.25 * (Hxx - Hyy) * (Hxx - Hyy) + Hxy * Hxy);
        if (mineig < KLT_MIN_EIG * KLT_N || det <= 0) {
            if (L == 0) return 0;
            dx = ddx / s; dy = ddy / s;
            continue;
        }
        for (int it = 0; it < KLT_ITERS; it++) {
            double qx = px + ddx, qy = py + ddy;
            if (qx < KLT_R + 1 || qy < KLT_R + 1 || qx > w - KLT_R - 2 || qy > h - KLT_R - 2) {
                if (L == 0) return 0;
                break;
            }
            int C[2 * KLT_R + 1][16];
            extract_fx_s(I1, w, qx, qy, KLT_R, N, C);
            long long bx = 0, by = 0, ea = 0;
            for (int v = 0; v < N; v++)
                for (int j = 0; j < 16; j++) {
                    int e = C[v][j] - T[v][j];
                    bx += GX[v][j] * e; by += GY[v][j] * e;
                    if (j < N) ea += e < 0 ? -e : e;
                }
            double Bx = bx / 128.0, By = by / 128.0;
            err = ea / 8.0 / KLT_N;
            double ux = (Hyy * Bx - Hxy * By) / det, uy = (Hxx * By - Hxy * Bx) / det;
            ddx -= ux; ddy -= uy;
            double eps = L == 0 ? KLT_EPS : KLT_EPS_COARSE;
            if (ux * ux + uy * uy < eps * eps) break;
        }
        dx = ddx / s; dy = ddy / s;
    }
    if (err > KLT_MAX_ERR) return 0;
    *ox = x0 + dx; *oy = y0 + dy;
    return 1;
}
#else
#include <wasm_simd128.h>
#define FX_ROWS (2 * KLT_R + 3)
typedef struct { v128_t lo, hi; } Row16;
/* n x 16 fixed-point samples of I at (x, y) + (u, v), u, v = -r .. ; weights from the subpixel offset */
static inline void extract_fx(const uint8_t *I, int w, double x, double y, int r, int n, Row16 *out) {
    int x0 = (int)x, y0 = (int)y;
    int ax = (int)((x - x0) * 16 + 0.5), ay = (int)((y - y0) * 16 + 0.5);
    if (ax > 16) ax = 16;
    if (ay > 16) ay = 16;
    const v128_t w00 = wasm_i16x8_splat((int16_t)((16 - ax) * (16 - ay))), w01 = wasm_i16x8_splat((int16_t)(ax * (16 - ay)));
    const v128_t w10 = wasm_i16x8_splat((int16_t)((16 - ax) * ay)), w11 = wasm_i16x8_splat((int16_t)(ax * ay));
    for (int v = 0; v < n; v++) {
        const uint8_t *p = I + (y0 - r + v) * w + x0 - r;
        v128_t a = wasm_v128_load(p), b = wasm_v128_load(p + 1), c = wasm_v128_load(p + w), d = wasm_v128_load(p + w + 1);
        v128_t lo = wasm_i16x8_add(wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_low_u8x16(a), w00), wasm_i16x8_mul(wasm_u16x8_extend_low_u8x16(b), w01)),
                                   wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_low_u8x16(c), w10), wasm_i16x8_mul(wasm_u16x8_extend_low_u8x16(d), w11)));
        v128_t hi = wasm_i16x8_add(wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_high_u8x16(a), w00), wasm_i16x8_mul(wasm_u16x8_extend_high_u8x16(b), w01)),
                                   wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_high_u8x16(c), w10), wasm_i16x8_mul(wasm_u16x8_extend_high_u8x16(d), w11)));
        out[v].lo = wasm_u16x8_shr(lo, 5); /* gray x 256 -> gray x 8 */
        out[v].hi = wasm_u16x8_shr(hi, 5);
    }
}
static inline int32_t hsum_i32x4(v128_t v) {
    return wasm_i32x4_extract_lane(v, 0) + wasm_i32x4_extract_lane(v, 1) + wasm_i32x4_extract_lane(v, 2) + wasm_i32x4_extract_lane(v, 3);
}
/* shift a 16-lane row by one lane: left (lane i <- i+1) and right (lane i <- i-1) */
static inline Row16 row_next(Row16 a) {
    Row16 o;
    o.lo = wasm_i8x16_shuffle(a.lo, a.hi, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17);
    o.hi = wasm_i8x16_shuffle(a.hi, a.hi, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 14, 15);
    return o;
}
static inline Row16 row_prev(Row16 a) {
    Row16 o;
    o.lo = wasm_i8x16_shuffle(a.lo, a.lo, 0, 1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13);
    o.hi = wasm_i8x16_shuffle(a.lo, a.hi, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29);
    return o;
}
static int klt(int prev, int cur, double x0, double y0, double gx, double gy, double *ox, double *oy) {
    const int N = 2 * KLT_R + 1;
    /* lane mask: lanes 0 .. N-1 of the 16 */
    static v128_t mlo, mhi;
    static int mask_ready;
    if (!mask_ready) {
        int16_t m[16];
        for (int i = 0; i < 16; i++) m[i] = i < N ? -1 : 0;
        mlo = wasm_v128_load(m); mhi = wasm_v128_load(m + 8);
        mask_ready = 1;
    }
    double dx = gx - x0, dy = gy - y0, err = 1e9;
    for (int L = LEVELS - 1; L >= 0; L--) {
        double s = 1.0 / (1 << L);
        int w = IMG_W >> L, h = IMG_H >> L;
        const uint8_t *I0 = pyr[prev][L], *I1 = pyr[cur][L];
        double px = x0 * s, py = y0 * s, ddx = dx * s, ddy = dy * s;
        if (px < KLT_R + 2 || py < KLT_R + 2 || px > w - KLT_R - 3 || py > h - KLT_R - 3) {
            if (L == 0) return 0;
            continue;
        }
        Row16 P[FX_ROWS], T[2 * KLT_R + 1], GX[2 * KLT_R + 1], GY[2 * KLT_R + 1];
        extract_fx(I0, w, px, py, KLT_R + 1, FX_ROWS, P); /* lane j of row v = sample (j - R - 1, v - R - 1) */
        v128_t hxx = wasm_i32x4_splat(0), hxy = hxx, hyy = hxx;
        for (int v = 0; v < N; v++) {
            Row16 c = row_next(P[v + 1]);             /* lane j -> sample j + 1 - R - 1 = j - R: the patch column */
            Row16 rgt = row_next(c), up = row_next(P[v]), dn = row_next(P[v + 2]);
            Row16 lft = P[v + 1];
            T[v] = c;
            GX[v].lo = wasm_v128_and(wasm_i16x8_sub(rgt.lo, lft.lo), mlo);
            GX[v].hi = wasm_v128_and(wasm_i16x8_sub(rgt.hi, lft.hi), mhi);
            GY[v].lo = wasm_v128_and(wasm_i16x8_sub(dn.lo, up.lo), mlo);
            GY[v].hi = wasm_v128_and(wasm_i16x8_sub(dn.hi, up.hi), mhi);
            hxx = wasm_i32x4_add(hxx, wasm_i32x4_add(wasm_i32x4_dot_i16x8(GX[v].lo, GX[v].lo), wasm_i32x4_dot_i16x8(GX[v].hi, GX[v].hi)));
            hxy = wasm_i32x4_add(hxy, wasm_i32x4_add(wasm_i32x4_dot_i16x8(GX[v].lo, GY[v].lo), wasm_i32x4_dot_i16x8(GX[v].hi, GY[v].hi)));
            hyy = wasm_i32x4_add(hyy, wasm_i32x4_add(wasm_i32x4_dot_i16x8(GY[v].lo, GY[v].lo), wasm_i32x4_dot_i16x8(GY[v].hi, GY[v].hi)));
        }
        /* gradients are (q[1] - q[-1]) x 8 = 16 x the scalar 0.5 (q[1] - q[-1]); errors are x 8 */
        double Hxx = (double)hsum_i32x4(hxx), Hxy = (double)hsum_i32x4(hxy), Hyy = (double)hsum_i32x4(hyy);
        Hxx /= 256.0; Hxy /= 256.0; Hyy /= 256.0;
        double det = Hxx * Hyy - Hxy * Hxy;
        double mineig = 0.5 * (Hxx + Hyy) - sqrt(0.25 * (Hxx - Hyy) * (Hxx - Hyy) + Hxy * Hxy);
        if (mineig < KLT_MIN_EIG * KLT_N || det <= 0) {
            if (L == 0) return 0;
            dx = ddx / s; dy = ddy / s;
            continue;
        }
        for (int it = 0; it < KLT_ITERS; it++) {
            double qx = px + ddx, qy = py + ddy;
            if (qx < KLT_R + 1 || qy < KLT_R + 1 || qx > w - KLT_R - 2 || qy > h - KLT_R - 2) {
                if (L == 0) return 0;
                break;
            }
            Row16 C[2 * KLT_R + 1];
            extract_fx(I1, w, qx, qy, KLT_R, N, C);
            v128_t bx = wasm_i32x4_splat(0), by = bx, ea = bx;
            for (int v = 0; v < N; v++) {
                v128_t elo = wasm_i16x8_sub(C[v].lo, T[v].lo), ehi = wasm_i16x8_sub(C[v].hi, T[v].hi);
                bx = wasm_i32x4_add(bx, wasm_i32x4_add(wasm_i32x4_dot_i16x8(GX[v].lo, elo), wasm_i32x4_dot_i16x8(GX[v].hi, ehi)));
                by = wasm_i32x4_add(by, wasm_i32x4_add(wasm_i32x4_dot_i16x8(GY[v].lo, elo), wasm_i32x4_dot_i16x8(GY[v].hi, ehi)));
                v128_t alo = wasm_v128_and(wasm_i16x8_abs(elo), mlo), ahi = wasm_v128_and(wasm_i16x8_abs(ehi), mhi);
                ea = wasm_i32x4_add(ea, wasm_i32x4_add(wasm_i32x4_extadd_pairwise_i16x8(alo), wasm_i32x4_extadd_pairwise_i16x8(ahi)));
            }
            double Bx = (double)hsum_i32x4(bx) / 128.0, By = (double)hsum_i32x4(by) / 128.0; /* gradient x16, error x8 */
            err = (double)hsum_i32x4(ea) / 8.0 / KLT_N;
            double ux = (Hyy * Bx - Hxy * By) / det, uy = (Hxx * By - Hxy * Bx) / det;
            ddx -= ux; ddy -= uy;
            double eps = L == 0 ? KLT_EPS : KLT_EPS_COARSE;
            if (ux * ux + uy * uy < eps * eps) break;
        }
        dx = ddx / s; dy = ddy / s;
    }
    if (err > KLT_MAX_ERR) return 0;
    *ox = x0 + dx; *oy = y0 + dy;
    return 1;
}
#endif /* wasm SIMD */
#endif

/* Shi-Tomasi: smaller eigenvalue of the 3x3 sum of gradient outer products (central differences) */
static double corner_score(const uint8_t *I, int x, int y) {
#if INT_CORNER
    int sxx = 0, syy = 0, sxy = 0;
#else
    double sxx = 0, syy = 0, sxy = 0;
#endif
    for (int v = -1; v <= 1; v++)
        for (int u = -1; u <= 1; u++) {
            const uint8_t *p = I + (y + v) * IMG_W + x + u;
            int gx = p[1] - p[-1], gy = p[IMG_W] - p[-IMG_W];
            sxx += gx * gx; syy += gy * gy; sxy += gx * gy;
        }
    return 0.5 * ((double)sxx + syy) - sqrt(0.25 * ((double)sxx - syy) * ((double)sxx - syy) + (double)sxy * sxy);
}

static int cell_of(double x, double y) {
    int gx = (int)(x / CELL_W), gy = (int)(y / CELL_H);
    if (gx < 0) gx = 0;
    if (gx >= GRID_X) gx = GRID_X - 1;
    if (gy < 0) gy = 0;
    if (gy >= GRID_Y) gy = GRID_Y - 1;
    return gy * GRID_X + gx;
}

/* top up the grid: in every cell without a live track, the best corner (stride 2) above DETECT_MIN_SCORE becomes a new
   track. Only empty cells are scored, so the cost follows the number of lost tracks. */
static void detect(int which) {
    int occupied[MAX_TRACKS] = {0}, free_slot[MAX_TRACKS], nfree = 0;
    for (int i = 0; i < MAX_TRACKS; i++) {
        if (tracks[i].alive) occupied[cell_of(tracks[i].x, tracks[i].y)] = 1;
        else free_slot[nfree++] = i;
    }
    const uint8_t *I = pyr[which][0];
    int scored = 0, k = 0;
    for (k = 0; k < MAX_TRACKS && nfree > 0 && scored < DETECT_MAX_CELLS; k++) {
        int cell = (detect_cursor + k) % MAX_TRACKS;
        if (occupied[cell]) continue;
        scored++;
        WL(w_cells++);
        int x0 = (cell % GRID_X) * CELL_W, y0 = (cell / GRID_X) * CELL_H;
        double best = DETECT_MIN_SCORE;
        int bx = -1, by = -1;
#if FAST_DETECT
        /* same scores: each pixel's gradient products once, then 3x3 sums (columns of 3 rows, then 3 columns) */
        {
            enum { RW = CELL_W + 1, RH = CELL_H + 1 };
            static int gxx[RH][RW], gyy[RH][RW], gxy[RH][RW];
            for (int r = 0; r < RH; r++) {
                int yy = y0 + r;
                for (int c = 0; c < RW; c++) {
                    int xx = x0 + c;
                    if (yy < 1 || yy > IMG_H - 2 || xx < 1 || xx > IMG_W - 2) { gxx[r][c] = gyy[r][c] = gxy[r][c] = 0; continue; }
                    const uint8_t *q = I + yy * IMG_W + xx;
                    int gx = q[1] - q[-1], gy = q[IMG_W] - q[-IMG_W];
                    gxx[r][c] = gx * gx; gyy[r][c] = gy * gy; gxy[r][c] = gx * gy;
                }
            }
            for (int y = y0 + 1; y < y0 + CELL_H; y += DETECT_STRIDE) {
                if (y < BORDER || y >= IMG_H - BORDER) continue;
                int r = y - y0, csxx[RW], csyy[RW], csxy[RW];
                for (int c = 0; c < RW; c++) {
                    csxx[c] = gxx[r - 1][c] + gxx[r][c] + gxx[r + 1][c];
                    csyy[c] = gyy[r - 1][c] + gyy[r][c] + gyy[r + 1][c];
                    csxy[c] = gxy[r - 1][c] + gxy[r][c] + gxy[r + 1][c];
                }
                for (int x = x0 + 1; x < x0 + CELL_W; x += DETECT_STRIDE) {
                    if (x < BORDER || x >= IMG_W - BORDER) continue;
                    int c = x - x0;
                    int sxx = csxx[c - 1] + csxx[c] + csxx[c + 1], syy = csyy[c - 1] + csyy[c] + csyy[c + 1];
                    int sxy = csxy[c - 1] + csxy[c] + csxy[c + 1];
                    double sc = 0.5 * ((double)sxx + syy) - sqrt(0.25 * ((double)sxx - syy) * ((double)sxx - syy) + (double)sxy * sxy);
                    if (sc > best) { best = sc; bx = x; by = y; }
                }
            }
        }
#else
        for (int y = y0 + 1; y < y0 + CELL_H; y += DETECT_STRIDE) {
            if (y < BORDER || y >= IMG_H - BORDER) continue;
            for (int x = x0 + 1; x < x0 + CELL_W; x += DETECT_STRIDE) {
                if (x < BORDER || x >= IMG_W - BORDER) continue;
                double s = corner_score(I, x, y);
                if (s > best) { best = s; bx = x; by = y; }
            }
        }
#endif
        if (bx >= 0) {
            Track *t = &tracks[free_slot[--nfree]];
            t->alive = 1; t->x = bx; t->y = by; t->obs.n = 0;
        }
    }
    detect_cursor = scored >= DETECT_MAX_CELLS ? (detect_cursor + k) % MAX_TRACKS : (detect_cursor + 7) % MAX_TRACKS;
}

/* track every live feature into the current image, starting at its gyro-predicted position (rotation only);
   a lost track with enough observations is queued for its update */
static void track_all(int prev, int cur, const double *Rwc_now) {
    double Rrel[9];
    m3tmul(Rwc_now, Rwc_prev, Rrel); /* previous camera -> current camera */
    for (int i = 0; i < MAX_TRACKS; i++) {
        Track *t = &tracks[i];
        if (!t->alive) continue;
        double ray[3] = {(t->x - cx) / fx, (t->y - cy) / fy, 1.0}, rp[3];
        WL(w_tracks++);
        m3vec(Rrel, ray, rp);
        double gx = t->x, gy = t->y;
        if (rp[2] > 1e-3) { gx = fx * rp[0] / rp[2] + cx; gy = fy * rp[1] / rp[2] + cy; }
        double nx, ny;
        if (klt(prev, cur, t->x, t->y, gx, gy, &nx, &ny) && nx >= 0 && ny >= 0 && nx < IMG_W && ny < IMG_H) {
            t->x = nx; t->y = ny;
        } else {
            t->alive = 0;
            if (t->obs.n >= MIN_OBS && nlost < 2 * MAX_TRACKS) lost[nlost++] = t->obs;
        }
    }
}

/* at a clone frame: every live track records its position (normalized coordinates) for the newest clone */
static void record_observations(void) {
    int cid = clones[nclones - 1].id;
    for (int i = 0; i < MAX_TRACKS; i++) {
        Track *t = &tracks[i];
        if (!t->alive) continue;
        if (t->obs.n == MAX_OBS) { /* keep the newest */
            memmove(t->obs.cid, t->obs.cid + 1, (MAX_OBS - 1) * sizeof(int));
            memmove(t->obs.x, t->obs.x + 1, (MAX_OBS - 1) * sizeof(double));
            memmove(t->obs.y, t->obs.y + 1, (MAX_OBS - 1) * sizeof(double));
            t->obs.n--;
        }
        t->obs.cid[t->obs.n] = cid;
        t->obs.x[t->obs.n] = (t->x - cx) / fx;
        t->obs.y[t->obs.n] = (t->y - cy) / fy;
        t->obs.n++;
    }
}

/* vision ZUPT: median disparity, with the rotation between the last two clones removed, of the features seen in both;
   below ZUPT_DISPARITY the camera did not translate -> v = 0 */
static void vision_zupt(void) {
    if (nclones < 2) return;
    const Clone *prev = &clones[nclones - 2], *cur = &clones[nclones - 1];
    double Rp[9], Rc[9], pp[3], pc[3], Rrel[9];
    camera_pose(prev, Rp, pp);
    camera_pose(cur, Rc, pc);
    m3tmul(Rc, Rp, Rrel);
    static double disp[MAX_TRACKS];
    int n = 0;
    for (int i = 0; i < MAX_TRACKS; i++) {
        const Obs *o = &tracks[i].obs;
        if (!tracks[i].alive || o->n < 2 || o->cid[o->n - 2] != prev->id || o->cid[o->n - 1] != cur->id) continue;
        double ray[3] = {o->x[o->n - 2], o->y[o->n - 2], 1.0}, rp[3];
        m3vec(Rrel, ray, rp);
        if (rp[2] <= 0) continue;
        disp[n++] = fx * hypot(rp[0] / rp[2] - o->x[o->n - 1], rp[1] / rp[2] - o->y[o->n - 1]);
    }
    if (n < ZUPT_MIN_FEATURES) return;
    for (int i = 1; i < n; i++) { /* insertion sort for the median (n <= 60) */
        double v = disp[i];
        int j = i - 1;
        while (j >= 0 && disp[j] > v) { disp[j + 1] = disp[j]; j--; }
        disp[j + 1] = v;
    }
    double median = n % 2 ? disp[n / 2] : 0.5 * (disp[n / 2 - 1] + disp[n / 2]);
    if (median < ZUPT_DISPARITY) {
        double r[3];
        memset(Hs, 0, sizeof Hs);
        for (int i = 0; i < 3; i++) { Hs[i * MAXD + V + i] = 1; r[i] = -vel[i]; }
        update(r, Hs, 3, ZUPT_STD * ZUPT_STD, INFINITY);
    }
}

/* take a track's observations for an update; it keeps only its newest, so no information is used twice */
static void take_for_update(Obs *o, Obs *batch, int *nb) {
    batch[(*nb)++] = *o;
    o->cid[0] = o->cid[o->n - 1]; o->x[0] = o->x[o->n - 1]; o->y[0] = o->y[o->n - 1];
    o->n = 1;
}

/* per frame, after the IMU part:
 *   clone frame (every CLONE_EVERY): clone, record observations, vision ZUPT, then update with the queued ended tracks
 *     and the tracks still observed in the oldest clone, and marginalize that clone once the window is full;
 *   other frames: update with up to MAX_UPDATE_FEATURES ended tracks and a third of the tracks that the next clone
 *     would otherwise carry, so the clone frame stays as cheap as the others (the max fuel per frame counts);
 *   then top up the features. */
static Obs batch[MAX_BATCH];
#ifndef PROF
#define PROF 0  /* fuel profiling: 1 = no vision, 2 = pyramid only, 3 = + tracking, 4 = + detection (no updates) */
#endif
static void vision(const uint8_t *frame) {
    int prev = cur_pyr, cur = 1 - cur_pyr;
#if PROF == 1
    (void)frame; (void)prev; return;
#endif
    { TSTART(py); build_pyramid(frame, cur); TSTOP(py, T_PYR); }
#if PROF == 2
    cur_pyr = cur; return;
#endif
    double Rwc_now[9];
    m3mul(R, R_bc, Rwc_now);
    { TSTART(tr); track_all(prev, cur, Rwc_now); TSTOP(tr, T_TRACK); }
#if PROF == 3 || PROF == 4
#if PROF == 4
    { int nl = nlost; (void)nl; nlost = 0; detect(cur); }
#endif
    nlost = 0; cur_pyr = cur; m3mul(R, R_bc, Rwc_prev); return;
#endif
    if (++frames_since_clone >= CLONE_EVERY) {
        frames_since_clone = 0;
        WL(w_clone = 1);
        { TSTART(cl); add_clone(); TSTOP(cl, T_CLONE); }
        record_observations();
        { TSTART(z); vision_zupt(); TSTOP(z, T_ZUPT); }
        int nb = 0;
#if CLONE_BATCH_MAX < 1000
        { /* ended tracks: at most CLONE_BATCH_MAX now, the rest stay queued for the next frames */
            int take = nlost < CLONE_BATCH_MAX ? nlost : CLONE_BATCH_MAX;
            for (int i = 0; i < take; i++) batch[nb++] = lost[i];
            memmove(lost, lost + take, (nlost - take) * sizeof(Obs));
            nlost -= take;
        }
#else
        for (int i = 0; i < nlost && nb < MAX_BATCH; i++) batch[nb++] = lost[i];
        nlost = 0;
#endif
        if (nclones > MAX_CLONES) {
            int oldest = clones[0].id;
            for (int i = 0; i < MAX_TRACKS && nb < MAX_BATCH && nb < CLONE_BATCH_MAX + 4; i++) {
                Obs *o = &tracks[i].obs;
                if (tracks[i].alive && o->n >= MIN_OBS && o->cid[0] == oldest) take_for_update(o, batch, &nb);
            }
            { TSTART(mu); msckf_update(batch, nb); TSTOP(mu, T_COMPRESS); }
            remove_oldest_clone();
            for (int i = 0; i < MAX_TRACKS; i++) { /* drop the remaining observations in the marginalized clone */
                Obs *o = &tracks[i].obs;
                int k = 0;
                for (int j = 0; j < o->n; j++)
                    if (o->cid[j] != oldest) { o->cid[k] = o->cid[j]; o->x[k] = o->x[j]; o->y[k] = o->y[j]; k++; }
                o->n = k;
            }
        } else {
            { TSTART(mu); msckf_update(batch, nb); TSTOP(mu, T_COMPRESS); }
        }
    } else {
        int nb = 0, take = nlost < MAX_UPDATE_FEATURES ? nlost : MAX_UPDATE_FEATURES;
        for (int i = 0; i < take; i++) batch[nb++] = lost[i];
        memmove(lost, lost + take, (nlost - take) * sizeof(Obs));
        nlost -= take;
        if (nclones == MAX_CLONES) { /* the next clone pushes clones[0] out */
            int oldest = clones[0].id, phase = frames_since_clone - 1; /* 0 .. CLONE_EVERY - 2 */
            for (int i = phase; i < MAX_TRACKS && nb < MAX_BATCH && nb < FRAME_BATCH_MAX; i += CLONE_EVERY - 1) {
                Obs *o = &tracks[i].obs;
                if (tracks[i].alive && o->n >= MIN_OBS && o->cid[0] == oldest) take_for_update(o, batch, &nb);
            }
        }
        { TSTART(mu); msckf_update(batch, nb); TSTOP(mu, T_COMPRESS); }
    }
#if UPDATE_ROWS_MAX
    if (pend_n && !updated_rows_this_frame) apply_pending(0, UPDATE_ROWS_MAX);
    updated_rows_this_frame = 0;
#endif
    { TSTART(d); detect(cur); TSTOP(d, T_DETECT); }
    cur_pyr = cur;
    m3mul(R, R_bc, Rwc_prev);
}

/* =====================================================================================================================
 * Output: pose of camera k in camera 0 (T_cam_imu [R0^T R, R0^T p] T_imu_cam), twist in camera k axes
 * ===================================================================================================================== */

static void write_state(double *out) {
    double Rr[9], pr[3], T[16] = {0}, tmp[16], Tc[16];
    m3tmul(R0, R, Rr);
    m3tvec(R0, pos, pr);
    for (int i = 0; i < 3; i++) { for (int j = 0; j < 3; j++) T[4 * i + j] = Rr[3 * i + j]; T[4 * i + 3] = pr[i]; }
    T[15] = 1;
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++) {
            double s = 0;
            for (int k = 0; k < 4; k++) s += T_cam_imu[4 * i + k] * T[4 * k + j];
            tmp[4 * i + j] = s;
        }
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++) {
            double s = 0;
            for (int k = 0; k < 4; k++) s += tmp[4 * i + k] * T_imu_cam[4 * k + j];
            Tc[4 * i + j] = s;
        }
    double Rc[9], Rci[9];
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { Rc[3 * i + j] = Tc[4 * i + j]; Rci[3 * i + j] = T_cam_imu[4 * i + j]; }
    out[0] = Tc[3]; out[1] = Tc[7]; out[2] = Tc[11];
    matrix_to_quaternion(Rc, out + 3);
    double vb[3], wxr[3]; /* camera centre velocity: v + omega x lever arm, in camera axes */
    m3tvec(R, vel, vb);
    wxr[0] = omega[1] * p_bc[2] - omega[2] * p_bc[1];
    wxr[1] = omega[2] * p_bc[0] - omega[0] * p_bc[2];
    wxr[2] = omega[0] * p_bc[1] - omega[1] * p_bc[0];
    for (int i = 0; i < 3; i++) vb[i] += wxr[i];
    m3vec(Rci, vb, out + 7);
    m3vec(Rci, omega, out + 10);
}

/* =====================================================================================================================
 * ABI (docs/ABI.md): _initialize -> frame_width -> init(config) -> alloc x3 -> step x N
 * ===================================================================================================================== */

int32_t abi_version(void) { return VIOBENCH_ABI_VERSION; }
void *alloc(uint32_t size) { return malloc(size ? size : 1); }
int32_t frame_width(void) { return IMG_W; }

/* `count` numbers following "key" in a JSON text (enough for this flat config) */
static int json_number(const char *buf, const char *key, double *out, int count) {
    const char *s = strstr(buf, key);
    if (!s) return 0;
    s += strlen(key);
    for (int i = 0; i < count; i++) {
        while (*s && !(*s == '-' || *s == '+' || *s == '.' || (*s >= '0' && *s <= '9'))) s++;
        if (!*s) return 0;
        char *end;
        out[i] = strtod(s, &end);
        s = end;
    }
    return 1;
}

/* config: {"width", "height", "fx", "fy", "cx", "cy", "T_cam_imu": 4x4} (intrinsics vary per episode) */
int32_t init(const char *json, uint32_t length) {
    static char buffer[4096];
    if (length >= sizeof buffer) return VIOBENCH_STATUS_ERROR;
    memcpy(buffer, json, length);
    buffer[length] = 0;
    if (!json_number(buffer, "\"T_cam_imu\"", T_cam_imu, 16) || !json_number(buffer, "\"fx\"", &fx, 1) ||
        !json_number(buffer, "\"fy\"", &fy, 1) || !json_number(buffer, "\"cx\"", &cx, 1) || !json_number(buffer, "\"cy\"", &cy, 1))
        return VIOBENCH_STATUS_ERROR;
    memset(T_imu_cam, 0, sizeof T_imu_cam); /* rigid inverse */
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) T_imu_cam[4 * i + j] = T_cam_imu[4 * j + i];
        T_imu_cam[4 * i + 3] = -(T_cam_imu[i] * T_cam_imu[3] + T_cam_imu[4 + i] * T_cam_imu[7] + T_cam_imu[8 + i] * T_cam_imu[11]);
    }
    T_imu_cam[15] = 1;
    for (int i = 0; i < 3; i++) { for (int j = 0; j < 3; j++) R_bc[3 * i + j] = T_imu_cam[4 * i + j]; p_bc[i] = T_imu_cam[4 * i + 3]; }
    initialized = 0;
    return VIOBENCH_STATUS_OK;
}

/* frame: 240 x 320 x 3 RGB; imu: imu_count rows [t, ax, ay, az, gx, gy, gz] with t_prev_frame < t <= t;
   out: [x, y, z, qx, qy, qz, qw, vx, vy, vz, wx, wy, wz] */
int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {
    if (!initialized) {
        if (imu_count == 0) { /* no IMU yet: identity, at rest */
            memset(out, 0, VIOBENCH_STATE_VALUES * sizeof(double));
            out[6] = 1;
            return VIOBENCH_STATUS_OK;
        }
        initialize(imu, imu_count, t);
        nclones = 0; clone_counter = 0; frames_since_clone = 0; nlost = 0; detect_cursor = 0;
        memset(tracks, 0, sizeof tracks);
        cur_pyr = 0;
        build_pyramid(frame, cur_pyr);
        add_clone();
        detect(cur_pyr);
        record_observations();
        m3mul(R, R_bc, Rwc_prev);
        initialized = 1;
        write_state(out);
        return VIOBENCH_STATUS_OK;
    }
    TSTART(a);
    for (int r = 0; r < imu_count; r++) propagate(imu + 7 * r);
    TSTOP(a, T_PROP);
    TSTART(b);
    if (imu_count) imu_measurements(imu, imu_count);
    TSTOP(b, T_IMUMEAS);
    vision(frame);
    TSTART(c);
    write_state(out);
    TSTOP(c, T_REST);
#if WORK_LOG
    { int alive = 0; for (int i = 0; i < MAX_TRACKS; i++) alive += tracks[i].alive;
      fprintf(stderr, "W %d %d %d %d %d %d %d %d %d\n", w_tracks, w_cells, w_feats, w_ok, w_k, w_clone, nclones, alive, D);
      w_tracks = w_cells = w_feats = w_ok = w_k = w_clone = 0; }
#endif
    t_end_frame();
    return VIOBENCH_STATUS_OK;
}
