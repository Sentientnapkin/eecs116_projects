"""ABI regression on synthetic RGB, a camera lever arm and nonzero time origin."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from viobench.tools.abi.config import default_guest_config
from viobench.tools.runner.sandbox import Sandbox

from replay import Host, max_abs
from streaming import Inputs, quaternion


class GuestTest(unittest.TestCase):
    def test_absolute_time_and_reset(self):
        camera = default_guest_config()
        camera["T_cam_imu"][0][3] = .08
        camera["T_cam_imu"][2][3] = -.17
        rot = np.array(camera["T_cam_imu"])[:3, :3].T
        ref = Inputs(self.sensor, camera, (240, 320), rot)
        host = Host(self.build)
        # Send length-delimited malformed input through the public C ABI.
        self.assertEqual(host.lib.init(b"{}", 2), -1)
        logs = TemporaryDirectory(prefix="odometry-abi-")
        self.addCleanup(logs.cleanup)
        guest = Sandbox(self.build / "odometry.wasm", log_dir=logs.name)
        guest.init(camera)
        host.init(camera)
        rng = np.random.default_rng(116)
        rgb = rng.integers(0, 256, (240, 320, 3), dtype=np.uint8)
        out = np.empty(13, dtype=np.float64)
        images = np.empty((5, self.sensor["height"], self.sensor["width"]), dtype=np.uint8)
        imu = np.empty(51, dtype=np.float32)
        rotation = np.empty((3, 3), dtype=np.float64)
        origin = 10.
        first = None
        for i in range(26):
            absolute_t = origin + i * .05
            t = absolute_t - origin
            packet = np.zeros((20, 7), dtype=np.float64)
            packet[:, 0] = absolute_t - .05 + np.arange(1, 21) * .0025
            packet[:, 3] = 9.81
            packet[:, 4:7] = (.22, -.10, .05)
            self.assertEqual(host.lib.step(absolute_t, rgb, packet, len(packet), out), 0)
            result = guest.step(absolute_t, rgb, packet)
            np.testing.assert_allclose(np.r_[result.pose, result.twist], out, atol=.002, rtol=0)
            self.assertAlmostEqual(np.linalg.norm(out[3:7]), 1., places=12)
            if i == 0:
                first = out.copy()
                np.testing.assert_array_equal(first[:7], [0, 0, 0, 0, 0, 0, 1])
            host.lib.host_features(images, imu, rotation)
            packet[:, 0] -= origin
            im, u, R, _ = ref.step(t, rgb, packet if i else packet[:0], "triple_derot")
            self.assertLessEqual(max_abs(images.astype(np.int16), im), 1)
            self.assertLessEqual(max_abs(imu, u), .00002)
            self.assertLessEqual(max_abs(rotation, R), 1e-8)
            np.testing.assert_allclose(out[3:7], quaternion(rot.T @ R @ rot), atol=1e-7, rtol=0)
            expected_gyro = rot.T @ (packet[-1, 4:7] - ref.orient.total_bias) if i else np.zeros(3)
            np.testing.assert_allclose(out[10:13], expected_gyro, atol=1e-12, rtol=0)
        self.assertEqual(host.lib.step(absolute_t, rgb, packet, len(packet), out), -1)
        host.init(camera)
        self.assertEqual(host.lib.step(origin, rgb, packet[:0], 0, out), 0)
        np.testing.assert_array_equal(out, first)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    GuestTest.build = args.build
    GuestTest.sensor = json.loads(args.manifest.read_text())["sensor_config"]
    unittest.main(argv=[__file__])
