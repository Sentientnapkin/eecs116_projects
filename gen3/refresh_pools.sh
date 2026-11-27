# refresh the local eval pools from out/keep. Since 2026-11-26 only a fixed stratified subset is kept locally
# (pools/v3val_keep.txt 358 v3 val flights, pools/v1val_keep.txt 120 v1 val flights); the rest are on HF (viobench-stage3 raw/val).
# Removes dangling links. Never includes test.
cd /data/backups/rganapa/Sebastian/gen3; mkdir -p pools/v3val pools/v1val
for z in out/keep/s3v3va*.zip; do ln -sf $(readlink -f $z) pools/v3val/; done
for z in out/keep/s3va*.zip; do ln -sf $(readlink -f $z) pools/v1val/; done
find pools/v3val pools/v1val -xtype l -delete
echo v3val $(ls pools/v3val | wc -l) v1val $(ls pools/v1val | wc -l)
