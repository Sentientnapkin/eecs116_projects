#!/bin/bash
# regen_one.sh TAG FLIGHT SCENE SEED SETTING CROP "title": regenerate a holdout flight on the CPU renderer, check it, run GSLV, render the video.
source "$HOME/.venv/bin/activate"; cd "$HOME"; mkdir -p data/regen data/ho_vid
export HYPERLUX_BACKEND=GENERIC HYPERLUX_CACHE_DIR=$HOME/.cache/hyperlux-generic VIOBENCH_CACHE=$HOME/.cache/viobench-generic
B=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/b16
FE=/mnt/c/Users/alexa/AppData/Local/Temp/claude/783e65b5158e7724/3a2fc1ba-5450-472b-89ec-113b3da26b48/scratchpad/ho_eval/feats.json
TAG=$1; F=$2
echo "$(date +%T) sim start $F"
python $B/regen_flight.py data/regen/$F.zip hssd-train $3 $4 $5 $6 > data/regen/$F.log 2>&1 || { echo "$(date +%T) SIM FAILED $F"; tail -5 data/regen/$F.log; exit 1; }
echo "$(date +%T) sim done $F"
cp data/regen/$F.zip data/ho_vid/$F.zip
python $B/regen_check.py $FE data/ho_vid/$F.zip 2>&1 | grep -v conta
bash $B/vid_run.sh $TAG $F "$7" 2>&1 | grep -v conta | tail -3
echo "$(date +%T) VIDEO DONE $F"
