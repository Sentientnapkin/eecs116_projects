"""Prototype VIO for viobench: IMU dead reckoning + sparse-feature gyro-bias / heading correction.

Pipeline (meant to be ported to C++ later; this Python version only answers "does it lower the error?"):
  1. IMU core, every frame: integrate the gyro (minus the estimated bias) for attitude, take gravity from the
     accelerometer, integrate a damped velocity (the course baseline's trick) for position.
  2. Vision, once per window (~1 s): pick ~40 corners at the window start, follow them frame to frame
     (gyro-predicted Lucas-Kanade), and at the window end compare where they went with where the gyro alone says they
     should be. The left-over rotation is the gyro's error: it corrects the attitude now and the bias for the future.
     Optionally the remaining (translational) motion steers the velocity direction.

The output is T_c0_ck and the twist, exactly as docs/ABI.md asks. `OPTIONS` can be overridden per instance by the
harness (run.py); the `oracle_*` attributes exist only for diagnostics and are never set on the server.
"""
import numpy as np
import cv2

GRAVITY = 9.81

DEFAULTS = dict(  # the chosen configuration is FINAL below; these are the building blocks' starting values

    vision=True,               # gyro-bias / attitude correction from tracked corners
    use_direction=False,       # also steer the velocity direction with the visual translation direction
    window_frames=20,          # frames between the window start and the correction (20 = 1 s)
    min_window_frames=5,       # a window that loses its tracks earlier than this is discarded
    keep_fraction=0.5,         # finish a window early once fewer than this fraction of its corners survive
    n_points=40,
    min_points=10,
    corner_quality=0.001,      # relative corner strength accepted (lower finds corners on plain walls too)
    stale_seconds=2.5,         # without a fresh vision answer for this long, the velocity fades to zero ...
    stale_decay_seconds=1.0,   # ... with this time constant (standing still is the safe guess)
    bias_gain=0.3,             # fraction of the measured bias error applied per window
    max_bias=0.06,             # rad/s, cap on the bias estimate
    max_rot_correction=0.08,   # rad, larger window corrections are rejected as outliers
    rot_apply=1.0,             # fraction of the window's rotation error removed from the current attitude
    pure_rotation_parallax=0.004,  # rad, median residual below which the window is treated as rotation only
    direction_gain=0.5,
    velocity_seconds=1.0,      # damping time constant of the velocity (course baseline: 1.0)
    fixed_speed=0.35,          # m/s: the speed assumed while the camera sees the drone moving
    retro=False,               # at each window end, redo the window's movement with the newly measured direction
    speed_mode="fixed",        # "fixed": fixed_speed while moving; "flow": typical_depth x measured translational flow
    typical_depth=2.5,         # m: assumed distance to the scene (tuned on the tuning flights only)
    speed_smoothing=0.5,       # weight of the newest flow speed measurement
    velocity_mode="imu",       # "imu": damped accelerometer integration; "visual": camera direction x speed;
                               # "filter": Kalman filter on [velocity, accelerometer bias] with camera direction/stop updates
    direction_frame="camera",  # between vision updates the direction of travel turns with the camera, or stays in "world"
    kf_accel_noise=0.15,       # m/s^2/sqrt(Hz): how fast velocity may wander between measurements
    kf_bias_noise=0.003,       # m/s^2/sqrt(s): how fast the accelerometer bias may wander
    kf_initial_speed_sigma=1.0,  # m/s: unknown velocity at the start (a start in flight)
    kf_direction_sigma=0.15,   # m/s per frame: "no velocity across the direction of travel"
    kf_stop_sigma=0.05,        # m/s per frame: "not moving"
    kf_speed_prior=0.5,        # m/s along the direction of travel, a weak pull ...
    kf_speed_prior_sigma=1.0,  # ... this loose
    kf_direction_timeout=2.5,  # s without a usable vision window before the direction is no longer trusted
    max_speed=4.0,
    moving_parallax=0.008,     # rad, median left-over motion of the corners above which the drone counts as moving
    tilt_seconds=2.0,
    calibration_seconds=0.5,
)

# The configuration chosen on the tuning flights (agile_a + public + 4 fast) and checked on held-out mixed flights.
# Solution uses it unless a harness overrides Solution.OPTIONS.
FINAL = dict(
    velocity_mode="visual",    # velocity = camera direction of travel x speed (stop when the camera sees no motion)
    retro=True,                # redo each window's movement once its direction is known
    speed_mode="blend",        # speed = geometric middle of 0.35 m/s and the camera's flow speed
    typical_depth=3.0,
    speed_smoothing=0.3,
    rot_apply=0.5,             # half of the camera's rotation correction into the attitude ...
    bias_gain=0.05,            # ... and a slow gyro-bias update
    keep_fraction=0.0,         # windows run their full second unless the corners are lost
    min_window_frames=8,
)

REST_ACCEL_STD = 1.0
REST_GYRO_STD = 0.2
MAX_GYRO_BIAS_AT_REST = 0.05
GRAVITY_TOLERANCE = 0.1 * GRAVITY


# ---------------------------------------------------------------- small rotation helpers
def skew(v):
    return np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])


def skew_batch(v):
    out = np.zeros((len(v), 3, 3))
    out[:, 0, 1], out[:, 0, 2] = -v[:, 2], v[:, 1]
    out[:, 1, 0], out[:, 1, 2] = v[:, 2], -v[:, 0]
    out[:, 2, 0], out[:, 2, 1] = -v[:, 1], v[:, 0]
    return out


def exp_so3(omega):
    angle = np.linalg.norm(omega)
    if angle < 1e-12:
        return np.eye(3) + skew(omega)
    K = skew(omega / angle)
    return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * K @ K


def project_rotation(R):
    U, _, Vt = np.linalg.svd(R)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1
        R = U @ Vt
    return R


def matrix_to_quaternion(R):
    trace = np.trace(R)
    if trace > 0:
        s = np.sqrt(trace + 1.0) * 2
        return np.array([(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s])
    i = int(np.argmax(np.diag(R)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = np.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2
    q = np.empty(4)
    q[i] = 0.25 * s
    q[j] = (R[j, i] + R[i, j]) / s
    q[k] = (R[k, i] + R[i, k]) / s
    q[3] = (R[k, j] - R[j, k]) / s
    return q / np.linalg.norm(q)


def huber_weights(residuals, scale):
    scale = max(scale, 1e-9)
    r = np.abs(residuals) / scale
    return np.where(r <= 1.0, 1.0, 1.0 / np.maximum(r, 1e-12))


# ---------------------------------------------------------------- two-view geometry on unit bearings
def solve_rotation_only(f0, f1, R):
    """Small correction d with f0 ~ R exp(d) f1 (pure rotation). Returns d and per-point residual angles."""
    g = f1 @ R.T
    A = -np.einsum("ij,njk->nik", R, skew_batch(f1))  # d(R exp(d) f1)/dd at d = 0
    b = f0 - g
    w = np.ones(len(f0))
    d = np.zeros(3)
    for _ in range(4):
        AtA = np.einsum("n,nji,njk->ik", w, A, A) + 1e-6 * np.eye(3)
        Atb = np.einsum("n,nji,nj->i", w, A, b)
        d = np.linalg.solve(AtA, Atb)
        res = np.linalg.norm(b - A @ d, axis=1)
        w = huber_weights(res, 1.5 * np.median(res))
    return d, res


def solve_epipolar(f0, f1, R, t_init, iterations=6):
    """Small rotation correction d and unit translation t with f0 . (t x R exp(d) f1) = 0 (both in camera k0)."""
    d = np.zeros(3)
    t = t_init / np.linalg.norm(t_init)
    w = np.ones(len(f0))
    for _ in range(iterations):
        Rd = R @ exp_so3(d)
        g = f1 @ Rd.T
        H = np.cross(g, f0)  # residual r = t . (g x f0)
        _, _, Vt = np.linalg.svd(H * w[:, None])
        t_new = Vt[-1]
        t = t_new if t_new @ t >= 0 else -t_new
        n = np.cross(f0, t)  # r = n . g
        r = np.einsum("ni,ni->n", n, g)
        a = np.einsum("ni,ij,njk->nk", n, Rd, skew_batch(f1))  # dr/de = -n^T Rd [f1]x e  ->  r - a e = 0 ... sign below
        AtA = np.einsum("n,ni,nj->ij", w, a, a) + 1e-4 * np.eye(3)
        Atb = np.einsum("n,ni,n->i", w, a, r)
        d = d + np.linalg.solve(AtA, Atb)
        w = huber_weights(r, 1.5 * np.median(np.abs(r)) + 1e-9)
    Rd = R @ exp_so3(d)
    g = f1 @ Rd.T
    r = np.einsum("ni,ni->n", np.cross(f0, t), g)
    # cheirality: the scene is in front of the camera. From Z0 f0 = Z1 g + t, Z1 = -(f0 x t).(f0 x g) / |f0 x g|^2;
    # the true sign of t makes most depths positive (the epipolar fit alone cannot tell t from -t)
    cross_g = np.cross(f0, g)
    weight = np.einsum("ni,ni->n", cross_g, cross_g)
    usable = weight > 1e-6
    if usable.sum() >= 3:
        depth_sign = -np.einsum("ni,ni->n", np.cross(f0, t), cross_g)[usable]
        if np.sum(depth_sign > 0) < np.sum(depth_sign < 0):
            t = -t
    return d, t, r


class Solution:
    frame_width = 320
    OPTIONS = FINAL

    def __init__(self, config):
        self.o = dict(DEFAULTS, **self.OPTIONS)
        self.T_cam_imu = np.asarray(config["T_cam_imu"], dtype=float)
        self.T_imu_cam = np.linalg.inv(self.T_cam_imu)
        self.R_ci = self.T_cam_imu[:3, :3]
        self.R_ic = self.R_ci.T
        self.K = np.array([[config["fx"], 0, config["cx"]], [0, config["fy"], config["cy"]], [0, 0, 1.0]])
        self.K_inv = np.linalg.inv(self.K)
        self.width, self.height = int(config["width"]), int(config["height"])
        self.R_wb = np.eye(3)  # world = IMU frame at the first camera timestamp
        self.v = np.zeros(3)
        self.p = np.zeros(3)
        self.omega = np.zeros(3)
        self.gyro_bias = np.zeros(3)
        self.gravity = None
        self.calibration_samples = []
        self.calibration_force = np.zeros(3)
        self.calibration_time = 0.0
        self.last_t = None
        self.frame_index = 0
        # vision state
        self.window = None
        self.prev_gray = None
        self.prev_R_wb = None
        self.stats = dict(windows=0, used=0, rejected=0, rotation_only=0, few_points=0, short=0, big_rotation=0,
                          no_corners=0)
        self.flow_speed = self.o["fixed_speed"]
        self.direction_cam = None  # unit direction of travel in current-camera axes, from the last vision window
        self.direction_world = None
        self.direction_time = -1e9
        self.moving = False
        self.now = 0.0
        # Kalman filter: x = [velocity (world), accelerometer bias (IMU axes)]
        self.kf_x = np.zeros(6)
        s0 = self.o["kf_initial_speed_sigma"]
        self.kf_P = np.diag([s0 ** 2] * 3 + [0.2 ** 2] * 3)
        # diagnostics only (set by the harness, never on the server)
        self.oracle_R_wb = None
        self.oracle_v = None
        self.oracle_mode = None
        self.oracle_speed = None
        self.oracle_dir_v = None
        self.oracle_gravity = None
        self.oracle_moving = None
        self.oracle_direction = None

    # ------------------------------------------------------------ velocity filter
    def _kf_predict(self, acceleration, dt):
        R = self.R_wb
        F = np.eye(6)
        F[:3, 3:] = -R * dt
        self.kf_x[:3] = self.kf_x[:3] + (acceleration - R @ self.kf_x[3:]) * dt
        q = np.r_[[self.o["kf_accel_noise"] ** 2 * dt] * 3, [self.o["kf_bias_noise"] ** 2 * dt] * 3]
        self.kf_P = F @ self.kf_P @ F.T + np.diag(q)
        return self.kf_x[:3].copy()

    def _kf_update(self, H, z, sigma):
        S = H @ self.kf_P @ H.T + sigma ** 2 * np.eye(len(z))
        K = self.kf_P @ H.T @ np.linalg.inv(S)
        self.kf_x = self.kf_x + K @ (z - H @ self.kf_x)
        self.kf_P = (np.eye(6) - K @ H) @ self.kf_P
        self.kf_P = 0.5 * (self.kf_P + self.kf_P.T)

    def _kf_measure(self):
        """Camera-derived pseudo-measurements of the velocity, once per frame."""
        if self.oracle_dir_v is not None:  # diagnostic: true direction and stop/go, the filter supplies the speed
            speed = np.linalg.norm(self.oracle_dir_v)
            self.moving = speed > 0.05
            self.direction_world = self.oracle_dir_v / max(speed, 1e-9)
            self.direction_time = self.now
            self.o["direction_frame"] = "world"
        if self.now - self.direction_time > self.o["kf_direction_timeout"]:
            return  # no recent vision: let the IMU carry the velocity
        H = np.zeros((3, 6))
        H[:, :3] = np.eye(3)
        if not self.moving:
            self._kf_update(H, np.zeros(3), self.o["kf_stop_sigma"])
        else:
            d = self._direction_world_now()
            if d is None:
                return
            helper = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 1.0, 0])
            e1 = np.cross(d, helper)
            e1 /= np.linalg.norm(e1)
            e2 = np.cross(d, e1)
            Hp = np.zeros((2, 6))
            Hp[0, :3], Hp[1, :3] = e1, e2
            self._kf_update(Hp, np.zeros(2), self.o["kf_direction_sigma"])
            Hs = np.zeros((1, 6))
            Hs[0, :3] = d
            self._kf_update(Hs, np.array([self.o["kf_speed_prior"]]), self.o["kf_speed_prior_sigma"])
            if self.kf_x[:3] @ d < 0:  # the drone does not fly backwards along the measured direction
                self.kf_x[:3] -= (self.kf_x[:3] @ d) * d
        speed = np.linalg.norm(self.kf_x[:3])
        if speed > self.o["max_speed"]:
            self.kf_x[:3] *= self.o["max_speed"] / speed
        self.v = self.kf_x[:3].copy()

    def _speed(self):
        if self.o["speed_mode"] == "fixed":
            return self.o["fixed_speed"]
        if self.o["speed_mode"] == "blend":  # geometric middle of the prior and the flow measurement
            return float(np.sqrt(self.o["fixed_speed"] * max(self.flow_speed, 1e-3)))
        return self.flow_speed

    def _direction_world_now(self):
        if self.o["direction_frame"] == "world":
            return self.direction_world
        if self.direction_cam is None:
            return None
        return self.R_wb @ self.R_ic @ self.direction_cam

    # ------------------------------------------------------------ IMU core
    def _calibrate(self, imu, force, dt):
        self.calibration_samples.extend(imu.tolist())
        self.calibration_force += force * dt
        self.calibration_time += dt
        if self.calibration_time < self.o["calibration_seconds"]:
            return
        mean_force = self.calibration_force / self.calibration_time
        if self.oracle_gravity is not None:  # diagnostic: the true specific force at rest in world axes
            mean_force = self.oracle_gravity.copy()
        magnitude = np.linalg.norm(mean_force)
        if abs(magnitude - GRAVITY) < GRAVITY_TOLERANCE:
            self.gravity = mean_force * (GRAVITY / magnitude)
            samples = np.asarray(self.calibration_samples)
            mean_gyro = samples[:, 4:7].mean(axis=0)
            if (np.linalg.norm(mean_gyro) < MAX_GYRO_BIAS_AT_REST and
                    np.linalg.norm(samples[:, 4:7].std(axis=0)) < REST_GYRO_STD and
                    np.linalg.norm(samples[:, 1:4].std(axis=0)) < REST_ACCEL_STD):
                self.gyro_bias = mean_gyro
                self.gravity = mean_force
        self.calibration_samples.clear()
        self.calibration_force[:] = 0
        self.calibration_time = 0.0

    def _integrate(self, imu):
        start = self.last_t
        force = np.zeros(3)
        for row in imu:
            dt = row[0] - self.last_t
            if dt <= 0:
                continue
            self.last_t = row[0]
            self.omega = row[4:7] - self.gyro_bias
            self.R_wb = self.R_wb @ exp_so3(self.omega * dt)
            force += (self.R_wb @ row[1:4]) * dt
        dt = self.last_t - start
        if dt <= 0:
            return
        force /= dt
        if self.gravity is None:
            self._calibrate(imu, force, dt)
            return
        magnitude = np.linalg.norm(force)
        if abs(magnitude - GRAVITY) < GRAVITY_TOLERANCE:
            axis = np.cross(force / magnitude, self.gravity / np.linalg.norm(self.gravity))
            correction = exp_so3(axis * -np.expm1(-dt / self.o["tilt_seconds"]))
            self.R_wb = correction @ self.R_wb
            force = correction @ force
        acceleration = force - self.gravity
        tau = self.o["velocity_seconds"]
        gain = -np.expm1(-dt / tau)
        next_v = (1.0 - gain) * self.v + gain * tau * acceleration
        if self.oracle_v is not None:
            if self.oracle_mode == "direction":  # true direction, the model's own speed
                next_v = self.oracle_v / max(np.linalg.norm(self.oracle_v), 1e-9) * np.linalg.norm(next_v)
            elif self.oracle_mode == "direction+fixed_speed":  # true direction, one constant speed while moving
                speed = np.linalg.norm(self.oracle_v)
                next_v = self.oracle_v / speed * self.o["fixed_speed"] if speed > 0.05 else np.zeros(3)
            else:
                next_v = self.oracle_v
        elif self.o["velocity_mode"] == "filter":
            next_v = self._kf_predict(acceleration, dt)
        elif self.o["velocity_mode"] == "visual":
            # the direction of travel is stored in camera axes (a quadrotor flies roughly along its camera), so it
            # turns with the drone between vision updates
            if self.oracle_moving is not None:  # diagnostic: true stop/go
                self.moving = self.oracle_moving
            if self.oracle_direction is not None:  # diagnostic: true direction of travel (world)
                self.direction_world, self.direction_time = self.oracle_direction, self.now
                self.o["direction_frame"] = "world"
            if self.now - self.direction_time > self.o["stale_seconds"]:
                next_v = self.v * np.exp(-dt / self.o["stale_decay_seconds"])  # vision has gone quiet
            elif self.moving and self.direction_cam is not None:
                speed = self._speed()
                if self.oracle_speed is not None:  # diagnostic
                    speed = self.oracle_speed if self.oracle_speed > 0.05 else 0.0
                next_v = self._direction_world_now() * min(speed, self.o["max_speed"])
            else:
                next_v = np.zeros(3)
        elif self.oracle_speed is not None:
            norm = np.linalg.norm(next_v)
            next_v = next_v / norm * self.oracle_speed if norm > 1e-9 else next_v
        self.p += 0.5 * dt * (self.v + next_v)
        self.v = next_v

    # ------------------------------------------------------------ vision
    def _bearings(self, pixels):
        h = np.c_[pixels, np.ones(len(pixels))] @ self.K_inv.T
        return h / np.linalg.norm(h, axis=1, keepdims=True)

    def _start_window(self, gray, t):
        border = 8
        mask = np.zeros_like(gray)
        mask[border:-border, border:-border] = 255
        corners = cv2.goodFeaturesToTrack(gray, maxCorners=self.o["n_points"], qualityLevel=self.o["corner_quality"],
                                          minDistance=10, blockSize=5, mask=mask)
        if corners is None or len(corners) < self.o["min_points"]:
            self.stats["no_corners"] += 1
            self.window = None
            return
        corners = corners.reshape(-1, 2).astype(np.float32)
        self.window = dict(start_pixels=corners.copy(), pixels=corners, R_wb=self.R_wb.copy(), p=self.p.copy(),
                           t=t, frames=0, initial=len(corners))

    def _track(self, gray):
        w = self.window
        # predict with the gyro: a far point keeps its bearing in the world, so f_cur = R_cur_prev f_prev
        R_prev_cur = self.R_ci @ self.prev_R_wb.T @ self.R_wb @ self.R_ic
        f = self._bearings(w["pixels"]) @ R_prev_cur  # rows: R_prev_cur^T f
        ok = f[:, 2] > 0.1
        predicted = (f @ self.K.T)[:, :2] / np.maximum(f[:, 2:3], 1e-6)
        predicted = np.where(ok[:, None], predicted, w["pixels"]).astype(np.float32)
        lk = dict(winSize=(15, 15), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))
        nxt, status, _ = cv2.calcOpticalFlowPyrLK(self.prev_gray, gray, w["pixels"], predicted.copy(),
                                                  flags=cv2.OPTFLOW_USE_INITIAL_FLOW, **lk)
        back, status_back, _ = cv2.calcOpticalFlowPyrLK(gray, self.prev_gray, nxt, w["pixels"].copy(),
                                                        flags=cv2.OPTFLOW_USE_INITIAL_FLOW, **lk)
        good = (ok & (status.ravel() == 1) & (status_back.ravel() == 1) &
                (np.linalg.norm(back - w["pixels"], axis=1) < 0.5) &
                (nxt[:, 0] >= 0) & (nxt[:, 0] < self.width) & (nxt[:, 1] >= 0) & (nxt[:, 1] < self.height))
        w["start_pixels"], w["pixels"] = w["start_pixels"][good], nxt[good]
        w["frames"] += 1

    def _finish_window(self, t):
        w = self.window
        self.stats["windows"] += 1
        if len(w["pixels"]) < self.o["min_points"] or w["frames"] < self.o["min_window_frames"]:
            self.stats["rejected"] += 1
            self.stats["few_points" if len(w["pixels"]) < self.o["min_points"] else "short"] += 1
            return
        f0, f1 = self._bearings(w["start_pixels"]), self._bearings(w["pixels"])
        R_pred = self.R_ci @ w["R_wb"].T @ self.R_wb @ self.R_ic  # camera k1 in camera k0, from the gyro
        d, residual = solve_rotation_only(f0, f1, R_pred)
        parallax = np.median(residual)
        t_cam = None
        if parallax < self.o["pure_rotation_parallax"]:
            self.stats["rotation_only"] += 1
        else:
            t_imu = self.R_ci @ w["R_wb"].T @ (self.p - w["p"])
            if self.direction_cam is not None:  # previous direction, carried into the window-start camera
                t_init = R_pred @ self.direction_cam
            else:
                t_init = t_imu if np.linalg.norm(t_imu) > 1e-3 else np.array([0.0, 0.0, 1.0])
            d, t_cam, _ = solve_epipolar(f0, f1, R_pred, t_init)
        self.moving = parallax >= self.o["moving_parallax"]
        if t_cam is not None and np.all(np.isfinite(t_cam)):
            # speed from the flow: a point at depth Z and angle a from the direction of travel shifts by about
            # |t| sin(a) / Z, so |t| ~ Z * shift / sin(a); with one typical Z for the scene, take the median
            g = f1 @ (R_pred @ exp_so3(d)).T
            shift = np.arccos(np.clip(np.einsum("ni,ni->n", f0, g), -1, 1))
            sin_a = np.linalg.norm(np.cross(f0, t_cam), axis=1)
            usable = sin_a > 0.2
            if usable.sum() >= 5:
                measured = self.o["typical_depth"] * np.median(shift[usable] / sin_a[usable]) / max(t - w["t"], 1e-3)
                a = self.o["speed_smoothing"]
                self.flow_speed = (1 - a) * self.flow_speed + a * measured
            if self.o["retro"] and self.o["velocity_mode"] == "visual" and self.oracle_speed is None:
                # redo the window's movement with the direction just measured: start + direction x speed x time
                speed = self._speed()
                travelled = speed * (t - w["t"]) if self.moving else 0.0
                self.p = w["p"] + (w["R_wb"] @ self.R_ic @ t_cam) * travelled
            direction = (R_pred @ exp_so3(d)).T @ t_cam  # window-start camera -> current camera axes
            self.direction_cam = direction / np.linalg.norm(direction)
            self.direction_world = w["R_wb"] @ self.R_ic @ t_cam
            self.direction_time = t
        elif not self.moving:
            self.direction_time = t  # a confident "standing still" is also a fresh measurement
        if not np.all(np.isfinite(d)) or np.linalg.norm(d) > self.o["max_rot_correction"]:
            self.stats["rejected"] += 1
            self.stats["big_rotation"] += 1
            return
        self.stats["used"] += 1
        d_imu = self.R_ic @ d  # the rotation the gyro missed over the window, in IMU axes of the window end
        elapsed = max(t - w["t"], 1e-3)
        self.R_wb = project_rotation(self.R_wb @ exp_so3(self.o["rot_apply"] * d_imu))
        self.gyro_bias = self.gyro_bias - self.o["bias_gain"] * d_imu / elapsed
        norm = np.linalg.norm(self.gyro_bias)
        if norm > self.o["max_bias"]:
            self.gyro_bias *= self.o["max_bias"] / norm
        if self.o["use_direction"] and t_cam is not None:
            direction = w["R_wb"] @ self.R_ic @ t_cam  # world axes
            speed = np.linalg.norm(self.v)
            if speed > 0.05:
                blended = (1 - self.o["direction_gain"]) * self.v / speed + self.o["direction_gain"] * direction
                if np.linalg.norm(blended) > 1e-6:
                    self.v = blended / np.linalg.norm(blended) * speed

    def _vision(self, t, frame):
        gray = np.ascontiguousarray(frame[:, :, 1])  # the green channel: a cheap stand-in for gray
        if self.window is not None:
            self._track(gray)
            survivors = len(self.window["pixels"])
            losing = self.o["keep_fraction"] > 0 and \
                survivors < max(self.o["min_points"] + 4, self.o["keep_fraction"] * self.window["initial"])
            if survivors < self.o["min_points"] or self.window["frames"] >= self.o["window_frames"] or \
                    (losing and self.window["frames"] >= self.o["min_window_frames"]):
                self._finish_window(t)
                self.window = None
        if self.window is None:
            self._start_window(gray, t)
        self.prev_gray = gray
        self.prev_R_wb = self.R_wb.copy()

    # ------------------------------------------------------------ output
    def _pose_camera(self):
        T_wb = np.eye(4)
        T_wb[:3, :3] = self.R_wb
        T_wb[:3, 3] = self.p
        return T_wb @ self.T_imu_cam

    def _twist_camera(self):
        r = self.T_imu_cam[:3, 3]
        velocity = self.R_ci @ (self.R_wb.T @ self.v + np.cross(self.omega, r))
        return np.concatenate([velocity, self.R_ci @ self.omega])

    def step(self, t, frame, imu):
        if self.last_t is None:
            self.last_t = t
            if self.o["vision"] and frame is not None:
                self._vision(t, frame)
            self.frame_index += 1
            return [0, 0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 0, 0]
        if self.oracle_R_wb is not None:
            self.R_wb = self.oracle_R_wb.copy()
        self.now = t
        self._integrate(imu)
        if self.o["vision"] and frame is not None and self.gravity is not None:
            self._vision(t, frame)
        if self.o["velocity_mode"] == "filter" and self.gravity is not None:
            self._kf_measure()
        self.frame_index += 1
        T_c0_c = self.T_cam_imu @ self._pose_camera()
        state = np.concatenate([T_c0_c[:3, 3], matrix_to_quaternion(T_c0_c[:3, :3]), self._twist_camera()])
        if not np.all(np.isfinite(state)):
            return [0, 0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 0, 0]
        return state
