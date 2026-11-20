"""Causal regression tests and a +20 m/s transient injection for WP3."""
import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from replay import physical_guard

def source(n=100):
    t=np.arange(n)*.05
    T=np.tile(np.eye(4),(n,1,1));T[:,0,3]=t
    states=np.zeros((n,13)); states[:,0]=t;states[:,6]=1;states[:,7]=1
    return t,{'T':T,'states':states,'init_s':0.,'valid':np.ones(n,dtype=bool)}

class ReplayTests(unittest.TestCase):
    def test_identity_for_healthy_source(self):
        t,s=source();out,events=physical_guard(t,s)
        np.testing.assert_allclose(out,s['states'],atol=1e-12);self.assertEqual(int(events.sum()),0)
    def test_velocity_and_position_jump(self):
        t,s=source();_,fallback=source()
        s['states'][40,7]+=20;s['T'][40,0,3]+=1
        out,event=physical_guard(t,s,fallback)
        self.assertEqual(event[40],1)
        np.testing.assert_allclose(out[:,:3],fallback['states'][:,:3],atol=1e-12)
        self.assertEqual(event[42],0)
    def test_future_poisoning(self):
        for origin in [False,True]:
            t,s=source();_,fallback=source();original,_=physical_guard(t,s,fallback,origin)
            poisoned={key:value.copy() if isinstance(value,np.ndarray) else value for key,value in s.items()}
            poisoned['T'][61:,:3,3]=1e4;poisoned['states'][61:,7:]=1e4
            changed,_=physical_guard(t,poisoned,fallback,origin)
            np.testing.assert_array_equal(changed[:61],original[:61])
    def test_prefix_matches_full(self):
        t,s=source();_,backup=source();full,_=physical_guard(t,s,backup)
        short=lambda x:{k:v[:61] if isinstance(v,np.ndarray) else v for k,v in x.items()}
        prefix,_=physical_guard(t[:61],short(s),short(backup))
        np.testing.assert_array_equal(full[:61],prefix)
if __name__=='__main__':unittest.main()
