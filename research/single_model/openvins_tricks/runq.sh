#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/openvins_tricks
while IFS=$'\t' read -r a d; do echo "$a|$d"; done < queue3.txt | xargs -P 2 -I{} bash -c 'x="{}"; ./job2.sh "${x%%|*}" "${x#*|}"'
