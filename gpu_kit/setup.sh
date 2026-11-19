#!/bin/bash
# One-time setup on the GPU computer (Linux, ideally native rather than WSL, with the NVIDIA driver installed).
#   bash setup.sh /path/to/your/viobench/clone     (the folder that has pyproject.toml and viobench/ inside)
#   bash setup.sh                                   (no path: clones a fresh copy into ~/viobench)
# Installs viobench with its own venv, applies our autopilot patch, and renders one 10 s test flight.
set -e
KIT=$(cd "$(dirname "$0")" && pwd)
REPO=${1:-$HOME/viobench}
[ -d "$REPO" ] || git clone https://github.com/jonas-eschmann/viobench "$REPO"
REPO=$(cd "$REPO" && pwd)
# a team repo that holds viobench in a subfolder: find the real checkout
if [ ! -f "$REPO/viobench/tools/datasets/generate/simulation.py" ]; then
  found=$(find "$REPO" -maxdepth 3 -path "*viobench/tools/datasets/generate/simulation.py" | head -1)
  [ -n "$found" ] || { echo "No viobench checkout found under $REPO"; exit 1; }
  REPO=${found%/viobench/tools/datasets/generate/simulation.py}
fi
echo "using viobench at $REPO"
echo "$REPO" > "$KIT/.repo_path"
cd "$REPO"
# patch relative to this folder (works whether or not it is the top of a git repo)
if grep -q TASK_EXTRA viobench/tools/datasets/generate/simulation.py; then echo "patch already applied"
elif command -v patch >/dev/null; then patch -p1 --forward < "$KIT/viobench_local.patch"
else git apply --directory="$(git rev-parse --show-prefix 2>/dev/null)" "$KIT/viobench_local.patch"; fi
grep -q TASK_EXTRA viobench/tools/datasets/generate/simulation.py || { echo "PATCH MISSING: stop and tell Claude"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -e .
# the renderer compiles itself on first use and needs CMake >= 3.24 (lab machines have 3.22): a newer one inside the venv
if ! cmake --version 2>/dev/null | awk 'NR==1 {split($3, v, "."); exit !(v[1] > 3 || (v[1] == 3 && v[2] >= 24))}'; then
  echo "installing a newer CMake into the venv (system one: $(cmake --version 2>/dev/null | head -1))"
  pip install -q "cmake>=3.24"
  hash -r
  rm -rf "$HOME/.cache/hyperlux"/renderer-* "$HOME/.cache/hyperlux"/hyperdrone-* 2>/dev/null  # half-configured builds from the old CMake
fi
echo "cmake: $(cmake --version | head -1)"
FLIGHTS=${FLIGHTS_DIR:-$HOME/flights_gpu}
mkdir -p "$FLIGHTS"
echo "$FLIGHTS" > "$KIT/.flights_path"
free_gb=$(df -Pk "$FLIGHTS" | awk 'NR==2 {print int($4 / 1048576)}')
echo "free space where the flights go ($FLIGHTS): ${free_gb} GB (about 20 GB needed)"
[ "$free_gb" -ge 22 ] || echo "WARNING: not enough space there. Re-run as:  FLIGHTS_DIR=/tmp/$USER/flights bash setup.sh $*   (pick a disk with room: df -h /tmp)"
echo "--- test flight (10 s; the first run also compiles the renderer, a few minutes) ---"
rm -rf "$FLIGHTS/_test"
time viobench simulate -o "$FLIGHTS/_test" --episodes 1 --seed 1 --duration 10 --no-video --scene-names ProcTHOR-Train-2 2>&1 | grep -v '^conta:' > "$KIT/test_flight.log" || true
grep -iE "adapter|backend|wrote" "$KIT/test_flight.log" || true
if ! ls "$FLIGHTS"/_test/*.zip >/dev/null 2>&1; then
  echo "FAILED: the test flight was not written. Last lines of the log:"
  tail -8 "$KIT/test_flight.log"
  echo "Send these lines to Claude (or commit gpu_kit/test_flight.log)."
  exit 1
elif grep -q llvmpipe "$KIT/test_flight.log"; then
  echo "WARNING: it works, but renders on the CPU (llvmpipe), not the GPU: flights will be slow (~10 min each)."
else
  echo "OK: test flight written with the GPU renderer. Next: bash calibrate.sh"
fi
