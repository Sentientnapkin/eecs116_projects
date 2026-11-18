cmake_minimum_required(VERSION 3.16)
project(viobench_openvins_replay LANGUAGES C CXX)

find_package(Eigen3 REQUIRED)
find_package(OpenCV 4 REQUIRED COMPONENTS core calib3d)
find_package(Boost REQUIRED COMPONENTS date_time)
find_package(Ceres REQUIRED)
find_library(OPENVINS_LIBRARY NAMES ov_msckf_lib HINTS "${OPENVINS_BUILD}" REQUIRED)

add_executable(openvins_replay replay.cpp)
target_compile_features(openvins_replay PRIVATE cxx_std_17)
target_compile_definitions(openvins_replay PRIVATE ROS_AVAILABLE=0 ENABLE_ARUCO_TAGS=0)
target_include_directories(openvins_replay PRIVATE
    "${OPENVINS_SOURCE}/ov_core/src"
    "${OPENVINS_SOURCE}/ov_init/src"
    "${OPENVINS_SOURCE}/ov_msckf/src")
target_link_libraries(openvins_replay PRIVATE
    "${OPENVINS_LIBRARY}" Eigen3::Eigen ${OpenCV_LIBS} Boost::date_time Ceres::ceres)
