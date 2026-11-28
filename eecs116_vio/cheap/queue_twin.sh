#!/bin/bash
# queue_twin.sh: retrain the IMU-only variants with the 120 twins (and the 236 neighbours) excluded, one at a time,
# then score each on twin120 / twin24.
cd /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/cheap
while pgrep -f "[m]lp_fit.py" > /dev/null; do sleep 15; done
S3=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/stage3
E=$S3/ids_excl_nb_twin.txt
run() { tag=$1; shift; env "$@" TAG=${tag}_ LOSS=rms EXCLUDE=$E TRAIN=s3nbtr VAL=s3va TEST=twin EPOCHS=1500 TH=14 PYTHONUNBUFFERED=1 \
        ~/.venv_gru/bin/python -W ignore mlp_fit.py > ~/data/s3logs/mlp_$tag.log 2>&1; echo "$tag: $(tail -1 ~/data/s3logs/mlp_$tag.log)"; }
run tA GROWS=27
run tWg10 GROWS=0123456789 FLIGHTW=$S3/weights_s3nbtr.json
run tH32 GROWS=27 H=32
echo "== twin scores"
~/.venv_gru/bin/python -W ignore s3twin_eval.py ~/data/mlpfit_tA_g27_H16relu_hw1_s0.pt ~/data/mlpfit_tH32_g27_H32relu_hw1_s0.pt 2>&1 | tail -5
GROWS=0123456789 ~/.venv_gru/bin/python -W ignore s3twin_eval.py ~/data/mlpfit_tWg10_g0123456789_H16relu_hw1_s0.pt 2>&1 | tail -1
