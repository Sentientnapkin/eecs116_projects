#!/bin/bash
# Upload the server-twin sets to HF viobench-stage3 under twin/ (lists, match tables, and the matched flight zips).
# Re-runnable: rebuilds the staging links from the current pools, uploads only changed files.
cd /data/backups/rganapa/Sebastian/gen3
S=twin_hf/twin; rm -f $S/zips/*.zip
for p in pools/twin24 pools/twin120; do for z in $p/*.zip; do ln -sf "$(readlink -f $z)" $S/zips/; done; done
cp twin/twin24.txt twin/twin120.txt twin/coverage.txt twin/match_table.json $S/ 2>/dev/null
cat > $S/README.md <<R
# Server-twin flight sets (stage 3)
Local viobench-stage3 flights matched to the 24 hidden stage-3 server episodes by probe-decoded statistics
(scene class, start state, FoV, exposure/blur, speed, path extent, rotation rates, image statistics).
- twin24.txt: one unique flight per server episode (episode order 1-12 rooms, 13-18 warehouse, 19-24 forest)
- twin120.txt: ~5 nearest flights per episode
- coverage.txt / match_table.json: match distances and per-feature gaps
- zips/: the matched flights (EuRoC-style zips, same format as raw/)
Generated $(date -u +%F).
R
../venv-teacher/bin/python - <<'P'
from huggingface_hub import HfApi
HfApi().upload_folder(folder_path='twin_hf/twin', path_in_repo='twin', repo_id='SentientNapkin/viobench-stage3', repo_type='dataset', commit_message='Add server-twin flight sets (twin24/twin120)')
print('TWIN UPLOAD DONE', flush=True)
P
