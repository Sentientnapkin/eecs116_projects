#pragma once
// Streaming port of selected_config_safe.json. Common first-camera coordinates;
// current/past poses only, no scores, episode IDs, split metadata, or truth.
#include <algorithm>
#include <cmath>
#include <cstring>
#ifndef FUSION_AGREEMENT_ABS
#define FUSION_AGREEMENT_ABS 1.0
#endif
#ifndef FUSION_AGREEMENT_REL
#define FUSION_AGREEMENT_REL 0.2
#endif

namespace fusion {
struct Selector {
    double previous[3][13] = {}, velocity[3][3] = {}, previous_weights[3] = {};
    double last_output[3] = {}, offset[3] = {}, last_t = 0;
    bool started = false;
    static double norm(const double *v) { return std::sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]); }
    static double distance(const double *a, const double *b) {
        double d[3]; for(int j=0;j<3;++j) d[j]=a[j]-b[j]; return norm(d);
    }
    static bool valid(const double *x) {
        for(int j=0;j<13;++j) if(!std::isfinite(x[j])) return false;
        return x[3]!=0 || x[4]!=0 || x[5]!=0 || x[6]!=0;
    }
    int step(double t, const double input[3][13], const bool ready[3], double out[13]) {
        double x[3][13], v[3][3], weights[3] = {};
        bool healthy[3];
        const double dt = started ? t-last_t : .05;
        for(int s=0;s<3;++s) {
            std::memcpy(x[s],input[s],sizeof x[s]);
            const bool usable=valid(x[s]);
            if(!usable) { std::memset(x[s],0,sizeof x[s]); x[s][6]=1; }
            double accel[3];
            for(int j=0;j<3;++j) {
                v[s][j]=started ? (x[s][j]-previous[s][j])/dt : 0;
                accel[j]=started ? (v[s][j]-velocity[s][j])/dt : 0;
            }
            healthy[s]=usable && ready[s] && norm(v[s])<=12. && norm(accel)<=100.;
        }
        const double vo=distance(x[0],x[1]);
        const double magnitude=std::max(norm(x[0]),norm(x[1]));
        if(healthy[0] && healthy[1] && vo <= FUSION_AGREEMENT_ABS+FUSION_AGREEMENT_REL*magnitude) {
            weights[0]=.5; weights[1]=.5;
        } else {
            const double dv=healthy[0] ? distance(x[0],x[2]) : HUGE_VAL;
            const double dvo=healthy[1] ? distance(x[1],x[2]) : HUGE_VAL;
            const int best=dv<=dvo ? 0 : 1;
            const double closest=std::min(dv,dvo);
            weights[closest <= 6.+norm(x[2]) ? best : 2]=1.;
        }
        int selected=0;
        for(int s=1;s<3;++s) if(weights[s]>weights[selected]) selected=s;
        std::memcpy(out,x[selected],13*sizeof(double));
        bool changed=false;
        for(int s=0;s<3;++s) changed |= weights[s]!=previous_weights[s];
        for(int j=0;j<3;++j) {
            double target=0, old_target=0;
            for(int s=0;s<3;++s) {
                target+=weights[s]*x[s][j];
                old_target+=weights[s]*previous[s][j];
            }
            if(started) {
                offset[j]*=std::exp(-dt/.5);
                if(changed) offset[j]=last_output[j]-old_target;
            }
            out[j]=target+offset[j]; last_output[j]=out[j];
        }
        std::memcpy(previous,x,sizeof previous);
        std::memcpy(velocity,v,sizeof velocity);
        std::memcpy(previous_weights,weights,sizeof previous_weights);
        started=true; last_t=t;
        return selected;
    }
};
} // namespace fusion
