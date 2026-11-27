#!/bin/bash
# wait until the coordinator's v3val shrink is done, refresh pools, then release the held eval queue
G=/data/backups/rganapa/Sebastian/gen3; A=$G/agents/netv2
until [ $(ls $G/out/keep/ | grep -c "^s3v3va-.*zip$") -le 360 ]; do sleep 60; done
sleep 180
cd $G && bash refresh_pools.sh > $A/logs/refresh_after_shrink.log 2>&1
cat $A/logs/queue_hold.txt >> $A/logs/queue.txt; : > $A/logs/queue_hold.txt
echo "$(date '+%F %H:%M') released queue; v3val $(ls $G/pools/v3val | wc -l) v1val $(ls $G/pools/v1val | wc -l)" >> $A/logs/queue_done.txt
