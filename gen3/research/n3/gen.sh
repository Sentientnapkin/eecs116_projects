#!/bin/bash
# gen.sh NET(C_lo32_kd1|A2_kd) EXT.inc OUT.c : single-file solution
N=/data/backups/rganapa/Sebastian/gen3/agents/smallnet/cheap_export/net_$1.c
{ grep -v '#include "net.h"' $N | sed -e 's/for (int y = 0; y < 24; y++) { const uint8_t \*r0/for (int y = sn_gy0; y < sn_gy1; y++) { const uint8_t *r0/' -e 's/sn_gray(frame, sn_g5); ns_have5 = 1;/ns_have5 = 1;/' -e 's/^static void sn_gray(/static int sn_gy0 = 0, sn_gy1 = 24;\nstatic void sn_gray(/'; cat <<'H'
void net_cam(double,double,double,const double*);void net_begin(const uint8_t*,const double*,int);int net_feed(const uint8_t*,const double*,int);void net_out(double*,double*);
H
sed -e "/#include \"ins_ext.inc\"/{r $2" -e 'd}' /data/backups/rganapa/Sebastian/gen3/research/n3/src/ins.c; } > $3
