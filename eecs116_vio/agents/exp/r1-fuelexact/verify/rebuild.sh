set -e
H=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r1-fuelexact
S=/mnt/c/Users/alexa/AppData/Local/Temp/claude/24df673cbfed4a36/7259d14f-b38a-4306-96ea-dba8960ce8af/scratchpad/par
T=/tmp/vrb; rm -rf $T; mkdir -p $T
cd $H
python3 tools/patch_upd.py src/base_sn.c $T/1.c > /dev/null
python3 tools/patch_gate.py $T/1.c $T/2.c > /dev/null
python3 tools/patch_s.py $T/2.c $T/r1.c > /dev/null
cmp $T/r1.c $H/r1.c && echo "r1.c identical to committed r1.c"
F2="-mllvm -disable-lsr -mllvm -unroll-threshold=3000 -mllvm -unroll-max-count=16 -mllvm -inline-threshold=1000"
WS=ws_verify bash $H/bld.sh $T/r1.c $T/cand.wasm "" "$F2"
WS=ws_verify bash $H/bld.sh $H/src/base_sn.c $T/base.wasm
sha256sum $T/cand.wasm $T/base.wasm
