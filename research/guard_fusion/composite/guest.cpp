#include "viobench_abi.h"
#include "selector.hpp"
#include <cstdlib>
#include <cstdio>
#include <exception>
#include <opencv2/core.hpp>

extern "C" {
int32_t vins_init(const char*,uint32_t);
int32_t ovsub_init(const char*,uint32_t);
int32_t n2_init(const char*,uint32_t);
int32_t vins_step(double,const uint8_t*,const double*,int32_t,double*);
int32_t ovsub_step(double,const uint8_t*,const double*,int32_t,double*);
int32_t n2_step(double,const uint8_t*,const double*,int32_t,double*);
int vins_ready(); int ovsub_ready();
}
namespace {
fusion::Selector selector;
bool alive[3]={false,false,false};
uint64_t source_rng[3];
using Init=int32_t(*)(const char*,uint32_t);
using Step=int32_t(*)(double,const uint8_t*,const double*,int32_t,double*);
Init initializers[3]={vins_init,ovsub_init,n2_init};
Step estimators[3]={vins_step,ovsub_step,n2_step};
}
extern "C" int32_t abi_version() {return VIOBENCH_ABI_VERSION;}
extern "C" void *alloc(uint32_t n) {return std::malloc(n?n:1);}
extern "C" int32_t frame_width() {return 320;}
extern "C" int32_t init(const char *json,uint32_t length) {
    selector=fusion::Selector{};
    for(int s=0;s<3;++s) {
        cv::theRNG().state=uint64_t(-1);
        try {alive[s]=initializers[s](json,length)==0;}
        catch(...) {alive[s]=false;}
        source_rng[s]=cv::theRNG().state;
    }
    return (alive[0] || alive[1] || alive[2]) ? 0 : -1;
}
extern "C" int32_t step(double t,const uint8_t *frame,const double *imu,int32_t n,double *out) {
    double x[3][13]; bool ready[3];
    for(int s=0;s<3;++s) {
        for(double &v:x[s]) v=NAN;
        if(alive[s]) {
            cv::theRNG().state=source_rng[s];
            try {
                if(estimators[s](t,frame,imu,n,x[s])!=0 || !fusion::Selector::valid(x[s])) alive[s]=false;
            } catch(const std::exception &e) {
                std::fprintf(stderr,"FUSION source=%d dead=%s\n",s,e.what()); alive[s]=false;
            } catch(...) {alive[s]=false;}
            source_rng[s]=cv::theRNG().state;
        }
        ready[s]=alive[s] && (s==0 ? vins_ready() : s==1 ? ovsub_ready() : true);
    }
    selector.step(t,x,ready,out);
    return fusion::Selector::valid(out) ? 0 : -1;
}
