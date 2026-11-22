import runpy,sys
sys.argv=['lv_prep.py','/data/backups/rganapa/Sebastian/gen/raw-learnvel-st3/bench','16','/data/backups/rganapa/Sebastian/tmp/sl_cache_st3']
runpy.run_path('research/single_model/learnvel/lv_prep.py',run_name='__main__')
