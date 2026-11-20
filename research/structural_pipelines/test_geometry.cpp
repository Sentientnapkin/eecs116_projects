#include "odometry.hpp"
#include "structure.hpp"
#include <cassert>
#include <iostream>
using namespace odo;
int main() {
    Structure s; s.init(160,160,159.5,119.5,eye());
    s.gravity_ready=true;
    M3 actual=exp_so3(.15,-.12,.23);
    std::vector<cv::Vec3d> planes; std::vector<int> regions;
    for(int axis=0;axis<2;++axis) for(int i=0;i<8;++i) {
        cv::Vec3d d=axis?cv::Vec3d(0,1,0):cv::Vec3d(1,0,0);
        cv::Vec3d n=s.up.cross(d)+s.up*(.3+.1*i);
        planes.push_back(Structure::matrix(tr(actual))*n); regions.push_back(i+axis*8);
    }
    for(int i=0;i<3;++i) s.observe_planes(planes,regions,actual);
    assert(s.anchored && s.manhattan_updates==0);
    M3 drift=mul(exp_so3(0,0,.06),actual);
    for(int i=0;i<40;++i) s.observe_planes(planes,regions,drift);
    assert(s.yaw<-.055 && s.yaw>-.061);
    assert(s.manhattan_updates>0);
    Structure weak; weak.gravity_ready=true;
    for(int i=0;i<8;++i) weak.observe_planes(planes,std::vector<int>(16,0),actual);
    assert(!weak.anchored);
    Structure vertical; vertical.gravity_ready=true;
    for(int i=0;i<8;++i) vertical.observe_planes(std::vector<cv::Vec3d>(16,cv::Vec3d(1,0,0)),regions,eye());
    assert(!vertical.anchored);
    Structure g; g.init(160,160,159.5,119.5,eye());
    double packet[7]={0,0,-9.81,0,0,0,0};
    for(int i=0;i<100;++i) g.gravity(i*.01,packet,1,eye());
    assert(g.gravity_ready && cv::norm(g.up-cv::Vec3d(0,-1,0))<1e-10);
    Structure moving; double accel[7]={0,0,0,12,0,0,0};
    for(int i=0;i<200;++i) moving.gravity(i*.01,accel,1,eye());
    assert(!moving.gravity_ready);
    // Known-rotation translation recovery, nontrivial camera motion and depth.
    Structure d; d.init(160,160,159.5,119.5,eye());
    cv::Matx33d rel=Structure::matrix(exp_so3(.02,-.03,.01));
    cv::Vec3d translation(.16,-.04,.08);
    std::vector<cv::Point2f> a,b;
    for(int i=0;i<64;++i) {
        cv::Vec3d p((i%8-3.5)*.2,(i/8-3.5)*.2,2.+(i%7)*.3);
        cv::Vec3d q=rel.t()*(p-translation), px=d.K*p, qx=d.K*q;
        a.emplace_back(px[0]/px[2],px[1]/px[2]); b.emplace_back(qx[0]/qx[2],qx[1]/qx[2]);
    }
    cv::Mat mask(64,1,CV_8U,cv::Scalar(1));
    assert(d.direction_rays(a,b,mask,rel));
    assert(d.observed_direction.dot(Structure::unit(translation))>.99999);
    assert(!d.direction_rays(a,a,mask,cv::Matx33d::eye()));
    // Real image front-end, with independently projected 3D points at varied depths.
    Structure frontend; frontend.init(160,160,159.5,119.5,eye());
    cv::Mat first(240,320,CV_8U,cv::Scalar(0)),second=first.clone();
    cv::RNG rng(116); cv::Vec3d shift(.12,.02,.03);
    M3 next=exp_so3(0,.005,0);
    for(int i=0;i<180;++i) {
        double z=rng.uniform(2.,5.);
        cv::Vec3d point(rng.uniform(-1.5,1.5),rng.uniform(-1.,1.),z);
        cv::Vec3d q=Structure::matrix(tr(next))*(point-shift);
        cv::Vec3d u=frontend.K*point,v=frontend.K*q;
        cv::Point a0(int(u[0]/u[2]),int(u[1]/u[2])), b0(int(v[0]/v[2]),int(v[1]/v[2]));
        int intensity=rng.uniform(90,255);
        cv::rectangle(first,cv::Rect(a0.x-2,a0.y-2,5,5),cv::Scalar(intensity),-1);
        cv::rectangle(second,cv::Rect(b0.x-2,b0.y-2,5,5),cv::Scalar(intensity),-1);
    }
    frontend.previous=first; frontend.anchor_R=eye();
    assert(frontend.direction(second,next));
    assert(frontend.observed_direction.dot(Structure::unit(shift))>.97);
    frontend.have_frame=true; frontend.anchor_t=0;
    double pos[3]={.12,.06,.03}, vel[3]={.24,.12,.06};
    cv::Vec3d before(vel[0],vel[1],vel[2]);
    cv::Mat rgb; cv::cvtColor(second,rgb,cv::COLOR_GRAY2RGB);
    frontend.velocity(.5,rgb.data,320,240,next,pos,vel);
    assert(frontend.direction_updates==1 && frontend.direction_valid);
    cv::Vec3d after(vel[0],vel[1],vel[2]);
    assert(std::abs(cv::norm(after)-cv::norm(before))<1e-12);
    assert(Structure::unit(after).dot(Structure::unit(shift))>Structure::unit(before).dot(Structure::unit(shift)));
    std::cout<<"PASS: Manhattan drift sign/convergence, support gates, gravity qualification, calibrated translation sign and degeneracy\n";
}
