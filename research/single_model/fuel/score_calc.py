"""Area-score arithmetic using the server's dominated_area/area_gains (copied logic). Baselines (fuel, ate)."""
from math import log
import sys
sys.path.insert(0,'/dev/shm/sebastian-vio/viobench')
from viobench.tools.server.evaluations import dominated_area
STEP=2e10; FREF=1.2*STEP
def area(base, pt, ref_err=None):
    ref = 1.2*min(base)[1] if ref_err is None else ref_err   # leftmost baseline anchors
    b = dominated_area(base, FREF, ref)
    g = dominated_area(base+[pt], FREF, ref)-b
    return g, 100*g/(log(FREF)*log(ref/0.001))
if __name__=='__main__':
    B=[(113,4.69),(3.4e9,0.475),(4.0e9,0.553),(14.7e6,5.8),(5.15e6,9.07)]
    for f,a in [(20.9e6,1.244),(20.9e6,0.98),(14.6e6,1.244),(20.9e6,1.12),(20.9e6,0.622),(10.45e6,1.244),(20.9e6,1.0),(14.6e6,1.0),(14.6e6,0.9)]:
        print(f'{f/1e6:6.2f}M {a:.3f}m  gain {area(B,(f,a))[0]:.4f}  {area(B,(f,a))[1]:.3f}%')
