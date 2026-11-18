"""Focused regressions for the teacher data, sampling, metrics and models.

    ./teacher_env.sh -m unittest test_teacher     (or: ./teacher_env.sh test_teacher.py)
"""
import unittest

import numpy as np
import torch

from teacher_data import CATEGORIES, WindowPlan, motion_labels, validate_roster
from teacher_ledger import checks, split_for
from teacher_models import Teacher
from teacher_train import loss_fn, sim3_ate


def labels_for(v, dt=.05):
    times = np.arange(len(v))*dt
    world = np.cumsum(v*dt, axis=0)
    cam = np.stack((-world[:, 1], -world[:, 2], world[:, 0]), axis=1)  # body x fwd,y left,z up -> camera x right,y down,z fwd
    return motion_labels(v, times, cam)


def synthetic(n_parents=6, frames=200):
    records, labels = [], []
    for i in range(n_parents):
        v = np.tile([.5, 0, 0], (frames, 1)).astype(float)
        if i % 3 == 0: v[120:160] = [-.5, 0, 0]   # backward stretch in a third of the parents
        if i % 3 == 1: v[40:80] = [0, .5, 0]      # lateral stretch
        records.append({"scene": f"S{i//2}", "frames": frames, "file": f"{i}.npz"})
        labels.append(labels_for(v))
    return records, labels


class Leakage(unittest.TestCase):
    def test_scene_split_policy(self):
        self.assertEqual(split_for("ProcTHOR-Train-166"), "development")
        self.assertEqual(split_for("ProcTHOR-Train-163"), "final_test")
        self.assertEqual(split_for("ProcTHOR-Train-177"), "confirmation")
        self.assertEqual(split_for("ProcTHOR-Train-155"), "proxy_validation")
        self.assertEqual(split_for("ProcTHOR-Train-20"), "train")

    def test_ledger_detects_duplicates_and_scene_leaks(self):
        rows = [{"sha256": "a", "path": "x", "scene": "S1", "split": "train"},
                {"sha256": "a", "path": "y", "scene": "S2", "split": "train"},
                {"sha256": "b", "path": "z", "scene": "S1", "split": "development"}]
        issues = checks(rows)
        self.assertTrue(any("duplicate" in i for i in issues))
        self.assertTrue(any("several splits" in i for i in issues))

    def test_roster_overlap_rejected(self):
        with self.assertRaises(ValueError):
            validate_roster({"train": [{"scene": "A", "sha256": "1"}], "development": [{"scene": "A", "sha256": "2"}]})


class Sampling(unittest.TestCase):
    def test_labels(self):
        v = np.tile([.5, 0, 0], (100, 1)).astype(float); v[50:] = [-.5, 0, 0]
        lab = labels_for(v)
        self.assertTrue(lab["backward"][60:].all() and not lab["backward"][:40].any())
        self.assertFalse(labels_for(np.zeros((50, 3)))["backward"].any())  # near-zero speed is hover only
        self.assertTrue(labels_for(np.zeros((50, 3)))["hover"].all())

    def test_deterministic_and_counted(self):
        records, labels = synthetic()
        opts = {"mode": "balanced", "windows_per_epoch": 60, "mixture": {"uniform": .4, "backward": .3, "lateral": .3}}
        a = WindowPlan(records, labels, 48, 16, opts, 5)
        self.assertEqual(a.plan(3), WindowPlan(records, labels, 48, 16, opts, 5).plan(3))
        self.assertNotEqual(a.plan(3), a.plan(4))
        items = a.plan(0)
        e = a.exposure(items)
        self.assertEqual(e["windows"], 60)
        self.assertEqual(sum(e["draws"].values()), 60)
        self.assertEqual(e["burn_in_frames"], 60*16)
        # Every window drawn for a category really contains it.
        for i, start, kind in items:
            if kind in CATEGORIES:
                self.assertGreaterEqual(labels[i][kind][start+16:start+48].sum(), 4)
        self.assertGreater(e["windows_containing"]["backward"], .2)

    def test_original_mode_covers_parents_evenly(self):
        records, labels = synthetic(n_parents=10)
        plan = WindowPlan(records, labels, 48, 16, {"mode": "original", "windows_per_epoch": 10}, 1)
        seen = []
        for epoch in range(4):
            items = plan.plan(epoch)
            self.assertEqual(sum(k == "startup" for _, _, k in items), 5)
            seen += [i for i, _, k in items if k == "startup"]
        self.assertEqual(sorted(np.bincount(seen, minlength=10).tolist()), [2]*10)


class DomainShare(unittest.TestCase):
    def test_domain_share_respected(self):
        records, labels = synthetic(n_parents=12)
        for i, r in enumerate(records): r["domain"] = "native" if i < 2 else "proxy"
        opts = {"mode": "balanced", "windows_per_epoch": 400, "mixture": {"uniform": .5, "backward": .5},
                "domain_share": {"native": .25, "proxy": .75}}
        items = WindowPlan(records, labels, 48, 16, opts, 3).plan(0)
        native = np.mean([records[i]["domain"] == "native" for i, _, _ in items])
        self.assertAlmostEqual(native, .25, delta=.06)


class Metrics(unittest.TestCase):
    def test_sim3_invariance(self):
        rng = np.random.default_rng(0)
        truth = np.cumsum(rng.normal(size=(200, 3)), axis=0)
        q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        if np.linalg.det(q) < 0: q[:, 0] *= -1
        estimate = 2.5*truth@q.T + np.array([1., -2, 3])
        self.assertLess(sim3_ate(estimate, truth), 1e-9)
        self.assertGreater(sim3_ate(estimate + rng.normal(size=estimate.shape), truth), .1)

    def test_horizon_longer_than_window_is_finite(self):
        n = 20
        row = {"v": torch.zeros(1, n, 3), "R": torch.eye(3).repeat(1, n, 1, 1),
               "times": torch.arange(n, dtype=torch.float32)[None]*.05,
               "T_bc": torch.eye(4)[None], "cam_gt": torch.zeros(1, n, 3)}
        loss = loss_fn(torch.zeros(1, n, 3), row, burn=5, horizons=[6.])
        self.assertTrue(torch.isfinite(loss) and float(loss) == 0.)


class Models(unittest.TestCase):
    cfg = {"width": 32, "height": 24, "channels": [8, 8, 8, 8], "embedding": 16, "hidden": 16,
           "layers": 2, "states": 4, "correlation": True, "correlation_radius": 1, "frame_chunk": 4}

    def inputs(self, steps=10, seed=0):
        g = torch.Generator().manual_seed(seed)
        images = torch.randint(0, 255, (1, steps, 5, 24, 32), generator=g, dtype=torch.uint8)
        imu = torch.randn(1, steps, 51, generator=g); imu[..., 13] = .05
        return images, imu

    def test_causal_and_streaming(self):
        for head in ("gru", "ssm", "gru_res", "gru_ssm"):
            torch.manual_seed(0)
            net = Teacher(dict(self.cfg, head=head)).eval()
            images, imu = self.inputs()
            with torch.no_grad():
                full, _ = net(images, imu)
                changed = images.clone(); changed[:, 6:] = 0
                imu2 = imu.clone(); imu2[:, 6:] += 3
                prefix, _ = net(changed, imu2)
                torch.testing.assert_close(full[:, :6], prefix[:, :6])  # future inputs cannot change the past
                a, state = net(images[:, :4], imu[:, :4])
                b, _ = net(images[:, 4:], imu[:, 4:], state)
                torch.testing.assert_close(torch.cat((a, b), 1), full, atol=1e-5, rtol=1e-4)  # chunked == whole


    @unittest.skipUnless(torch.cuda.is_available(), "cuDNN flat GRU buffers exist only on CUDA")
    def test_checkpoint_keeps_every_tensor(self):
        import tempfile
        from accelerate import Accelerator
        accelerator = Accelerator()
        for head in ("gru", "gru_res", "gru_ssm", "ssm"):
            net = accelerator.prepare(Teacher(dict(self.cfg, head=head)))
            want = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
            with tempfile.TemporaryDirectory() as tmp:
                accelerator.save_state(tmp, safe_serialization=False)  # as teacher_train.py does
                with torch.no_grad():
                    for p in net.parameters(): p.zero_()
                accelerator.load_state(tmp)
            got = net.state_dict()
            self.assertEqual(set(got), set(want), head)
            for k in want: torch.testing.assert_close(got[k].cpu(), want[k], msg=f"{head} {k}")
            accelerator._models.clear()


if __name__ == "__main__":
    unittest.main()
