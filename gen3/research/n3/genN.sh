cd /data/backups/rganapa/Sebastian/gen3/research/n3
sed -e '/^#include "ins_ext.inc"/{r src/ext_patch.inc' -e 'd}' ../n2/src/ins.c | sed 's/^void net_cam.*$//' > src/ins_N.c
sed -i '0,/#include "viobench_abi.h"/s//#include "viobench_abi.h"\n#include "stub_net.h"/' src/ins_N.c
