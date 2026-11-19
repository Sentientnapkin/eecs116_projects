"""Focused checks for cached motion inputs and replay conventions."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from teacher_eval import integrate, load_guest_estimator, load_weights
from teacher_models import Teacher
from visual_motion_cache import flow_features


class VisualMotionTests(unittest.TestCase):
    def test_flow_pixels_padding_and_warp_support(self):
        def synthetic(current, past, **kwargs):
            self.assertEqual(current.shape[-2:], (128, 128))
            self.assertEqual(tuple(current[:, 0, 20, 0]), (17.,))
            self.assertIn(float(past[:, 0, 20, 0]), (23., 29.))
            self.assertEqual(kwargs["iters"], 4)
            flow = current[:, :2].clone().fill_(0)
            flow[:, 0] = 2
            flow[:, 1] = -3
            return {"flow": [flow]}

        images = torch.zeros((1, 5, 96, 128), dtype=torch.uint8)
        images[:, 0:3] = torch.tensor([17, 23, 29])[None, :, None, None]
        images[:, 3] = 255
        features = flow_features(synthetic, images).reshape(1, 6, 12)
        torch.testing.assert_close(features[0, :2, 5], torch.tensor([2., -3.]))
        self.assertEqual(float(features[0, 2, 5]), 1.)
        self.assertLess(float(features[0, 2, 0]), 1.)
        self.assertFalse(features[0, 3:].any())

    def test_cached_ssm_chunking_and_future_perturbation(self):
        config = json.loads(Path("configs/visual-motion-screen.json").read_text())["model"]
        model = Teacher(dict(config, cached_visual_size=72)).eval()
        x, imu = torch.randn(1, 12, 72), torch.zeros(1, 12, 51)
        imu[..., 13] = .05
        with torch.inference_mode():
            full, _ = model(x, imu)
            first, state = model(x[:, :5], imu[:, :5])
            rest, _ = model(x[:, 5:], imu[:, 5:], state)
            x[:, 5:] *= 10
            other, _ = model(x, imu)
        torch.testing.assert_close(full, torch.cat((first, rest), dim=1))
        torch.testing.assert_close(full[:, :5], other[:, :5])

    def test_guest_loads_bundle_orientation_even_when_host_is_imported(self):
        import orientation
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/"orientation.py").write_text("value = 42\n")
            (folder/"streaming.py").write_text("from orientation import value\nEstimator = value\n")
            self.assertEqual(load_guest_estimator(folder), 42)
        import orientation as after
        self.assertIs(after, orientation)

    def test_last_ema_uses_completed_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run/"config.json").write_text('{"training": {"weight_ema": 0.995}}')
            for number in (1, 2):
                (run/f"checkpoints/epoch-{number:04d}").mkdir(parents=True)
            complete = run/"checkpoints/epoch-0001"
            (complete/"complete.json").write_text("{}")
            torch.save({"n_averaged": torch.tensor(9), "module.weight": torch.tensor(42)},
                       complete/"custom_checkpoint_1.pkl")
            self.assertEqual(load_weights(run, "last"), {"weight": torch.tensor(42)})

    def test_integration_includes_camera_lever_arm(self):
        rotations = np.array([np.eye(3), [[0, -1, 0], [1, 0, 0], [0, 0, 1]]])
        extrinsic = np.eye(4)
        extrinsic[:3, 3] = (1, 0, 0)
        position = integrate(np.zeros((2, 3)), {
            "R": rotations, "times": np.array([0., 1.]), "T_bc": extrinsic})
        np.testing.assert_allclose(position, [[0, 0, 0], [-1, 1, 0]])


if __name__ == "__main__":
    unittest.main()
