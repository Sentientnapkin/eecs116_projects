#!/bin/bash
# q.sh JOBFILE : run lines "NAME CFG DEFINES... [@rep]" two at a time (48 workers each)
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/atepush
run() { set -- $1; n=$1; c=$2; shift 2; rep=0; d=""; for x in "$@"; do case $x in @*) rep=${x#@};; *) d="$d $x";; esac; done
  [ -f tables/$n.json ] && { echo "skip $n"; return; }; ./ev.sh $n $c "$d" $rep; }
export -f run
grep -v '^#' $1 | grep . | xargs -P ${P:-2} -I{} bash -c 'run "{}"'
