cd /mnt/c/Users/alexa/Projects/eecs116_vio/msckf
until grep -q "^ms_r10s3g " summary.txt; do sleep 15; done
bash m_batch.sh mb6.txt
