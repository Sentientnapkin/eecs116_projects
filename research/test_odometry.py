"""Focused regressions for the odometry data, sampling, metrics and models.

    ./odometry_env.sh -m unittest test_odometry     (or: ./odometry_env.sh test_odometry.py)
"""
import unittest

import numpy as np
import torch

from odometry_data import CATEGORIES, WindowPlan, motion_labels, validate_roster
from odometry_ledger import checks, split_for
from odometry_models import OdometryNet
from odometry_train import loss_fn


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


    def test_uncertainty_head(self):
        from odometry_models import split_output
        images, imu = self.inputs()
        torch.manual_seed(0)
        plain, _ = OdometryNet(dict(self.cfg, head="ssm")).eval()(images, imu)
        self.assertEqual(plain.shape[-1], 3)
        self.assertIsNone(split_output(plain)[1])
        net = OdometryNet(dict(self.cfg, head="ssm", uncertainty=True))
        pred, _ = net(images, imu)
        velocity, log_variance = split_output(pred)
        self.assertEqual((velocity.shape[-1], log_variance.shape[-1]), (3, 3))
        n = images.shape[1]
        row = {"v": torch.zeros(1, n, 3), "R": torch.eye(3).repeat(1, n, 1, 1),
               "times": torch.arange(n, dtype=torch.float32)[None]*.05, "T_bc": torch.eye(4)[None],
               "cam_gt": torch.zeros(1, n, 3)}
        base = loss_fn(pred, row, burn=2, horizons=[.25])
        with_nll = loss_fn(pred, row, burn=2, horizons=[.25], nll_weight=.1)
        self.assertTrue(torch.isfinite(with_nll) and float(with_nll.detach()) != float(base.detach()))
        torch.testing.assert_close(base, loss_fn(velocity, row, burn=2, horizons=[.25]))  # weight 0 ignores the head
        with_nll.backward()
        self.assertGreater(float(net.output[-1].weight.grad[3:].abs().sum()), 0)

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



class Fusion(unittest.TestCase):
    """EKF post-processor (odometry_eval.ekf_fuse) on a synthetic flight with exact kinematics."""

    def flight(self, n=400, dt=.05, accel_noise=0., seed=0):
        from odometry_eval import so3_exp
        rng = np.random.default_rng(seed)
        t = np.arange(n)*dt
        R = np.stack([so3_exp(np.array([.05*np.sin(.7*s), .04*np.cos(.5*s)-.04, .3*s])) for s in t])
        world = np.stack((np.sin(.3*t), .5*np.cos(.2*t)-.5, .1*np.sin(.5*t)), 1)
        g = so3_exp(np.array([.03, -.02, 0]))@np.array([0, 0, -9.81])  # frame zero is tilted from gravity
        a = np.zeros_like(world); a[1:] = np.diff(world, axis=0)/dt  # frame k's packet spans (t[k-1], t[k]]
        accel = np.einsum("nji,nj->ni", R, a-g)+accel_noise*rng.standard_normal((n, 3))
        imu = np.zeros((n, 51)); imu[:, :3] = accel/9.81; imu[1:, 12] = 1; imu[:, 13] = dt
        T_bc = np.eye(4); T_bc[:3, 3] = [.1, 0, .05]
        row = {"times": t, "R": R, "imu": imu, "T_bc": T_bc, "v": np.einsum("nji,nj->ni", R, world)}
        return row

    def test_bias_filter_is_causal_with_missing_packet(self):
        from odometry_eval import ekf_fuse, integrate
        row = self.flight(n=400)
        row["imu"][:, :3] += np.array([.25, -.15, .1])/9.81
        row["imu"][100, :13] = 0
        cfg = {"accel_bias_sigma": .3, "accel_sigma": .2, "velocity_sigma": [1e-3]*3}
        track, velocities, info = ekf_fuse(row["v"], row, cfg, check=True)
        self.assertGreater(info["min_eigenvalue"], 0)
        np.testing.assert_allclose(track, integrate(row["v"], row), atol=2e-3)
        stop = 103
        prefix = {k: v if k == "T_bc" else v[:stop] for k, v in row.items()}
        prefix_track, prefix_velocities, _ = ekf_fuse(prefix["v"], prefix, cfg)
        np.testing.assert_array_equal(track[:stop], prefix_track)
        np.testing.assert_array_equal(velocities[:stop], prefix_velocities)

    def test_perfect_measurements_reproduce_truth(self):
        from odometry_eval import ekf_fuse, integrate
        row = self.flight()
        truth = integrate(row["v"], row)
        for attitude in (False, True):
            p, fused, info = ekf_fuse(row["v"], row, {"attitude": attitude, "velocity_sigma": [1e-4]*3}, check=True)
            # With the attitude state, the unknown gravity tilt briefly leaks into phi (a few mm).
            self.assertLess(np.abs(p-truth).max(), 5e-3 if attitude else 1e-3, attitude)
            self.assertLess(np.abs(fused-row["v"]).max(), 1e-3)
            self.assertGreater(info["min_eigenvalue"], 0)

    def test_consistent_and_positive_definite_under_noise(self):
        from odometry_eval import ekf_fuse
        row = self.flight(n=1200, accel_noise=.5, seed=1)
        rng = np.random.default_rng(2)
        sigma = np.array([.1, .05, .08])
        noisy = row["v"]+sigma*rng.standard_normal(row["v"].shape)
        for attitude in (False, True):
            params = {"attitude": attitude, "velocity_sigma": sigma.tolist(), "accel_sigma": .5}
            _, fused, info = ekf_fuse(noisy, row, params, check=True)
            self.assertGreater(info["min_eigenvalue"], 0)
            self.assertTrue(2.4 < info["nis"] < 3.6, info["nis"])  # chi-square with 3 dof
            self.assertLess(np.sqrt(np.mean((fused-row["v"])**2)), np.sqrt(np.mean((noisy-row["v"])**2)))
        # Predicted per-frame log-variance gives the same filter as the equal fixed covariance.
        lv = np.tile(np.log(sigma**2), (len(noisy), 1))
        a, _, _ = ekf_fuse(noisy, row, {"velocity_sigma": sigma.tolist(), "accel_sigma": .5})
        b, _, _ = ekf_fuse(noisy, row, {"accel_sigma": .5}, log_variance=lv)
        np.testing.assert_allclose(a, b, atol=1e-9)
        # A supplied attitude replaces the row's.
        c, _, _ = ekf_fuse(noisy, row, {"velocity_sigma": sigma.tolist(), "accel_sigma": .5}, R=row["R"].copy())
        np.testing.assert_allclose(a, c, atol=1e-12)


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
