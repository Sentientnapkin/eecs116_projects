#!/bin/bash
# ho_dl.sh : mirror SentientNapkin/viobench-holdout-240 flights/*.zip into ~/data/ho240 (keeps polling while the upload is in progress)
source "$HOME/.venv/bin/activate"
D=$HOME/data/ho240; mkdir -p $D; cd $D
idle=0
while :; do
  python - > want.txt <<'PY'
import json, urllib.request, re
url = "https://huggingface.co/api/datasets/SentientNapkin/viobench-holdout-240/tree/main/flights?limit=1000"
z = []
while url:
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "py"}))
    z += json.load(r)
    m = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("Link", "") or "")
    url = m.group(1) if m else None
for f in z:
    if f["path"].endswith(".zip"): print(f["path"].split("/")[-1], f["size"])
PY
  n=0
  while read f sz; do
    [ -f "$f" ] && [ "$(stat -c %s "$f")" = "$sz" ] && continue
    echo "$f"; n=$((n+1))
  done < want.txt > todo.txt
  have=$(( $(wc -l < want.txt) - n ))
  echo "$(date +%T) listed $(wc -l < want.txt) have $have todo $n"
  if [ $n -gt 0 ]; then
    idle=0
    xargs -P 6 -I{} sh -c 'curl -sSfL --retry 5 -o "{}.part" "https://huggingface.co/datasets/SentientNapkin/viobench-holdout-240/resolve/main/flights/{}" && mv "{}.part" "{}"' < todo.txt
  else
    [ "$(wc -l < want.txt)" -ge 240 ] && { echo "done: all 240"; break; }
    idle=$((idle+1)); [ $idle -ge 20 ] && { echo "stopped: no new files for 20 checks"; break; }
    sleep 90
  fi
done
