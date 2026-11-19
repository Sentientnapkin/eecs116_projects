"""Focused regressions for the odometry data, sampling, metrics and models.

    ./odometry_env.sh -m unittest test_odometry     (or: ./odometry_env.sh test_odometry.py)
"""
import unittest

import numpy as np
import torch

from odometry_data import CATEGORIES, WindowPlan, motion_labels, validate_roster
from odometry_eval import batched_velocities
from odometry_ledger import checks, split_for
from odometry_models import OdometryNet
from odometry_train import loss_fn, replay


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

    def test_batched_replay_keeps_independent_states_and_lengths(self):
        rows = []
        for length in (5, 9):
            images, imu = self.inputs(length, seed=length)
            rows.append({"images": images[0].numpy(), "imu": imu[0].numpy(),
                         "R": np.broadcast_to(np.eye(3), (length, 3, 3)), "times": np.arange(length) * .05})
        for head in ("ssm", "gru", "ema", "gru_res", "gru_ssm"):
            with self.subTest(head=head):
                net = OdometryNet({**self.cfg, "head": head}).eval()
                batched = batched_velocities(net, rows, "cpu", chunk=4)
                for row, actual in zip(rows, batched):
                    solo = batched_velocities(net, [row], "cpu", chunk=4)[0]
                    np.testing.assert_allclose(actual, solo, atol=1e-5, rtol=1e-5)

    def test_causal_and_streaming(self):
        for head in ("gru", "ssm", "gru_res", "gru_ssm"):
            torch.manual_seed(0)
            net = OdometryNet(dict(self.cfg, head=head)).eval()
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

    def test_parallel_scan_matches_loop(self):
        from odometry_models import SelectiveBlock
        torch.manual_seed(1)
        for scan, chunk in (("parallel", 1), ("parallel", 5), ("parallel", 32),
                            ("parallel", 200), ("prefix", 5), ("prefix", 96)):
            loop = SelectiveBlock(16, 8).double()
            with torch.no_grad():  # spread rates and inputs over the clamp range, as training can
                loop.log_rate.uniform_(-4, 4); loop.parameters_in.weight.mul_(4)
            fast = SelectiveBlock(16, 8, scan, chunk).double()
            fast.load_state_dict(loop.state_dict())
            x = torch.randn(3, 70, 16, dtype=torch.float64, requires_grad=True)
            dt = torch.rand(3, 70, dtype=torch.float64)*.1; dt[:, 0] = 2.  # large first interval
            h0 = torch.randn(3, 16, 8, dtype=torch.float64)
            for memory in (None, h0):
                y1, s1 = loop(x, dt, memory); y2, s2 = fast(x, dt, memory)
                torch.testing.assert_close(y2, y1, atol=1e-10, rtol=1e-9); torch.testing.assert_close(s2, s1)
                g1 = torch.autograd.grad(y1.square().sum(), [x, loop.log_rate])
                g2 = torch.autograd.grad(y2.square().sum(), [x, fast.log_rate])
                for a, b in zip(g1, g2): torch.testing.assert_close(b, a, atol=1e-9, rtol=1e-8)
            with torch.no_grad():  # float32, as trained: ~1e-5
                y1, _ = loop.float()(x.float(), dt.float()); y2, _ = fast.float()(x.float(), dt.float())
                torch.testing.assert_close(y2, y1, atol=1e-5, rtol=1e-5)
        # Whole model: parallel == loop, and chunked == whole streaming with the parallel scan.
        torch.manual_seed(0)
        loop = OdometryNet(dict(self.cfg, head="ssm")).eval()
        fast = OdometryNet(dict(self.cfg, head="ssm", ssm_scan="parallel", ssm_chunk=3)).eval()
        fast.load_state_dict(loop.state_dict())
        images, imu = self.inputs()
        with torch.no_grad():
            full, _ = loop(images, imu)
            torch.testing.assert_close(fast(images, imu)[0], full, atol=1e-5, rtol=1e-4)
            a, state = fast(images[:, :4], imu[:, :4])
            b, _ = fast(images[:, 4:], imu[:, 4:], state)
            torch.testing.assert_close(torch.cat((a, b), 1), full, atol=1e-5, rtol=1e-4)


    def test_batched_replay_matches_single_flights(self):
        torch.manual_seed(0)
        net = OdometryNet(dict(self.cfg, head="ssm", ssm_scan="prefix", ssm_chunk=4,
                               channels_last=True)).eval()
        rows = []
        for steps in (3, 11, 15):
            images, imu = self.inputs(steps, seed=steps)
            rows.append({"images": images[0].numpy(), "imu": imu[0].numpy(),
                         "R": np.broadcast_to(np.eye(3), (steps, 3, 3)).copy(),
                         "v": np.zeros((steps, 3))})
        batched = replay(net, rows, "cpu", chunk=6)
        for row, pred in zip(rows, batched):
            single, = replay(net, [row], "cpu", chunk=6)
            np.testing.assert_allclose(pred, single, atol=1e-6, rtol=1e-5)

    @unittest.skipUnless(torch.cuda.is_available(), "cuDNN flat GRU buffers exist only on CUDA")
    def test_checkpoint_keeps_every_tensor(self):
        import tempfile
        from accelerate import Accelerator
        accelerator = Accelerator()
        for head in ("gru", "gru_res", "gru_ssm", "ssm"):
            net = accelerator.prepare(OdometryNet(dict(self.cfg, head=head)))
            want = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
            with tempfile.TemporaryDirectory() as tmp:
                accelerator.save_state(tmp, safe_serialization=False)  # as odometry_train.py does
                with torch.no_grad():
                    for p in net.parameters(): p.zero_()
                accelerator.load_state(tmp)
            got = net.state_dict()
            self.assertEqual(set(got), set(want), head)
            for k in want: torch.testing.assert_close(got[k].cpu(), want[k], msg=f"{head} {k}")
            accelerator._models.clear()



class NativeCampaign(unittest.TestCase):
    def test_roster_splits_are_disjoint(self):
        import json
        from native_campaign import ROSTER, check_splits
        flights = json.loads(ROSTER.read_text())["flights"]
        check_splits(flights)  # raises on any scene shared by splits or a ProcTHOR scene outside its split
        excluded = {f"ProcTHOR-Train-{i}" for i in [*range(10, 46), *range(150, 162), *range(176, 180)]}
        self.assertFalse(excluded & {f["scene"] for f in flights})
        with self.assertRaises(ValueError):
            check_splits(flights + [dict(flights[0], split="dev")])

    def test_truth_integration_detects_wrong_frame(self):
        from types import SimpleNamespace
        from native_campaign import truth_integration_error
        t = np.arange(400)*.05
        yaw = .4*t
        R = np.stack([np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]]) for a in yaw])
        v_body = np.tile([.5, .1, 0.], (len(t), 1))
        v = np.einsum("nij,nj->ni", R, v_body)
        p = np.zeros_like(v); p[1:] = np.cumsum(.5*(v[1:]+v[:-1])*.05, axis=0)
        self.assertLess(truth_integration_error(SimpleNamespace(ft=t, v=v, p=p)), 1e-9)
        self.assertGreater(truth_integration_error(SimpleNamespace(ft=t, v=v_body, p=p)), .5)


if __name__ == "__main__":
    unittest.main()
