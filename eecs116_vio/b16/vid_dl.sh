#!/bin/bash
# vid_dl.sh NAME... : fetch the named holdout flights (no .zip) into ~/data/ho_vid, waiting for each to be uploaded
D=$HOME/data/ho_vid; mkdir -p $D; cd $D
for n in "$@"; do
  [ -f ~/data/ho240/$n.zip ] && { cp ~/data/ho240/$n.zip .; echo "copied $n"; continue; }
  until curl -sSfL --retry 3 -o "$n.zip.part" "https://huggingface.co/datasets/SentientNapkin/viobench-holdout-240/resolve/main/flights/$n.zip"; do echo "waiting for $n"; sleep 60; done
  mv "$n.zip.part" "$n.zip"; echo "got $n"
done
