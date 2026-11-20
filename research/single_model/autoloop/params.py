"""Parameter registry + source generator for the autoloop. Only `#define NAME value` numeric tokens are replaced; code never changes.
Base source: research/single_model/final/submit/gate.c (f0 + vision movement gate = server 1.244 m build)."""
import hashlib, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE_SRC = ROOT / 'research/single_model/inventive/adopted.c'   # G + C1 (INV_HOLD, INV_VZ, INV_LAT)
REF_RUN = ROOT / 'research/results/single_model/inv_adopted'   # reference scores (visible rows only are ever compared)
GATE_WASM_SHA = '28ab13673e5a32370af26fad02f128b9589faf56feee7e6756f3ef2585f00214'   # results/single_model/inv_adopted/solution.wasm

# name, default (as source token), lo, hi, kind ('f' float, 'i' int), scale ('log'|'lin'), group
_R = [
 ('GYRO_NOISE', .07, .03, .2, 'f', 'log', 'imu'), ('ACCEL_NOISE', .28, .1, .8, 'f', 'log', 'imu'),
 ('GYRO_BIAS_WALK', 6e-4, 1e-4, 3e-3, 'f', 'log', 'imu'), ('ACCEL_BIAS_WALK', 1e-3, 2e-4, 5e-3, 'f', 'log', 'imu'),
 ('INIT_TILT_STD', .05, .01, .2, 'f', 'log', 'init'), ('INIT_VELOCITY_STD', 1.0, .3, 3.0, 'f', 'log', 'init'),
 ('MOVE_TILT_STD', .15, .05, .4, 'f', 'log', 'startup'),
 ('DET_GYRO', .2, .1, .4, 'f', 'log', 'detector'), ('DET_FORCE', 8.8, 8.75, 9.3, 'f', 'lin', 'detector'),
 ('GATE_DISP', 2.0, .8, 4.0, 'f', 'log', 'gate'), ('GATE_PAIRS', 2, 1, 3, 'i', 'lin', 'gate'), ('GATE_PAIRS_MAX', 5, 3, 8, 'i', 'lin', 'gate'),
 ('START_T', 2.0, .5, 4.0, 'f', 'log', 'startup'), ('START_MEAN_FWD', .9, .3, 1.3, 'f', 'lin', 'startup'),
 ('START_STD_X', .5, .15, 1.2, 'f', 'log', 'startup'), ('START_STD_Y', .35, .1, 1.0, 'f', 'log', 'startup'), ('START_STD_Z', .6, .2, 1.4, 'f', 'log', 'startup'),
 ('SPEED_STD', .5, .2, 1.2, 'f', 'log', 'prior'), ('SPEED_TAU', 2.0, .8, 6.0, 'f', 'log', 'prior'),
 ('THRUST_MODEL_STD', .05, .01, .2, 'f', 'log', 'prior'), ('THRUST_GATE', 9.21, 5.99, 13.8, 'f', 'lin', 'prior'),
 ('PIXEL_STD', 1.5, .8, 3.0, 'f', 'log', 'vision'), ('CHI2_Z', 1.645, 1.2, 2.6, 'f', 'lin', 'vision'),
 ('ZUPT_DISPARITY', .4, .15, .8, 'f', 'log', 'zupt'), ('ZUPT_MIN_FEATURES', 10, 6, 20, 'i', 'lin', 'zupt'), ('ZUPT_STD', .02, .005, .08, 'f', 'log', 'zupt'),
 ('MIN_OBS', 3, 2, 5, 'i', 'lin', 'msckf'),
 ('CLONE_EVERY', 4, 3, 6, 'i', 'lin', 'msckf'), ('MAX_CLONES', 6, 4, 8, 'i', 'lin', 'msckf'),
 ('MIN_DEPTH', .2, .1, .5, 'f', 'log', 'msckf'), ('MAX_DEPTH', 40.0, 15.0, 80.0, 'f', 'log', 'msckf'),
 ('TRI_MIN_EIG', 1e-6, 1e-8, 1e-4, 'f', 'log', 'msckf'), ('MAX_UPDATE_FEATURES', 20, 10, 40, 'i', 'lin', 'msckf'),
 ('KLT_ITERS', 5, 3, 10, 'i', 'lin', 'klt'), ('KLT_EPS', .03, .01, .1, 'f', 'log', 'klt'),
 ('KLT_MAX_ERR', 25.0, 12.0, 50.0, 'f', 'log', 'klt'), ('KLT_MIN_EIG', 2.0, .5, 6.0, 'f', 'log', 'klt'),
 ('HOLD_T', 1.0, .5, 2.0, 'f', 'log', 'inv'), ('HOLD_T0', .4, .1, .8, 'f', 'lin', 'inv'), ('HOLD_GN', .12, .04, .4, 'f', 'log', 'inv'),
 ('HOLD_TAU', 1.0, .5, 3.0, 'f', 'log', 'inv'), ('INV_VZ', .3, .1, 1.0, 'f', 'log', 'inv'), ('INV_LAT', .5, .15, 1.5, 'f', 'log', 'inv'),
 ('DETECT_MIN_SCORE', 1000.0, 300.0, 3000.0, 'f', 'log', 'klt'),
]
REG = {n: dict(name=n, default=d, lo=lo, hi=hi, kind=k, scale=s, group=g) for n, d, lo, hi, k, s, g in _R}
NAMES = [r[0] for r in _R]
NUDGE = ('PIXEL_STD', 'DETECT_MIN_SCORE')   # nuisance parameters for the chaos replicates (as tails/rep.sh)


def default_vec():
    return {n: REG[n]['default'] for n in NAMES}


def clamp(name, v):
    r = REG[name]; v = min(max(v, r['lo']), r['hi'])
    return int(round(v)) if r['kind'] == 'i' else float('%.6g' % v)


def norm(vec):
    out = default_vec()
    for k, v in vec.items():
        out[k] = clamp(k, v)
    return out


def vhash(vec):
    v = norm(vec)
    return hashlib.sha1(json.dumps([[n, v[n]] for n in NAMES]).encode()).hexdigest()[:12]


def ill_posed(vec):
    v = norm(vec)
    if v['GATE_PAIRS'] > v['GATE_PAIRS_MAX']: return 'GATE_PAIRS > GATE_PAIRS_MAX'
    if v['MIN_DEPTH'] >= v['MAX_DEPTH']: return 'MIN_DEPTH >= MAX_DEPTH'
    if v['MIN_OBS'] > 8: return 'MIN_OBS > MAX_OBS'
    if v['HOLD_T0'] >= v['HOLD_T']: return 'HOLD_T0 >= HOLD_T'
    if v['MIN_OBS'] > v['MAX_CLONES']: return 'MIN_OBS > MAX_CLONES'
    return None


def fmt(name, v):
    if REG[name]['kind'] == 'i':
        return str(int(v))
    s = '%.6g' % v
    return s if ('.' in s or 'e' in s) else s + '.0'


def render(vec, nudge=1.0, src=BASE_SRC):
    """Source text with the vector's values; `nudge` multiplies the NUDGE parameters (chaos replicates). Unchanged values keep the
    original token, so the default vector with nudge 1 reproduces gate.c byte for byte."""
    v = norm(vec); text = Path(src).read_text()
    for n in NAMES:
        val = v[n] * (nudge if n in NUDGE else 1.0)
        pat = re.compile(r'^(\s*#define\s+' + n + r'\s+)(\S+)(.*)$', re.M)
        hits = pat.findall(text)
        if len(hits) != 1: raise RuntimeError(f'{n}: {len(hits)} defines in source')
        tok = hits[0][1]
        if float(tok) == float(val):
            continue
        text = pat.sub(lambda m: m.group(1) + fmt(n, val) + m.group(3), text, count=1)
    return text


def check_registry():
    t = BASE_SRC.read_text()
    for n in NAMES:
        m = re.search(r'^\s*#define\s+' + n + r'\s+(\S+)', t, re.M)
        assert m and abs(float(m.group(1)) - REG[n]['default']) < 1e-12 * max(1, abs(REG[n]['default'])), (n, m and m.group(1))
        assert REG[n]['lo'] <= REG[n]['default'] <= REG[n]['hi'], n
    assert render(default_vec()) == t
    return len(NAMES)

if __name__ == '__main__':
    print(check_registry(), 'parameters OK, default renders identical source')
