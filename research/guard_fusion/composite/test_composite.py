"""Compile the real selector and exercise source faults and clean resets."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import numpy as np

HERE=Path(__file__).resolve().parent


class SelectorFaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(dir='/dev/shm',prefix='selector-faults-')
        tmp=Path(cls.temp.name)
        shutil.copy2(HERE/'selector.hpp',tmp/'selector.hpp')
        (tmp/'wrapper.cpp').write_text('''#include "selector.hpp"
static fusion::Selector selector;
extern "C" void reset_selector() { selector=fusion::Selector{}; }
extern "C" int step_selector(double t,const double *input,const unsigned char *r,double *out) {
  bool ready[3]={bool(r[0]),bool(r[1]),bool(r[2])};
  return selector.step(t,reinterpret_cast<const double (*)[13]>(input),ready,out);
}
''')
        subprocess.run(['c++','-std=c++17','-O2','-shared','-fPIC',str(tmp/'wrapper.cpp'),'-o',str(tmp/'selector.so')],check=True)
        cls.lib=ctypes.CDLL(str(tmp/'selector.so'))
        cls.lib.step_selector.argtypes=[ctypes.c_double,
            np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS'),
            np.ctypeslib.ndpointer(dtype=np.uint8,flags='C_CONTIGUOUS'),
            np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.lib.reset_selector()

    def step(self,t,x,ready=(1,1,1)):
        out=np.zeros(13,dtype=np.float64)
        source=self.lib.step_selector(t,np.ascontiguousarray(x,dtype=np.float64),np.asarray(ready,dtype=np.uint8),out)
        return source,out

    def identities(self):
        x=np.zeros((3,13)); x[:,6]=1
        return x

    def test_all_failed_sources_produce_finite_identity(self):
        _,out=self.step(.05,np.full((3,13),np.nan),ready=(0,0,0))
        self.assertTrue(np.isfinite(out).all())
        np.testing.assert_array_equal(out,self.identities()[0])

    def test_zero_quaternions_are_rejected(self):
        x=self.identities();x[0,6]=0; x[0,0]=1e6
        source,out=self.step(.05,x)
        self.assertNotEqual(source,0)
        self.assertTrue(np.isfinite(out).all())
        self.assertEqual(out[0],0)

    def test_vio_jump_does_not_leak_into_continuity_offset(self):
        output=[]
        for k in range(50):
            x=self.identities();x[:,0]=k*.01
            if k>=25:
                x[0,0]+=1e6
            _,out=self.step((k+1)*.05,x)
            output.append(out)
        output=np.asarray(output)
        self.assertLess(np.max(np.abs(np.diff(output[:,0]))),.1)
        self.assertTrue(np.isfinite(output).all())

    def test_reset_reproduces_selector_state(self):
        def run():
            result=[]
            for k in range(30):
                x=self.identities();x[:,0]=k*.01
                if k>15:
                    x[0,0]+=1.
                _,out=self.step((k+1)*.05,x)
                result.append(out)
            return np.asarray(result)
        first=run()
        self.lib.reset_selector()
        np.testing.assert_array_equal(first,run())

if __name__=='__main__':
    unittest.main()
