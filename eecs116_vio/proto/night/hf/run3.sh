cd /mnt/c/Users/alexa/Projects/eecs116_vio/proto/night/hf
until grep -q '^rma_sw8' summary.txt; do sleep 20; done
bash hf_batch.sh batch3.txt
