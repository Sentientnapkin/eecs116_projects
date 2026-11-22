cd /mnt/c/Users/alexa/Projects/eecs116_vio/msckf
until grep -q "^ms_a1g10 " summary.txt; do sleep 15; done
bash m_batch.sh mb8.txt
