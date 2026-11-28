#!/bin/bash
# vid_run.sh TAG FLIGHT "title" : run GSLV (~/ws_m/ms_gslv.wasm) on ~/data/ho_vid/FLIGHT.zip and render videos/gslv_holdout/TAG_FLIGHT.mp4
source "$HOME/.venv/bin/activate"; cd "$HOME/ws_m"
TAG=$1; F=$2; TITLE=$3; R=vid_$F
rm -rf $R; viobench evaluate ms_gslv.wasm ~/data/ho_vid/$F.zip -o $R > $R.log 2>&1 || { tail -5 $R.log; exit 1; }
grep summary $R.log
python3 /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/b16/vio_video.py ~/data/ho_vid/$F.zip $(ls -d $R/logs/*/) \
  "/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/videos/gslv_holdout/${TAG}_$F.mp4" "$TITLE"
