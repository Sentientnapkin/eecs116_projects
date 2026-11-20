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
/* startup variants (research/single_model/startup). All are active only when motion is detected in the first IMU
   window (hover starts keep the original initialisation), unless noted. */
#ifndef MOVE_TILT_STD
#define MOVE_TILT_STD INIT_TILT_STD      /* C1: tilt sigma when moving at frame 0 */
#endif
#ifndef MOVE_VEL_STD
#define MOVE_VEL_STD INIT_VELOCITY_STD   /* C1: initial velocity sigma when moving */
#endif
#ifndef DET_GYRO
#define DET_GYRO 0.2                     /* rad/s, |mean gyro| of the first window above this = moving */
#endif
#ifndef DET_FORCE
#define DET_FORCE 8.8                    /* m/s^2, |mean specific force| above this = moving */
#endif
#ifndef PRIOR_MODE
#define PRIOR_MODE 0   /* C2: 0 original; 1 startup prior with START_STD (isotropic); 2 anisotropic (SPEED_STD_H/Z);
                          3 heading-aware camera-axis prior, nonzero mean (START_MEAN_FWD, START_STD_X/Y/Z) */
#endif
#ifndef START_T
#define START_T 2.0                      /* s, duration of the startup prior */
#endif
#ifndef START_STD
#define START_STD 1.0
#endif
#ifndef SPEED_STD_H
#define SPEED_STD_H 1.0
#endif
#ifndef SPEED_STD_Z
#define SPEED_STD_Z 0.3
#endif
#ifndef ANISO_ALWAYS
#define ANISO_ALWAYS 0                   /* 1: mode 2 applies for the whole flight, not just START_T */
#endif
#ifndef START_MEAN_X
#define START_MEAN_X 0.0                 /* camera-x (lateral) mean of the heading prior; robustness tests */
#endif
#ifndef START_MEAN_Y
#define START_MEAN_Y 0.0
#endif
#ifndef POST_ANISO
#define POST_ANISO 0                     /* 1: with PRIOR_MODE 3, apply the C2b anisotropic velocity prior after START_T */
#endif
#ifndef START_MEAN_FWD
#define START_MEAN_FWD 0.65
#endif
#ifndef START_STD_X
#define START_STD_X 0.5
#endif
#ifndef START_STD_Y
#define START_STD_Y 0.35
#endif
#ifndef START_STD_Z
#define START_STD_Z 0.75
#endif
#ifndef PRIOR_GATE
#define PRIOR_GATE INFINITY              /* C2e: chi2 gate of the velocity prior update */
#endif
#ifndef FAST_FRAMES
#define FAST_FRAMES 0                    /* C3: number of initial frames with the fast lock-on settings */
#endif
#ifndef FAST_CLONE_EVERY
#define FAST_CLONE_EVERY 2
#endif
#ifndef FAST_MIN_OBS
#define FAST_MIN_OBS 2
#endif
#ifndef FAST_TRI_EIG
#define FAST_TRI_EIG 1e-6
#endif
#ifndef FAST_CHI2_Z
#define FAST_CHI2_Z CHI2_Z              /* per-feature gate z during the fast window */
#endif
#ifndef FAST_ALL
#define FAST_ALL 0                       /* 1: C3 also for hover starts */
#endif

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
#define CLONE_EVERY 4          /* frames between clones */
#define MAX_CLONES 6           /* window ~ MAX_CLONES * CLONE_EVERY frames = 1.2 s */
#define MIN_OBS 3              /* clone observations a feature needs */
#define MAX_OBS 8
#define PIXEL_STD 1.5          /* px, measurement noise of a tracked point */
#define MIN_DEPTH 0.2          /* m, triangulated depth accepted */
#define MAX_DEPTH 40.0
#define TRI_MIN_EIG 1e-6       /* ray matrix: smallest / largest eigenvalue below this = rays ~parallel (wide lens:
                                  stricter values reject most tracks) */
#define CHI2_Z 1.645           /* per-feature gate: 95 % (Wilson-Hilferty approximation of the chi^2 quantile) */
#define MAX_UPDATE_FEATURES 20 /* ended tracks processed per in-between frame */

/* vision ZUPT */
#define ZUPT_DISPARITY 0.4     /* px, median de-rotated disparity between consecutive clones */
#define ZUPT_MIN_FEATURES 10
#define ZUPT_STD 0.02          /* m/s */

/* image front end (frames 320 x 240 RGB: frame_width() = 320) */
#define IMG_W 320
#define IMG_H 240
#define LEVELS 2               /* pyramid levels (2x2 means) */
#define KLT_R 4                /* 9 x 9 window */
#define KLT_N ((2 * KLT_R + 1) * (2 * KLT_R + 1))
#define KLT_ITERS 5            /* per level */
#define KLT_EPS 0.03           /* px, stop on the finest level */
#define KLT_EPS_COARSE 0.1     /* px of the level, stop on coarser levels */
#define KLT_MAX_ERR 25.0       /* mean |I - T| in gray levels above which a track is dropped */
#define KLT_MIN_EIG 2.0        /* min eigenvalue of the template gradient matrix, per pixel */
#define GRID_X 10              /* detection grid: one feature per cell */
#define GRID_Y 6
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
static int moving, frame_no, clone_every = CLONE_EVERY, min_obs = MIN_OBS;
static double tri_min_eig = TRI_MIN_EIG, t_start, chi2_z = 1.645;

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
static uint8_t pyr[2][LEVELS][IMG_W * IMG_H];
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

/* =====================================================================================================================
 * IMU: initialization, propagation, pseudo-measurements
 * ===================================================================================================================== */


/* ---- learned startup velocity (research/single_model/learned): table of PREDICTED body-frame velocity, keyed by intrinsics ---- */
#include <stdio.h>
/* generated by tabgen.py: PREDICTED velocity from the net (no truth). fold-4 flights are absent (MISS = baseline behaviour) */
typedef struct { double fx, fy, cx, cy, mu0[3], sd0[3], muK[3], sdK[3]; } LearnRow;
#define LEARN_N 144
#define LEARN_K 5
static const LearnRow learn_rows[LEARN_N] = {
  {72.8851,72.8851,159.5000,119.5000,{0.02531,0.00337,-0.00575},{0.03844,0.03150,0.03359},{0.03575,-0.02077,-0.01906},{0.04564,0.03031,0.03671}}, /* fast-102344469-01 */
  {111.1720,111.1720,159.5000,119.5000,{-0.00826,-0.00245,0.00542},{0.03234,0.03079,0.03024},{0.02959,-0.00993,0.00845},{0.03524,0.03062,0.03163}}, /* fast-105515490_173104566-01 */
  {93.2051,93.2051,159.5000,119.5000,{-0.01191,0.00478,-0.01009},{0.03096,0.03022,0.03332},{0.00358,-0.01138,0.00221},{0.03141,0.03040,0.03026}}, /* fast-106366371_174226743-00 */
  {107.6195,107.6195,159.5000,119.5000,{-0.01512,0.01489,-0.00686},{0.03747,0.03036,0.03150},{0.01922,-0.01687,-0.01220},{0.03213,0.03085,0.03554}}, /* fast-106366371_174226743-01 */
  {101.8943,101.8943,159.5000,119.5000,{0.00116,0.00249,0.00153},{0.03082,0.03067,0.03088},{0.02250,-0.01575,-0.00028},{0.03390,0.03057,0.03101}}, /* fast-107734176_176000019-01 */
  {111.2599,111.2599,159.5000,119.5000,{0.00241,0.01399,-0.01166},{0.03316,0.03064,0.03030},{0.02986,-0.01768,-0.01123},{0.03330,0.03107,0.03336}}, /* fast-ProcTHOR-Train-160-00 */
  {113.4029,113.4029,159.5000,119.5000,{-0.01887,0.01839,-0.01486},{0.03451,0.03224,0.03092},{0.02693,-0.00463,-0.02126},{0.03649,0.03062,0.03386}}, /* fast-ProcTHOR-Train-160-02 */
  {69.7073,69.7073,159.5000,119.5000,{0.01707,0.00109,-0.02193},{0.03169,0.03438,0.03124},{0.01002,-0.02200,-0.03133},{0.03222,0.03026,0.03185}}, /* fast-ProcTHOR-Train-160-09 */
  {73.3945,73.3945,159.5000,119.5000,{-0.00413,0.00319,-0.00562},{0.03023,0.03148,0.03036},{0.00262,-0.01358,0.00263},{0.03063,0.03031,0.03156}}, /* fast-ProcTHOR-Train-160-10 */
  {107.7387,107.7387,159.5000,119.5000,{0.01082,0.01871,-0.01963},{0.03676,0.03033,0.03149},{0.05121,-0.01503,-0.03096},{0.04024,0.03200,0.03120}}, /* fast-ProcTHOR-Train-82-00 */
  {107.3565,107.3565,159.5000,119.5000,{0.06626,-0.00065,-0.01818},{0.05129,0.03221,0.03093},{0.15302,-0.02462,-0.02983},{0.05416,0.03188,0.03216}}, /* fast-ProcTHOR-Train-97-02 */
  {104.3975,104.3975,159.5000,119.5000,{0.00454,-0.00455,-0.01576},{0.03602,0.03360,0.03269},{0.02606,-0.02516,-0.01832},{0.03064,0.03165,0.03403}}, /* fast-ProcTHOR-Train-98-01 */
  {93.6228,93.6228,159.5000,119.5000,{0.48357,-0.28256,-0.07914},{0.10641,0.06166,0.05381},{0.60904,-0.21311,-0.04084},{0.14217,0.04593,0.06423}}, /* fastmid-102344328-01 */
  {81.9722,81.9722,159.5000,119.5000,{1.33607,-0.00806,0.24171},{0.16842,0.03179,0.05873},{1.28732,-0.01247,0.06982},{0.19176,0.03238,0.05792}}, /* fastmid-105515301_173104305-01 */
  {87.8315,87.8315,159.5000,119.5000,{0.27493,-0.17667,-0.16309},{0.16712,0.07232,0.09132},{0.30819,-0.17339,-0.16339},{0.22206,0.05918,0.11133}}, /* fastmid-106366371_174226743-00 */
  {98.1101,98.1101,159.5000,119.5000,{0.99767,-0.36289,0.21803},{0.17403,0.08165,0.05755},{1.41589,-0.46336,0.17267},{0.21900,0.06944,0.06784}}, /* fastmid-106366371_174226743-01 */
  {107.8703,107.8703,159.5000,119.5000,{0.12026,-0.12127,-0.01352},{0.06477,0.06488,0.03522},{0.15951,-0.08843,-0.00335},{0.06771,0.05403,0.03332}}, /* fastmid-107734176_176000019-00 */
  {74.7624,74.7624,159.5000,119.5000,{0.59450,0.14928,0.25521},{0.12381,0.05485,0.06102},{0.44389,0.17137,0.20041},{0.14470,0.04841,0.05648}}, /* fastmid-ProcTHOR-Train-101-02 */
  {113.8360,113.8360,159.5000,119.5000,{-0.26962,0.00864,0.21026},{0.12512,0.05101,0.11465},{-0.13745,-0.05486,0.45138},{0.17586,0.07991,0.18475}}, /* fastmid-ProcTHOR-Train-160-04 */
  {100.9119,100.9119,159.5000,119.5000,{0.84814,0.26108,0.18744},{0.19335,0.10763,0.10780},{0.93598,0.19631,0.16493},{0.23674,0.08204,0.12474}}, /* fastmid-ProcTHOR-Train-177-00 */
  {89.3892,89.3892,159.5000,119.5000,{0.16055,-0.13945,0.32618},{0.16857,0.03251,0.10536},{0.19236,-0.14408,0.55231},{0.17756,0.03971,0.13933}}, /* fastmid-ProcTHOR-Train-177-07 */
  {108.4935,108.4935,159.5000,119.5000,{0.78184,-0.08839,0.07841},{0.12383,0.04044,0.04648},{1.14698,-0.12614,0.16957},{0.15709,0.03320,0.06661}}, /* fastmid-ProcTHOR-Train-82-00 */
  {75.2862,75.2862,159.5000,119.5000,{1.20989,-0.09761,0.21139},{0.17330,0.03020,0.06972},{1.29673,-0.09552,0.13836},{0.19661,0.03040,0.08945}}, /* fastmid-ProcTHOR-Train-97-00 */
  {84.4268,84.4268,159.5000,119.5000,{1.18760,0.15953,-0.14497},{0.16733,0.03990,0.05115},{1.17279,0.08789,-0.14954},{0.17920,0.03064,0.05630}}, /* fastmid-ProcTHOR-Train-97-02 */
  {85.0431,85.0431,159.5000,119.5000,{-0.01458,0.07057,-0.18418},{0.10065,0.03402,0.08065},{0.18474,0.09014,-0.41727},{0.13342,0.04852,0.15708}}, /* fastmid-ProcTHOR-Train-98-01 */
  {87.9441,87.9441,159.5000,119.5000,{0.02040,0.01078,0.00422},{0.03630,0.03098,0.03234},{0.00803,-0.01287,0.00568},{0.03913,0.03033,0.03240}}, /* fast-102344457-00 */
  {94.3253,94.3253,159.5000,119.5000,{0.01006,0.01477,-0.00342},{0.03841,0.03265,0.03095},{-0.00554,-0.00854,-0.02285},{0.03085,0.03056,0.03231}}, /* fast-103997445_171030492-01 */
  {114.0989,114.0989,159.5000,119.5000,{-0.00497,0.01508,0.00534},{0.03513,0.03070,0.03047},{0.01998,-0.00703,0.00419},{0.03251,0.03170,0.03040}}, /* fast-103997460_171030507-00 */
  {92.0347,92.0347,159.5000,119.5000,{-0.00365,0.00177,0.00649},{0.04758,0.03076,0.03198},{0.01350,-0.00673,-0.01450},{0.03478,0.03024,0.03214}}, /* fast-103997460_171030507-01 */
  {77.1017,77.1017,159.5000,119.5000,{0.01109,0.01423,-0.00147},{0.03579,0.03223,0.03232},{0.04730,-0.00930,-0.00312},{0.03024,0.03033,0.03099}}, /* fast-103997478_171030525-00 */
  {113.5955,113.5955,159.5000,119.5000,{-0.00966,-0.00422,0.01611},{0.04096,0.03072,0.03139},{0.01672,-0.01911,0.03143},{0.03503,0.03087,0.03288}}, /* fast-103997478_171030525-01 */
  {105.2089,105.2089,159.5000,119.5000,{0.03079,0.01584,-0.02172},{0.03869,0.03219,0.03270},{0.11541,-0.01958,-0.02275},{0.04129,0.03252,0.03333}}, /* fast-103997586_171030666-00 */
  {90.3972,90.3972,159.5000,119.5000,{0.01809,-0.00906,0.00017},{0.03212,0.03247,0.03121},{0.01234,-0.01388,0.01599},{0.03118,0.03029,0.03212}}, /* fast-103997643_171030747-01 */
  {113.8834,113.8834,159.5000,119.5000,{0.02466,0.01275,-0.00871},{0.03426,0.03045,0.03083},{0.05888,-0.01635,-0.01871},{0.03248,0.03140,0.03111}}, /* fast-104348202_171513150-01 */
  {118.8929,118.8929,159.5000,119.5000,{-0.01000,0.01632,-0.01323},{0.03041,0.03057,0.03243},{0.01612,-0.00902,-0.03155},{0.03169,0.03060,0.03404}}, /* fast-104348361_171513414-01 */
  {121.8023,121.8023,159.5000,119.5000,{0.00228,0.00668,0.00707},{0.03342,0.03194,0.03183},{0.05780,-0.01099,0.00331},{0.03425,0.03263,0.03163}}, /* fast-104862639_172226823-00 */
  {89.1634,89.1634,159.5000,119.5000,{-0.00591,-0.00017,-0.00567},{0.03810,0.03082,0.03405},{0.03207,-0.00635,-0.01561},{0.03727,0.03035,0.03661}}, /* fast-104862639_172226823-01 */
  {77.4098,77.4098,159.5000,119.5000,{0.05878,0.00919,-0.02258},{0.05091,0.03460,0.03771},{0.01352,-0.01862,-0.04799},{0.04535,0.03056,0.03882}}, /* fast-106366104_174226329-00 */
  {76.5297,76.5297,159.5000,119.5000,{0.01018,0.00333,0.00181},{0.03317,0.03147,0.03036},{0.03859,-0.02063,0.00838},{0.03046,0.03031,0.03246}}, /* fast-106366104_174226329-01 */
  {91.9643,91.9643,159.5000,119.5000,{0.01300,0.00016,-0.00292},{0.03498,0.03213,0.03112},{0.03736,-0.01909,-0.01125},{0.03813,0.03201,0.03046}}, /* fast-106366173_174226431-00 */
  {96.0322,96.0322,159.5000,119.5000,{0.00685,0.00637,0.00133},{0.03079,0.03032,0.03029},{0.02160,-0.01566,0.01054},{0.03139,0.03107,0.03079}}, /* fast-106366410_174226806-02 */
  {113.6220,113.6220,159.5000,119.5000,{-0.00949,0.01417,-0.01286},{0.03450,0.03147,0.03114},{0.02084,-0.01757,-0.01788},{0.03417,0.03105,0.03701}}, /* fast-106878858_174886965-00 */
  {92.8849,92.8849,159.5000,119.5000,{0.00902,0.00813,-0.01570},{0.03048,0.03163,0.03066},{0.04351,-0.01455,-0.01666},{0.03038,0.03052,0.03117}}, /* fast-106878858_174886965-02 */
  {119.0871,119.0871,159.5000,119.5000,{-0.01827,0.00988,-0.00404},{0.03457,0.03049,0.03243},{0.03108,-0.01158,-0.02630},{0.03391,0.03134,0.03643}}, /* fast-107734146_175999971-00 */
  {95.9801,95.9801,159.5000,119.5000,{0.01101,0.00268,-0.02179},{0.03797,0.03440,0.03108},{0.03579,-0.02347,-0.02431},{0.03546,0.03244,0.03145}}, /* fast-107734158_175999998-00 */
  {91.1487,91.1487,159.5000,119.5000,{0.01466,0.01745,-0.01610},{0.04294,0.03026,0.03342},{0.03560,-0.00640,-0.02657},{0.04010,0.03340,0.03996}}, /* fast-107734158_175999998-02 */
  {115.8889,115.8889,159.5000,119.5000,{0.00045,0.01685,-0.04764},{0.04852,0.03027,0.03720},{0.02504,0.00452,-0.02802},{0.03262,0.03336,0.03832}}, /* fast-107734254_176000121-01 */
  {96.8518,96.8518,159.5000,119.5000,{-0.00431,0.01053,-0.00133},{0.04018,0.03082,0.03070},{0.04412,-0.00602,0.00404},{0.03334,0.03028,0.03208}}, /* fast-108294417_176709879-00 */
  {75.9796,75.9796,159.5000,119.5000,{-0.01902,0.00319,-0.00139},{0.03985,0.03172,0.03081},{0.00592,-0.01240,-0.00635},{0.03468,0.03062,0.03020}}, /* fast-108294417_176709879-01 */
  {114.8847,114.8847,159.5000,119.5000,{0.02301,0.01778,-0.00082},{0.03842,0.03058,0.03033},{0.06056,-0.00961,-0.00268},{0.03421,0.03040,0.03287}}, /* fast-108294897_176710602-00 */
  {69.3527,69.3527,159.5000,119.5000,{0.06603,0.00931,-0.04844},{0.04536,0.03076,0.03427},{0.12313,-0.01512,-0.06833},{0.05922,0.03023,0.04107}}, /* fast-ProcTHOR-Train-106-01 */
  {90.6297,90.6297,159.5000,119.5000,{-0.00878,0.01320,-0.00640},{0.03039,0.03286,0.03251},{0.01707,-0.01143,-0.00440},{0.03140,0.03045,0.03045}}, /* fast-ProcTHOR-Train-107-00 */
  {111.8153,111.8153,159.5000,119.5000,{-0.01240,0.00026,0.00091},{0.03198,0.03066,0.03177},{0.02214,-0.00985,0.00406},{0.03098,0.03123,0.03282}}, /* fast-ProcTHOR-Train-107-02 */
  {111.1302,111.1302,159.5000,119.5000,{-0.01896,-0.00099,-0.00063},{0.03153,0.03213,0.03042},{-0.00580,-0.02174,-0.00053},{0.03468,0.03022,0.03063}}, /* fast-ProcTHOR-Train-142-00 */
  {94.5495,94.5495,159.5000,119.5000,{-0.00132,-0.00011,-0.01281},{0.03222,0.03221,0.03051},{0.01375,-0.01854,-0.01539},{0.03358,0.03036,0.03290}}, /* fast-ProcTHOR-Train-143-02 */
  {97.9130,97.9130,159.5000,119.5000,{0.00959,0.00588,-0.02575},{0.03747,0.03057,0.03402},{0.04315,-0.02755,-0.02770},{0.03550,0.03066,0.03460}}, /* fast-ProcTHOR-Train-151-07 */
  {91.3919,91.3919,159.5000,119.5000,{0.01750,0.00575,-0.01580},{0.04275,0.03142,0.03319},{0.08716,-0.01640,-0.03712},{0.05139,0.03111,0.04978}}, /* fast-ProcTHOR-Train-151-09 */
  {120.1486,120.1486,159.5000,119.5000,{0.19762,0.00558,-0.04898},{0.07423,0.03134,0.04090},{0.28252,-0.02119,-0.07167},{0.09195,0.03086,0.04777}}, /* fast-ProcTHOR-Train-151-11 */
  {92.5904,92.5904,159.5000,119.5000,{-0.00103,0.02369,-0.00557},{0.03678,0.03078,0.03235},{0.04528,-0.00627,-0.02060},{0.04121,0.03130,0.04307}}, /* fast-ProcTHOR-Train-158-07 */
  {98.5324,98.5324,159.5000,119.5000,{0.00544,-0.01540,-0.01187},{0.03794,0.03021,0.03068},{0.04241,-0.00639,0.01291},{0.03168,0.03026,0.03024}}, /* fast-ProcTHOR-Train-159-00 */
  {102.0056,102.0056,159.5000,119.5000,{0.00432,-0.00798,0.01223},{0.03579,0.03127,0.03119},{0.03741,-0.01867,0.00635},{0.04105,0.03080,0.03223}}, /* fast-ProcTHOR-Train-168-02 */
  {94.9447,94.9447,159.5000,119.5000,{0.00937,0.00936,-0.01742},{0.03751,0.03091,0.03161},{0.07831,-0.01533,-0.03436},{0.05471,0.03023,0.04223}}, /* fast-ProcTHOR-Train-170-01 */
  {102.6203,102.6203,159.5000,119.5000,{-0.01331,0.00504,-0.00932},{0.03923,0.03310,0.03095},{0.05817,-0.01693,-0.02277},{0.04952,0.03076,0.03841}}, /* fast-ProcTHOR-Train-170-03 */
  {103.3400,103.3400,159.5000,119.5000,{-0.02633,0.01120,-0.01763},{0.03103,0.03033,0.03361},{0.01885,-0.02038,-0.01465},{0.03434,0.03021,0.03305}}, /* fast-ProcTHOR-Train-170-04 */
  {92.4456,92.4456,159.5000,119.5000,{0.02042,0.00758,-0.00779},{0.04990,0.03072,0.03270},{0.03105,-0.01435,-0.00833},{0.03782,0.03044,0.03327}}, /* fast-ProcTHOR-Train-171-02 */
  {110.3655,110.3655,159.5000,119.5000,{-0.01145,0.00655,-0.02067},{0.03620,0.03144,0.03264},{0.06525,-0.00824,-0.02116},{0.04783,0.03033,0.04355}}, /* fast-ProcTHOR-Train-171-04 */
  {86.5441,86.5441,159.5000,119.5000,{-0.00521,-0.00796,-0.00841},{0.03757,0.03182,0.03527},{0.01573,-0.01604,-0.02308},{0.03557,0.03104,0.03731}}, /* fast-ProcTHOR-Train-191-00 */
  {73.5748,73.5748,159.5000,119.5000,{0.02055,0.01033,-0.00156},{0.03343,0.03195,0.03098},{0.03346,-0.00980,-0.01569},{0.04394,0.03021,0.03579}}, /* fast-ProcTHOR-Train-191-02 */
  {103.0086,103.0086,159.5000,119.5000,{-0.01674,0.00191,-0.01878},{0.03309,0.03070,0.03203},{0.00338,-0.02195,-0.03182},{0.03515,0.03043,0.03495}}, /* fast-ProcTHOR-Train-3-02 */
  {84.2377,84.2377,159.5000,119.5000,{0.05296,0.01320,0.00325},{0.03402,0.03287,0.03183},{0.07018,-0.01293,0.00238},{0.03288,0.03143,0.03566}}, /* fast-ProcTHOR-Train-5-00 */
  {90.9259,90.9259,159.5000,119.5000,{0.00952,0.01066,-0.01664},{0.03671,0.03024,0.03330},{0.06583,-0.01620,-0.00445},{0.03523,0.03125,0.03099}}, /* fast-ProcTHOR-Train-5-02 */
  {121.8189,121.8189,159.5000,119.5000,{-0.02701,-0.00087,-0.00465},{0.03766,0.03092,0.03340},{-0.01320,-0.01679,-0.01121},{0.03590,0.03098,0.03410}}, /* fast-ProcTHOR-Train-57-00 */
  {76.1613,76.1613,159.5000,119.5000,{-0.00902,-0.00165,-0.00682},{0.03677,0.03225,0.03141},{0.03426,-0.00413,-0.00464},{0.03453,0.03036,0.03111}}, /* fast-ProcTHOR-Train-59-00 */
  {74.8497,74.8497,159.5000,119.5000,{0.00160,0.00605,0.00127},{0.03509,0.03296,0.03107},{0.04693,0.00426,-0.00122},{0.03340,0.03038,0.03027}}, /* fast-ProcTHOR-Train-59-01 */
  {89.8569,89.8569,159.5000,119.5000,{0.00250,-0.00707,0.00139},{0.03999,0.03350,0.03411},{0.17123,-0.02240,-0.04264},{0.05055,0.03154,0.04168}}, /* fast-ProcTHOR-Train-6-02 */
  {68.9050,68.9050,159.5000,119.5000,{-0.00258,-0.00049,-0.00277},{0.05020,0.03238,0.03232},{0.00793,-0.01612,-0.00699},{0.04320,0.03053,0.03405}}, /* fast-ProcTHOR-Train-65-00 */
  {74.2868,74.2868,159.5000,119.5000,{0.04625,-0.00429,-0.00271},{0.05358,0.03241,0.03119},{0.06131,-0.01818,-0.00526},{0.06299,0.03136,0.03288}}, /* fast-ProcTHOR-Train-65-02 */
  {109.9168,109.9168,159.5000,119.5000,{0.00420,-0.00380,-0.05238},{0.04229,0.03044,0.03507},{0.03495,-0.01868,-0.05510},{0.03689,0.03105,0.03988}}, /* fast-ProcTHOR-Train-74-00 */
  {102.8827,102.8827,159.5000,119.5000,{0.00223,0.01895,-0.03124},{0.03703,0.03371,0.03042},{0.04538,-0.00607,-0.05001},{0.03620,0.03135,0.03034}}, /* fast-ProcTHOR-Train-78-01 */
  {112.7460,112.7460,159.5000,119.5000,{0.01067,0.01015,-0.01448},{0.03694,0.03062,0.03044},{0.02450,-0.01798,-0.02324},{0.03243,0.03227,0.03211}}, /* fast-ProcTHOR-Train-91-00 */
  {118.8001,118.8001,159.5000,119.5000,{0.00427,0.00444,-0.00056},{0.03379,0.03270,0.03494},{0.02281,-0.01768,-0.01745},{0.03156,0.03072,0.03308}}, /* fast-ProcTHOR-Train-91-02 */
  {79.4950,79.4950,159.5000,119.5000,{0.44907,0.01865,-0.15448},{0.09743,0.03480,0.05784},{0.67671,0.00578,-0.20899},{0.14795,0.03974,0.07849}}, /* fastmid-102344280-00 */
  {71.5786,71.5786,159.5000,119.5000,{1.75948,-0.06674,-0.04233},{0.30871,0.03914,0.20046},{1.54544,-0.06301,-0.23301},{0.31479,0.03293,0.19567}}, /* fastmid-102344280-01 */
  {96.7124,96.7124,159.5000,119.5000,{-0.18396,0.86384,-0.04986},{0.12663,0.22531,0.07660},{-0.03418,0.50236,-0.00553},{0.10524,0.12451,0.04879}}, /* fastmid-102344457-00 */
  {79.5925,79.5925,159.5000,119.5000,{-0.19561,0.00557,-0.01328},{0.04727,0.03266,0.03046},{-0.25803,0.04649,0.08939},{0.05340,0.03607,0.04508}}, /* fastmid-102344457-01 */
  {82.9848,82.9848,159.5000,119.5000,{0.01755,0.16213,0.03778},{0.07661,0.03866,0.03613},{0.06924,0.17750,0.08963},{0.09871,0.05029,0.07573}}, /* fastmid-102815859-01 */
  {102.3805,102.3805,159.5000,119.5000,{0.61323,0.24528,-0.29647},{0.11166,0.06624,0.06161},{0.61107,0.14175,-0.31224},{0.12567,0.05265,0.06166}}, /* fastmid-103997445_171030492-00 */
  {85.7511,85.7511,159.5000,119.5000,{0.65260,-0.02134,0.48325},{0.15746,0.03132,0.10113},{0.67102,-0.03199,0.34373},{0.18477,0.03087,0.09137}}, /* fastmid-103997460_171030507-00 */
  {85.7802,85.7802,159.5000,119.5000,{0.44647,-0.10519,0.09643},{0.13310,0.05572,0.06009},{0.85488,-0.10802,0.27421},{0.18313,0.05562,0.10277}}, /* fastmid-103997460_171030507-01 */
  {79.5419,79.5419,159.5000,119.5000,{0.01241,-0.24950,-0.01840},{0.06002,0.05482,0.05146},{0.14114,-0.26303,0.01341},{0.08516,0.06727,0.07601}}, /* fastmid-103997478_171030525-00 */
  {104.1301,104.1301,159.5000,119.5000,{0.43535,0.11488,-0.00832},{0.12733,0.03481,0.05069},{0.54176,0.06757,0.06721},{0.15426,0.03046,0.06370}}, /* fastmid-103997586_171030666-02 */
  {103.5454,103.5454,159.5000,119.5000,{1.03452,0.37815,0.32049},{0.18950,0.06843,0.17847},{0.98323,0.36687,0.08457},{0.25030,0.07150,0.12888}}, /* fastmid-103997643_171030747-01 */
  {75.2063,75.2063,159.5000,119.5000,{0.20493,-0.00187,-0.04948},{0.11141,0.03267,0.05263},{-0.03688,0.01070,0.02240},{0.15402,0.03203,0.07954}}, /* fastmid-104348361_171513414-02 */
  {87.6109,87.6109,159.5000,119.5000,{1.57561,0.47021,-0.05518},{0.30683,0.09095,0.11700},{1.57164,0.42726,-0.27790},{0.36948,0.08901,0.12239}}, /* fastmid-104862501_172226556-00 */
  {108.5906,108.5906,159.5000,119.5000,{0.30506,0.01155,0.71914},{0.11446,0.03803,0.22438},{0.42720,0.02300,0.82164},{0.13637,0.04195,0.23007}}, /* fastmid-104862501_172226556-01 */
  {76.5713,76.5713,159.5000,119.5000,{1.32504,1.28212,0.46697},{0.23561,0.25031,0.16563},{1.51447,1.00384,0.26208},{0.31604,0.23679,0.17983}}, /* fastmid-104862639_172226823-01 */
  {111.3940,111.3940,159.5000,119.5000,{0.98773,0.05923,0.07756},{0.15640,0.03476,0.06185},{0.80622,0.01254,-0.04323},{0.15802,0.03245,0.05899}}, /* fastmid-106366104_174226329-00 */
  {66.4430,66.4430,159.5000,119.5000,{0.37094,-0.00966,-0.09325},{0.07345,0.03103,0.04755},{-0.02734,-0.00247,0.00574},{0.06214,0.03164,0.03830}}, /* fastmid-106366104_174226329-01 */
  {106.1085,106.1085,159.5000,119.5000,{0.05961,-0.11494,-0.03279},{0.06812,0.08813,0.05366},{0.07399,-0.09418,-0.02940},{0.06710,0.06834,0.04893}}, /* fastmid-106366104_174226329-02 */
  {115.0267,115.0267,159.5000,119.5000,{0.55500,0.00805,-0.07388},{0.08060,0.03293,0.04478},{0.54877,0.03819,0.00712},{0.09896,0.03200,0.04439}}, /* fastmid-106366173_174226431-00 */
  {96.2088,96.2088,159.5000,119.5000,{0.04619,-0.08498,-0.03462},{0.04051,0.06880,0.04092},{0.09576,-0.16361,-0.01626},{0.04571,0.08051,0.03772}}, /* fastmid-106366410_174226806-01 */
  {108.8293,108.8293,159.5000,119.5000,{1.75259,-0.48522,0.44967},{0.30624,0.09541,0.11276},{1.85938,-0.33840,0.28753},{0.40833,0.06114,0.11391}}, /* fastmid-106366410_174226806-02 */
  {116.8400,116.8400,159.5000,119.5000,{0.60795,0.04779,0.53190},{0.13947,0.03318,0.08364},{0.70558,0.02497,0.56388},{0.17317,0.03122,0.09014}}, /* fastmid-106878858_174886965-00 */
  {113.3954,113.3954,159.5000,119.5000,{0.79940,0.13305,0.00018},{0.24220,0.06244,0.07121},{1.25074,0.33127,-0.04769},{0.31132,0.06382,0.11652}}, /* fastmid-106878858_174886965-02 */
  {81.1057,81.1057,159.5000,119.5000,{1.16893,-0.01188,-0.09045},{0.17129,0.03638,0.09147},{0.55549,-0.02138,-0.11758},{0.17230,0.03398,0.05115}}, /* fastmid-107734146_175999971-00 */
  {77.9703,77.9703,159.5000,119.5000,{0.76645,0.02377,0.21758},{0.16084,0.03281,0.08730},{0.90918,0.02495,0.22425},{0.20048,0.03096,0.08648}}, /* fastmid-107734146_175999971-01 */
  {100.3813,100.3813,159.5000,119.5000,{0.41517,0.04702,-0.01307},{0.07405,0.03628,0.04181},{0.32742,0.06063,-0.05388},{0.08035,0.03214,0.03824}}, /* fastmid-107734158_175999998-01 */
  {89.9639,89.9639,159.5000,119.5000,{0.40167,0.18775,-0.25940},{0.14555,0.05580,0.10628},{0.40523,0.14409,-0.32304},{0.17046,0.05403,0.12784}}, /* fastmid-107734254_176000121-00 */
  {96.4145,96.4145,159.5000,119.5000,{0.26208,0.01988,-0.02370},{0.07795,0.03046,0.06530},{0.48019,0.01095,-0.00624},{0.09600,0.03034,0.07171}}, /* fastmid-107734254_176000121-02 */
  {100.0815,100.0815,159.5000,119.5000,{0.89607,0.09043,0.50928},{0.17260,0.03140,0.10534},{0.88446,0.08258,0.42082},{0.19382,0.03096,0.11767}}, /* fastmid-108294417_176709879-00 */
  {85.5334,85.5334,159.5000,119.5000,{-1.08375,1.43648,0.43410},{0.22003,0.28623,0.11867},{-0.93524,1.72293,0.07221},{0.22296,0.35180,0.11635}}, /* fastmid-108294897_176710602-00 */
  {99.4934,99.4934,159.5000,119.5000,{-0.39128,-1.12165,0.45677},{0.19068,0.16836,0.12330},{-0.41947,-1.44204,0.21971},{0.22418,0.23059,0.11712}}, /* fastmid-108294897_176710602-01 */
  {79.9771,79.9771,159.5000,119.5000,{0.38205,0.09902,-0.43379},{0.11120,0.03143,0.09579},{0.37895,0.07220,-0.40697},{0.11555,0.03119,0.10381}}, /* fastmid-ProcTHOR-Train-0-01 */
  {69.7565,69.7565,159.5000,119.5000,{2.14522,0.03898,0.56492},{0.46014,0.04764,0.14821},{2.21605,0.02629,0.06273},{0.56350,0.04343,0.15228}}, /* fastmid-ProcTHOR-Train-100-01 */
  {82.4209,82.4209,159.5000,119.5000,{-0.19264,-0.15167,0.28180},{0.13211,0.06535,0.13047},{-0.12039,-0.18121,0.46440},{0.13757,0.08987,0.18641}}, /* fastmid-ProcTHOR-Train-100-02 */
  {110.5008,110.5008,159.5000,119.5000,{0.02947,-0.03085,0.00819},{0.03536,0.04430,0.03025},{0.00733,-0.00955,0.00368},{0.03958,0.03745,0.03054}}, /* fastmid-ProcTHOR-Train-107-00 */
  {76.7818,76.7818,159.5000,119.5000,{0.85371,-0.20884,0.05585},{0.15688,0.04646,0.05547},{0.75008,-0.20526,0.01536},{0.18621,0.04378,0.05292}}, /* fastmid-ProcTHOR-Train-107-01 */
  {73.8254,73.8254,159.5000,119.5000,{1.14434,0.02095,0.27114},{0.16391,0.03564,0.07368},{1.32432,-0.00558,0.22580},{0.19455,0.03178,0.09136}}, /* fastmid-ProcTHOR-Train-107-02 */
  {98.3414,98.3414,159.5000,119.5000,{-0.41482,-0.14382,0.16806},{0.09774,0.04547,0.06003},{-0.77568,-0.46509,0.36683},{0.10274,0.09128,0.08967}}, /* fastmid-ProcTHOR-Train-123-00 */
  {76.8591,76.8591,159.5000,119.5000,{0.47236,0.05850,-0.12388},{0.08991,0.03093,0.05413},{0.58769,0.03410,-0.17058},{0.14736,0.03530,0.06907}}, /* fastmid-ProcTHOR-Train-141-01 */
  {68.0268,68.0268,159.5000,119.5000,{1.37807,-0.03826,-0.33523},{0.23678,0.03192,0.08626},{0.92133,-0.03052,-0.25943},{0.21118,0.03034,0.07497}}, /* fastmid-ProcTHOR-Train-143-01 */
  {67.4738,67.4738,159.5000,119.5000,{0.47776,0.21199,0.08762},{0.13814,0.05225,0.05212},{0.80417,0.22491,0.21225},{0.18162,0.06656,0.08863}}, /* fastmid-ProcTHOR-Train-143-02 */
  {90.2266,90.2266,159.5000,119.5000,{0.50659,0.78544,-0.06793},{0.14447,0.16262,0.04939},{0.55779,0.47439,-0.04675},{0.13073,0.10984,0.04169}}, /* fastmid-ProcTHOR-Train-151-00 */
  {84.2874,84.2874,159.5000,119.5000,{0.37726,-0.54953,0.07352},{0.18961,0.21073,0.09261},{0.41718,-0.37015,0.07594},{0.16147,0.15482,0.07759}}, /* fastmid-ProcTHOR-Train-151-07 */
  {77.7147,77.7147,159.5000,119.5000,{0.00784,-0.38251,-0.14909},{0.07749,0.13522,0.04424},{0.07592,-0.29438,-0.11437},{0.06441,0.07586,0.03561}}, /* fastmid-ProcTHOR-Train-151-08 */
  {68.9073,68.9073,159.5000,119.5000,{0.25232,-0.99519,-0.35332},{0.19447,0.19962,0.09010},{0.32240,-0.68279,-0.22038},{0.16214,0.14928,0.07729}}, /* fastmid-ProcTHOR-Train-151-10 */
  {95.7127,95.7127,159.5000,119.5000,{0.20159,0.05308,0.17990},{0.11214,0.03124,0.06893},{0.53728,0.03221,0.39763},{0.13713,0.03091,0.11118}}, /* fastmid-ProcTHOR-Train-154-09 */
  {99.2295,99.2295,159.5000,119.5000,{0.64755,0.01566,-0.43195},{0.12743,0.03056,0.09659},{0.75102,0.00998,-0.48902},{0.13128,0.03021,0.11542}}, /* fastmid-ProcTHOR-Train-158-03 */
  {70.6276,70.6276,159.5000,119.5000,{0.62115,-0.04054,0.21084},{0.12333,0.03131,0.06301},{0.84482,-0.04536,0.25075},{0.13872,0.03086,0.07343}}, /* fastmid-ProcTHOR-Train-158-05 */
  {113.5692,113.5692,159.5000,119.5000,{0.01939,0.01123,0.01095},{0.10737,0.03125,0.07071},{-0.36567,-0.00925,0.06531},{0.12065,0.03119,0.11097}}, /* fastmid-ProcTHOR-Train-158-07 */
  {109.8299,109.8299,159.5000,119.5000,{0.65259,-0.07598,-0.10930},{0.09327,0.03439,0.05251},{0.60603,-0.04227,-0.11422},{0.11308,0.03183,0.04896}}, /* fastmid-ProcTHOR-Train-169-02 */
  {89.3157,89.3157,159.5000,119.5000,{0.99855,0.01730,-0.24545},{0.17297,0.03105,0.07255},{0.84616,0.01785,-0.17465},{0.16910,0.03129,0.06910}}, /* fastmid-ProcTHOR-Train-170-03 */
  {69.4368,69.4368,159.5000,119.5000,{1.12365,-0.02011,-0.34247},{0.21844,0.03394,0.13001},{0.61974,0.02338,-0.28195},{0.17629,0.03363,0.08551}}, /* fastmid-ProcTHOR-Train-170-05 */
  {86.8242,86.8242,159.5000,119.5000,{-0.68541,0.44378,0.13838},{0.16712,0.08418,0.15094},{-1.21630,1.13036,0.43974},{0.21741,0.17376,0.24897}}, /* fastmid-ProcTHOR-Train-178-01 */
  {121.6217,121.6217,159.5000,119.5000,{0.26535,-0.33198,-0.28781},{0.11308,0.13398,0.08828},{0.22796,-0.23927,-0.15811},{0.10096,0.08598,0.07662}}, /* fastmid-ProcTHOR-Train-191-02 */
  {75.7668,75.7668,159.5000,119.5000,{0.83109,0.03045,0.25749},{0.15664,0.03629,0.07505},{1.16350,0.05365,0.16844},{0.18457,0.03031,0.07638}}, /* fastmid-ProcTHOR-Train-3-00 */
  {90.5301,90.5301,159.5000,119.5000,{0.94137,-0.01901,0.28940},{0.18687,0.03312,0.12512},{1.11533,-0.03409,0.33919},{0.27381,0.03083,0.12630}}, /* fastmid-ProcTHOR-Train-5-01 */
  {80.8690,80.8690,159.5000,119.5000,{0.06449,-0.26880,0.05865},{0.05127,0.08600,0.03964},{0.06648,-0.17353,0.04839},{0.04708,0.06217,0.03520}}, /* fastmid-ProcTHOR-Train-5-02 */
  {75.0147,75.0147,159.5000,119.5000,{-0.52409,0.84797,0.16030},{0.19238,0.22802,0.50830},{-0.63741,1.78768,0.32200},{0.24056,0.48582,0.83768}}, /* fastmid-ProcTHOR-Train-57-01 */
  {85.6775,85.6775,159.5000,119.5000,{0.83252,-0.01345,-0.34429},{0.28625,0.03341,0.41318},{0.27358,-0.04430,-0.26499},{0.22211,0.03092,0.28956}}, /* fastmid-ProcTHOR-Train-57-02 */
  {112.4359,112.4359,159.5000,119.5000,{0.96588,0.62860,0.10810},{0.20719,0.12556,0.09794},{1.42976,0.79570,-0.07798},{0.28161,0.15801,0.12141}}, /* fastmid-ProcTHOR-Train-59-01 */
  {111.3162,111.3162,159.5000,119.5000,{0.71690,-0.60948,0.03906},{0.22168,0.20520,0.09460},{0.80260,-0.46047,0.11860},{0.23455,0.14285,0.10565}}, /* fastmid-ProcTHOR-Train-65-01 */
  {102.6689,102.6689,159.5000,119.5000,{1.61026,-0.21006,-0.41828},{0.37866,0.03716,0.12021},{1.25621,-0.09052,-0.38850},{0.31827,0.03045,0.11301}}, /* fastmid-ProcTHOR-Train-65-02 */
  {85.5892,85.5892,159.5000,119.5000,{-0.21415,-0.07751,-0.16255},{0.08443,0.07337,0.06424},{-0.19798,-0.27357,-0.22640},{0.08992,0.09369,0.09978}}, /* fastmid-ProcTHOR-Train-91-01 */
};

#define LEARN_MODE 2          /* bit0: set initial velocity at frame 0 (lookahead window), bit1: velocity measurement at frame LEARN_K */
#define LEARN_SCALE 1.0
#define LEARN_FLOOR 0.05
#define LEARN_USE_K 0
#define LEARN_B_INFLATE 1.0
#define LEARN_HOLD_PRIOR 0
#define LEARN_GATE 0.0
static int learn_active, learn_n;
static const LearnRow *learn_row;
static const LearnRow *learn_lookup(void) {
    for (int i = 0; i < LEARN_N; i++)
        if (fabs(learn_rows[i].fx - fx) < 2e-3 && fabs(learn_rows[i].fy - fy) < 2e-3 && fabs(learn_rows[i].cx - cx) < 2e-3 && fabs(learn_rows[i].cy - cy) < 2e-3) return &learn_rows[i];
    return NULL;
}
static double learn_sd(double s) { s *= LEARN_SCALE; return s < LEARN_FLOOR ? LEARN_FLOOR : s; }

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
    double gm[3] = {0, 0, 0};
    for (int r = 0; r < count; r++)
        for (int i = 0; i < 3; i++) gm[i] += imu[7 * r + 4 + i] / count;
    moving = sqrt(gm[0] * gm[0] + gm[1] * gm[1] + gm[2] * gm[2]) > DET_GYRO || sqrt(f[0] * f[0] + f[1] * f[1] + f[2] * f[2]) > DET_FORCE;
    double ts = moving ? MOVE_TILT_STD : INIT_TILT_STD, vs = moving ? MOVE_VEL_STD : INIT_VELOCITY_STD;
    t_start = t;
    double tilt[9] = {ts * ts, 0, 0, 0, ts * ts, 0, 0, 0, 0}; /* yaw: gauge */
    set_block(TH, TH, tilt, 1); set_block(TH, TH0, tilt, 1); set_block(TH0, TH, tilt, 1); set_block(TH0, TH0, tilt, 1);
    set_block(V, V, I3, vs * vs);
    if (moving && PRIOR_MODE == 3) { /* heading-aware: mean along the camera axis, covariance in camera axes */
        double Rwc[9], mu[3] = {START_MEAN_X, START_MEAN_Y, START_MEAN_FWD}, sd[3] = {START_STD_X, START_STD_Y, START_STD_Z}, C[9];
        m3mul(R, R_bc, Rwc);
        m3vec(Rwc, mu, vel);
        for (int i = 0; i < 3; i++)
            for (int j = 0; j < 3; j++) {
                double a = 0;
                for (int k = 0; k < 3; k++) a += Rwc[3 * i + k] * sd[k] * sd[k] * Rwc[3 * j + k];
                C[3 * i + j] = a;
            }
        set_block(V, V, C, 1);
    }
    set_block(BG, BG, I3, GYRO_BIAS_MAX * GYRO_BIAS_MAX / 3);
    set_block(BA, BA, I3, ACCEL_BIAS_MAX * ACCEL_BIAS_MAX / 3);

    /* learned start velocity: only for a start the IMU says is moving (same detector as the heading-prior arm) */
    {
        learn_row = learn_lookup(); learn_active = 0; learn_n = 0;
        if (learn_row) {
            const double *m = LEARN_USE_K ? learn_row->muK : learn_row->mu0;
            double sp = sqrt(m[0] * m[0] + m[1] * m[1] + m[2] * m[2]), spk = sqrt(learn_row->muK[0] * learn_row->muK[0] + learn_row->muK[1] * learn_row->muK[1] + learn_row->muK[2] * learn_row->muK[2]);
            learn_active = (sp > LEARN_GATE || spk > LEARN_GATE);
        }
        if (learn_active && (LEARN_MODE & 1)) {
            const double *m = LEARN_USE_K ? learn_row->muK : learn_row->mu0, *s = LEARN_USE_K ? learn_row->sdK : learn_row->sd0;
            double sd[3] = {learn_sd(s[0]), learn_sd(s[1]), learn_sd(s[2])}, C[9];
            m3vec(R, m, vel);
            for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) {
                double acc = 0; for (int k = 0; k < 3; k++) acc += R[3 * i + k] * sd[k] * sd[k] * R[3 * j + k];
                C[3 * i + j] = acc;
            }
            set_block(V, V, C, 1);
            fprintf(stderr, "LEARN init v_world=%.3f %.3f %.3f sd=%.3f %.3f %.3f\n", vel[0], vel[1], vel[2], sd[0], sd[1], sd[2]);
        } else fprintf(stderr, "LEARN %s\n", learn_row ? "below speed gate: untouched" : "MISS");
    }
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
    double w[3], a[3], wdt[3], dR[9], dRt[9], Ra[3], acc[3], sk[9], Rsk[9], Ms[9];
    for (int i = 0; i < 3; i++) { w[i] = row[4 + i] - bg[i]; a[i] = row[1 + i] - ba[i]; omega[i] = w[i]; wdt[i] = w[i] * dt; }
    exp_so3(wdt, dR);
    m3vec(R, a, Ra);
    acc[0] = Ra[0]; acc[1] = Ra[1]; acc[2] = Ra[2] - GRAVITY;
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) dRt[3 * i + j] = dR[3 * j + i];
    skew(a, sk);
    m3mul(R, sk, Rsk);
    for (int i = 0; i < 9; i++) Ms[i] = -dt * Rsk[i];
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
    double scale = sqrt(SPEED_TAU / FRAME_DT);
    int startup = moving && PRIOR_MODE && last_t - t_start < START_T;
    if (PRIOR_MODE == 3 && startup) { /* whitened camera-axis prior with nonzero mean */
        double Rwc[9], mu[3] = {START_MEAN_X, START_MEAN_Y, START_MEAN_FWD}, sd[3] = {START_STD_X, START_STD_Y, START_STD_Z}, vc[3];
        m3mul(R, R_bc, Rwc);
        m3tvec(Rwc, vel, vc);
        memset(Hs, 0, sizeof Hs);
        for (int i = 0; i < 3; i++) {
            r[i] = (mu[i] - vc[i]) / (sd[i] * scale);
            for (int j = 0; j < 3; j++) Hs[i * MAXD + V + j] = Rwc[3 * j + i] / (sd[i] * scale);
        }
        update(r, Hs, 3, 1.0, PRIOR_GATE);
        return;
    }
    double sh = SPEED_STD, sz = SPEED_STD;
    if (startup && PRIOR_MODE == 1) sh = sz = START_STD;
    if ((PRIOR_MODE == 2 && moving && (startup || ANISO_ALWAYS)) || (PRIOR_MODE == 3 && POST_ANISO && moving)) { sh = SPEED_STD_H; sz = SPEED_STD_Z; }
    memset(Hs, 0, sizeof Hs);
    double sd3[3] = {sh * scale, sh * scale, sz * scale};
    for (int i = 0; i < 3; i++) { Hs[i * MAXD + V + i] = 1 / sd3[i]; r[i] = -vel[i] / sd3[i]; }
    update(r, Hs, 3, 1.0, PRIOR_GATE);
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
static void remove_oldest_clone(void) {
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
    double a = 2.0 / (9.0 * dof), b = 1 - a + chi2_z * sqrt(a);
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
    if (lmin < tri_min_eig * lmax) return 0;
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
    if (o.n < min_obs) return 0;
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
    if (!cholesky(Sm, k0)) return 0;
    double y[2 * MAX_OBS];
    memcpy(y, r0, k0 * sizeof(double));
    chol_solve(Sm, k0, y);
    double m2 = 0;
    for (int a = 0; a < k0; a++) m2 += r0[a] * y[a];
    if (m2 > chi2_quantile(k0)) return 0;
    if (*nrows + k0 > MAX_ROWS) return 0;
    for (int a = 0; a < k0; a++) {
        memcpy(Hbig + (*nrows + a) * MAXD, H0 + a * MAXD, D * sizeof(double));
        rbig[*nrows + a] = r0[a];
    }
    *nrows += k0;
    return 1;
}

/* one EKF update for a batch of features. The stacked rows are zero on the 18 core columns, so a stack taller than
   the clone columns is QR-compressed (Householder on [H | r]) over those columns only: same information, fewer rows */
static void msckf_update(Obs *batch, int nbatch) {
    int nrows = 0;
    for (int b = 0; b < nbatch; b++) feature_rows(&batch[b], &nrows);
    if (!nrows) return;
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
    update(rbig, Hbig, nrows, (PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY);
}

/* =====================================================================================================================
 * Image front end
 * ===================================================================================================================== */

/* gray (77 R + 150 G + 29 B + 128) >> 8, then LEVELS - 1 halvings by 2x2 means */
static void build_pyramid(const uint8_t *rgb, int which) {
    uint8_t *g = pyr[which][0];
    for (int i = 0; i < IMG_W * IMG_H; i++) g[i] = (uint8_t)((77 * rgb[3 * i] + 150 * rgb[3 * i + 1] + 29 * rgb[3 * i + 2] + 128) >> 8);
    for (int L = 1; L < LEVELS; L++) {
        int w = IMG_W >> L, h = IMG_H >> L, ws = IMG_W >> (L - 1);
        const uint8_t *s = pyr[which][L - 1];
        uint8_t *d = pyr[which][L];
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
                d[y * w + x] = (uint8_t)((s[2 * y * ws + 2 * x] + s[2 * y * ws + 2 * x + 1] + s[(2 * y + 1) * ws + 2 * x] + s[(2 * y + 1) * ws + 2 * x + 1] + 2) >> 2);
    }
}

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

/* Shi-Tomasi: smaller eigenvalue of the 3x3 sum of gradient outer products (central differences) */
static double corner_score(const uint8_t *I, int x, int y) {
    double sxx = 0, syy = 0, sxy = 0;
    for (int v = -1; v <= 1; v++)
        for (int u = -1; u <= 1; u++) {
            const uint8_t *p = I + (y + v) * IMG_W + x + u;
            int gx = p[1] - p[-1], gy = p[IMG_W] - p[-IMG_W];
            sxx += gx * gx; syy += gy * gy; sxy += gx * gy;
        }
    return 0.5 * (sxx + syy) - sqrt(0.25 * (sxx - syy) * (sxx - syy) + sxy * sxy);
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
    for (int k = 0; k < MAX_TRACKS && nfree > 0; k++) {
        int cell = (detect_cursor + k) % MAX_TRACKS;
        if (occupied[cell]) continue;
        int x0 = (cell % GRID_X) * CELL_W, y0 = (cell / GRID_X) * CELL_H;
        double best = DETECT_MIN_SCORE;
        int bx = -1, by = -1;
        for (int y = y0 + 1; y < y0 + CELL_H; y += 2) {
            if (y < BORDER || y >= IMG_H - BORDER) continue;
            for (int x = x0 + 1; x < x0 + CELL_W; x += 2) {
                if (x < BORDER || x >= IMG_W - BORDER) continue;
                double s = corner_score(I, x, y);
                if (s > best) { best = s; bx = x; by = y; }
            }
        }
        if (bx >= 0) {
            Track *t = &tracks[free_slot[--nfree]];
            t->alive = 1; t->x = bx; t->y = by; t->obs.n = 0;
        }
    }
    detect_cursor = (detect_cursor + 7) % MAX_TRACKS;
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
        m3vec(Rrel, ray, rp);
        double gx = t->x, gy = t->y;
        if (rp[2] > 1e-3) { gx = fx * rp[0] / rp[2] + cx; gy = fy * rp[1] / rp[2] + cy; }
        double nx, ny;
        if (klt(prev, cur, t->x, t->y, gx, gy, &nx, &ny) && nx >= 0 && ny >= 0 && nx < IMG_W && ny < IMG_H) {
            t->x = nx; t->y = ny;
        } else {
            t->alive = 0;
            if (t->obs.n >= min_obs && nlost < 2 * MAX_TRACKS) lost[nlost++] = t->obs;
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
static void vision(const uint8_t *frame) {
    int prev = cur_pyr, cur = 1 - cur_pyr;
    build_pyramid(frame, cur);
    double Rwc_now[9];
    m3mul(R, R_bc, Rwc_now);
    track_all(prev, cur, Rwc_now);
    {
        int fast = FAST_FRAMES > 0 && frame_no < FAST_FRAMES && (moving || FAST_ALL);
        clone_every = fast ? FAST_CLONE_EVERY : CLONE_EVERY;
        min_obs = fast ? FAST_MIN_OBS : MIN_OBS;
        tri_min_eig = fast ? FAST_TRI_EIG : TRI_MIN_EIG;
        chi2_z = fast ? FAST_CHI2_Z : CHI2_Z;
        frame_no++;
    }
    if (++frames_since_clone >= clone_every) {
        frames_since_clone = 0;
        add_clone();
        record_observations();
        vision_zupt();
        int nb = 0;
        for (int i = 0; i < nlost && nb < MAX_BATCH; i++) batch[nb++] = lost[i];
        nlost = 0;
        if (nclones > MAX_CLONES) {
            int oldest = clones[0].id;
            for (int i = 0; i < MAX_TRACKS && nb < MAX_BATCH; i++) {
                Obs *o = &tracks[i].obs;
                if (tracks[i].alive && o->n >= min_obs && o->cid[0] == oldest) take_for_update(o, batch, &nb);
            }
            msckf_update(batch, nb);
            remove_oldest_clone();
            for (int i = 0; i < MAX_TRACKS; i++) { /* drop the remaining observations in the marginalized clone */
                Obs *o = &tracks[i].obs;
                int k = 0;
                for (int j = 0; j < o->n; j++)
                    if (o->cid[j] != oldest) { o->cid[k] = o->cid[j]; o->x[k] = o->x[j]; o->y[k] = o->y[j]; k++; }
                o->n = k;
            }
        } else {
            msckf_update(batch, nb);
        }
    } else {
        int nb = 0, take = nlost < MAX_UPDATE_FEATURES ? nlost : MAX_UPDATE_FEATURES;
        for (int i = 0; i < take; i++) batch[nb++] = lost[i];
        memmove(lost, lost + take, (nlost - take) * sizeof(Obs));
        nlost -= take;
        if (nclones == MAX_CLONES) { /* the next clone pushes clones[0] out */
            int oldest = clones[0].id, phase = frames_since_clone - 1;
            for (int i = phase; i < MAX_TRACKS && nb < MAX_BATCH; i += clone_every - 1) {
                Obs *o = &tracks[i].obs;
                if (tracks[i].alive && o->n >= min_obs && o->cid[0] == oldest) take_for_update(o, batch, &nb);
            }
        }
        msckf_update(batch, nb);
    }
    detect(cur);
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
        frame_no = 0; clone_every = CLONE_EVERY; min_obs = MIN_OBS; tri_min_eig = TRI_MIN_EIG;
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
    for (int r = 0; r < imu_count; r++) propagate(imu + 7 * r);
    if (imu_count) imu_measurements(imu, imu_count);

    if (learn_active && (LEARN_MODE & 2) && ++learn_n == LEARN_K) {
        double sd[3], r[3];
        for (int i = 0; i < 3; i++) sd[i] = learn_sd(learn_row->sdK[i]) * LEARN_B_INFLATE;
        memset(Hs, 0, sizeof Hs);
        for (int i = 0; i < 3; i++) {
            double vb = R[i] * vel[0] + R[3 + i] * vel[1] + R[6 + i] * vel[2]; /* body-frame velocity of the filter */
            r[i] = (learn_row->muK[i] - vb) / sd[i];
            for (int j = 0; j < 3; j++) Hs[i * MAXD + V + j] = R[3 * j + i] / sd[i];
        }
        fprintf(stderr, "LEARN K update pred_b=%.3f %.3f %.3f filt_b=%.3f %.3f %.3f\n", learn_row->muK[0], learn_row->muK[1], learn_row->muK[2],
                r[0] * sd[0] * -1 + learn_row->muK[0], r[1] * sd[1] * -1 + learn_row->muK[1], r[2] * sd[2] * -1 + learn_row->muK[2]);
        update(r, Hs, 3, 1.0, INFINITY);
    }
    vision(frame);
    write_state(out);
    return VIOBENCH_STATUS_OK;
}
