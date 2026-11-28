# r1-fuelexact: bit-exact fuel cuts to "GSLV smaller net"

The output is bit-identical to the uploaded build `gslv_s3_snace6e1.wasm` (sha256 1a169f28...): the same pose and twist
doubles on every frame. The only differences are fewer wasm instructions per frame.

- Final wasm: `r1-fuelexact.wasm`, sha256 `4795edf1ca219b84a80c9e7325762c994f511814dfd0d3268f37ea84701efba0`
  (627,602 bytes; the base is 446,401 bytes).
- Held-out (`sets/heldout_s3.txt`, 52 flights): ATE 0.6220 = base. Peak fuel 3,138,350 vs 4,077,458 (-23.0%).
  Median per-flight max 2.73M vs 3.53M. Max p99 2.61M vs 3.42M.
- No training and no data sets are involved, so there is nothing to leak-check. twin120 was not used.

## Commands (source to wasm)
All commands run in WSL (`~/.venv` with viobench). `H=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r1-fuelexact`.

```bash
# 0. sources from origin/main (run in Git Bash at the repo root)
D=eecs116_vio/agents/exp/r1-fuelexact/src
for f in base_sn.c flags.txt gslv_s3_snace6e1.wasm; do git show origin/main:gen3/preserved_best/$f > $D/$f; done

# 1. reproduce the base: preserved_best flags as -D defines, -O3 after the recipe's -O2 (as in mk.py's CMakeLists)
bash $H/bld.sh $H/src/base_sn.c $H/base_local.wasm        # -> sha 1a169f28916acd81 == the uploaded wasm (VERIFIED)

# 2. the candidate: three text patches of base_sn.c, then the same build plus four LLVM options
bash $H/mk.sh $H/r1-fuelexact.wasm                         # -> sha 4795edf1ca219b84
#    = python3 tools/patch_upd.py src/base_sn.c /tmp/r1fe_1.c
#      python3 tools/patch_gate.py /tmp/r1fe_1.c /tmp/r1fe_2.c
#      python3 tools/patch_s.py /tmp/r1fe_2.c r1.c
#      bash bld.sh r1.c OUT "" "-mllvm -disable-lsr -mllvm -unroll-threshold=3000 -mllvm -unroll-max-count=16 -mllvm -inline-threshold=1000"
viobench check $H/r1-fuelexact.wasm                       # check: ok
```
`bld.sh` uses its own workspace `~/ws_r1fe` (`viobench init native`). It passes the `-mllvm` options as one CMake `SHELL:` group,
because CMake drops repeated `-mllvm` tokens from `target_compile_options`. Toolchain: the wasi-sdk that `viobench bundle`
installs (clang 23.1.0).

Each code change has a switch (default 1) so it can be turned off for checking: `bash mk.sh x.wasm "-DR1_SBLK=0"` gives
stage r1e (sha a55b1819, rebuilt identically). `F2X='' bash mk.sh x.wasm -DR1_SBLK=0` gives stage r1d (9df884b9, rebuilt
identically). With `-DR1_W18=0` the static buffer layout changes, so the bytes differ from the old intermediate builds; the
output does not.

## What changed (none of these touch the governor's cost model)
The governor charges fixed estimates (GC_ROW, GC_PYR, GC_KLT, GC_CELL, the ns_cost table x1.1, ...). Those constants are
unchanged, so every frame does exactly the same work and gives the same output; the frames simply cost less fuel. The
governor now overestimates the cost, and nothing refills the freed budget. That is intentional: a different schedule would
give a different trajectory.

Fuel was measured on 6 profiling flights (the 4 base peak flights s3v3te-ro-9300648/-9300784/-9300867, s3va-ro-9010255,
plus s3v3te-wa-h9500246 and s3te-fo-9011115). Each stage is cumulative, and the output was bit-identical at every stage.

| stage | change | max fuel (6 flights) | mean fuel/frame |
|---|---|---|---|
| base | uploaded build | 4,077,458 | - |
| r1a | 1. `R1_UPD` update(): HP = H P with 4 rows x 12 columns per pass over the nonzero-H columns, skipping a column when all 4 H entries are exactly 0. S = HP H^T with 4x8 blocks and the same skip. Kt = L^-1 HP with 2 rows x 12 columns. P -= Kt^T Kt with 6 rows x 12 columns and the mirror done by 2x2 transposes. The gate's chol_solve and r^T S^-1 r are skipped when gate == INFINITY (that test can never fire) | 3,451k (-15.4%) | -8.0% |
| r1b | 2. `R1_GATE` per-feature Mahalanobis gate in feature_rows()/line_rows(): H0P and S with 4-row blocks (`r1_hph`) | 3,435k (-15.7%) | -9.0% |
| r1c | 3. `R1_REM` row-remainder kernels (1-3 rows) instead of padding rows in HP and H0P | 3,386k (-17.0%) | -10.2% |
| r1d | 4. `R1_W18` 18-column register blocks in HP and the P update | 3,342k (-18.0%) | -11.0% |
| r1e | 5. compiler: `-mllvm -disable-lsr` (lets clang fold constant offsets into the wasm load/store offset), `-unroll-threshold=3000 -unroll-max-count=16`, `-inline-threshold=1000`. All IEEE-preserving: no fast-math, and wasm has no FMA contraction | 3,161k (-22.5%) | about -23% |
| r1f = final | 6. `R1_SBLK` S kernels (update and r1_hph) use na-row x 8- or 4-column blocks that stop at the diagonal | 3,138k (-23.0%) | -23.4% |

The flags alone on the unmodified base give mean -8.7% but max +1.2%. The peak gains need the new kernels.

### Why these changes are exact
- Each output element is the same sum of the same products in the same order, from the same starting value (+0, or HP for
  Kt). Only the commutativity of IEEE `*` and `+` is used (for example c*p instead of p*c).
- Skipped terms are h*p with h == 0 exactly, which is +-0 when p is finite. An accumulator that starts at +0 can never become
  -0 under round-to-nearest, so adding +-0 never changes it.
- When gate == INFINITY, `m2 > gate` is false for every m2, NaN included. The y that the skipped solve would compute is
  recomputed after `have_s` anyway.
- Write-back reads the same upper-triangle P[i][j] and writes P[i][j] = P[j][i] = P[i][j] - s(i,j), as before.

## Profile (tools/mkprof.py + mkprof2.py + prof.py: env.mark host import, self fuel per phase)
Base, on the top-10 frames of the 6 flights (3.39M average): update() 49% (HP 19%, P update 16%, S 6%, Kt 6%),
feature_rows 12%, klt 9%, line_rows 8%, pyramid 6%, detect 4%. The 4.08M peak was one MSCKF update with k=41 rows at D=72
(2.58M in update()), plus line gates.

After the change (r1e, top-10 frames of 12 top flights, 2.63M average): P update 14%, HP 12%, line gates 10.5%, klt 7%,
detect 6%, pyramid 6%, S 5%, Kt 4%, feature gates 4%, the net about 6%.
The dense kernels now run at about 3.4-3.9 wasm instructions per multiply-add; the floor for f64x2 stack code is 3.0
(get, get, get, mul, add, set per two multiply-adds). The held-out maximum is still s3v3te-ro-9300784 frame 482 (MSCKF k=34
plus 3 line gates). The next flights are at 2.94-2.96M.

## Parity evidence
- `tools/run6.sh WASM DIR` + `tools/cmp.py BASE_DIR CAND_DIR`: the poses and twists of every frame, compared as uint64 bit
  patterns. All stages were IDENTICAL on the 6 flights.
- The final build against the uploaded wasm on all 52 held-out flights: 52/52 IDENTICAL on every frame
  (`parity_heldout52.txt`). Every frame was also cheaper: the per-flight `frame-max-ratio` is at most 0.90.
- `agents/eval_set.sh r1-fuelexact.wasm r1-fuelexact` + `python agents/paired.py r1-fuelexact base_gslv`: ATE 0.6220 vs
  0.6220, d = 0 exactly on every flight. Peak 3,138,350 vs 4,077,458. Estimated server: 0.4444 m @ 3,103,894, gain 2.968
  vs 2.848 claimed.

## Files
- `src/`: the origin/main sources (`base_sn.c`, `flags.txt`, the uploaded wasm, the teammate's `mk.py` / `CMakeLists.txt`).
- `tools/patch_upd.py`, `patch_gate.py`, `patch_s.py`, `kgen.py`: the code changes (kernels are generated text).
- `bld.sh`, `mk.sh`: build. `r1.c`: the generated source of the final build.
- `tools/prof*.py|sh`, `an.py`, `an2.py`, `mkprof*.py`, `pp.sh`/`active.py` (active-line view under the flags),
  `asm.sh` + `loops.py` (instruction counts of inner loops): profiling.
- `r1b.wasm`, `r1d.wasm`, `r1e.wasm`: intermediate stages. `base_local.wasm`: the reproduced base.
  `base_flagsonly.wasm`: the base with the change-5 flags.
