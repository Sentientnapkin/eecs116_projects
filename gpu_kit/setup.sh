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
echo "--- test flight (10 s) ---"
rm -rf "$HOME/flights_gpu/_test"
time viobench simulate -o "$HOME/flights_gpu/_test" --episodes 1 --seed 1 --duration 10 --no-video --scene-names ProcTHOR-Train-2 2>&1 | grep -v '^conta:' | tee "$KIT/test_flight.log" | grep -iE "adapter|backend|wrote|error" || true
if grep -q llvmpipe "$KIT/test_flight.log"; then
  echo "WARNING: rendering on the CPU (llvmpipe), not the GPU. Flights will be slow; check the NVIDIA/Vulkan driver."
else
  echo "OK: GPU renderer in use. Next: bash make_flights.sh"
fi
