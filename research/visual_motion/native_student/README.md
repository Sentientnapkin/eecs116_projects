# C++ student deployment

The C++ predictor implements CHW normalization, two stride-2 convolutions, feature projection, fixed EMA, and velocity output. It uses the same parameter layout as the existing CNN + EMA predictor and allocates buffers at construction. A separate kinematics component integrates body velocity and applies the calibrated camera lever arm.

Run the host smoke test from the research directory.

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Werror native_student/predictor_test.cpp -o /tmp/vio-predictor-test
/tmp/vio-predictor-test
```

The next porting steps are camera config and ABI entry points, image resize and calibrated history warps, IMU orientation and calibration, camera quaternion and twist output, and export of trained weights. Require full-episode Python/C++/WASM parity and zero filled frames. Measure initialization separately and compare maximum step fuel on the same roster. The host-tested predictor is one component of the port. The frozen SEA-RAFT teacher and preprocessing used to cache its training features run offline.
