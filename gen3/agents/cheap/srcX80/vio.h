// classical/vio: a lean monocular visual-inertial EKF for stage 2 (raw ATE on agile flights). No dependencies.
//
// World frame W = the IMU frame at frame 0, so the pose at frame 0 is exactly the identity and the unknown tilt lives
// in a gravity state instead of in the initial orientation (the score is the raw position error in frame-0 axes).
//
// Error state (NC = 17): attitude (body perturbation, R = R^ Exp(dtheta)), position, velocity, gyro bias,
// accelerometer bias, gravity direction (2 dof on the sphere of radius G).  Then MAXA anchor poses (6 each: clones of the
// body pose at the frames where features were detected) and MAXF log inverse depths, one per feature.  A feature is the
// centre of the 8x8 patch cut out of its anchor frame, so its bearing there is exact by definition and only its depth
// is estimated; the logarithm keeps the depth positive and its uncertainty relative, which is what stops the filter
// from pushing every feature to infinity to explain a velocity error (the monocular collapse).  The layout is fixed:
// unused slots have zero rows and columns.
//
// Per frame: IMU propagation (state per sample, covariance once with the composed transition); for the features whose
// turn it is, the predicted pixel and 2x2 patch warp from the filter state, inverse-compositional alignment of the
// anchor template (coarse to fine as far as the predicted uncertainty requires) and a gated 2-d EKF update, all
// linearised at the propagated state and injected once; then new features on a new anchor when slots are free.
//
// Fuel (one unit per executed wasm operator, the score is the worst frame) shapes the code: the covariance is float32
// and every pass over it is 4 lanes wide, the level-0 image is never built (patches are sampled from the green bytes
// of the RGB frame), levels 1 and 2 are built with byte shuffles, and the number of feature updates, alignment passes
// and new features per frame is capped so that the worst frame costs about what the usual one does.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>
#if defined(__wasm_simd128__)
#include <wasm_simd128.h>
#endif

#ifndef VIO_MAXA
#define VIO_MAXA 5
#endif
#ifndef VIO_MAXF
#define VIO_MAXF 24
#endif

namespace vio {

const int W = 320, H = 240;
const int MAXA = VIO_MAXA, MAXF = VIO_MAXF;
#ifndef VIO_NC
#define VIO_NC 17
#endif
const int NC = VIO_NC;  // agents/cheap: 20 = + velocity clone (net measurement epoch)
const int NS = NC + 6 * MAXA + MAXF, NSP = (NS + 3) & ~3, NCH = NSP / 4;
const int TP = 8, TN = TP * TP, LEVELS = 3;  // template side (its centre lies between pixels), pixels, pyramid levels
const double G = 9.81;

typedef float f4 __attribute__((vector_size(16), aligned(4)));
typedef int i4 __attribute__((vector_size(16), aligned(4)));
static inline f4 splat(float x) { return (f4){x, x, x, x}; }
static inline float hsum(f4 v) { return (v[0] + v[1]) + (v[2] + v[3]); }

// tunables: X(name, default)
#define VIO_PARAMS(X) \
    X(sig_g, 0.07 / 14.1421356) /* gyro white noise density, rad/s/sqrt(Hz): 0.07 per sample at 200 Hz */ \
    X(sig_a, 0.28 / 14.1421356) /* accelerometer white noise density */ \
    X(sig_bg, 0.0006) X(sig_ba, 0.001) /* bias random walks */ \
    X(q_scale, 1.0) /* inflation of the white-noise process noise */ \
    X(init_bg, 0.012) X(init_ba, 0.12) X(init_v, 2.0) X(init_tilt, 0.3) /* prior sigmas; the velocity one must cover a start in mid-flight */ \
    X(stage, 1.0) /* share of the bias prior sigmas (gyro, accelerometer z) in force until the velocity has converged */ \
    X(scale_q0, 0.0) X(scale_q, 0.0) X(scale_frames, 60) /* scale-gauge sigma added per frame: right after a (re)start, in the long run, and the frames in between */ \
    X(g_body, 1) /* gravity starts along body z (thrust-only specific force) instead of along the measured specific force */ \
    X(px_sigma, 0.4) /* measurement noise, pixels at 320 wide */ \
    X(img_sigma, 1.5) /* grey-level noise behind the alignment covariance (large along edges); the frames are rendered without noise */ \
    X(gate, 9.2) /* chi2 gate, 2 dof */ \
    X(rho0, 0.5) X(rho_log_sigma, 0.7) /* prior inverse depth (1/m) and the sigma of its logarithm */ \
    X(rho_min, 0.01) X(rho_max, 10.0) \
    X(rho_corr, 0) X(rho_ind, 0.5) X(rho_common, 0.5) /* correlated depth priors: on/off, sigma of a feature's own log depth, sigma of the scene's */ \
    X(scene_sigma, 0.0) /* sigma (log) of the scene-depth prior applied to the median feature every 2 s; 0: off */ \
    X(rho_pull, 0.3) /* share of the way (in log) a new feature's depth prior moves from the median of the tracked ones to rho0 */ \
    X(nfeat, VIO_MAXF) X(nanchor, VIO_MAXA) /* active limits */ \
    X(min_new, 4) /* free feature slots that trigger a new anchor */ \
    X(min_batch, 1) /* new features a new anchor needs at least (unless few are alive) */ \
    X(evict_max, 2) /* with every anchor in use, one holding at most this many features may be replaced */ \
    X(reserve_new, 4) /* templates' worth of budget kept back from tracking when slots are free */ \
    X(sigma_full, 1) /* the search level also accounts for the velocity uncertainty */ \
    X(anchor_gap, 2) /* frames between anchors at least */ \
    X(max_new, VIO_MAXF) X(max_cells, 48) /* new features and detection cells per frame at most (the budget usually binds first) */ \
    X(det_thresh, 2.0) /* corner score: min eigenvalue of the structure tensor per pixel of a 4x4 level-1 window */ \
    X(border, 14) /* a feature is dropped closer than this to the image border */ \
    X(zncc_min, 0.75) X(max_fail, 2) X(passes, 2) X(coarse_passes, 2) /* alignment passes at level 0 / at a coarser level at most */ \
    X(coarse_sigma, 2.5) /* predicted pixel sigma above which alignment starts at level 2 */ \
    X(mid_sigma, 0.0) /* ... above which it starts at level 1 (below: level 0 only) */ \
    X(young, 3) /* a feature is used every frame until it has this many updates */ \
    /* work budget per frame in thousands of fuel units, and what each piece of work is charged (bench.py) */ \
    X(budget, 250) X(cost_update, 19.5) X(cost_edge, 13.0) X(cost_pass, 1.85) X(cost_cell, 4.9) X(cost_template, 8.8) X(cost_anchor, 5.0) \
    X(bank_frames, 0) X(bank_budget, 250) X(bank_spread, 1.8) /* depth hypotheses at the start (see solution.cpp): frames they run side by side (0: off), work budget of each, ratio between neighbours */ \
    X(edge_fill, VIO_MAXF / 2) /* edge features are added while fewer features than this are alive; 0: corners only */ \
    X(edge_thresh, 8.0) /* edge candidate: largest eigenvalue of the structure tensor per pixel, level 1 */ \
    X(edge_min, 3.0) /* gradient energy across the edge per pixel that every level of an edge template needs */ \
    X(edge_sigma, 0.5) /* measurement noise across an edge, pixels */ \
    X(rescue, 0.0) /* velocity sigma (m/s) added when most aligned features fail the gate; 0 disables */ \
    X(force_edge, 0) /* test switch: every feature is treated as an edge */ \
    X(second_order, 0.0) /* weight of the second-order depth term in the feature updates */ \
    X(seed, 1) X(seed_var, 0.25) X(seed_px, 2.0) /* start-up relinearisation: on while the velocity variance (m2/s2) exceeds seed_var; pixel sigma of its least squares */ \
    X(vprior, 0.0) /* sigma of a zero-velocity prior applied twice a second per axis (m/s); 0 disables */ \
    X(thrust_sigma, 0.1) /* body x/y specific force is zero (no drag): observes accelerometer bias x/y; 0 disables */ \
    X(scale_lo, 0.45) X(scale_hi, 2.6) /* patch scale change beyond which a feature is dropped */ \
    X(min_ratio, 0.08) X(min_eig, 0.7) /* corner test on the template's structure tensor at every level */ \
    X(watchdog, 1) X(max_speed, 6.0) X(ba_max, 0.4) X(bg_max, 0.05) X(nis_bad, 1.8) X(max_streak, 20) X(rho_floor, 0.07) X(max_far, 20) /* watchdog: what counts as diverged */ \
    X(gprior, 0.0) X(up_tau, 2.0) /* sigma (rad) of the weak gravity prior from the low-passed specific force; its time constant */ \
    X(debug, 0)

struct Params {
#define X(name, value) double name = value;
    VIO_PARAMS(X)
#undef X
};

// ---------------------------------------------------------------- small linear algebra (double)
struct V3 {
    double x, y, z;
};
inline V3 operator+(V3 a, V3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
inline V3 operator-(V3 a, V3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline V3 operator*(V3 a, double s) { return {a.x * s, a.y * s, a.z * s}; }
inline double dot(V3 a, V3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
inline V3 cross(V3 a, V3 b) { return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x}; }
inline double norm(V3 a) { return std::sqrt(dot(a, a)); }

struct M3 {
    double m[9];
    double &operator()(int r, int c) { return m[3 * r + c]; }
    double operator()(int r, int c) const { return m[3 * r + c]; }
};
inline M3 identity() { return {{1, 0, 0, 0, 1, 0, 0, 0, 1}}; }
inline M3 operator*(const M3 &a, const M3 &b) {
    M3 c;
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) c.m[3 * i + j] = a.m[3 * i] * b.m[j] + a.m[3 * i + 1] * b.m[3 + j] + a.m[3 * i + 2] * b.m[6 + j];
    return c;
}
inline V3 operator*(const M3 &a, V3 v) { return {a.m[0] * v.x + a.m[1] * v.y + a.m[2] * v.z, a.m[3] * v.x + a.m[4] * v.y + a.m[5] * v.z, a.m[6] * v.x + a.m[7] * v.y + a.m[8] * v.z}; }
inline M3 transpose(const M3 &a) { return {{a.m[0], a.m[3], a.m[6], a.m[1], a.m[4], a.m[7], a.m[2], a.m[5], a.m[8]}}; }
inline V3 tmul(const M3 &a, V3 v) { return {a.m[0] * v.x + a.m[3] * v.y + a.m[6] * v.z, a.m[1] * v.x + a.m[4] * v.y + a.m[7] * v.z, a.m[2] * v.x + a.m[5] * v.y + a.m[8] * v.z}; }  // a^T v
inline M3 skew(V3 v) { return {{0, -v.z, v.y, v.z, 0, -v.x, -v.y, v.x, 0}}; }
inline M3 expm(V3 w) {  // Rodrigues; the series covers every per-sample and per-update angle without a libm call
    double t2 = dot(w, w), a, b;
    if (t2 < 0.09) {
        a = 1.0 - t2 * (1.0 / 6.0) * (1.0 - t2 * (1.0 / 20.0) * (1.0 - t2 * (1.0 / 42.0)));
        b = 0.5 - t2 * (1.0 / 24.0) * (1.0 - t2 * (1.0 / 30.0) * (1.0 - t2 * (1.0 / 56.0)));
    } else {
        double t = std::sqrt(t2);
        a = std::sin(t) / t;
        b = (1.0 - std::cos(t)) / t2;
    }
    double xx = w.x * w.x, yy = w.y * w.y, zz = w.z * w.z, xy = b * w.x * w.y, xz = b * w.x * w.z, yz = b * w.y * w.z;
    return {{1 - b * (yy + zz), xy - a * w.z, xz + a * w.y, xy + a * w.z, 1 - b * (xx + zz), yz - a * w.x, xz - a * w.y, yz + a * w.x, 1 - b * (xx + yy)}};
}
inline double exp_small(double x) {  // exp for the per-frame log-depth corrections
    if (x > -0.5 && x < 0.5) return 1.0 + x * (1.0 + x * (0.5 + x * (1.0 / 6.0 + x * (1.0 / 24.0 + x * (1.0 / 120.0 + x * (1.0 / 720.0))))));
    return std::exp(x);
}
inline void orthonormalize(M3 &R) {  // Gram-Schmidt on the columns
    V3 a{R.m[0], R.m[3], R.m[6]}, b{R.m[1], R.m[4], R.m[7]};
    a = a * (1.0 / norm(a));
    b = b - a * dot(a, b);
    b = b * (1.0 / norm(b));
    V3 c = cross(a, b);
    R = {{a.x, b.x, c.x, a.y, b.y, c.y, a.z, b.z, c.z}};
}
inline void to_quaternion(const M3 &R, double *q) {  // [x, y, z, w]
    double tr = R.m[0] + R.m[4] + R.m[8];
    if (tr > 0) {
        double s = std::sqrt(tr + 1.0) * 2;
        q[3] = 0.25 * s, q[0] = (R.m[7] - R.m[5]) / s, q[1] = (R.m[2] - R.m[6]) / s, q[2] = (R.m[3] - R.m[1]) / s;
    } else if (R.m[0] > R.m[4] && R.m[0] > R.m[8]) {
        double s = std::sqrt(1.0 + R.m[0] - R.m[4] - R.m[8]) * 2;
        q[3] = (R.m[7] - R.m[5]) / s, q[0] = 0.25 * s, q[1] = (R.m[1] + R.m[3]) / s, q[2] = (R.m[2] + R.m[6]) / s;
    } else if (R.m[4] > R.m[8]) {
        double s = std::sqrt(1.0 + R.m[4] - R.m[0] - R.m[8]) * 2;
        q[3] = (R.m[2] - R.m[6]) / s, q[0] = (R.m[1] + R.m[3]) / s, q[1] = 0.25 * s, q[2] = (R.m[5] + R.m[7]) / s;
    } else {
        double s = std::sqrt(1.0 + R.m[8] - R.m[0] - R.m[4]) * 2;
        q[3] = (R.m[3] - R.m[1]) / s, q[0] = (R.m[2] + R.m[6]) / s, q[1] = (R.m[5] + R.m[7]) / s, q[2] = 0.25 * s;
    }
}

// ---------------------------------------------------------------- records
struct Feature {
    bool alive = false;
    int anchor = 0;
    double bx, by;       // normalized image coordinates of the patch centre in the anchor camera
    double ax, ay;       // patch centre in the anchor frame, level-0 pixels (integer + 0.5)
    double rho;          // inverse z-depth in the anchor camera
    double px, py;       // last measured pixel
    float A[4];          // predicted patch warp, anchor -> current frame
    int age = 0, fails = 0, used = 0;
    int mframe = -100, pframe = -100; double ppx = 0, ppy = 0;  // agents/cheap: frame of the last / previous measurement (ZUPT)
    bool edge = false;   // an edge feature: only its position across the edge is measured
    float nx, ny;        // unit normal of the edge in template coordinates
    bool level_ok[LEVELS];
    // per level: zero-mean template, the two rows of (inverse structure tensor) x (zero-mean gradient), their products
    // with the template, the template energy and the inverse structure tensor itself
    alignas(16) float T[LEVELS][TN], cx[LEVELS][TN], cy[LEVELS][TN];
    float cT[LEVELS][2], TT[LEVELS], Gi[LEVELS][3];
};

struct Anchor {
    bool alive = false;
    M3 R;
    V3 p;
    int count = 0;
    // per frame: camera-k coordinates (times rho) of the anchor-camera point b / rho are  Rrel b + rho t
    M3 Rrel;
    V3 t;
};

struct Vio {
    Params P;
    double fx, fy, cx, cy;
    M3 Rcb;  // camera <- body
    V3 tcb, tbc;
    M3 R;
    V3 p, v, bg, ba, g, b1, b2;
    Anchor anchors[MAXA];
    Feature feats[MAXF];
    alignas(16) float C[NS][NSP];  // covariance
    alignas(16) float dx[NSP];     // error state accumulated over the updates of one frame
    alignas(16) uint8_t pyr1[(W / 2) * (H / 2) + 64], pyr2[(W / 4) * (H / 4) + 64];
    const uint8_t *green = nullptr;  // level 0: the green bytes of the current RGB frame (stride 3)
    const uint8_t *l1 = nullptr, *l2 = nullptr;  // levels 1 and 2 of this frame (this instance's buffers, or another's)
    int frame = 0, last_anchor_frame = -100, scan_cell = 0, rr = 0, streak = 0, far = 0, restart_frame = 0;
    bool staged = false;
    V3 up_lp;  // low-passed specific force in world axes
    V3 scale_origin{0, 0, 0};  // the position at the last (re)start: where a change of scale leaves the position alone
    double scale_step = 0, scale_log = 0;  // this frame's revision of the map scale (log), and its sum
    int scene_ref = -1;
    double rho_med = 0.4;  // median inverse depth of the established features in the current frame
    double nis = 1.0;  // running mean of the normalised innovation squared per degree of freedom (about 1 when healthy)
    double spent = 0;  // work charged to this frame's budget
    double budget_now = 250;
    V3 gyro_mean, acc_mean;
    double thrust_sum[2] = {0, 0};
    int thrust_count[2] = {0, 0}, thrust_checks = 0, thrust_misfits = 0;
    bool thrust_on = true;
    double last_t = 0;
    double last_out[13];
    int n_tracked = 0, n_updated = 0, n_alive = 0, n_new = 0, n_passes = 0, n_tried = 0;
#ifdef VIO_DIAG
    struct {
        int restarts[5] = {0, 0, 0, 0, 0};  // by cause: innovation consistency, scale, speed, accelerometer bias, gyro bias
        int first_restart = -1, blackout = 0, run = 0, longest = 0, longest_start = 0;  // frames without any accepted update
        double speed10 = 0, speed40 = 0, alive_sum = 0, rho2 = 0, lrho = 0, lrho10 = 0;
        int nrho = 0, nrho10 = 0, hypothesis = 0;  // 1..: which depth hypothesis of the start was kept (0: no bank)
    } diag;
#endif
    // counters: kills by border / scale, alignment failures (lost, low correlation), gated updates, kills after
    // repeated alignment / gate failures, anchor requests refused, cells examined, cells with a candidate, templates
    // rejected / made, anchors made, anchors evicted
    int stats[20] = {};

    // ---- agents/cheap hybrid (our priors, Manhattan lines, ZUPT, net velocity clone); see hyb.inc
    V3 vk{0, 0, 0}; M3 Rk = identity(); int vk_ok = 0, vk_restarts = 0, net_landed = 0;
    int moving = 1, hold_on = 1, zupt_n = 0, ln_v = 0, ln_y = 0;
    double my_c = 0, my_s = 0, my_phi = 0; int my_n = 0, my_fixed = 0;
    M3 Rhist[16]; V3 Rk_my{1, 0, 0};
    void update_row(const int *idx, const double *h, int n, double r, double var);
    void hyb_frame0(const double *imu, int count);
    void hyb_priors();
    void hyb_vision();
    void hyb_post();
    void clone_vk();
    void net_measure(const double *mu, const double *sd, double floor_v, double scale_sig);
    void init(double fx_, double fy_, double cx_, double cy_, const double *T_cam_imu);
    void step(double t, const uint8_t *rgb, const double *imu, int count, double *out, const Vio *pyramid_of = nullptr);

    void build_pyramid(const uint8_t *rgb);
    void propagate(const double *imu, int count);
    void anchor_frames();
    bool project(const Feature &f, int ir, double &u, double &v_, float *A, double &sigma) const;
    void track_and_update();
    bool pass(int m, float x, float y, const float *A, float k, const Feature &f, int l, float &ddx, float &ddy, float &zncc) const;
    bool rows_of(int i, float *h0, float *h1, float &r0, float &r1) const;
    bool update_feature(int i, double zu, double zv);
    bool update_edge(int i, double zu, double zv);
    void update_state(int k, double r, double var);
    void inject();
    void kill_feature(int i);
    void update_att(const double *h, double r, double var);
    void restart(bool first);
    void scene_median();
    void inflate_scale(double sigma);
    void add_features();
    void clone_anchor(int slot);
    bool make_template(Feature &f, bool allow_edge);
    void output(double *out);
};

}  // namespace vio
