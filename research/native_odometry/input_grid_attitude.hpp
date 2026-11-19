#pragma once
// Full-input raw attitude path: causal transcription of training-finish attitude_bias.attitudes(kf_grid).
// Requires odo::M3/eye/mul/tr/exp_so3/mv defined by odometry.hpp before inclusion.
// Does not change model inputs itself; caller consumes R and post-frame bias when deriving them.
#include <vector>
#include <array>
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/video/tracking.hpp>
#include <opencv2/calib3d.hpp>
#ifdef ODO_KF_GRID_TRACE
#include <cstdio>
#endif

namespace odo {

struct InputGridAttitude {
    static constexpr double INIT_VAR = 0.02 * 0.02 / 3, WALK = 0.0006, WHITE = 0.07, WINDOW = 0.8, PERIOD = 0.5;
    M3 R = eye(), R_anchor = eye(), R_bc;
    double bias[3] = {0, 0, 0}, P[3] = {INIT_VAR, INIT_VAR, INIT_VAR}, previous = 0, last_t = 0, anchor_t = 0;
    cv::Matx33d K, Kinv;
    cv::Mat anchor, current, rgb_view;
    bool decided = false, have_anchor = false;
    int accepted = 0, rejected = 0;
    struct StartupFrame { double t; std::vector<double> packet; };
    std::vector<StartupFrame> startup;
    std::vector<M3> startup_rotations;
    bool startup_repropagated = false, window_done = false, measurement_valid = false;
    cv::Vec3d last_delta = {0, 0, 0};
    double last_sigma = 0, median_flow = 0;
    int track_count = 0, occupied_cells = 0;
    bool activated() const { return decided && (bias[0] != 0 || bias[1] != 0 || bias[2] != 0); }

    void init(double fx, double fy, double cx, double cy, const M3 &body_from_camera) {
        *this = InputGridAttitude{};
        cv::setNumThreads(1);
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
        for (const auto &frame : startup)
            for (size_t i = 0; i < frame.packet.size(); i += 7) {
                const double *row = frame.packet.data() + i;
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
        R = eye();
        previous = t0;
        startup_rotations.clear();
        startup_rotations.push_back(eye());
        for (const auto &frame : startup) {
            integrate(frame.t, frame.packet.data(), int(frame.packet.size()/7), bias);
            startup_rotations.push_back(R);
        }
        startup_repropagated = true;
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
    const char *why = "";
    bool measure(const cv::Matx33d &relative, cv::Vec3d &delta, double &sigma) {
        const int h = anchor.rows, w = anchor.cols;
        std::vector<cv::Point2f> points;
        for (int gy = 0; gy < 4; ++gy)
            for (int gx = 0; gx < 4; ++gx) {
                std::vector<cv::Point2f> found;
                const cv::Rect cell(gx * w / 4, gy * h / 4, (gx + 1) * w / 4 - gx * w / 4, (gy + 1) * h / 4 - gy * h / 4);
                cv::goodFeaturesToTrack(anchor(cell), found, 10, 0.003, 5);
                for (const auto &p : found) points.emplace_back(p.x + cell.x, p.y + cell.y);
            }
        if (points.size() < 16) { why = "few corners"; return false; }
        std::vector<cv::Point2f> guess, tracked, back;
        cv::perspectiveTransform(points, guess, cv::Matx33d(K * relative.t() * Kinv));
        tracked = guess;
        std::vector<uchar> found, returned;
        std::vector<float> error;
        cv::calcOpticalFlowPyrLK(anchor, current, points, tracked, found, error, cv::Size(21, 21), 3,
                                 cv::TermCriteria(cv::TermCriteria::COUNT + cv::TermCriteria::EPS, 30, 0.01),
                                 cv::OPTFLOW_USE_INITIAL_FLOW);
        back = points;
        cv::calcOpticalFlowPyrLK(current, anchor, tracked, back, returned, error, cv::Size(21, 21), 3,
                                 cv::TermCriteria(cv::TermCriteria::COUNT + cv::TermCriteria::EPS, 30, 0.01),
                                 cv::OPTFLOW_USE_INITIAL_FLOW);
        std::vector<cv::Point2f> old_px, new_px;
        std::vector<double> flow;
        bool cells[4][4] = {};
        int occupied = 0;
        for (size_t i = 0; i < points.size(); ++i) {
            if (!found[i] || !returned[i] || cv::norm(back[i] - points[i]) >= 0.8) continue;
            old_px.push_back(points[i]); new_px.push_back(tracked[i]);
            flow.push_back(cv::norm(tracked[i] - guess[i]));
            const int cx = std::min(3, (int)(4 * points[i].x / w)), cy = std::min(3, (int)(4 * points[i].y / h));
            if (!cells[cx][cy]) { cells[cx][cy] = true; ++occupied; }
        }
        track_count = int(old_px.size()); occupied_cells = occupied;
        if (old_px.size() < 16 || occupied < 5) { why = "few tracks"; return false; }
        std::vector<double> f = flow;
        std::sort(f.begin(), f.end());
        const size_t m = f.size();
        const double median = m % 2 ? f[m / 2] : .5 * (f[m / 2 - 1] + f[m / 2]);
        median_flow = median;
        if (median <= 1.0) {
            double err;
            if (!fit_rotation(old_px, new_px, Kinv, relative, delta, err) || err > 0.012) { why = "rotation fit"; return false; }
            sigma = 0.002;
            return true;
        }
        cv::Mat mask, Rm, tm;
        try {
            const cv::Mat E = cv::findEssentialMat(old_px, new_px, cv::Mat(K), cv::RANSAC, 0.999, 1.0, 500, mask);
            if (E.rows != 3 || E.cols != 3) { why = "essential"; return false; }
            // Python supplies the RANSAC mask; recoverPose uses it when selecting among pose hypotheses.
            const int inliers = cv::recoverPose(E, old_px, new_px, cv::Mat(K), Rm, tm, mask);
            if (inliers < std::max(12.0, 0.5 * (double)old_px.size())) { why = "cheirality"; return false; }
        } catch (const cv::Exception &) {
            why = "essential-degenerate";
            return false;
        }
        const cv::Matx33d old_to_new(Rm);
        cv::Vec3d rv;
        cv::Rodrigues(cv::Mat(relative.t() * old_to_new.t()), rv);
        delta = rv;
        sigma = 0.004;
        return true;
    }

    // t: seconds since the origin; packet rows (t, accel xyz, gyro xyz) with origin-relative times; rgb: HxWx3.
    M3 step(double t, const uint8_t *rgb, int width, int height, const double *packet, int n, bool first) {
        startup_repropagated = window_done = measurement_valid = false;
        cv::cvtColor(cv::Mat(height, width, CV_8UC3, const_cast<uint8_t *>(rgb)), current, cv::COLOR_RGB2GRAY);
        if (first) {
            previous = last_t = anchor_t = 0;
            current.copyTo(anchor);
            R_anchor = R;
            return R;
        }
        if (!decided && (!n || packet[0] >= WINDOW)) decide(0.0);
        if (!decided) {
            startup.push_back({t, {}});
            if (n) startup.back().packet.assign(packet, packet + 7*n);
        }
        integrate(t, packet, n, bias);
        for (double &p : P) p += WALK * WALK * (t - last_t);
        last_t = t;
        if (t - anchor_t >= PERIOD - 1e-8) {
            window_done = true;
            const double dt = t - anchor_t;
            const M3 rel = mul(mul(tr(R_bc), mul(tr(R_anchor), R)), R_bc);
            const cv::Matx33d relative(rel.a[0], rel.a[1], rel.a[2], rel.a[3], rel.a[4], rel.a[5], rel.a[6], rel.a[7], rel.a[8]);
            cv::Vec3d delta;
            double sigma;
            bool ok = measure(relative, delta, sigma) && cv::norm(delta) <= 0.05;
            if (ok) { last_delta = delta; last_sigma = sigma; }
            measurement_valid = ok;
            double residual[3];
            if (ok) {
                const double dv[3] = {delta[0], delta[1], delta[2]};
                mv(R_bc, dv, residual);                     // body frame, ~ (b_hat - b_true) * dt
                sigma /= dt;
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
            current.copyTo(anchor);
            R_anchor = R;
            anchor_t = t;
        }
        return R;
    }
};

}  // namespace odo
