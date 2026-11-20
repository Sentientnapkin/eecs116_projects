"""Diagnostic velocity arms (ORACLE ONLY). Reuses make_arms.py helpers; writes arms/<name>.c.
Arm name: <mode>_<sigma>[_seed]. Velocity = f(truth body-frame velocity vb), rotated by the filter's initial R, filter
sigma = <sigma>. Tilt NOT injected (INIT_TILT_STD stays 0.05, like the baseline).
 zero : v=0 (control, must reproduce the baseline when sigma=1.0)
 mag  : truth speed, random direction (seeded gaussian draw, independent of truth)
 dir  : truth direction, speed = 0.97 if |vb|>0.3 else truth (wrong magnitude, right direction)
 fwd  : v = 0.97 along body +x if |vb|>0.3 else 0  (constant forward velocity, gated by truth 'moving')
 fwdall: v = 0.97 along body +x for ALL flights (ungated)
 half : 0.5 * truth
 neg  : -truth (error = 2x speed, systematic)
 vn   : truth + N(0, sigma) per axis, seed offset k (vn_1.0_s2 = other noise draw)
 vx   : exact truth"""
import re, sys
from pathlib import Path
import make_arms as M
here = Path(__file__).parent
MODES = {
 'zero': 'double u[3]={0,0,0};',
 'mag': 'double g0=oracle_gauss(o),g1=oracle_gauss(o),g2=oracle_gauss(o),gn=sqrt(g0*g0+g1*g1+g2*g2)+1e-12,sp=sqrt(o->vb[0]*o->vb[0]+o->vb[1]*o->vb[1]+o->vb[2]*o->vb[2]); double u[3]={sp*g0/gn,sp*g1/gn,sp*g2/gn};',
 'dir': 'double sp=sqrt(o->vb[0]*o->vb[0]+o->vb[1]*o->vb[1]+o->vb[2]*o->vb[2]),k=sp>0.3?0.97/sp:1.0; double u[3]={k*o->vb[0],k*o->vb[1],k*o->vb[2]};',
 'fwd': 'double sp=sqrt(o->vb[0]*o->vb[0]+o->vb[1]*o->vb[1]+o->vb[2]*o->vb[2]); double u[3]={sp>0.3?0.97:0,0,0};',
 'fwdall': 'double u[3]={0.97,0,0};',
 'half': 'double u[3]={0.5*o->vb[0],0.5*o->vb[1],0.5*o->vb[2]};',
 'neg': 'double u[3]={-o->vb[0],-o->vb[1],-o->vb[2]};',
 'vx': 'double u[3]={o->vb[0],o->vb[1],o->vb[2]};',
 'vn': 'double u[3]={o->vb[0],o->vb[1],o->vb[2]}; for(int i=0;i<ORACLE_SEED_SKIP;i++) oracle_gauss(o); u[0]+=NOISE*oracle_gauss(o)*0; /* noise added in world frame below */',
}
def make(mode, sig, seed=0):
    name = f'{mode}_{sig}' + (f'_s{seed}' if seed else '')
    s = M.SRC
    s = re.sub(r'#define INIT_TILT_STD [0-9.]+', '#define INIT_TILT_STD 0.05', s)
    s = re.sub(r'#define INIT_VELOCITY_STD [0-9.]+', f'#define INIT_VELOCITY_STD {sig}', s)
    defs = f'#define ORACLE_VEL 1\n#define ORACLE_VEL_NOISE 0.0\n#define ORACLE_TILT 0\n#define ORACLE_TILT_NOISE 0.0\n#define ORACLE_SEED_SKIP {3*seed}\n'
    s = s.replace('static void set_block(', defs + M.HELPERS + '\nstatic void set_block(', 1)
    if mode == 'vn':
        body = ('double u[3]={o->vb[0],o->vb[1],o->vb[2]}; for(int i=0;i<ORACLE_SEED_SKIP;i++) oracle_gauss(o);')
        add = f'+ {sig} * oracle_gauss(o)'
    else:
        body = MODES[mode]; add = ''
    blk = ('\n    {\n        const OracleRow *o = oracle_lookup();\n        if (o) {\n            ' + body + '\n'
           '            for (int i = 0; i < 3; i++) vel[i] = R[3*i]*u[0] + R[3*i+1]*u[1] + R[3*i+2]*u[2] ' + add + ';\n'
           '            fprintf(stderr, "ORACLE hit v_world=%.4f %.4f %.4f\\n", vel[0], vel[1], vel[2]);\n'
           '        } else fprintf(stderr, "ORACLE MISS\\n");\n    }\n')
    s = s.replace('    last_t = t;\n}\n\n/* one IMU sample', blk + '    last_t = t;\n}\n\n/* one IMU sample', 1)
    assert 'ORACLE hit' in s
    (here / 'arms' / f'{name}.c').write_text(s)
    return name
if __name__ == '__main__':
    arms = [('zero',1.0),('mag',0.3),('dir',0.3),('fwd',0.3),('fwdall',0.3),('half',0.3),('vx',3.0),('vn',1.0,2),('vn',1.0,3),('neg',1.0),('mag',1.0),('zero',3.0)]
    print([make(*a) for a in arms])
