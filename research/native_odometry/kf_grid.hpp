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
    int still_frames = 0, accepted = 0, rejected = 0;
#ifdef ODO_VEL_FUSION
    // research/vel_fusion.py (--direction knownrot, arm a_replace): per-window camera translation direction
    bool window_done = false, dir_valid = false;
    double dir_world[3] = {0, 0, 0};   // unit camera-centre displacement direction, kf_grid world frame
    cv::Vec3d dir_cam;
    int dir_inliers = 0;
    double dir_flow = 0;
#endif
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

#ifdef ODO_VEL_FUSION
    // vel_fusion.known_rotation_direction: camera-k centre direction in camera-a axes with the rotation fixed to
    // `relative` (camera-k vectors -> camera-a): null vector of rows (relative x_new) x x_old (normalised) over the
    // RANSAC & cheirality inliers; sign by majority two-view depth cheirality.
    bool known_rotation_direction(const std::vector<cv::Point2f> &old_px, const std::vector<cv::Point2f> &new_px,
                                  const cv::Mat &ransac, const cv::Mat &cheiral, const cv::Matx33d &relative, cv::Vec3d &c) const {
        cv::Matx33d M = cv::Matx33d::zeros();
        std::vector<cv::Vec3d> xo, xn;
        for (size_t i = 0; i < old_px.size(); ++i) {
            if (!ransac.at<uchar>((int)i) || (!cheiral.empty() && !cheiral.at<uchar>((int)i))) continue;
            const cv::Vec3d o = Kinv * cv::Vec3d(old_px[i].x, old_px[i].y, 1);
            const cv::Vec3d n = relative * (Kinv * cv::Vec3d(new_px[i].x, new_px[i].y, 1));
            cv::Vec3d r = n.cross(o);
            const double norm = cv::norm(r);
            r *= 1.0 / std::max(norm, 1e-12);
            M += r * r.t();
            xo.push_back(o); xn.push_back(n);
        }
        if (xo.size() < 8) return false;
        cv::Matx31d values;
        cv::Matx33d vectors;
        cv::eigen(M, values, vectors);                      // descending; smallest = last row
        c = cv::Vec3d(vectors(2, 0), vectors(2, 1), vectors(2, 2));
        int vote = 0;
        for (size_t i = 0; i < xo.size(); ++i) {
            // least squares [xo, -xn] [l1 l2]^T = c
            const cv::Vec3d &a = xo[i], &b = xn[i];
            const double aa = a.dot(a), ab = -a.dot(b), bb = b.dot(b), ac = a.dot(c), bc = -b.dot(c);
            const double det = aa * bb - ab * ab;
            if (std::fabs(det) < 1e-15) continue;
            const double l1 = (bb * ac - ab * bc) / det, l2 = (aa * bc - ab * ac) / det;
            vote += (l1 > 0 && l2 > 0) ? 1 : ((l1 < 0 && l2 < 0) ? -1 : 0);
        }
        if (vote < 0) c = -c;
        return true;
    }
#endif

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
        if (old_px.size() < 16 || occupied < 5) { why = "few tracks"; return false; }
        std::vector<double> f = flow;
        std::sort(f.begin(), f.end());
        const size_t m = f.size();
        const double median = m % 2 ? f[m / 2] : .5 * (f[m / 2 - 1] + f[m / 2]);
#ifdef ODO_VEL_FUSION
        dir_flow = median;
#endif
        if (median <= 1.0) {
            double err;
            if (!fit_rotation(old_px, new_px, Kinv, relative, delta, err) || err > 0.012) { why = "rotation fit"; return false; }
            sigma = 0.002;
            return true;
        }
        cv::Mat mask, Rm, tm;
        const cv::Mat E = cv::findEssentialMat(old_px, new_px, cv::Mat(K), cv::RANSAC, 0.999, 1.0, 500, mask);
        if (E.rows != 3 || E.cols != 3) { why = "essential"; return false; }
        cv::Mat cheiral;  // no input mask: like the reference, every tracked point enters the cheirality count
#ifdef ODO_KFG_RECOVER_RANSAC_MASK
        // Explicit parity repair: the Python reference passes the RANSAC mask.
        // Keep historical guests reproducible without this separately named flag.
        cheiral = mask.clone();
#endif
        const int inliers = cv::recoverPose(E, old_px, new_px, cv::Mat(K), Rm, tm, cheiral);
        if (inliers < std::max(12.0, 0.5 * (double)old_px.size())) { why = "cheirality"; return false; }
#ifdef ODO_VEL_FUSION
        // Python passes the RANSAC mask into recoverPose, which leaves it = RANSAC inliers passing cheirality.
        dir_inliers = inliers;
        dir_valid = known_rotation_direction(old_px, new_px, mask, cheiral, relative, dir_cam);
#endif
        const cv::Matx33d old_to_new(Rm);
        cv::Vec3d rv;
        cv::Rodrigues(cv::Mat(relative.t() * old_to_new.t()), rv);
        delta = rv;
        sigma = 0.004;
        return true;
    }

    // t: seconds since the origin; packet rows (t, accel xyz, gyro xyz) with origin-relative times; rgb: HxWx3.
    M3 step(double t, const uint8_t *rgb, int width, int height, const double *packet, int n, bool first) {
        cv::cvtColor(cv::Mat(height, width, CV_8UC3, const_cast<uint8_t *>(rgb)), current, cv::COLOR_RGB2GRAY);
        if (first) {
            previous = last_t = anchor_t = 0;
            current.copyTo(anchor);
            R_anchor = R;
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
        if (t - anchor_t >= PERIOD - 1e-8) {
            const double dt = t - anchor_t;
            const M3 rel = mul(mul(tr(R_bc), mul(tr(R_anchor), R)), R_bc);
            const cv::Matx33d relative(rel.a[0], rel.a[1], rel.a[2], rel.a[3], rel.a[4], rel.a[5], rel.a[6], rel.a[7], rel.a[8]);
            cv::Vec3d delta;
            double sigma;
#ifdef ODO_VEL_FUSION
            dir_valid = false; dir_inliers = 0; dir_flow = 0;
#endif
            bool ok = measure(relative, delta, sigma) && cv::norm(delta) <= 0.05;
#ifdef ODO_VEL_FUSION
            window_done = true;
            dir_valid = dir_valid && dir_inliers >= 30 && dir_flow >= 2.0;
            if (dir_valid) {
                const M3 Rw = mul(R_anchor, R_bc);            // world_from_camera at the window anchor
                const double dc[3] = {dir_cam[0], dir_cam[1], dir_cam[2]};
                mv(Rw, dc, dir_world);
                const double n = std::sqrt(dir_world[0] * dir_world[0] + dir_world[1] * dir_world[1] + dir_world[2] * dir_world[2]);
                for (double &x : dir_world) x /= n;
            }
#endif
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
#if defined(ODO_VEL_FUSION) && defined(ODO_FUSION_REQUIRE_ACCEPTED_ROTATION)
            // Frozen reference vis_ok includes acceptance of the rotation fit.
            dir_valid = dir_valid && ok;
#endif
            current.copyTo(anchor);
            R_anchor = R;
            anchor_t = t;
        }
        return R;
    }
};

}  // namespace odo
