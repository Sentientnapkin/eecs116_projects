"""Focused regressions for the odometry data, sampling, metrics and models.

    ./odometry_env.sh -m unittest test_odometry     (or: ./odometry_env.sh test_odometry.py)
"""
import shutil
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

    def test_refinement_causal_and_streaming(self):
        """Iterative refinement (model.refine_iters) keeps the causal and chunked-streaming
        guarantees: past outputs ignore future frames, and a stream split anywhere matches."""
        steps = 10
        g = torch.Generator().manual_seed(1)
        R = torch.linalg.qr(torch.randn(1, steps, 3, 3, generator=g))[0]
        for signals in (["inertial"], ["corr"], ["inertial", "corr"]):
            for head in ("ssm", "gru"):
                torch.manual_seed(0)
                net = OdometryNet(dict(self.cfg, head=head, refine_iters=3, refine_signals=signals)).eval()
                for p in net.refiner.delta.parameters():  # zero-initialized: make the updates nontrivial
                    torch.nn.init.normal_(p, std=.1)
                images, imu = self.inputs(steps)
                imu[..., 14] = .36
                with torch.no_grad():
                    full, _ = net(images, imu, R=R)
                    every, _ = net(images, imu, R=R, iterations=True)
                    self.assertEqual(tuple(every.shape), (4, 1, steps, 3))
                    torch.testing.assert_close(every[-1], full)
                    self.assertGreater(float((every[-1]-every[0]).abs().max()), 1e-4)  # refinement acts
                    changed = images.clone(); changed[:, 6:] = 0
                    imu2 = imu.clone(); imu2[:, 6:, :3] += 3
                    R2 = R.clone(); R2[:, 6:] = torch.eye(3)
                    prefix, _ = net(changed, imu2, R=R2)
                    torch.testing.assert_close(full[:, :6], prefix[:, :6])
                    for split in (1, 4, 7):
                        a, state = net(images[:, :split], imu[:, :split], R=R[:, :split])
                        b, _ = net(images[:, split:], imu[:, split:], state, R[:, split:])
                        torch.testing.assert_close(torch.cat((a, b), 1), full, atol=1e-5, rtol=1e-4)

    def test_refinement_is_opt_in(self):
        torch.manual_seed(0)
        plain = OdometryNet(dict(self.cfg, head="ssm"))
        torch.manual_seed(0)
        zero = OdometryNet(dict(self.cfg, head="ssm", refine_iters=0))
        self.assertIsNone(zero.refiner)
        for (k, a), (_, b) in zip(plain.state_dict().items(), zero.state_dict().items()):
            torch.testing.assert_close(a, b, msg=k)
        torch.manual_seed(0)
        refined = OdometryNet(dict(self.cfg, head="ssm", refine_iters=2))
        shared = {k: v for k, v in refined.state_dict().items() if not k.startswith("refiner.")}
        self.assertEqual(set(shared), set(plain.state_dict()))
        for k, v in plain.state_dict().items():
            torch.testing.assert_close(shared[k], v, msg=k)  # refiner created last: same initialization
        images, imu = self.inputs()
        with torch.no_grad():  # zero-initialized update: refined output starts at the head estimate
            torch.testing.assert_close(refined.eval()(images, imu)[0], plain.eval()(images, imu)[0])

    def test_inertial_residual_vanishes_for_consistent_motion(self):
        """Constant world acceleration exactly matched by the accelerometer gives a zero inertial
        residual once the estimate equals the true velocity."""
        from odometry_models import Refiner
        net = Refiner(dict(self.cfg, refine_iters=1, refine_signals=["inertial"]), 16, None)
        captured = []
        net.input.register_forward_hook(lambda m, i, o: captured.append(i[0][:, 5:8].clone()))
        steps, dt = 6, .05
        g = torch.Generator().manual_seed(2)
        R = torch.linalg.qr(torch.randn(1, steps, 3, 3, generator=g))[0]
        accel = torch.tensor([.3, -.2, .5])
        v_world = torch.stack([torch.tensor([1., 0, 0]) + accel*dt*i for i in range(steps)])[None]
        v_body = (R.transpose(-1, -2) @ v_world.unsqueeze(-1)).squeeze(-1)
        imu = torch.zeros(1, steps, 51); imu[..., 12] = 1; imu[..., 13] = dt
        imu[..., :3] = ((R.transpose(-1, -2) @ (accel - torch.tensor([0, 0, -9.81])).unsqueeze(-1)).squeeze(-1))/9.81
        with torch.no_grad():
            net(v_body, torch.zeros(1, steps, 16), imu, R, None)
        residual = torch.stack(captured)
        self.assertEqual(float(residual[0].abs().max()), 0.)  # no previous frame yet
        torch.testing.assert_close(residual[1:], torch.zeros_like(residual[1:]), atol=1e-5, rtol=0)

        captured.clear()
        imu[:, 2, 12] = 0
        with torch.no_grad():
            net(v_body, torch.zeros(1, steps, 16), imu, R, None)
        expected = ((v_world[:, 1] - v_world[:, 2]).unsqueeze(1) @ R[:, 2]).squeeze(1)
        torch.testing.assert_close(captured[2], expected, atol=1e-5, rtol=0)

    def test_refinement_correlation_lookup(self):
        from odometry_models import Refiner

        cfg = dict(self.cfg, refine_iters=1, refine_signals=["corr"])
        net = Refiner(cfg, 16, (4, 2))
        # Offset values encode horizontal displacement. A leftward body velocity
        # predicts negative horizontal displacement in camera coordinates.
        bins = torch.arange(-2., 3.).repeat(5)
        volume = bins[None, None, :, None, None].expand(1, 2, 25, 3, 4)
        mask = torch.ones(1, 2, 3, 4)
        mask[:, 1] = 0
        depth = torch.ones(1, 3, 4, requires_grad=True)
        fx = torch.tensor([cfg["width"]/4])
        features = net.lookup(volume, mask, depth, torch.tensor([[0., 2., 0.]]), fx)
        sampled = features.view(1, 2, 9, 3, 4)
        torch.testing.assert_close(sampled[:, 0, 4], torch.full((1, 3, 4), -.5))
        torch.testing.assert_close(sampled[:, 1], torch.zeros_like(sampled[:, 1]))
        sampled[:, 0, 4].sum().backward()
        torch.testing.assert_close(depth.grad, torch.full_like(depth, -.5))

    @unittest.skipUnless(shutil.which("cc"), "C compiler required for C parity")
    def test_inertial_refinement_c_parity(self):
        from odometry_models import Refiner
        from refine_c.check import compare

        torch.manual_seed(1)
        cfg = dict(self.cfg, refine_iters=3, refine_signals=["inertial"], refine_hidden=8)
        refiner = Refiner(cfg, 16, None)
        torch.nn.init.normal_(refiner.delta.weight, std=.2)
        initial = torch.randn(2, 14, 3)*2
        context = torch.randn(2, 14, 16)
        imu = torch.randn(2, 14, 51)
        imu[..., 12] = (imu[..., 12] > 0).float()
        imu[..., 13] = torch.rand(2, 14)*.15
        R = torch.linalg.qr(torch.randn(2, 14, 3, 3))[0]
        R[..., 2] *= torch.linalg.det(R).unsqueeze(-1)
        compare(refiner, cfg, (initial, context, imu, R))

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
