#!/bin/bash
# queue_nb.sh: after the H32 / 10-row runs finish, train the narrower / weighted neighbour variants one at a time.
cd /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/cheap
until grep -q BEST ~/data/s3logs/mlp_nbA_g10.log 2>/dev/null; do sleep 30; done
while pgrep -f "[m]lp_fit.py" > /dev/null; do sleep 10; done
E=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/stage3/ids_s3nb.txt
run() { tag=$1; shift; env "$@" TAG=${tag}_ LOSS=rms EXCLUDE=$E VAL=s3va TEST=s3nb EPOCHS=1500 TH=14 PYTHONUNBUFFERED=1 \
        ~/.venv_gru/bin/python -W ignore mlp_fit.py > ~/data/s3logs/mlp_$tag.log 2>&1; echo "$tag: $(tail -1 ~/data/s3logs/mlp_$tag.log)"; }
run s3r35 TRAIN=s3nb_r11_35
run s3r60 TRAIN=s3nb_r11_60
run s3nbW TRAIN=s3nbtr FLIGHTW=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/stage3/weights_s3nbtr.json
