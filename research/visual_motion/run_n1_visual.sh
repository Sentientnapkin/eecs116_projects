#!/usr/bin/env bash
# Run from research/ after activating the teacher environment.
set -euo pipefail
: "${N1_MANIFEST:?point to a pinned copy of the published n1-campaign manifest}"
: "${CAMPAIGN_DEV:?point to the published campaign dev-records.json}"
: "${CAMPAIGN_SHARDS:?point to the prepared campaign shards}"
: "${SSM_RECIPE_RUN:?point to the legacy SSM checkpoint directory}"
: "${LEDGER:?point to the audited legacy ledger}"
work=data/visual-motion
out=results/visual-motion/n1-screen

for arm in v2 v0; do
    reuse=(--reuse "$work/$arm")
    if [[ "$arm" == v2 ]]; then
        reuse+=(--reuse "$work/n1-sea-stage-001")
        encoder=(--sea-source "$work/SEA-RAFT")
        size=72
    else
        encoder=(--cnn-run "$SSM_RECIPE_RUN")
        size=5232
    fi
    common=(--manifest "$N1_MANIFEST" --campaign-dev "$CAMPAIGN_DEV"
            --source "$work/d0" --source "$CAMPAIGN_SHARDS")
    python -B n1_visual_inputs.py "${common[@]}" "${reuse[@]}" --output "$work/n1-$arm-plan"
    if [[ -f "$work/n1-$arm-plan/missing/manifest.json" ]]; then
        python -B visual_motion_cache.py --data "$work/n1-$arm-plan/missing" "${encoder[@]}" --output "$work/n1-$arm-extra"
        reuse+=(--reuse "$work/n1-$arm-extra")
    fi
    python -B n1_visual_inputs.py "${common[@]}" "${reuse[@]}" --output "$work/n1-$arm"
    test ! -d "$work/n1-$arm/missing"
    python -B -u teacher_train.py --config configs/visual-motion-screen.json --epochs 36 \
        --data "$work/n1-$arm" --set "model.cached_visual_size=$size" --output "$out/$arm-ssm-s217"
    python -B - "$work/n1-$arm" <<'PY'
from pathlib import Path
import json, sys
root=Path(sys.argv[1])
target=root/"campaign-replay"
target.mkdir()
manifest=json.loads((root/"manifest.json").read_text())
manifest["datasets"]={"development":manifest["campaign_development"]}
(target/"manifest.json").write_text(json.dumps(manifest))
for row in manifest["datasets"]["development"]:
    (target/row["file"]).symlink_to((root/row["file"]).resolve())
PY
    python -B teacher_eval.py --data "$work/n1-$arm/campaign-replay" --ledger "$LEDGER" \
        --runs "$out/$arm-ssm-s217" --output "$out/$arm-campaign"
    python -B teacher_eval.py --data "$work/n1-$arm/campaign-replay" --ledger "$LEDGER" \
        --runs "$out/$arm-ssm-s217" --max-seconds 30 --output "$out/$arm-campaign-30s"
done
