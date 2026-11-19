# Provided VIOBench OpenVINS reproduction

Source: https://github.com/jonas-eschmann/viobench , main pinned to
`9b1b07906aff5a3e6f00155e7aecf967d90aa960` (19 November 2026).
Isolated checkout: `/data/backups/rganapa/Sebastian/viobench-provided-openvins`.
The example source is unchanged. Generated artifacts and logs stay outside the working environment.

The pinned README's eight **120-second** episode ATE values are
0.866, 0.686, 0.832, 1.562, 1.379, 0.790, 1.595, 0.666 m.
Their median is 0.849 m; their arithmetic mean is 1.047 m (rounded table inputs).
These are upstream claims, not our reproduced measurements, and are a different roster/horizon.
The README reports median fuel statistics and p95; these do not establish peak per-frame fuel.

## Environment issue and repair

The ordinary unchanged bundle command automatically invoked the Python runtime dependency build
inside its WASI CMake configure. Its CPython **host** configure inherited the WASI clang compiler;
conftest was WebAssembly and failed with an executable-format error (exit 77).
The failed log is `build-initial-failed.log`; CPython logs are in
`viobench/solution/build/runtime/logs/` in the isolated checkout.
The environment-only repair builds runtime dependencies directly before re-running unchanged bundle:

```bash
SOURCE=/data/backups/rganapa/Sebastian/viobench-provided-openvins
BUILD=/dev/shm/viobench-openvins-runtime-9b1b079 \
  CC=/usr/bin/gcc CXX=/usr/bin/g++ TMPDIR=/dev/shm \
  bash "$SOURCE/viobench/solution/runtime/python/build.sh" \
  > "$SOURCE/runtime-build-host-cc.log" 2>&1
bash /data/backups/rganapa/Sebastian/odometry-provided-comparison/research/provided_baseline/continue.sh
```

No baseline source changes, shared environment installation, paid infrastructure, submission or reserved-test access.
Teacher Python lacks pytest; the provided build's isolated toolchain venv supplies pytest through PYTHONPATH.

The initial NFS runtime dependency build then hit a second environment error: the NFS server's write timestamps
are about 13–16 minutes ahead of the host clock, and NumPy Meson rejects future source timestamps. A fresh local
tmpfs BUILD avoids this; the default workspace build/runtime path will point to that completed dependency build.
The failed NFS tree remains preserved. Clock skew was also reported by native Make, which nevertheless completed.
The native host build uses existing OpenCV 4.13.0 at
`/data/backups/rganapa/Sebastian/tmp/odometry-openvins/env/lib/cmake/opencv4` and required
`-DCMAKE_EXE_LINKER_FLAGS='-L/data/backups/rganapa/Sebastian/tmp/odometry-openvins/env/lib -Wl,-rpath,/data/backups/rganapa/Sebastian/tmp/odometry-openvins/env/lib'`
to use the matching newer libstdc++ required by that library. This host build is an additional check;
the measured Wasm uses the provided pinned runtime's OpenCV 4.12.0 recipe.

## Scoring

`replay.py` executes the actual guest and saves states, truth positions, timestamps and whole-step fuel.
The primary direct unaligned position RMSE uses historical hold-last treatment after guest failures,
origin before any usable state. It also reports upstream's newer origin-fill policy for comparison.
No aligned trajectory metric is computed. Prefixes are continuous first 600 / 601 / 1,200 frames,
without reinitialization, allowing historical 601-frame comparisons as well as exactly 600-frame prefixes.
Campaign resets are the original nominal and five-second crop origins; full replays run to parent end.
Per-flight archive SHA256 and guest SHA256 are retained. Campaign inputs verify parent hashes.
All 120 campaign records are dev only; no reserved original/campaign split is read.

## Completed checks

The unmodified `tests/native/openvins_consensus.cpp` compiled with GCC against the pinned example's
fetched Eigen headers and passed **40,912 native numerical checks**. Log:
`math-native-result.log` in the isolated checkout. This is a mathematical contract check;
it does not establish guest startup/tracking or accuracy.
