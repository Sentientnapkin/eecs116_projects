"""Focused regressions for the odometry data, sampling, metrics and models.

    ./odometry_env.sh -m unittest test_odometry     (or: ./odometry_env.sh test_odometry.py)
"""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import unittest
from unittest.mock import patch

import numpy as np
import torch

import hp_search
from odometry_data import CATEGORIES, WindowPlan, motion_labels, validate_roster
from odometry_eval import batched_velocities
from odometry_ledger import checks, split_for
from odometry_models import OdometryNet, correct_gyro_attitude
from odometry_train import loss_fn, make_optimizer, replay


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

    def test_native_early_keeps_unmatched_windows_and_budget(self):
        records, labels = synthetic(n_parents=24)
        for i, (row, label) in enumerate(zip(records, labels)):
            row.update(domain="native-campaign" if i < 20 else "proxy",
                       catalog="procthor", crop_s=0, parent_sha256=str(i))
            for kind in ("backward", "lateral"):
                label[kind][:] = False
                label[kind][120:] = True
            if i < 12:
                label["backward"][16:28] = True
        opts = {"mode": "balanced", "windows_per_epoch": 40,
                "mixture": {"uniform": .4, "backward": .5, "lateral": .1}}
        early = {"fraction": .25, "max_start": 4, "min_scenes": 6}
        control = WindowPlan(records, labels, 48, 16, opts, 217)
        targeted = WindowPlan(records, labels, 48, 16, dict(opts, native_early=early), 217)
        first, second = control.plan(0), targeted.plan(0)
        self.assertEqual(second, targeted.plan(0))
        self.assertEqual(len(first), len(second))
        changed = [(before, after) for before, after in zip(first, second) if before != after]
        self.assertTrue(changed)
        for (old, start, kind), (new, early_start, new_kind) in changed:
            self.assertEqual((kind, new_kind), ("backward", "backward"))
            self.assertEqual(records[old]["domain"], "native-campaign")
            self.assertEqual(records[new]["domain"], "native-campaign")
            self.assertGreater(start, 4)
            self.assertLessEqual(early_start, 4)
            self.assertIn(early_start, targeted.eligible[new]["backward"])
        native_hard = [s for i, s, k in second if k == "backward" and i < 20]
        self.assertGreaterEqual(np.mean(np.array(native_hard) <= 4), .25)

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
    def test_hybrid_visual_interval_replaces_learned_correction_at_acceptance(self):
        from attitude_hybrid import join_attitudes
        from orientation import exp_so3

        learned = np.stack([exp_so3((0., 0., angle)) for angle in (0., .025, .05, .075, .1)])
        visual = np.stack([exp_so3((0., 0., angle)) for angle in (0., 0., .1, .1, .1)])
        anchors = np.array([-1, -1, 0, -1, -1])
        hybrid = join_attitudes(learned, visual, anchors)
        expected = np.stack([exp_so3((0., 0., angle)) for angle in (0., .025, .1, .125, .15)])
        np.testing.assert_allclose(hybrid, expected, atol=1e-12)
        np.testing.assert_allclose(join_attitudes(learned[:2], visual[:2], anchors[:2]), hybrid[:2], atol=1e-12)

    def test_horizon_longer_than_window_is_finite(self):
        n = 20
        row = {"v": torch.zeros(1, n, 3), "R": torch.eye(3).repeat(1, n, 1, 1),
               "times": torch.arange(n, dtype=torch.float32)[None]*.05,
               "T_bc": torch.eye(4)[None], "cam_gt": torch.zeros(1, n, 3)}
        loss = loss_fn(torch.zeros(1, n, 3), row, burn=5, horizons=[6.])
        self.assertTrue(torch.isfinite(loss) and float(loss) == 0.)


class Optimizer(unittest.TestCase):
    def test_weight_decay_defaults_to_legacy_value(self):
        p = [torch.nn.Parameter(torch.zeros(2))]
        self.assertEqual(make_optimizer(p, {"learning_rate": 3e-4}).param_groups[0]["weight_decay"], .01)
        opt = make_optimizer(p, {"learning_rate": 1e-3, "weight_decay": .05})
        self.assertEqual((opt.param_groups[0]["lr"], opt.param_groups[0]["weight_decay"]), (1e-3, .05))


class Hyperparameters(unittest.TestCase):
    def test_fast_trial_inherits_recipe_then_applies_trial_overrides(self):
        with TemporaryDirectory() as root, patch.object(hp_search, "RUNS", Path(root)):
            _, cmd = hp_search.command("w128-h4", 12, 218, "hpfast", [], False, recipe="B-speed-compiled-x3")
            options = dict(value.split("=", 1) for flag, value in zip(cmd, cmd[1:]) if flag == "--set")
            self.assertEqual(options["training.batch_size"], "2")
            self.assertEqual(options["training.accumulation"], "1")
            self.assertEqual(options["model.compile_correlation"], "true")
            self.assertEqual(options["training.window_frames"], "128")
            self.assertEqual(json.loads(options["training.sampler"])["windows_per_epoch"], 122)
            self.assertEqual(cmd[cmd.index("--seed")+1], "218")
            self.assertEqual([value for flag, value in zip(cmd, cmd[1:]) if flag == "--epochs"][-1], "12")

    def test_local_data_views_use_distinct_paths(self):
        with TemporaryDirectory() as root, patch.object(hp_search, "RUNS", Path(root)):
            source = Path(root) / "source"
            source.mkdir()
            (source / "manifest.json").write_text("manifest")
            (source / "shard.npz").write_bytes(b"shard")
            run, cmd = hp_search.command("base", 12, 217, "hpfast", [], False, local_source=source)
            hp_search.stage_local_data(source, run)
            hp_search.stage_local_data(source, run)
            local = Path(cmd[cmd.index("--data")+1])
            self.assertEqual(local.name, run)
            self.assertEqual((local / "manifest.json").read_text(), "manifest")
            self.assertTrue((local / "shard.npz").samefile(source / "shard.npz"))

    def test_promotion_requires_both_seeds_and_ranks_paired_means(self):
        scores = {"base": (1.3, 1.3), "lr1e-4": (1.0, 1.5), "lr6e-4": (1.2, 1.2), "lr1e-3": (1.0, 1.6)}
        args = argparse.Namespace(trials=list(scores), tag="test")
        with TemporaryDirectory() as root, patch.object(hp_search, "RUNS", Path(root)), \
                patch.object(hp_search, "schedule", return_value=0) as schedule, patch("builtins.print"):
            for trial, pair in scores.items():
                for seed, score in zip((217, 218), pair):
                    path = Path(root)/hp_search.run_name(trial, 12, seed, args.tag)
                    path.mkdir()
                    (path/"manifest.json").write_text(json.dumps({"status": "completed"}))
                    (path/"metrics.json").write_text(json.dumps([{"selection_score": score + 1}, {"selection_score": score}]))
            self.assertEqual(hp_search.promote(args), 0)
            self.assertEqual(args.trials, ["lr6e-4", "lr1e-4"])
            self.assertEqual(args.epochs, 36)
            self.assertEqual(args.seeds, [217, 218, 219])
            manifest = Path(root)/hp_search.run_name("base", 12, 218, args.tag)/"manifest.json"
            manifest.write_text(json.dumps({"status": "running"}))
            with self.assertRaisesRegex(SystemExit, "incomplete screen"):
                hp_search.promote(argparse.Namespace(trials=list(scores), tag=args.tag))
            schedule.assert_called_once()


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
        cfg = dict(self.cfg, head="ssm", ssm_scan="prefix", ssm_chunk=4, channels_last=True)
        rows = []
        for steps in (3, 11, 15):
            images, imu = self.inputs(steps, seed=steps)
            rows.append({"images": images[0].numpy(), "imu": imu[0].numpy(),
                         "R": np.broadcast_to(np.eye(3), (steps, 3, 3)).copy(),
                         "v": np.zeros((steps, 3))})
        for correction in (False, True):
            net = OdometryNet(dict(cfg, gyro_bias_correction=correction)).eval()
            if correction:
                with torch.no_grad():
                    net.gyro_bias[-1].bias.copy_(torch.tensor([.3, -.1, .2]))
            batched = replay(net, rows, "cpu", chunk=6, return_attitude=True)
            for row, (pred, rotations) in zip(rows, batched):
                (single, single_rotations), = replay(net, [row], "cpu", chunk=6, return_attitude=True)
                np.testing.assert_allclose(pred, single, atol=1e-6, rtol=1e-5)
                np.testing.assert_allclose(rotations, single_rotations, atol=1e-6, rtol=1e-5)
                self.assertEqual(np.array_equal(rotations, row["R"]), not correction)

    def test_gyro_bias_cancels_known_drift(self):
        dt = torch.full((1, 60), .05)
        angle = torch.arange(dt.shape[1]) * .05 * .1
        sin, cos = angle.sin(), angle.cos()
        zero, one = torch.zeros_like(sin), torch.ones_like(sin)
        raw = torch.stack((cos, -sin, zero, sin, cos, zero, zero, zero, one), dim=1).reshape(1, -1, 3, 3)
        bias = torch.tensor([0., 0., .1]).expand(1, dt.shape[1], 3)
        corrected, _ = correct_gyro_attitude(raw, bias, dt)
        torch.testing.assert_close(corrected, torch.eye(3).expand_as(raw), atol=1e-5, rtol=0.)
        # Time-varying body increments do not commute, so this also checks scan order.
        from orientation import exp_so3
        bias = torch.randn(bias.shape, generator=torch.Generator().manual_seed(5)) * .1
        corrected, _ = correct_gyro_attitude(raw, bias, dt)
        previous, expected = np.eye(3), []
        for i, rotation in enumerate(raw[0].numpy()):
            if i:
                old = raw[0, i - 1].numpy()
                previous = previous @ exp_so3(-old @ bias[0, i].numpy() * float(dt[0, i]))
            expected.append(previous @ rotation)
        np.testing.assert_allclose(corrected[0].numpy(), expected, atol=5e-6, rtol=0.)

    def test_gyro_bias_head_is_streaming_and_learns_from_displacement(self):
        net = OdometryNet(dict(self.cfg, head="ssm", ssm_scan="prefix", ssm_chunk=8, gyro_bias_correction=True))
        images, imu = self.inputs()
        raw = torch.eye(3).expand(1, images.shape[1], 3, 3)
        with torch.autocast(device_type="cpu", dtype=torch.bfloat16):
            pred, _, corrected = net(images, imu, R=raw, return_attitude=True)
        torch.testing.assert_close(corrected, raw)
        v = torch.tensor([1., 0., 0.]).expand_as(pred)
        times = torch.arange(images.shape[1])[None] * .05
        # Lateral acceleration in the camera truth gives the correction a training signal.
        cam_gt = torch.stack((times, times.square(), torch.zeros_like(times)), dim=-1)
        row = {"v": v, "R": raw, "times": times, "T_bc": torch.eye(4)[None], "cam_gt": cam_gt}
        loss_fn(v, row, 2, [.1], rotations=corrected).backward()
        gradient = net.gyro_bias[-1].bias.grad
        self.assertTrue(torch.isfinite(gradient).all() and gradient.norm() > 0)
        with torch.no_grad():
            net.gyro_bias[-1].bias.add_(torch.tensor([.3, -.1, .2]))
            _, _, full = net(images, imu, R=raw, return_attitude=True)
            _, state, first = net(images[:, :4], imu[:, :4], R=raw[:, :4], return_attitude=True)
            _, _, last = net(images[:, 4:], imu[:, 4:], state, raw[:, 4:], return_attitude=True)
        torch.testing.assert_close(torch.cat((first, last), 1), full)


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
