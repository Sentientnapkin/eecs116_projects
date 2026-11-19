"""Meaningful raw-input startup, timing, reset and visual tracking contracts."""
import argparse
import ctypes as ct
import json
from pathlib import Path
import sys
import unittest
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / 'native_odometry'))
from replay import Host
from new_input_reference import NewInputReference
from orientation import exp_so3
from viobench.tools.abi.config import default_guest_config
from viobench.tools.runner.sandbox import Sandbox


class RawInputContracts(unittest.TestCase):
    def run_case(self, rate, textured=False):
        camera = default_guest_config()
        camera['T_cam_imu'][0][3] = .08; camera['T_cam_imu'][2][3] = -.17
        rbc = np.asarray(camera['T_cam_imu'])[:3, :3].T
        ref = NewInputReference(self.sensor, camera, (240, 320), rbc)
        host = Host(self.build); host.init(camera)
        array = lambda dtype: np.ctypeslib.ndpointer(dtype=dtype, flags='C_CONTIGUOUS')
        host.lib.input_features.argtypes = [array(np.uint8), array(np.float32), array(np.float64), array(np.float64)]
        guest = Sandbox(self.build / 'odometry.wasm', log_dir=self.out / ('visual' if textured else str(rate)))
        guest.init(camera)
        rng = np.random.default_rng(116)
        source = rng.integers(0, 256, (240, 320, 3), dtype=np.uint8) if textured else np.zeros((240, 320, 3), np.uint8)
        K = np.array([[camera['fx'], 0, camera['cx']], [0, camera['fy'], camera['cy']], [0, 0, 1.]])
        outputs = []
        origin = 10.045
        for i in range(26):
            absolute = origin + i * .05; t = absolute - origin
            packet = np.zeros((10, 7), dtype=np.float64)
            packet[:, 0] = absolute - .05 + np.arange(1, 11) * .005
            packet[:, 3] = 9.81; packet[:, 4:7] = rate
            true_R = exp_so3(np.asarray(rate) * t)
            if textured:
                cam_R = rbc.T @ true_R @ rbc
                rgb = cv2.warpPerspective(source, K @ cam_R.T @ np.linalg.inv(K), (320, 240))
            else: rgb = source
            out = np.zeros(13); self.assertEqual(host.lib.step(absolute, rgb, packet, len(packet), out), 0)
            result = guest.step(absolute, rgb, packet)
            outputs.append(np.r_[result.pose, result.twist])
            np.testing.assert_allclose(outputs[-1], out, atol=2e-5, rtol=0)
            images, imu, rotation, state = np.empty((5, 96, 128), np.uint8), np.empty(51, np.float32), np.empty((3, 3)), np.empty(13)
            host.lib.input_features(images, imu, rotation, state)
            relative_packet = packet.copy(); relative_packet[:, 0] -= origin
            im, u, R, _ = ref.step(t, rgb, relative_packet)
            if not textured:
                np.testing.assert_array_equal(images, im)
                np.testing.assert_allclose(imu, u, atol=2e-7, rtol=0)
                np.testing.assert_allclose(rotation, R, atol=1e-12, rtol=0)
            self.assertAlmostEqual(float(np.linalg.norm(out[3:7])), 1.0, places=12)
            if i == 0:
                first_native = out.copy()
                np.testing.assert_array_equal(out[:7], [0, 0, 0, 0, 0, 0, 1])
        host.init(camera)
        out = np.zeros(13)
        packet = np.zeros((0, 7))
        self.assertEqual(host.lib.step(origin, source, packet, 0, out), 0)
        np.testing.assert_array_equal(out, first_native)
        if textured: self.assertGreaterEqual(state[7], 1, 'No visual update accepted on analytic rotating texture')

    def test_static_bias_startup(self): self.run_case((.012, -.008, .004))
    def test_rotating_start_rejects_static_bias(self): self.run_case((.22, -.10, .05))
    def test_visual_rotation_updates(self): self.run_case((0., .30, 0.), textured=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('build', type=Path);p.add_argument('manifest', type=Path)
    p.add_argument('--out', type=Path, required=True);a = p.parse_args()
    RawInputContracts.build = a.build; RawInputContracts.sensor = json.loads(a.manifest.read_text())['sensor_config']
    a.out.mkdir(parents=True, exist_ok=True);RawInputContracts.out = a.out
    unittest.main(argv=[__file__])
