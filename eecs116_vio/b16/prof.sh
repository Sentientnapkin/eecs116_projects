# prof.sh NAME DEFS... : PROF build of b16p.c with DEFS, profile 8 HF flights
source ~/.venv/bin/activate
N=$1; shift
cd ~ && SRC=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/b16p.c FLAGS="-O3 -DPROF" bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh p_$N "$@" 2>&1 | tail -2
rm -rf ~/prof/$N; mkdir -p ~/prof/$N
cd /mnt/c/Users/alexa/Projects/eecs116_vio/b16 && python prof_run.py ~/ws_m/ms_p_$N.wasm ~/prof/$N 8 8 | grep -v '^done'
python prof_an.py ~/prof/$N
