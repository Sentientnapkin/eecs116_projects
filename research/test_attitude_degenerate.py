"""A degenerate essential solve is an unavailable visual measurement."""
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from attitude_bias import grid_rotation

class DegenerateGeometry(unittest.TestCase):
    def test_essential_solver_failure_rejects_measurement(self):
        rng=np.random.default_rng(217)
        first=rng.integers(0,256,(120,160),dtype=np.uint8)
        last=cv2.warpAffine(first,np.array([[1.,0.,3.],[0.,1.,0.]]),(160,120))
        K=np.array([[140.,0.,79.5],[0.,140.,59.5],[0.,0.,1.]])
        with patch('attitude_bias.cv2.findEssentialMat', side_effect=cv2.error('degenerate polynomial')) as solve:
            delta, reason=grid_rotation(first,last,K,np.eye(3))
        self.assertTrue(solve.called)
        self.assertIsNone(delta)
        self.assertEqual(reason,'essential-degenerate')

    def test_pose_solver_failure_rejects_measurement(self):
        rng=np.random.default_rng(218)
        first=rng.integers(0,256,(120,160),dtype=np.uint8)
        last=cv2.warpAffine(first,np.array([[1.,0.,3.],[0.,1.,0.]]),(160,120))
        K=np.array([[140.,0.,79.5],[0.,140.,59.5],[0.,0.,1.]])
        with patch('attitude_bias.cv2.findEssentialMat', return_value=(np.eye(3),np.ones((160,1),np.uint8))), \
             patch('attitude_bias.cv2.recoverPose', side_effect=cv2.error('degenerate pose')) as solve:
            delta, reason=grid_rotation(first,last,K,np.eye(3))
        self.assertTrue(solve.called)
        self.assertIsNone(delta)
        self.assertEqual(reason,'essential-degenerate')

    def test_rejected_visual_updates_preserve_causal_prefix(self):
        from types import SimpleNamespace
        from attitude_bias import attitudes
        rng=np.random.default_rng(219)
        frames=[rng.integers(0,256,(120,160),dtype=np.uint8) for _ in range(26)]
        t=np.arange(26,dtype=float)*.05
        packets=[np.empty((0,7))]
        for k in range(1,len(t)):
            ts=np.linspace(t[k-1]+.005,t[k],10)
            packets.append(np.c_[ts,np.tile([0.,0.,9.81,.02,.01,.03],(10,1))])
        def flight(n):return SimpleNamespace(ft=t[:n],win=packets[:n],frames=frames[:n],
            K={'fx':140.,'fy':140.,'cx':79.5,'cy':59.5},T_bc=np.eye(4))
        with patch('attitude_bias.grid_rotation',return_value=(None,'essential-degenerate')):
            full,_,_=attitudes(flight(26),'kf_grid')
            prefix,_,_=attitudes(flight(17),'kf_grid')
        np.testing.assert_array_equal(full[:17],prefix)
        static,_,_=attitudes(flight(26),'static08')
        np.testing.assert_array_equal(full,static)

if __name__=='__main__':unittest.main()
