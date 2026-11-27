#ifndef ENS2_METER_H
#define ENS2_METER_H
static int ens_scope_begin(int job,int a,int b,int c) { ens_meter(job,a,b,c);return 0; }
static void ens_scope_end(int *unused) { (void)unused;ens_meter_end(); }
#endif
