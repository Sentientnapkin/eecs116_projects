# r2-fuelexact: chained accumulation on top of r1-fuelexact (bit-exact)

- `r2-fuelexact.wasm`, sha256 `83c1957883af70b2e6b1a0b0f01a40d1b5c05b3fee0bee1fc547b48e2d6ac6fd`
- heldout_s3 (52 flights): ATE 0.6220, identical to base_gslv on every flight. Peak 2,758,550 (r1: 3,138,350, base: 4,077,458).
  Median per-flight max 2.53M. The max flight is now s3v3te-ro-9300780.
- Pose and twist bits are identical on all 52 flights and every frame, against the base (`parity52_vs_base.txt`) and against r1 (`parity52_vs_r1.txt`).

## Commands (WSL; workspace ~/ws_r2fe)
```bash
H=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r2-fuelexact
# src/ = origin/main gen3/preserved_best/{base_sn.c,flags.txt,gslv_s3_snace6e1.wasm} (+ a copy of r1-fuelexact.wasm)
bash $H/mk.sh $H/r2-fuelexact.wasm                 # -> 83c1957883af70b2
bash $H/mk.sh $H/x.wasm -DR2_CHAIN=0               # -> 4795edf1ca219b84 = r1-fuelexact exactly (verified)
viobench check $H/r2-fuelexact.wasm                # ok
```
`mk.sh` runs the r1 pipeline: `tools/patch_upd.py`, then `patch_gate.py`, then `patch_s.py`, then `bld.sh` with the four LLVM
flags. The copied tools now also emit the r2 kernels.

## Change (switch `R2_CHAIN`, default 1; `R2U` = iterations per pass, default 8, set at patch time from the env var)
All the dense register-block kernels from r1 now take 8 iterations per pass: HP, S, Kt and the P update in `update()`, plus
H0P and S in the feature and line gates (`r1_hph`). Each accumulator update is written as one expression,
`acc = add(add(...add(acc, c0*v0)..., c7*v7))`, so the partial sum stays on the wasm operand stack: one local.get/set per
8 multiply-adds instead of one per multiply-add. Every accumulator still sees the same operations in the same order (Kt uses
`sub` the same way), so the result is bit-identical. A tail loop handles the remaining iterations.

Fuel on the 6 profiling flights, max / mean versus r1:
| stage | max | mean |
|---|---|---|
| P update only, U=2 | -2.3% | -1.5% |
| P update only, U=4 | -3.2% | -2.1% |
| all kernels, U=4 | -10.9% | -6.0% |
| all kernels, U=8 (final) | -12.2% | -5.8% |

Held-out: peak -12.1% versus r1. Not done (cut for session budget): the image-side cuts (klt, detect, pyramid), cholesky,
and the line-fit code.
