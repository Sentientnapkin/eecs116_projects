"""Analytic motion, preprocessing causality, and deployment parity regressions."""
import unittest

import numpy as np
import torch

from common import Flight, integrate_body_velocity
from decompose import moving_mean, scale_fit
from learned_probe import Net, displacement_loss
from orientation import Orientation, exp_so3
from pairs import config
from seq_heads import Head
from streaming import CHANNELS, Inputs, Predictor, Temporal


class CausalTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        self.K = {"fx": 82., "fy": 75., "cx": 40., "cy": 29.}
        self.times = np.array([0., .12, .33, .71, 1.01, 1.10, 1.42, 1.63])
        rng = np.random.default_rng(123)
        still = rng.integers(0, 256, (60, 82), dtype=np.uint8)
        self.images = [still if t <= 1.01 else np.roll(still, 8, axis=0) for t in self.times]
        self.packets = [np.array([[t, 0, 0, 9.81, .01, .02, .03]]) for t in self.times]

    def stream(self, count, initial=None):
        x = Inputs(self.cfg, self.K, self.images[0].shape, np.eye(3))
        if initial is not None:
            x.orient = Orientation(self.cfg, initial)
        rows = [x.step(t, img, pkt) for t, img, pkt in
                zip(self.times[:count], self.images[:count], self.packets[:count])]
        return tuple(np.stack(group) for group in zip(*rows))

    def test_prefix(self):
        full = self.stream(len(self.times))
        for end in range(2, len(self.times)):
            for prefix, entire in zip(self.stream(end), full):
                np.testing.assert_array_equal(prefix, entire[:end])

    def test_gauge(self):
        gauge = exp_so3([.45, -.08, .77])
        base, rotated = self.stream(8), self.stream(8, gauge)
        np.testing.assert_array_equal(base[0], rotated[0])
        np.testing.assert_allclose(gauge @ base[2], rotated[2], atol=1e-12)
        f = object.__new__(Flight)
        f.T_bc = np.eye(4)
        f.T_bc[:3, 3] = [.13, .09, -.04]
        v = np.full((8,3), .5)
        results = [f.camera_positions(integrate_body_velocity(data[2], v, times=self.times), data[2])
                   for data in (base, rotated)]
        np.testing.assert_allclose(*results, atol=1e-12)

    def test_resize_and_history_mask(self):
        x = Inputs(self.cfg, self.K, self.images[0].shape, np.eye(3))
        self.assertAlmostEqual(x.K[0, 2], (40.5)*32/82-.5)
        images, *_ = self.stream(8)
        self.assertFalse(images[0,1:].any())
        self.assertTrue(images[2,4].all())

    def test_startup_bias_applies_forward(self):
        raw = Orientation({**self.cfg,"policy":"none"})
        calibrated = Orientation({**self.cfg,"policy":"startup"})
        for t, packet in zip(self.times, self.packets):
            a, b = raw.step(t, packet, 0), calibrated.step(t, packet, 0)
            if t <= 1.01:
                np.testing.assert_array_equal(a,b)
        self.assertTrue(calibrated.activated)
        self.assertGreater(np.linalg.norm(a-b), 1e-4)
        evidence = Orientation(self.cfg)
        for t, packet in zip(self.times,self.packets):
            evidence.step(t,packet,.15)
        self.assertFalse(evidence.activated)

    def test_straight_and_acceleration_irregular(self):
        t = self.times
        R = np.repeat(np.eye(3)[None],len(t),axis=0)
        for v, expected in ((np.full_like(t,2),2*t),(3*t,1.5*t**2)):
            vel = np.column_stack((v,0*t,0*t))
            np.testing.assert_allclose(integrate_body_velocity(R,vel,times=t)[:,0],expected)

    def test_turning_constant_body_velocity_and_rotation_lever_arm(self):
        t = np.linspace(0,1,1001)
        R = np.array([exp_so3(np.array([0.,0.,s])) for s in t])
        v = np.repeat([[1.,0.,0.]],len(t),axis=0)
        p = integrate_body_velocity(R,v,times=t)
        np.testing.assert_allclose(p[:,:2],np.c_[np.sin(t),1-np.cos(t)],atol=1e-7)
        f = object.__new__(Flight)
        f.T_bc = np.eye(4)
        f.T_bc[0,3] = .2
        camera = f.camera_positions(0*p,R)
        np.testing.assert_allclose(camera[:,:2],np.c_[.2*(np.cos(t)-1),.2*np.sin(t)])

    def test_zero_tiny_and_scale_diagnostics(self):
        z = np.zeros((5,3))
        np.testing.assert_array_equal(scale_fit(z,z),[1,0])
        tiny = z.copy()
        tiny[-1,2] = 1e-10
        scale,error=scale_fit(tiny,2*tiny)
        self.assertAlmostEqual(scale,2.)
        self.assertEqual(error,0.)
        lever=2*tiny
        self.assertLessEqual(scale_fit(tiny,5*tiny,lever)[1],np.linalg.norm(3*tiny-5*tiny))
        self.assertEqual(float(displacement_loss(torch.zeros(8,3),torch.zeros(8,3),
                            torch.eye(3).expand(8,3,3),torch.tensor(self.times,dtype=torch.float32),self.cfg)),0)

    def test_streaming_temporal_against_batch(self):
        rng = np.random.default_rng(8)
        x = rng.normal(size=(8,32)).astype(np.float32)
        dt = np.diff(self.times,prepend=self.times[0]).astype(np.float32)
        for kind in ("frame","ema","ssm","gru","selective"):
            model = Head(kind)
            model.eval()
            ref = model(torch.from_numpy(x),torch.from_numpy(dt)).detach().numpy()
            weights = {k:v.numpy() for k,v in model.state_dict().items()}
            for end in (8,4):
                stream = Temporal(kind,weights)
                actual=np.stack([stream.step(a,b) for a,b in zip(x[:end],dt[:end])])
                np.testing.assert_allclose(actual,ref[:end],atol=1e-6)

    def test_streaming_cnn_against_batch(self):
        images, imu, *_ = self.stream(8)
        for variant, compact in [(name, False) for name in CHANNELS] + [("triple_derot", True)]:
            net = Net(variant, compact).eval()
            w = {k:v.numpy() for k,v in net.state_dict().items()}
            selected = images[:,CHANNELS[variant]]
            stream = Predictor(variant,w)
            expected=net(torch.tensor(selected,dtype=torch.float32)/255-.5,torch.tensor(imu)).detach().numpy()
            np.testing.assert_allclose(np.stack([stream.step(a,b) for a,b in zip(selected,imu)]),expected,atol=1e-6)

    def test_rolling_retries_after_bad_window_and_is_prefix_invariant(self):
        cfg={**self.cfg,"policy":"rolling"}
        times=np.arange(61)*.05
        def collect(count):
            orient=Orientation(cfg)
            result=[]
            for t in times[:count]:
                packet=np.array([[t,0,0,9.81,.02,.03,.01]])
                R=orient.step(t,packet,.2 if t<1. else 0.)
                result.append((R,orient.bias.copy()))
            return result,orient.accepted_at
        full,activation=collect(61)
        prefix,early=collect(20)
        self.assertIsNone(early)
        self.assertGreater(activation,1.)
        self.assertLess(activation,2.4)
        for a,b in zip(prefix,full):
            np.testing.assert_equal(a,b)

    def test_joint_feedback_matches_torch_before_loop_and_streams_causally(self):
        from seq_heads import Joint, joint_model
        from streaming import Estimator
        settings=dict(variant="triple_derot",kind="selective",embedding=48,hidden=64,
                      width=32,height=24,packet_mode="ordered",bias_head=True,feedback=True)
        cfg={**self.cfg,"policy":"rolling","ordered_packet":True}
        net=Joint(settings).eval()
        model=joint_model(net)
        inp=Inputs(cfg,self.K,self.images[0].shape,np.eye(3))
        data=[inp.step(t,f,p,"triple_derot")[:2] for t,f,p in zip(self.times,self.images,self.packets)]
        image, imu=map(np.stack,zip(*data))
        expected=net(torch.tensor(image,dtype=torch.float32)/255-.5,torch.tensor(imu)).detach().numpy()
        predictor=Predictor(model["variant"],model["encoder"],model["kind"],model["temporal"],settings)
        actual=np.stack([predictor.step(a,b) for a,b in data])
        np.testing.assert_allclose(actual,expected,atol=2e-6)
        camera={**self.K,"width":82,"height":60,"T_cam_imu":np.eye(4)}
        def rollout(count,feedback=True):
            estimator=Estimator(camera,{**model,"settings":{**settings,"feedback":feedback}},cfg)
            rows=[]
            for i in range(count):
                frame=self.images[i] if i!=4 else None
                rows.append(estimator.step(self.times[i],frame,self.packets[i]))
            return np.stack(rows),estimator
        a,_=rollout(4)
        b,est=rollout(8)
        c,disable=rollout(8,False)
        np.testing.assert_equal(a,b[:4])
        self.assertTrue(np.isfinite(b).all())
        self.assertGreater(np.linalg.norm(est.inputs.orient.learned_bias),0.)
        self.assertEqual(np.linalg.norm(disable.inputs.orient.learned_bias),0.)
        np.testing.assert_allclose(b[1,:7],c[1,:7],atol=1e-9)
        self.assertGreater(np.linalg.norm(b[-1,:7]-c[-1,:7]),1e-6)

    def test_fixed_remap_matches_reference_pixels(self):
        from streaming import portable_warp
        y,x = np.indices((24,32))
        pixels = np.stack((x.ravel(),y.ravel(),np.ones(x.size)))
        frame = self.images[0][:24,:32]
        inverse = np.array([[1.03,.02,-2.1],[-.03,.98,1.8],[.001,-.002,1.]])
        reference = portable_warp(frame,inverse,pixels)
        exact = portable_warp(frame,inverse,pixels,fast=True)
        np.testing.assert_array_equal(reference,exact)

    def test_zero_initial_state_matches_deployed_step(self):
        torch.manual_seed(103)
        head = Head("selective",n=5,hidden=3,zero_initial_state=True)
        x = torch.randn(11,5)
        dt = torch.linspace(0,.12,len(x))
        weights = {key:value.detach().numpy() for key,value in head.state_dict().items()}
        deployed = Temporal("selective",weights,zero_initial_state=True)
        expected = head(x,dt).detach().numpy()
        actual = np.stack([deployed.step(a,b.item()) for a,b in zip(x.numpy(),dt)])
        np.testing.assert_allclose(actual,expected,atol=2e-6)

    def test_trajectory_loss_exposes_attitude_error(self):
        from robust_train import camera_loss
        times = np.arange(21)*.05
        v = np.tile([1.,0.,0.], (len(times),1))
        truth = np.eye(3)[None].repeat(len(times),axis=0)
        targets = dict(v=v,times=times,R=truth,T_bc=np.eye(4),cam_gt=v*times[:,None])
        pred = torch.tensor(v,dtype=torch.float32,requires_grad=True)
        self.assertLess(float(camera_loss(pred,targets,[.25,.5]).detach()),1e-10)
        angles = np.linspace(0,1.,len(times))
        targets["R"] = np.stack([exp_so3([0,0,a]) for a in angles])
        legacy = displacement_loss(pred,pred,torch.tensor(targets["R"],dtype=torch.float32),
                                   torch.tensor(times,dtype=torch.float32),{"horizons":[.25,.5]})
        self.assertEqual(float(legacy.detach()),0.)
        corrected = camera_loss(pred,targets,[.25,.5])
        self.assertGreater(float(corrected.detach()),.01)
        corrected.backward()
        self.assertGreater(float(pred.grad.abs().max()),0.)

    def test_sensor_variants_causal_and_packet_ordered(self):
        from types import SimpleNamespace
        from pairs import variant_rows
        times = np.arange(142)*.05
        observations = SimpleNamespace(ft=times,frames=[self.images[0]]*len(times),
                                      path="test.npz",win=[np.empty((0,7))])
        for elapsed in times[1:]:
            observations.win.append(np.c_[elapsed+np.arange(-9,1)*.005,np.zeros((10,6))])
        a = list(variant_rows(observations,"combined",651))
        b = list(variant_rows(observations,"combined",651))
        self.assertIsNone(a[137][1])
        for (time, _, first), (_, _, second) in zip(a[1:],b[1:]):
            self.assertTrue((np.diff(first[:,0])>0).all())
            self.assertGreater(first[0,0],time-.05)
            self.assertLessEqual(first[-1,0],time+1e-12)
            np.testing.assert_array_equal(first,second)

    def test_causal_smoothing_prefix(self):
        values = np.arange(24).reshape(8,3)
        np.testing.assert_array_equal(moving_mean(values[:4],self.times[:4],.5),
                                      moving_mean(values,self.times,.5)[:4])


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main()
