"""Splice the displacement teacher (dt_weights.h + dt_core.h) into a B16-family source -> one solution.c.

  python -I make_dt.py --base ../tailcap/tc_b16.c --weights out/dt_weights.h --out build/x/solution.c [-D NAME=VAL ...]
With DT_ON=0 the result behaves exactly like the base (dt_push only copies frames).
"""
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent


def splice(base, weights, defines):
    s = Path(base).read_text()
    head = "".join(f"#define {d.split('=')[0]} {d.split('=', 1)[1]}\n" for d in defines)
    core = Path(weights).read_text() + "\n" + (HERE / "dt_core.h").read_text()
    anchor = "int32_t abi_version(void)"
    assert s.count(anchor) == 1
    s = s.replace(anchor, core + "\n" + anchor)
    a = "        lc_begin(frame, imu, imu_count);\n        write_state(out);\n        return VIOBENCH_STATUS_OK;"
    assert s.count(a) == 1
    s = s.replace(a, "        lc_begin(frame, imu, imu_count);\n        dt_reset(); dt_push(frame);\n        write_state(out);\n        return VIOBENCH_STATUS_OK;")
    c = "    for (int r = 0; r < imu_count; r++) propagate(imu + 7 * r);\n    if (imu_count) imu_measurements(imu, imu_count);"
    assert s.count(c) == 1
    s = s.replace(c, "    dt_preint(imu, imu_count);\n" + c)
    b = "    vision(frame);\n    if (TC_POST && tc_nanch > 0 && !tc_began) lc_step(frame, imu, imu_count);"
    assert s.count(b) == 1
    s = s.replace(b, "    vision(frame);\n    dt_update(frame);\n    if (TC_POST && tc_nanch > 0 && !tc_began) lc_step(frame, imu, imu_count);\n    dt_push(frame);")
    if "#include <math.h>" not in s:
        s = "#include <math.h>\n" + s
    return head + s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(HERE.parent / "tailcap/tc_b16.c"))
    ap.add_argument("--weights", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("-D", action="append", default=[])
    a = ap.parse_args()
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(splice(a.base, a.weights, a.D))
    print("wrote", out)


if __name__ == "__main__":
    main()
