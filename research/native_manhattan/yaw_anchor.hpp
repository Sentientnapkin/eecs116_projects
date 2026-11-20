#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

// Experimental causal Manhattan yaw anchor. Input line directions are normalized
// image-plane (dx,dy) directions from a front-end. Output corrects gyro yaw only;
// it never uses learned velocity to infer heading.
namespace odo_manhattan {
struct Line { double dx, dy, weight; int region; };
struct YawAnchor {
    double reference = 0, candidate = 0;
    int support = 0, streak = 0;
    bool anchored = false;
    static double wrap(double a) { while(a>3.141592653589793) a-=6.283185307179586; while(a< -3.141592653589793) a+=6.283185307179586; return a; }
    void reset() { *this = YawAnchor{}; }
    // Called once per frame after gyro propagation. Camera yaw is relative to
    // first camera. Gravity alignment and calibrated intrinsics are caller-owned.
    // Manhattan axes are pi/2 periodic; choose the branch nearest gyro prediction.
    double update(double gyro_yaw, const Line* lines, int n, bool gravity_reliable) {
        if (!gravity_reliable || !lines || n<8) { streak=0; return gyro_yaw; }
        double c=0,s=0,w=0; bool bins[16]={}; int nb=0;
        for(int i=0;i<n;++i) {
            double a=std::atan2(lines[i].dy,lines[i].dx);
            // doubled angle removes line polarity; fourth harmonic adds 90-degree ambiguity.
            c += lines[i].weight*std::cos(4*a); s += lines[i].weight*std::sin(4*a); w+=lines[i].weight;
            int b=std::max(0,std::min(15,int((a+3.141592653589793)*16/6.283185307179586)));
            if(!bins[b]) { bins[b]=true; ++nb; }
        }
        double concentration=std::hypot(c,s)/std::max(w,1e-9);
        if(concentration<0.72 || nb<3) { streak=0; return gyro_yaw; }
        // Image line angle is not world yaw without camera calibration/attitude.
        // Front-end supplies candidate as gravity-rectified yaw residual via atan2.
        double residual=0.25*std::atan2(s,c);
        double target=wrap(gyro_yaw+residual);
        if(!anchored) { candidate=target; streak=1; } else {
            double d=wrap(target-candidate);
            if(std::abs(d)>0.20) { streak=0; return gyro_yaw; }
            candidate=wrap(candidate+0.2*d); ++streak;
        }
        support=nb;
        if(streak<3) return gyro_yaw;
        if(!anchored) { reference=gyro_yaw; anchored=true; }
        double error=wrap(candidate-gyro_yaw);
        if(std::abs(error)>0.12) error=std::copysign(0.12,error);
        return wrap(gyro_yaw+0.05*error);
    }
};
}
