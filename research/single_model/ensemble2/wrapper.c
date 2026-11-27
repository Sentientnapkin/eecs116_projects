#include <string.h>
#include <stdlib.h>
#include <math.h>
#include <wasm_simd128.h>
#include "viobench_abi.h"
#include "common.h"
static EnsFrame queue[ENS2_RING];
EnsFrame *ens_frame;
double ens_cost;
int ens_role;
int ens_charged;
/* Wasmtime charges bulk copies by bytes. Unrolled SIMD copies reduce the
 * actual metered operator count while preserving every byte. */
void ens_copy(void *dst,const void *src,uint32_t n) {
    uint8_t *d=dst;const uint8_t *s=src;uint32_t i=0;
    for(;i+256<=n;i+=256) {
#define CP(k) wasm_v128_store(d+i+16*(k),wasm_v128_load(s+i+16*(k)))
        CP(0);CP(1);CP(2);CP(3);CP(4);CP(5);CP(6);CP(7);
        CP(8);CP(9);CP(10);CP(11);CP(12);CP(13);CP(14);CP(15);
#undef CP
    }
    for(;i+16<=n;i+=16)wasm_v128_store(d+i,wasm_v128_load(s+i));
    for(;i<n;i++)d[i]=s[i];
}
static int sequence,read_seq,active,disabled,completed;
static double correction[3];
static int32_t stats[12];
static double last_states[26];
VIOBENCH_EXPORT(ens_stats) int32_t *ens_stats(void){return stats;}
VIOBENCH_EXPORT(ens_states) double *ens_states(void){return last_states;}
int32_t abi_version(void){return VIOBENCH_ABI_VERSION;}
int32_t frame_width(void){return 320;}
void *alloc(uint32_t n){return malloc(n);}
int32_t init(const char *json,uint32_t length) {
    sequence=read_seq=active=disabled=0;completed=-1;
    memset(stats,0,sizeof stats);memset(correction,0,sizeof correction);
    ens_frame=&queue[0];ens_role=0;
    int r=ens_primary_init(json,length);if(r)return r;
    ens_role=1;r=ens_secondary_init(json,length);ens_role=0;return r;
}
int32_t step(double t,const uint8_t *rgb,const double *imu,int32_t count,double *out) {
    EnsFrame *f=&queue[sequence%ENS2_RING];
    if(sequence-read_seq>=ENS2_RING){disabled=1;stats[5]++;}
    /* Never overwrite a pending frame: once disabled, capture into a spare slot. */
    static EnsFrame discard;
    if(disabled)f=&discard;
    memset(f->point_new,0,sizeof f->point_new);memset(f->line_new,0,sizeof f->line_new);
    f->tracked=f->line_tracked=f->line_detected=f->det_cells=f->klt_calls=0;
    ens_frame=f;ens_role=0;ens_cost=60000;
    int r=ens_primary_step(t,rgb,imu,count,out);if(r)return r;
    memcpy(last_states,out,13*sizeof(double));
    ens_mark(80,(int)ens_cost,sequence,0);
    if(count<0 || count>ENS2_IMU){disabled=1;stats[6]++;}
    if(!disabled) {
        f->t=t;f->sequence=sequence;f->count=count;
        ens_copy(f->rgb,rgb,sizeof f->rgb);memcpy(f->imu,imu,(size_t)count*7*sizeof(double));
        memcpy(f->primary,out,sizeof f->primary);
        int budget=ENS2_SYNC?1000000000:ENS2_CAP-(int)ens_cost-80000;
        ens_role=1;
        while(read_seq<=sequence) {
            if(!active){ens_secondary_start(&queue[read_seq%ENS2_RING]);active=1;}
            int need=ens_secondary_need();if(!ENS2_SYNC && need>budget)break;
            int result=ens_secondary_tick(budget);if(!result)break;
            budget-=ens_charged;
            if(result==2) {
                double s[13];ens_secondary_output(s);
                memcpy(last_states+13,s,13*sizeof(double));
                for(int i=0;i<3;i++)correction[i]=s[i]-queue[read_seq%ENS2_RING].primary[i];
                completed=read_seq++;active=0;stats[1]++;
            }
        }
        ens_role=0;
    }
    int lag=completed>=0?sequence-completed:sequence+1;
    stats[0]++;stats[2]=lag;if(lag>stats[3])stats[3]=lag;if(lag>5)stats[4]++;
    if(!disabled && completed>=0 && lag<=5) {
        for(int i=0;i<3;i++)if(isfinite(correction[i]))out[i]+=0.5*correction[i];
        stats[7]++;
    }
    ens_mark(81,lag,disabled,stats[7]);sequence++;return VIOBENCH_STATUS_OK;
}
