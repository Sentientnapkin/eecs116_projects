#!/usr/bin/env bash
# Local snapshot commit of the single-model work (never pushes). Excludes checkpoints, caches, episode zips (and symlinks) and bulky binaries.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
msg="${1:-Single-model optimization loop snapshot}"
git add reports research_notes research/single_model >/dev/null 2>&1
for p in research/results/single_model/*/report.txt; do [ -f "$p" ] && git add "$p" >/dev/null 2>&1; done
mapfile -t drop < <(git diff --cached --name-only | grep -E '\.(zip|pt|npz|npy|pkl|o|a|mp4)$|/eval/|\.partial\.json$' || true)
mapfile -t wasm < <(git diff --cached --name-only | grep -E '\.wasm$' | grep -v '^research/single_model/final/submit/' || true)
[ "${#drop[@]}" -gt 0 ] && git reset -q -- "${drop[@]}"
[ "${#wasm[@]}" -gt 0 ] && git reset -q -- "${wasm[@]}"
while read -r f; do
  if [ -L "$f" ] || { [ -f "$f" ] && [ "$(stat -c %s "$f")" -gt 20000000 ]; }; then git reset -q -- "$f"; echo "skipped: $f"; fi
done < <(git diff --cached --name-only)
git diff --cached --quiet && { echo "nothing to commit"; exit 0; }
git commit -q -m "$msg" && git log --oneline -1 && git show --stat --oneline HEAD | tail -1
