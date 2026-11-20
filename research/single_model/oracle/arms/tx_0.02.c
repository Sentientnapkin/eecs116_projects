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
#define INIT_TILT_STD 0.02     /* rad */
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

#define ORACLE_VEL 0
#define ORACLE_VEL_NOISE 0.0
#define ORACLE_TILT 1
#define ORACLE_TILT_NOISE 0.0

#include <stdio.h>
/* generated by gen_table.py: ORACLE ONLY, uses ground truth */
typedef struct { double fx, fy, cx, cy, vb[3], up[3]; } OracleRow;
#define ORACLE_N 171
static const OracleRow oracle_rows[ORACLE_N] = {
  {88.4077,88.4077,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-102344193-01 */
  {87.9441,87.9441,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-102344457-00 */
  {72.8851,72.8851,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-102344469-01 */
  {94.3253,94.3253,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-103997445_171030492-01 */
  {114.0989,114.0989,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-103997460_171030507-00 */
  {92.0347,92.0347,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-103997460_171030507-01 */
  {77.1017,77.1017,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-103997478_171030525-00 */
  {113.5955,113.5955,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-103997478_171030525-01 */
  {105.2089,105.2089,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-103997586_171030666-00 */
  {90.3972,90.3972,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-103997643_171030747-01 */
  {113.8834,113.8834,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-104348202_171513150-01 */
  {118.8929,118.8929,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-104348361_171513414-01 */
  {74.1457,74.1457,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-104862573_172226682-01 */
  {121.8023,121.8023,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-104862639_172226823-00 */
  {89.1634,89.1634,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-104862639_172226823-01 */
  {79.0890,79.0890,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-105515184_173104128-00 */
  {111.1720,111.1720,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-105515490_173104566-01 */
  {77.4098,77.4098,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-106366104_174226329-00 */
  {76.5297,76.5297,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-106366104_174226329-01 */
  {91.9643,91.9643,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-106366173_174226431-00 */
  {93.2051,93.2051,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-106366371_174226743-00 */
  {107.6195,107.6195,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-106366371_174226743-01 */
  {96.0322,96.0322,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-106366410_174226806-02 */
  {113.6220,113.6220,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-106878858_174886965-00 */
  {92.8849,92.8849,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-106878858_174886965-02 */
  {83.1242,83.1242,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-106879044_174887172-01 */
  {119.0871,119.0871,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-107734146_175999971-00 */
  {95.9801,95.9801,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-107734158_175999998-00 */
  {91.1487,91.1487,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-107734158_175999998-02 */
  {101.8943,101.8943,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-107734176_176000019-01 */
  {115.8889,115.8889,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-107734254_176000121-01 */
  {100.6853,100.6853,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-107734338_176000244-02 */
  {96.8518,96.8518,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-108294417_176709879-00 */
  {75.9796,75.9796,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-108294417_176709879-01 */
  {114.8847,114.8847,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-108294897_176710602-00 */
  {88.2693,88.2693,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-108736884_177263634-00 */
  {86.1050,86.1050,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-108736884_177263634-01 */
  {118.1689,118.1689,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-108736884_177263634-02 */
  {69.3527,69.3527,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-106-01 */
  {90.6297,90.6297,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-107-00 */
  {111.8153,111.8153,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-107-02 */
  {111.1302,111.1302,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-142-00 */
  {94.5495,94.5495,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-143-02 */
  {97.9130,97.9130,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-151-07 */
  {91.3919,91.3919,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-151-09 */
  {120.1486,120.1486,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-151-11 */
  {92.5904,92.5904,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-158-07 */
  {98.5324,98.5324,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-159-00 */
  {111.2599,111.2599,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-160-00 */
  {113.4029,113.4029,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-160-02 */
  {69.7073,69.7073,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-160-09 */
  {73.3945,73.3945,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-160-10 */
  {122.2610,122.2610,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-167-00 */
  {122.2356,122.2356,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-167-01 */
  {73.8718,73.8718,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-167-02 */
  {74.4266,74.4266,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-167-03 */
  {106.9823,106.9823,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-167-05 */
  {102.0056,102.0056,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-168-02 */
  {94.9447,94.9447,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-170-01 */
  {102.6203,102.6203,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-170-03 */
  {103.3400,103.3400,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-170-04 */
  {92.4456,92.4456,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-171-02 */
  {110.3655,110.3655,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-171-04 */
  {86.5441,86.5441,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-191-00 */
  {73.5748,73.5748,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-191-02 */
  {103.0086,103.0086,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-3-02 */
  {84.2377,84.2377,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-5-00 */
  {90.9259,90.9259,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-5-02 */
  {121.8189,121.8189,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-57-00 */
  {76.1613,76.1613,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-59-00 */
  {74.8497,74.8497,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-59-01 */
  {89.8569,89.8569,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-6-02 */
  {78.7962,78.7962,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-63-02 */
  {107.1038,107.1038,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-64-00 */
  {79.0574,79.0574,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-64-01 */
  {68.9050,68.9050,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-65-00 */
  {74.2868,74.2868,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-65-02 */
  {88.8617,88.8617,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-71-00 */
  {109.9168,109.9168,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-74-00 */
  {102.8827,102.8827,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-78-01 */
  {107.7387,107.7387,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-82-00 */
  {112.7460,112.7460,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-91-00 */
  {118.8001,118.8001,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-91-02 */
  {107.3565,107.3565,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-97-02 */
  {104.3975,104.3975,159.5000,119.5000,{0.000295,-0.000098,-0.061567},{-0.001713,0.000740,0.999998}}, /* fast-ProcTHOR-Train-98-01 */
  {79.4950,79.4950,159.5000,119.5000,{0.381167,0.009752,-0.140040},{0.008639,0.006972,0.999938}}, /* fastmid-102344280-00 */
  {71.5786,71.5786,159.5000,119.5000,{1.952539,-0.057834,-0.101474},{0.133650,-0.002876,0.991024}}, /* fastmid-102344280-01 */
  {93.6228,93.6228,159.5000,119.5000,{0.547248,-0.237990,-0.122638},{0.029218,0.029036,0.999151}}, /* fastmid-102344328-01 */
  {96.7124,96.7124,159.5000,119.5000,{-0.148956,1.487514,-0.180932},{-0.025937,0.207263,0.977941}}, /* fastmid-102344457-00 */
  {79.5925,79.5925,159.5000,119.5000,{-0.116556,0.005506,-0.010573},{0.045408,0.006415,0.998948}}, /* fastmid-102344457-01 */
  {82.9848,82.9848,159.5000,119.5000,{0.007106,0.209242,0.066333},{0.065710,0.001123,0.997838}}, /* fastmid-102815859-01 */
  {102.3805,102.3805,159.5000,119.5000,{0.735323,0.276427,-0.341460},{-0.074803,-0.028219,0.996799}}, /* fastmid-103997445_171030492-00 */
  {85.7511,85.7511,159.5000,119.5000,{0.725709,-0.019132,0.655690},{-0.052836,0.008453,0.998567}}, /* fastmid-103997460_171030507-00 */
  {85.7802,85.7802,159.5000,119.5000,{0.557275,-0.124128,0.033822},{-0.121117,0.038248,0.991901}}, /* fastmid-103997460_171030507-01 */
  {79.5419,79.5419,159.5000,119.5000,{0.102821,-0.425784,-0.195116},{0.088979,0.033942,0.995455}}, /* fastmid-103997478_171030525-00 */
  {104.1301,104.1301,159.5000,119.5000,{0.455464,0.105276,0.003918},{0.021247,-0.013195,0.999687}}, /* fastmid-103997586_171030666-02 */
  {103.5454,103.5454,159.5000,119.5000,{1.486310,0.586744,0.017888},{-0.110891,-0.114292,0.987239}}, /* fastmid-103997643_171030747-01 */
  {75.2063,75.2063,159.5000,119.5000,{0.569385,0.009985,-0.158259},{0.105951,0.007263,0.994345}}, /* fastmid-104348361_171513414-02 */
  {87.6109,87.6109,159.5000,119.5000,{1.684582,0.362057,-0.041724},{-0.078937,-0.126592,0.988809}}, /* fastmid-104862501_172226556-00 */
  {108.5906,108.5906,159.5000,119.5000,{0.278635,0.013707,0.701981},{-0.066715,-0.007396,0.997745}}, /* fastmid-104862501_172226556-01 */
  {76.5713,76.5713,159.5000,119.5000,{1.416459,2.039111,0.373652},{0.034843,0.081617,0.996055}}, /* fastmid-104862639_172226823-01 */
  {68.7040,68.7040,159.5000,119.5000,{0.337029,0.192254,0.198995},{-0.037536,-0.033009,0.998750}}, /* fastmid-105515184_173104128-02 */
  {81.9722,81.9722,159.5000,119.5000,{1.401541,0.007669,0.145999},{-0.018276,-0.002806,0.999829}}, /* fastmid-105515301_173104305-01 */
  {111.3940,111.3940,159.5000,119.5000,{1.372421,0.072558,-0.039020},{0.082120,0.005403,0.996608}}, /* fastmid-106366104_174226329-00 */
  {66.4430,66.4430,159.5000,119.5000,{0.359318,0.017686,-0.074631},{0.159786,0.000344,0.987152}}, /* fastmid-106366104_174226329-01 */
  {106.1085,106.1085,159.5000,119.5000,{0.067208,-0.091022,0.006761},{0.008728,-0.007977,0.999930}}, /* fastmid-106366104_174226329-02 */
  {115.0267,115.0267,159.5000,119.5000,{0.646155,0.028087,-0.118450},{-0.006860,-0.009102,0.999935}}, /* fastmid-106366173_174226431-00 */
  {87.8315,87.8315,159.5000,119.5000,{0.114099,-0.208890,-0.260691},{0.084412,0.048089,0.995270}}, /* fastmid-106366371_174226743-00 */
  {98.1101,98.1101,159.5000,119.5000,{0.903876,-0.344366,0.152501},{-0.154341,0.141935,0.977770}}, /* fastmid-106366371_174226743-01 */
  {96.2088,96.2088,159.5000,119.5000,{0.076153,-0.035663,-0.081510},{-0.007135,0.046985,0.998870}}, /* fastmid-106366410_174226806-01 */
  {108.8293,108.8293,159.5000,119.5000,{1.904811,-0.484684,0.344951},{-0.102807,0.105001,0.989144}}, /* fastmid-106366410_174226806-02 */
  {116.8400,116.8400,159.5000,119.5000,{0.662923,0.021166,0.851092},{-0.041419,-0.009846,0.999093}}, /* fastmid-106878858_174886965-00 */
  {113.3954,113.3954,159.5000,119.5000,{1.167023,0.140363,-0.196332},{-0.237865,-0.113393,0.964657}}, /* fastmid-106878858_174886965-02 */
  {68.4866,68.4866,159.5000,119.5000,{-0.478601,1.380022,-0.003030},{0.084426,-0.133210,0.987485}}, /* fastmid-106879044_174887172-01 */
  {81.1057,81.1057,159.5000,119.5000,{1.319424,-0.019979,-0.148329},{0.236514,0.001365,0.971627}}, /* fastmid-107734146_175999971-00 */
  {77.9703,77.9703,159.5000,119.5000,{1.619014,0.002007,0.515063},{-0.155665,-0.001070,0.987809}}, /* fastmid-107734146_175999971-01 */
  {100.3813,100.3813,159.5000,119.5000,{0.535875,0.051868,0.054445},{0.039322,-0.032809,0.998688}}, /* fastmid-107734158_175999998-01 */
  {107.8703,107.8703,159.5000,119.5000,{0.112321,-0.117955,0.001924},{-0.013240,0.012949,0.999829}}, /* fastmid-107734176_176000019-00 */
  {89.9639,89.9639,159.5000,119.5000,{0.395835,0.187753,-0.212773},{0.122627,-0.024591,0.992148}}, /* fastmid-107734254_176000121-00 */
  {96.4145,96.4145,159.5000,119.5000,{0.347063,-0.002590,0.095254},{-0.029741,-0.004550,0.999547}}, /* fastmid-107734254_176000121-02 */
  {100.0815,100.0815,159.5000,119.5000,{0.770462,0.064778,0.520251},{-0.070258,-0.042351,0.996629}}, /* fastmid-108294417_176709879-00 */
  {85.5334,85.5334,159.5000,119.5000,{-1.023132,1.449121,0.501109},{0.144187,-0.115275,0.982813}}, /* fastmid-108294897_176710602-00 */
  {99.4934,99.4934,159.5000,119.5000,{-0.694723,-1.221405,0.431768},{0.160961,0.198232,0.966848}}, /* fastmid-108294897_176710602-01 */
  {78.8555,78.8555,159.5000,119.5000,{2.001121,-0.085024,-0.604179},{-0.085037,0.023667,0.996097}}, /* fastmid-108736884_177263634-00 */
  {79.9771,79.9771,159.5000,119.5000,{0.596307,0.121955,-0.547037},{0.010251,-0.014590,0.999841}}, /* fastmid-ProcTHOR-Train-0-01 */
  {69.7565,69.7565,159.5000,119.5000,{2.074852,0.009499,0.562271},{0.120498,-0.011141,0.992651}}, /* fastmid-ProcTHOR-Train-100-01 */
  {82.4209,82.4209,159.5000,119.5000,{-0.176970,-0.041420,0.269108},{0.046342,0.013035,0.998841}}, /* fastmid-ProcTHOR-Train-100-02 */
  {74.7624,74.7624,159.5000,119.5000,{0.629081,0.111835,0.315553},{0.093621,-0.073657,0.992880}}, /* fastmid-ProcTHOR-Train-101-02 */
  {110.5008,110.5008,159.5000,119.5000,{0.058706,-0.030484,0.023531},{0.037993,-0.029680,0.998837}}, /* fastmid-ProcTHOR-Train-107-00 */
  {76.7818,76.7818,159.5000,119.5000,{0.976288,-0.226638,-0.045367},{-0.016799,0.069241,0.997459}}, /* fastmid-ProcTHOR-Train-107-01 */
  {73.8254,73.8254,159.5000,119.5000,{1.059788,0.040139,0.162389},{-0.093548,0.006958,0.995590}}, /* fastmid-ProcTHOR-Train-107-02 */
  {98.3414,98.3414,159.5000,119.5000,{-0.352765,-0.127011,0.163585},{0.160094,0.065849,0.984903}}, /* fastmid-ProcTHOR-Train-123-00 */
  {76.8591,76.8591,159.5000,119.5000,{0.360732,0.030380,-0.161960},{0.011544,-0.017638,0.999778}}, /* fastmid-ProcTHOR-Train-141-01 */
  {68.0268,68.0268,159.5000,119.5000,{2.325121,0.004867,-0.758183},{0.162527,0.006715,0.986681}}, /* fastmid-ProcTHOR-Train-143-01 */
  {67.4738,67.4738,159.5000,119.5000,{0.642878,0.161686,0.067146},{-0.035953,0.004019,0.999345}}, /* fastmid-ProcTHOR-Train-143-02 */
  {90.2266,90.2266,159.5000,119.5000,{0.444030,0.857736,-0.123375},{0.027134,0.084981,0.996013}}, /* fastmid-ProcTHOR-Train-151-00 */
  {84.2874,84.2874,159.5000,119.5000,{1.014902,-0.522567,-0.091301},{0.129863,-0.065575,0.989361}}, /* fastmid-ProcTHOR-Train-151-07 */
  {77.7147,77.7147,159.5000,119.5000,{0.015600,-0.301467,-0.090181},{0.003013,-0.032208,0.999477}}, /* fastmid-ProcTHOR-Train-151-08 */
  {68.9073,68.9073,159.5000,119.5000,{0.317871,-1.176193,-0.439327},{0.037433,-0.156431,0.986979}}, /* fastmid-ProcTHOR-Train-151-10 */
  {95.7127,95.7127,159.5000,119.5000,{0.399123,0.112694,0.204394},{0.024271,0.018524,0.999534}}, /* fastmid-ProcTHOR-Train-154-09 */
  {99.2295,99.2295,159.5000,119.5000,{0.709833,0.008406,-0.435889},{-0.052975,0.006747,0.998573}}, /* fastmid-ProcTHOR-Train-158-03 */
  {70.6276,70.6276,159.5000,119.5000,{0.752444,-0.049870,0.191970},{-0.075924,0.012460,0.997036}}, /* fastmid-ProcTHOR-Train-158-05 */
  {113.5692,113.5692,159.5000,119.5000,{-0.074831,0.007471,0.012612},{0.224805,0.015875,0.974274}}, /* fastmid-ProcTHOR-Train-158-07 */
  {113.8360,113.8360,159.5000,119.5000,{-0.266687,-0.005491,0.030151},{0.057210,0.010101,0.998311}}, /* fastmid-ProcTHOR-Train-160-04 */
  {93.5341,93.5341,159.5000,119.5000,{0.909265,0.726422,0.210645},{0.094775,0.078211,0.992422}}, /* fastmid-ProcTHOR-Train-167-02 */
  {85.6608,85.6608,159.5000,119.5000,{0.992222,0.491217,0.213244},{-0.082016,-0.031801,0.996123}}, /* fastmid-ProcTHOR-Train-167-04 */
  {109.8299,109.8299,159.5000,119.5000,{0.656727,-0.075462,-0.153739},{0.031167,-0.010955,0.999454}}, /* fastmid-ProcTHOR-Train-169-02 */
  {89.3157,89.3157,159.5000,119.5000,{1.589201,0.041383,-0.532451},{0.316288,-0.003883,0.948655}}, /* fastmid-ProcTHOR-Train-170-03 */
  {69.4368,69.4368,159.5000,119.5000,{1.376128,-0.027088,-0.212489},{0.147376,-0.039729,0.988282}}, /* fastmid-ProcTHOR-Train-170-05 */
  {100.9119,100.9119,159.5000,119.5000,{1.282506,0.439455,-0.043397},{-0.000252,-0.001452,0.999999}}, /* fastmid-ProcTHOR-Train-177-00 */
  {89.3892,89.3892,159.5000,119.5000,{0.292069,-0.141806,0.331434},{0.079454,0.026178,0.996495}}, /* fastmid-ProcTHOR-Train-177-07 */
  {86.8242,86.8242,159.5000,119.5000,{-0.800389,0.282698,0.332127},{0.259844,-0.165480,0.951366}}, /* fastmid-ProcTHOR-Train-178-01 */
  {121.6217,121.6217,159.5000,119.5000,{0.210219,-0.240968,-0.304825},{0.012597,-0.027543,0.999541}}, /* fastmid-ProcTHOR-Train-191-02 */
  {75.7668,75.7668,159.5000,119.5000,{0.848605,0.020623,0.466972},{-0.179295,-0.020890,0.983573}}, /* fastmid-ProcTHOR-Train-3-00 */
  {90.5301,90.5301,159.5000,119.5000,{1.874388,-0.055502,0.524761},{-0.145682,-0.004785,0.989320}}, /* fastmid-ProcTHOR-Train-5-01 */
  {80.8690,80.8690,159.5000,119.5000,{0.090306,-0.186097,0.044266},{0.010639,-0.019150,0.999760}}, /* fastmid-ProcTHOR-Train-5-02 */
  {75.0147,75.0147,159.5000,119.5000,{-0.433859,1.031870,0.207666},{0.146587,-0.441611,0.885151}}, /* fastmid-ProcTHOR-Train-57-01 */
  {85.6775,85.6775,159.5000,119.5000,{1.400477,0.013929,-0.566797},{0.260326,0.035502,0.964868}}, /* fastmid-ProcTHOR-Train-57-02 */
  {112.4359,112.4359,159.5000,119.5000,{0.878435,0.587296,0.148101},{-0.184817,-0.202555,0.961673}}, /* fastmid-ProcTHOR-Train-59-01 */
  {111.3162,111.3162,159.5000,119.5000,{1.090134,-0.679897,-0.039044},{0.062267,-0.032666,0.997525}}, /* fastmid-ProcTHOR-Train-65-01 */
  {102.6689,102.6689,159.5000,119.5000,{1.841742,-0.284655,-0.479241},{-0.007948,-0.008104,0.999936}}, /* fastmid-ProcTHOR-Train-65-02 */
  {90.4877,90.4877,159.5000,119.5000,{0.244328,-0.648966,0.054378},{0.024115,-0.071401,0.997156}}, /* fastmid-ProcTHOR-Train-71-00 */
  {117.6737,117.6737,159.5000,119.5000,{-0.221391,0.062644,0.099487},{0.048361,-0.067831,0.996524}}, /* fastmid-ProcTHOR-Train-71-01 */
  {75.0719,75.0719,159.5000,119.5000,{1.550210,-0.062218,-0.791784},{0.058382,-0.004165,0.998286}}, /* fastmid-ProcTHOR-Train-71-02 */
  {76.4193,76.4193,159.5000,119.5000,{1.438949,0.008411,0.539309},{-0.045095,-0.006087,0.998964}}, /* fastmid-ProcTHOR-Train-72-01 */
  {98.0254,98.0254,159.5000,119.5000,{1.477736,-0.007532,0.466850},{-0.146080,-0.006386,0.989252}}, /* fastmid-ProcTHOR-Train-72-02 */
  {108.4935,108.4935,159.5000,119.5000,{0.948200,-0.121072,0.075468},{-0.203160,0.083012,0.975620}}, /* fastmid-ProcTHOR-Train-82-00 */
  {85.5892,85.5892,159.5000,119.5000,{-0.235199,-0.083604,-0.238131},{-0.040802,0.039723,0.998377}}, /* fastmid-ProcTHOR-Train-91-01 */
  {75.2862,75.2862,159.5000,119.5000,{1.071818,-0.085089,0.195588},{-0.034753,0.019069,0.999214}}, /* fastmid-ProcTHOR-Train-97-00 */
  {84.4268,84.4268,159.5000,119.5000,{1.401226,0.190862,-0.273280},{0.109487,0.021395,0.993758}}, /* fastmid-ProcTHOR-Train-97-02 */
  {85.0431,85.0431,159.5000,119.5000,{0.080836,0.093579,-0.257549},{0.010489,0.015922,0.999818}}, /* fastmid-ProcTHOR-Train-98-01 */
};

static const OracleRow *oracle_lookup(void) {
    for (int i = 0; i < ORACLE_N; i++)
        if (fabs(oracle_rows[i].fx - fx) < 2e-3 && fabs(oracle_rows[i].fy - fy) < 2e-3 &&
            fabs(oracle_rows[i].cx - cx) < 2e-3 && fabs(oracle_rows[i].cy - cy) < 2e-3) return &oracle_rows[i];
    return NULL;
}
static unsigned long long oracle_state;
static double oracle_gauss(const OracleRow *o) { /* deterministic per episode: LCG seeded from intrinsics */
    if (!oracle_state) oracle_state = (unsigned long long)(o->fx * 1e4) * 2654435761ULL + 88172645463325252ULL;
    double u[2];
    for (int k = 0; k < 2; k++) { oracle_state = oracle_state * 6364136223846793005ULL + 1442695040888963407ULL;
        u[k] = ((oracle_state >> 11) + 0.5) / 9007199254740992.0; }
    return sqrt(-2 * log(u[0])) * cos(2 * M_PI * u[1]);
}

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
    /* ORACLE tilt: roll/pitch from the true up direction in the body frame (R f_up = +z) */
    {
        const OracleRow *o = oracle_lookup();
        if (o && ORACLE_TILT) {
            double up[3] = {o->up[0], o->up[1], o->up[2]};
            align_to_z(up, R);
            if (ORACLE_TILT_NOISE > 0) { /* noisy estimate: tilt error ~ N(0, sigma) about the world x,y axes */
                double w[3] = {ORACLE_TILT_NOISE * oracle_gauss(o), ORACLE_TILT_NOISE * oracle_gauss(o), 0}, dR[9], Rn[9];
                exp_so3(w, dR); m3mul(dR, R, Rn); memcpy(R, Rn, sizeof R);
            }
        }
    }
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

    /* ORACLE velocity: true body-frame velocity rotated by the filter's initial R (world<-body) */
    {
        const OracleRow *o = oracle_lookup();
        if (o && ORACLE_VEL) {
            double v[3];
            for (int i = 0; i < 3; i++) v[i] = R[3*i]*o->vb[0] + R[3*i+1]*o->vb[1] + R[3*i+2]*o->vb[2];
            for (int i = 0; i < 3; i++) vel[i] = v[i] + ORACLE_VEL_NOISE * oracle_gauss(o);
            fprintf(stderr, "ORACLE hit v_world=%.4f %.4f %.4f vb=%.4f %.4f %.4f\n", vel[0], vel[1], vel[2], o->vb[0], o->vb[1], o->vb[2]);
        } else fprintf(stderr, "ORACLE %s\n", o ? "hit (vel off)" : "MISS");
    }
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
static void vision(const uint8_t *frame) {
    int prev = cur_pyr, cur = 1 - cur_pyr;
    build_pyramid(frame, cur);
    double Rwc_now[9];
    m3mul(R, R_bc, Rwc_now);
    track_all(prev, cur, Rwc_now);
    if (++frames_since_clone >= CLONE_EVERY) {
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
                if (tracks[i].alive && o->n >= MIN_OBS && o->cid[0] == oldest) take_for_update(o, batch, &nb);
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
            int oldest = clones[0].id, phase = frames_since_clone - 1; /* 0 .. CLONE_EVERY - 2 */
            for (int i = phase; i < MAX_TRACKS && nb < MAX_BATCH; i += CLONE_EVERY - 1) {
                Obs *o = &tracks[i].obs;
                if (tracks[i].alive && o->n >= MIN_OBS && o->cid[0] == oldest) take_for_update(o, batch, &nb);
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
    vision(frame);
    write_state(out);
    return VIOBENCH_STATUS_OK;
}
