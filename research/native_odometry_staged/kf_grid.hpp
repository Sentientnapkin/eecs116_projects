#pragma once
// Opt-in (-DODO_KF_GRID) attitude for position integration: static-window gyro bias plus a 3-state Kalman filter on
// gyro bias measured by visual relative rotations every 0.5 s (grid corners, gyro-predicted KLT, forward/backward
// check, essential RANSAC + cheirality or a robust rotation-only fit). Transcribes research/attitude_bias.py
// (arm "kf_grid", or "kf_grid_gated" with -DODO_KF_GRID_GATED; causal static window). The network's inputs keep the original Orientation; only the attitude used
// to integrate velocity and to report the pose changes. Uses the wasm OpenCV of the pinned VIOBench runtime.
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/video/tracking.hpp>
#include <opencv2/calib3d.hpp>
#ifdef ODO_KF_GRID_TRACE
#include <cstdio>
#endif

namespace odo {

struct GridAttitude {
    static constexpr double INIT_VAR = 0.02 * 0.02 / 3, WALK = 0.0006, WHITE = 0.07, WINDOW = 0.8, PERIOD = 0.5;
    static constexpr int STILL_FRAMES = 64, STILL_ROWS = 32;
    M3 R = eye(), R_anchor = eye(), R_bc;
    double bias[3] = {0, 0, 0}, P[3] = {INIT_VAR, INIT_VAR, INIT_VAR}, previous = 0, last_t = 0, anchor_t = 0;
    cv::Matx33d K, Kinv;
    cv::Mat anchor, current, rgb_view;
    bool decided = false, have_anchor = false;
    int still_frames = 0, accepted = 0, rejected = 0, resets = 0;
    double still_t[STILL_FRAMES];
    int still_n[STILL_FRAMES];
    double still_rows[STILL_FRAMES][STILL_ROWS][7];

    void init(double fx, double fy, double cx, double cy, const M3 &body_from_camera) {
        K = cv::Matx33d(fx, 0, cx, 0, fy, cy, 0, 0, 1);
        Kinv = K.inv();
        R_bc = body_from_camera;
        cv::theRNG().state = 217;
    }

    // Orientation.step's integration: each row's rate held until the next row, the last up to the frame time.
    void integrate(double t, const double *packet, int n, const double *b) {
        if (!n) { previous = t; return; }
        const double *last = packet + 4;
        for (int i = 0; i < n; ++i) {
            const double *row = packet + 7 * i;
            const double rt = std::max(previous, std::min(row[0], t)), d = rt - previous;
            R = mul(R, exp_so3((row[4] - b[0]) * d, (row[5] - b[1]) * d, (row[6] - b[2]) * d));
            previous = rt;
            last = row + 4;
        }
        const double d = t - previous;
        R = mul(R, exp_so3((last[0] - b[0]) * d, (last[1] - b[1]) * d, (last[2] - b[2]) * d));
        previous = t;
    }

    void decide(double t0) {
        decided = true;
        int count = 0;
        double mean[3] = {0, 0, 0}, sq[3] = {0, 0, 0}, an = 0, an2 = 0;
        for (int f = 0; f < still_frames; ++f)
            for (int i = 0; i < still_n[f]; ++i) {
                const double *row = still_rows[f][i];
                const double a = std::sqrt(row[1] * row[1] + row[2] * row[2] + row[3] * row[3]);
                for (int c = 0; c < 3; ++c) { mean[c] += row[4 + c]; sq[c] += row[4 + c] * row[4 + c]; }
                an += a; an2 += a * a; ++count;
            }
        if (count <= 40) return;
        double sd = 0, norm = 0;
        for (int c = 0; c < 3; ++c) {
            mean[c] /= count;
            sd = std::max(sd, std::sqrt(std::max(0.0, sq[c] / count - mean[c] * mean[c])));
            norm += mean[c] * mean[c];
        }
        an /= count;
        const double asd = std::sqrt(std::max(0.0, an2 / count - an * an));
        if (!(std::sqrt(norm) < 0.1 && sd < 0.12 && std::fabs(an - 9.81) < 0.3 && asd < 0.5)) return;
        for (int c = 0; c < 3; ++c) { bias[c] = mean[c]; P[c] = WHITE * WHITE / count + 1e-8; }
        ++resets;
        R = eye();
        previous = t0;
        for (int f = 0; f < still_frames; ++f) integrate(still_t[f], &still_rows[f][0][0], still_n[f], bias);
    }

    // Robust small-rotation fit to corresponding normalized rays (orientation.fit_visual_rotation).
    static bool fit_rotation(const std::vector<cv::Point2f> &old_px, const std::vector<cv::Point2f> &new_px,
                             const cv::Matx33d &Kinv, const cv::Matx33d &relative, cv::Vec3d &delta, double &err) {
        const int n = (int)old_px.size();
        std::vector<double> x(n), y(n), rx(n), ry(n), w(n, 1.0), e(n);
        for (int i = 0; i < n; ++i) {
            const cv::Vec3d o = Kinv * cv::Vec3d(old_px[i].x, old_px[i].y, 1), nw = Kinv * cv::Vec3d(new_px[i].x, new_px[i].y, 1);
            const cv::Vec3d p = relative.t() * o;  // numpy: old @ relative
            if (p[2] < .1) return false;
            x[i] = p[0] / p[2]; y[i] = p[1] / p[2];
            rx[i] = nw[0] / nw[2] - x[i]; ry[i] = nw[1] / nw[2] - y[i];
        }
        cv::Vec3d d;
        for (int it = 0; it < 3; ++it) {
            cv::Mat A(2 * n, 3, CV_64F), b(2 * n, 1, CV_64F), sol;
            for (int i = 0; i < n; ++i) {
                const double X0[3] = {-x[i] * y[i], 1 + x[i] * x[i], -y[i]}, X1[3] = {-1 - y[i] * y[i], x[i] * y[i], x[i]};
                for (int c = 0; c < 3; ++c) { A.at<double>(2 * i, c) = w[i] * X0[c]; A.at<double>(2 * i + 1, c) = w[i] * X1[c]; }
                b.at<double>(2 * i) = w[i] * rx[i]; b.at<double>(2 * i + 1) = w[i] * ry[i];
            }
            cv::solve(A, b, sol, cv::DECOMP_SVD);
            d = cv::Vec3d(sol.at<double>(0), sol.at<double>(1), sol.at<double>(2));
            for (int i = 0; i < n; ++i) {
                const double ex = rx[i] - (-x[i] * y[i] * d[0] + (1 + x[i] * x[i]) * d[1] - y[i] * d[2]);
                const double ey = ry[i] - ((-1 - y[i] * y[i]) * d[0] + x[i] * y[i] * d[1] + x[i] * d[2]);
                e[i] = std::sqrt(ex * ex + ey * ey);
                w[i] = std::sqrt(std::min(1.0, .012 / std::max(e[i], 1e-8)));
            }
        }
        std::vector<double> sorted = e;
        std::sort(sorted.begin(), sorted.end());
        err = n % 2 ? sorted[n / 2] : .5 * (sorted[n / 2 - 1] + sorted[n / 2]);
        delta = -d;
        return true;
    }

    // attitude_bias.grid_rotation: camera right-multiplicative correction and sigma (rad), or false.
    // Measurement stages (shared by the one-frame schedule and the -DODO_KF_GRID_SPLIT schedule). Tunables default to
    // the reference arm: 10 corners per 4x4 cell, 21x21 KLT window, 3 pyramid levels, 500 RANSAC iterations.
#ifndef ODO_KFG_CORNERS
#define ODO_KFG_CORNERS 10
#endif
#ifndef ODO_KFG_WIN
#define ODO_KFG_WIN 21
#endif
#ifndef ODO_KFG_LEVELS
#define ODO_KFG_LEVELS 3
#endif
#ifndef ODO_KFG_RANSAC_ITERS
#define ODO_KFG_RANSAC_ITERS 500
#endif
    const char *why = "";
    std::vector<cv::Point2f> points, guess, tracked, back;
    std::vector<uchar> found_fwd, returned;
    std::vector<float> klt_error;

    void detect(const cv::Mat &image) {  // corners on the window's anchor image
        const int h = image.rows, w = image.cols;
        points.clear();
        for (int gy = 0; gy < 4; ++gy)
            for (int gx = 0; gx < 4; ++gx) {
                std::vector<cv::Point2f> found;
                const cv::Rect cell(gx * w / 4, gy * h / 4, (gx + 1) * w / 4 - gx * w / 4, (gy + 1) * h / 4 - gy * h / 4);
                cv::goodFeaturesToTrack(image(cell), found, ODO_KFG_CORNERS, 0.003, 5);
                for (const auto &p : found) points.emplace_back(p.x + cell.x, p.y + cell.y);
            }
    }

    static cv::TermCriteria klt_criteria() {
        return cv::TermCriteria(cv::TermCriteria::COUNT + cv::TermCriteria::EPS, 30, 0.01);
    }

    void forward(const cv::Mat &first, const cv::Mat &last, const cv::Matx33d &relative) {
        cv::perspectiveTransform(points, guess, cv::Matx33d(K * relative.t() * Kinv));
        tracked = guess;
        cv::calcOpticalFlowPyrLK(first, last, points, tracked, found_fwd, klt_error, cv::Size(ODO_KFG_WIN, ODO_KFG_WIN),
                                 ODO_KFG_LEVELS, klt_criteria(), cv::OPTFLOW_USE_INITIAL_FLOW);
    }

    void backward(const cv::Mat &first, const cv::Mat &last) {
        back = points;
        cv::calcOpticalFlowPyrLK(last, first, tracked, back, returned, klt_error, cv::Size(ODO_KFG_WIN, ODO_KFG_WIN),
                                 ODO_KFG_LEVELS, klt_criteria(), cv::OPTFLOW_USE_INITIAL_FLOW);
    }

    // attitude_bias.grid_rotation after tracking: camera right-multiplicative correction and sigma (rad), or false.
    bool fit(int h, int w, const cv::Matx33d &relative, cv::Vec3d &delta, double &sigma) {
        std::vector<cv::Point2f> old_px, new_px;
        std::vector<double> flow;
        bool cells[4][4] = {};
        int occupied = 0;
        for (size_t i = 0; i < points.size(); ++i) {
            if (!found_fwd[i] || !returned[i] || cv::norm(back[i] - points[i]) >= 0.8) continue;
            old_px.push_back(points[i]); new_px.push_back(tracked[i]);
            flow.push_back(cv::norm(tracked[i] - guess[i]));
            const int cx = std::min(3, (int)(4 * points[i].x / w)), cy = std::min(3, (int)(4 * points[i].y / h));
            if (!cells[cx][cy]) { cells[cx][cy] = true; ++occupied; }
        }
        if (old_px.size() < 16 || occupied < 5) { why = "few tracks"; return false; }
        std::vector<double> f = flow;
        std::sort(f.begin(), f.end());
        const size_t m = f.size();
        const double median = m % 2 ? f[m / 2] : .5 * (f[m / 2 - 1] + f[m / 2]);
        if (median <= 1.0) {
            double err;
            if (!fit_rotation(old_px, new_px, Kinv, relative, delta, err) || err > 0.012) { why = "rotation fit"; return false; }
            sigma = 0.002;
            return true;
        }
        cv::Mat mask, Rm, tm;
        const cv::Mat E = cv::findEssentialMat(old_px, new_px, cv::Mat(K), cv::RANSAC, 0.999, 1.0, ODO_KFG_RANSAC_ITERS, mask);
        if (E.rows != 3 || E.cols != 3) { why = "essential"; return false; }
        cv::Mat cheiral;  // no input mask: like the reference, every tracked point enters the cheirality count
        const int inliers = cv::recoverPose(E, old_px, new_px, cv::Mat(K), Rm, tm, cheiral);
        if (inliers < std::max(12.0, 0.5 * (double)old_px.size())) { why = "cheirality"; return false; }
        const cv::Matx33d old_to_new(Rm);
        cv::Vec3d rv;
        cv::Rodrigues(cv::Mat(relative.t() * old_to_new.t()), rv);
        delta = rv;
        sigma = 0.004;
        return true;
    }

    bool measure(const cv::Matx33d &relative, cv::Vec3d &delta, double &sigma) {
        detect(anchor);
        if (points.size() < 16) { why = "few corners"; return false; }
        forward(anchor, current, relative);
        backward(anchor, current);
        return fit(anchor.rows, anchor.cols, relative, delta, sigma);
    }

    // Kalman update of the gyro bias from one window's visual correction (delta, camera frame) over dt seconds.
    void update(bool ok, const cv::Vec3d &delta, double sigma, double dt, double t) {
        ok = ok && cv::norm(delta) <= 0.05;
        double residual[3];
        if (ok) {
            const double dv[3] = {delta[0], delta[1], delta[2]};
            mv(R_bc, dv, residual);                     // body frame, ~ (b_hat - b_true) * dt
            sigma /= dt;
            // 3-sigma innovation gate per axis (attitude_bias.py arm "kf_grid_gated")
#ifdef ODO_KF_GRID_GATED
            for (int c = 0; c < 3; ++c)
                if (std::fabs(residual[c] / dt) > 3 * std::sqrt(P[c] + sigma * sigma)) { ok = false; why = "innovation"; }
#endif
        }
        if (ok) {
            for (int c = 0; c < 3; ++c) {
                const double gain = P[c] / (P[c] + sigma * sigma);
                bias[c] += gain * (-(residual[c] / dt));
                P[c] *= (1 - gain);
            }
            ++accepted;
#ifdef ODO_KF_GRID_TRACE
            std::fprintf(stderr, "win t=%.3f ok sigma=%.4f delta=%.6f %.6f %.6f bias=%.6f %.6f %.6f\n", t, sigma * dt,
                         delta[0], delta[1], delta[2], bias[0], bias[1], bias[2]);
#endif
        } else {
            ++rejected;
#ifdef ODO_KF_GRID_TRACE
            std::fprintf(stderr, "win t=%.3f rejected %s\n", t, why);
#endif
        }
        (void)t;
    }

#ifdef ODO_KF_GRID_STAGED
    // Staged schedule: every heavy piece of the measurement runs on its own frame. The window ending at frame b builds
    // that frame's KLT pyramid (with Scharr derivatives, exactly what calcOpticalFlowPyrLK builds internally) at b,
    // tracks forward in ODO_KFG_TRACK_PARTS point slices at b+1.., backward likewise, then selects tracks and runs
    // the essential RANSAC (or rotation fit), then recoverPose and the Kalman update at b + 2 * parts + 2; corners
    // on the new anchor (frame b) are detected on the following frame. Each image's pyramid is built once and reused
    // as the next window's anchor pyramid. KLT is per-point independent, so the measurement equals the one-frame
    // schedule's; only the bias update lands 2 * parts + 2 frames later.
#ifndef ODO_KFG_TRACK_PARTS
#define ODO_KFG_TRACK_PARTS 2
#endif
    static constexpr int PARTS = ODO_KFG_TRACK_PARTS;
    std::vector<cv::Mat> pyr_anchor, pyr_current;
    cv::Matx33d pending_relative;
    double pending_dt = 0, pending_t = 0, pending_sigma = 0;
    int stage = 0;               // 1..PARTS forward slices, ..2*PARTS backward, 2*PARTS+1 select/essential, +2 pose
    bool detect_due = false, pyramid_due = false, pending_ok = false;
    std::vector<cv::Point2f> old_px, new_px;
    cv::Mat essential;
    cv::Vec3d pending_delta;

    void build_pyramid(const cv::Mat &image, std::vector<cv::Mat> &pyr) {
        cv::buildOpticalFlowPyramid(image, pyr, cv::Size(ODO_KFG_WIN, ODO_KFG_WIN), ODO_KFG_LEVELS, true,
                                    cv::BORDER_REFLECT_101, cv::BORDER_CONSTANT, true);
    }

    void track_slice(int part, bool fwd) {
        const int n = (int)points.size(), i0 = n * part / PARTS, i1 = n * (part + 1) / PARTS;
        if (i1 <= i0) return;
        std::vector<cv::Point2f> from, to;
        std::vector<uchar> status;
        std::vector<float> err;
        if (fwd) { from.assign(points.begin() + i0, points.begin() + i1); to.assign(guess.begin() + i0, guess.begin() + i1); }
        else { from.assign(tracked.begin() + i0, tracked.begin() + i1); to.assign(points.begin() + i0, points.begin() + i1); }
        cv::calcOpticalFlowPyrLK(fwd ? pyr_anchor : pyr_current, fwd ? pyr_current : pyr_anchor, from, to, status, err,
                                 cv::Size(ODO_KFG_WIN, ODO_KFG_WIN), ODO_KFG_LEVELS, klt_criteria(),
                                 cv::OPTFLOW_USE_INITIAL_FLOW);
        std::copy(to.begin(), to.end(), (fwd ? tracked : back).begin() + i0);
        std::copy(status.begin(), status.end(), (fwd ? found_fwd : returned).begin() + i0);
    }

    // fit()'s selection plus either the rotation-only fit (final) or the essential RANSAC (pose follows next stage).
    // Returns true when the result is final.
    bool select_and_solve() {
        const int h = anchor.rows, w = anchor.cols;
        old_px.clear(); new_px.clear();
        std::vector<double> flow;
        bool cells[4][4] = {};
        int occupied = 0;
        for (size_t i = 0; i < points.size(); ++i) {
            if (!found_fwd[i] || !returned[i] || cv::norm(back[i] - points[i]) >= 0.8) continue;
            old_px.push_back(points[i]); new_px.push_back(tracked[i]);
            flow.push_back(cv::norm(tracked[i] - guess[i]));
            const int cx = std::min(3, (int)(4 * points[i].x / w)), cy = std::min(3, (int)(4 * points[i].y / h));
            if (!cells[cx][cy]) { cells[cx][cy] = true; ++occupied; }
        }
        pending_ok = false;
        if (old_px.size() < 16 || occupied < 5) { why = "few tracks"; return true; }
        std::vector<double> f = flow;
        std::sort(f.begin(), f.end());
        const size_t m = f.size();
        const double median = m % 2 ? f[m / 2] : .5 * (f[m / 2 - 1] + f[m / 2]);
        if (median <= 1.0) {
            double err;
            if (!fit_rotation(old_px, new_px, Kinv, pending_relative, pending_delta, err) || err > 0.012) { why = "rotation fit"; return true; }
            pending_sigma = 0.002;
            pending_ok = true;
            return true;
        }
        cv::Mat mask;
        essential = cv::findEssentialMat(old_px, new_px, cv::Mat(K), cv::RANSAC, 0.999, 1.0, ODO_KFG_RANSAC_ITERS, mask);
        if (essential.rows != 3 || essential.cols != 3) { why = "essential"; return true; }
        return false;
    }

    void pose() {
        cv::Mat Rm, tm, cheiral;
        const int inliers = cv::recoverPose(essential, old_px, new_px, cv::Mat(K), Rm, tm, cheiral);
        if (inliers < std::max(12.0, 0.5 * (double)old_px.size())) { why = "cheirality"; return; }
        const cv::Matx33d old_to_new(Rm);
        cv::Vec3d rv;
        cv::Rodrigues(cv::Mat(pending_relative.t() * old_to_new.t()), rv);
        pending_delta = rv;
        pending_sigma = 0.004;
        pending_ok = true;
    }

#ifdef ODO_KF_GRID_REPLAY
    // Replay (-DODO_KF_GRID_REPLAY): the delayed update uses the covariance of frame b, then the gyro rows of frames
    // b+1..k are re-integrated from frame b's attitude with the new bias and the covariance walk re-added, so the
    // filter state after frame k equals the one-frame schedule's (fuel_attitude.py arm "staged6r").
    static constexpr int REPLAY_FRAMES = 16, REPLAY_ROWS = 64;
    double P_b[3] = {0, 0, 0}, replay_t[REPLAY_FRAMES], replay_rows[REPLAY_FRAMES][REPLAY_ROWS * 7];
    int replay_n[REPLAY_FRAMES], replay_frames = 0, resets_b = 0;
    bool replay_overflow = false;

    void remember(double t, const double *packet, int n) {
        if (replay_frames >= REPLAY_FRAMES || n > REPLAY_ROWS) { replay_overflow = true; return; }
        replay_t[replay_frames] = t;
        replay_n[replay_frames] = n;
        std::memcpy(replay_rows[replay_frames], packet, sizeof(double) * 7 * n);
        ++replay_frames;
    }

    void delayed_update() {
        if (resets != resets_b) { ++rejected; return; }  // the static-window reset overrides it in the reference too
        if (replay_overflow) { update(pending_ok, pending_delta, pending_sigma, pending_dt, pending_t); return; }
        double P_now[3] = {P[0], P[1], P[2]};
        const int before = accepted;
        std::memcpy(P, P_b, sizeof P);
        update(pending_ok, pending_delta, pending_sigma, pending_dt, pending_t);
        if (accepted == before) { std::memcpy(P, P_now, sizeof P); return; }
        R = R_anchor;
        previous = anchor_t;
        double tprev = anchor_t;
        for (int j = 0; j < replay_frames; ++j) {
            integrate(replay_t[j], replay_rows[j], replay_n[j], bias);
            for (double &p : P) p += WALK * WALK * (replay_t[j] - tprev);
            tprev = replay_t[j];
        }
    }
#endif

    bool final_result = false;
    void run_stage() {
        if (stage >= 1 && stage <= PARTS) { track_slice(stage - 1, true); ++stage; return; }
        if (stage > PARTS && stage <= 2 * PARTS) {
            track_slice(stage - PARTS - 1, false);
            if (++stage > 2 * PARTS) std::swap(pyr_anchor, pyr_current);  // frame b's pyramid anchors the next window
            return;
        }
        if (stage == 2 * PARTS + 1) { final_result = select_and_solve(); ++stage; return; }
        if (stage == 2 * PARTS + 2) {
            if (!final_result) pose();
#ifdef ODO_KF_GRID_REPLAY
            delayed_update();
#else
            update(pending_ok, pending_delta, pending_sigma, pending_dt, pending_t);
#endif
            stage = 0;
            return;
        }
        if (pyramid_due) { build_pyramid(anchor, pyr_anchor); pyramid_due = false; return; }
        if (detect_due) { detect(anchor); detect_due = false; }
    }
#endif

#ifdef ODO_KF_GRID_SPLIT
    // Split schedule: no frame carries more than one heavy stage. The window ending at frame b runs forward KLT at b,
    // backward KLT at b+1, the fit and Kalman update at b+2; corners for the next window (anchor = frame b) are
    // detected at b+3. Measurements equal the one-frame schedule's; only the bias update lands two frames later.
    cv::Mat previous_anchor;
    cv::Matx33d pending_relative;
    double pending_dt = 0, pending_t = 0;
    int stage = 0;               // 1: backward KLT due, 2: fit + update due
    bool detect_due = false;

    void run_stage() {
        if (stage == 1) { backward(previous_anchor, anchor); stage = 2; return; }
        if (stage == 2) {
            cv::Vec3d delta;
            double sigma = 0;
            const bool ok = fit(anchor.rows, anchor.cols, pending_relative, delta, sigma);
            update(ok, delta, sigma, pending_dt, pending_t);
            stage = 0;
            return;
        }
        if (detect_due) { detect(anchor); detect_due = false; }
    }
#endif

    // t: seconds since the origin; packet rows (t, accel xyz, gyro xyz) with origin-relative times; rgb: HxWx3.
    M3 step(double t, const uint8_t *rgb, int width, int height, const double *packet, int n, bool first) {
        cv::cvtColor(cv::Mat(height, width, CV_8UC3, const_cast<uint8_t *>(rgb)), current, cv::COLOR_RGB2GRAY);
        if (first) {
            previous = last_t = anchor_t = 0;
            current.copyTo(anchor);
            R_anchor = R;
#if defined(ODO_KF_GRID_SPLIT) || defined(ODO_KF_GRID_STAGED)
            detect_due = true;
#endif
#ifdef ODO_KF_GRID_STAGED
            pyramid_due = true;
#endif
            return R;
        }
        if (!decided && (!n || packet[0] >= WINDOW)) decide(0.0);
        if (!decided && still_frames < STILL_FRAMES) {
            still_t[still_frames] = t;
            still_n[still_frames] = std::min(n, STILL_ROWS);
            std::memcpy(still_rows[still_frames], packet, sizeof(double) * 7 * still_n[still_frames]);
            ++still_frames;
        }
        integrate(t, packet, n, bias);
#ifdef ODO_KF_GRID_TRACE
        if (decided && still_frames >= 0) {
            std::fprintf(stderr, "decide t=%.3f bias=%.6f %.6f %.6f n=%d\n", t, bias[0], bias[1], bias[2], still_frames);
            still_frames = -1000000;
        }
#endif
        for (double &p : P) p += WALK * WALK * (t - last_t);
        last_t = t;
#if defined(ODO_KF_GRID_STAGED)
#ifdef ODO_KF_GRID_REPLAY
        if (stage > 0) remember(t, packet, n);
#endif
        if (t - anchor_t >= PERIOD - 1e-8) {
            while (stage || detect_due || pyramid_due) run_stage();  // only if frames outpace the stages
            const M3 rel = mul(mul(tr(R_bc), mul(tr(R_anchor), R)), R_bc);
            pending_relative = cv::Matx33d(rel.a[0], rel.a[1], rel.a[2], rel.a[3], rel.a[4], rel.a[5], rel.a[6], rel.a[7], rel.a[8]);
            pending_dt = t - anchor_t;
            pending_t = t;
            build_pyramid(current, pyr_current);
            if (points.size() < 16) {
                why = "few corners";
                update(false, cv::Vec3d(), 0, pending_dt, t);
                std::swap(pyr_anchor, pyr_current);
            } else {
                cv::perspectiveTransform(points, guess, cv::Matx33d(K * pending_relative.t() * Kinv));
                tracked = guess;
                back = points;
                found_fwd.assign(points.size(), 0);
                returned.assign(points.size(), 0);
                stage = 1;
#ifdef ODO_KF_GRID_REPLAY
                std::memcpy(P_b, P, sizeof P);
                resets_b = resets;
                replay_frames = 0;
                replay_overflow = false;
#endif
            }
            current.copyTo(anchor);
            R_anchor = R;
            anchor_t = t;
            detect_due = true;
        } else {
            run_stage();
        }
#elif defined(ODO_KF_GRID_SPLIT)
        if (t - anchor_t >= PERIOD - 1e-8) {
            while (stage || detect_due) run_stage();  // only if frames arrive faster than the stages (dropped frames)
            const M3 rel = mul(mul(tr(R_bc), mul(tr(R_anchor), R)), R_bc);
            pending_relative = cv::Matx33d(rel.a[0], rel.a[1], rel.a[2], rel.a[3], rel.a[4], rel.a[5], rel.a[6], rel.a[7], rel.a[8]);
            pending_dt = t - anchor_t;
            pending_t = t;
            if (points.size() < 16) {
                why = "few corners";
                update(false, cv::Vec3d(), 0, pending_dt, t);
            } else {
                forward(anchor, current, pending_relative);
                stage = 1;
            }
            std::swap(previous_anchor, anchor);
            current.copyTo(anchor);
            R_anchor = R;
            anchor_t = t;
            detect_due = true;
        } else {
            run_stage();
        }
#else
        if (t - anchor_t >= PERIOD - 1e-8) {
            const double dt = t - anchor_t;
            const M3 rel = mul(mul(tr(R_bc), mul(tr(R_anchor), R)), R_bc);
            const cv::Matx33d relative(rel.a[0], rel.a[1], rel.a[2], rel.a[3], rel.a[4], rel.a[5], rel.a[6], rel.a[7], rel.a[8]);
            cv::Vec3d delta;
            double sigma = 0;
            const bool ok = measure(relative, delta, sigma);
            update(ok, delta, sigma, dt, t);
            current.copyTo(anchor);
            R_anchor = R;
            anchor_t = t;
        }
#endif
        return R;
    }
};

}  // namespace odo
