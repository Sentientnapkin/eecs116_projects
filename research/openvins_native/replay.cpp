#include "cam/CamRadtan.h"
#include "core/VioManager.h"
#include "state/State.h"
#include "utils/print.h"
#include "utils/quat_ops.h"
#include "utils/sensor_data.h"

#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
class Estimator : public ov_msckf::VioManager {
public:
  using VioManager::VioManager;
  bool updated_by_zupt() const { return did_zupt_update; }
  bool ready() const { return is_initialized_vio; }
};

void read_bytes(std::istream &input, void *out, std::streamsize count) {
  if (!input.read(static_cast<char *>(out), count)) {
    throw std::runtime_error("Incomplete replay input");
  }
}

template <typename T> T read(std::istream &input) {
  T value;
  read_bytes(input, &value, sizeof(value));
  return value;
}

ov_msckf::VioManagerOptions options(std::istream &input, int w, int h, const std::string &mode) {
  ov_msckf::VioManagerOptions result;
  result.try_zupt = mode != "0";
  if (mode == "2" || mode == "3") {
    result.zupt_max_disparity = 0.0;
  }
  if (mode == "3") {
    // Retain the non-jerk initializer path while rejecting each post-init ZUPT.
    result.zupt_options.chi2_multipler = 0.0;
  }
  result.use_stereo = false;
  result.use_aruco = false;
  result.use_multi_threading_pubs = false;
  result.num_opencv_threads = 1;
  result.init_options.use_stereo = false;
  result.init_options.init_dyn_use = true;
  result.init_options.init_dyn_mle_max_threads = 1;
  // The YAML loader normally fills these fields. This wrapper provides a
  // factory-calibrated IMU directly, using the default Kalibr upper-triangle layout.
  result.vec_dw << 1, 0, 1, 0, 0, 1;
  result.vec_da = result.vec_dw;
  result.vec_tg.setZero();
  result.q_ACCtoIMU = ov_core::rot_2_quat(Eigen::Matrix3d::Identity());
  result.q_GYROtoIMU = result.q_ACCtoIMU;

  Eigen::Matrix<double, 8, 1> intrinsics;
  for (int i = 0; i < intrinsics.size(); ++i) {
    intrinsics(i) = read<double>(input);
  }
  auto camera = std::make_shared<ov_core::CamRadtan>(w, h);
  camera->set_value(intrinsics);
  result.camera_intrinsics.emplace(0, camera);
  result.init_options.camera_intrinsics.emplace(0, camera);

  Eigen::Matrix3d camera_to_body;
  for (int row = 0; row < 3; ++row) {
    for (int col = 0; col < 3; ++col) {
      camera_to_body(row, col) = read<double>(input);
    }
  }
  Eigen::Vector3d camera_origin;
  for (int i = 0; i < 3; ++i) {
    camera_origin(i) = read<double>(input);
  }
  Eigen::Matrix<double, 7, 1> body_to_camera;
  body_to_camera.head<4>() = ov_core::rot_2_quat(camera_to_body.transpose());
  body_to_camera.tail<3>() = -camera_to_body.transpose() * camera_origin;
  result.camera_extrinsics.emplace(0, body_to_camera);
  result.init_options.camera_extrinsics.emplace(0, body_to_camera);

  auto &noise = result.imu_noises;
  auto &init = result.init_options;
  noise.sigma_w = init.sigma_w = read<double>(input);
  noise.sigma_wb = init.sigma_wb = read<double>(input);
  noise.sigma_a = init.sigma_a = read<double>(input);
  noise.sigma_ab = init.sigma_ab = read<double>(input);
  noise.sigma_w_2 = noise.sigma_w * noise.sigma_w;
  noise.sigma_wb_2 = noise.sigma_wb * noise.sigma_wb;
  noise.sigma_a_2 = noise.sigma_a * noise.sigma_a;
  noise.sigma_ab_2 = noise.sigma_ab * noise.sigma_ab;
  return result;
}

class ImuStream {
public:
  void feed(std::istream &input, Estimator &estimator, double camera_time) {
    const auto count = read<std::uint32_t>(input);
    for (std::uint32_t i = 0; i < count; ++i) {
      ov_core::ImuData sample;
      sample.timestamp = read<double>(input);
      for (int j = 0; j < 3; ++j) {
        sample.am(j) = read<double>(input);
      }
      for (int j = 0; j < 3; ++j) {
        sample.wm(j) = read<double>(input);
      }
      if (sample.timestamp > camera_time || (seen_ && sample.timestamp <= last_.timestamp)) {
        throw std::runtime_error("Non-causal or out-of-order IMU packet");
      }
      estimator.feed_measurement_imu(sample);
      last_ = sample;
      seen_ = true;
    }
    // Some episodes have a small gap from the last sample to the camera time.
    // Hold that already-delivered IMU value until exposure to bound interpolation causally.
    if (seen_ && last_.timestamp < camera_time) {
      last_.timestamp = camera_time;
      estimator.feed_measurement_imu(last_);
    }
  }

private:
  ov_core::ImuData last_;
  bool seen_ = false;
};
} // namespace

int main(int argc, char **argv) {
  try {
    const std::string mode = argc >= 4 ? argv[3] : "";
    const bool diagnostics = argc == 5 && std::string(argv[4]) == "--diagnose";
    if ((argc != 4 && !diagnostics) || (mode != "0" && mode != "1" && mode != "2" && mode != "3")) {
      throw std::invalid_argument("Usage: openvins_replay INPUT OUTPUT ZUPT_MODE [--diagnose]");
    }
    std::ifstream input(argv[1], std::ios::binary);
    std::ofstream output(argv[2]);
    if (!input || !output) {
      throw std::runtime_error("Cannot open replay input or output");
    }
    const auto w = read<std::uint32_t>(input);
    const auto h = read<std::uint32_t>(input);
    const auto frames = read<std::uint32_t>(input);
    if (w == 0 || h == 0 || frames == 0) {
      throw std::runtime_error("Empty replay input");
    }
    auto config = options(input, w, h, mode);
    const auto log_level = diagnostics ? (mode == "3" ? ov_core::Printer::DEBUG : ov_core::Printer::INFO)
                                       : ov_core::Printer::WARNING;
    ov_core::Printer::setPrintLevel(log_level);
    Estimator estimator(config);
    const auto state = estimator.get_state();
    ImuStream imu;
    output << std::setprecision(17);
    for (std::uint32_t frame = 0; frame < frames; ++frame) {
      const double timestamp = read<double>(input);
      imu.feed(input, estimator, timestamp);
      cv::Mat image(static_cast<int>(h), static_cast<int>(w), CV_8UC1);
      read_bytes(input, image.data, image.total());
      ov_core::CameraData camera;
      camera.timestamp = timestamp;
      camera.sensor_ids = {0};
      camera.images = {image};
      camera.masks = {cv::Mat::zeros(image.size(), CV_8UC1)};
      estimator.feed_measurement_camera(camera);
      const bool valid = estimator.ready() && std::abs(state->_timestamp - timestamp) < 1e-7;
      const Eigen::Vector3d position = state->_imu->pos();
      const Eigen::Matrix3d body_to_world = state->_imu->Rot().transpose();
      output << timestamp << ',' << valid << ',' << (valid && estimator.updated_by_zupt());
      for (int i = 0; i < 3; ++i) {
        output << ',' << position(i);
      }
      for (int row = 0; row < 3; ++row) {
        for (int col = 0; col < 3; ++col) {
          output << ',' << body_to_world(row, col);
        }
      }
      output << '\n';
    }
    if (!output) {
      throw std::runtime_error("Replay output write failed");
    }
    return 0;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
