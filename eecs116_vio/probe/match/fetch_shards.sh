#!/bin/bash
# fetch_shards.sh LIST : download viobench-stage3 shard tars (one path per line, e.g. shards/train-0012.tar) to ~/data/s3shards/
mkdir -p ~/data/s3shards; cd ~/data/s3shards
sed 's/\r$//' "$1" | grep -v '^$' | xargs -P 3 -I{} bash -c 'f=$(basename {}); [ -f $f ] || { curl -sSL --retry 8 --retry-all-errors -o $f.part "https://huggingface.co/datasets/SentientNapkin/viobench-stage3/resolve/main/{}" && mv -f $f.part $f; }; echo "$f $(stat -c %s $f 2>/dev/null)"'
