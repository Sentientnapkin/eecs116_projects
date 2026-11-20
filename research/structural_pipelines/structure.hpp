#pragma once
// Sensor-only integration corrections; base learned inputs remain untouched.
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/video/tracking.hpp>
#include <opencv2/geometry.hpp>
#include <vector>
#include <algorithm>
#include <cmath>

namespace odo {
struct Structure {
    static constexpr double PI = 3.14159265358979323846;
    cv::Matx33d K, Ki;
    cv::Mat previous;
    cv::Ptr<cv::LineSegmentDetector> detector;
    M3 Rbc = eye(), anchor_R = eye(), correction = eye();
    cv::Vec3d up = {0,0,1}, ex = {1,0,0}, ey = {0,1,0}, gravity_sum = {0,0,0}, gyro_sum = {0,0,0};
    int gravity_n = 0, gravity_bad = 0, stable = 0, lines_used = 0, manhattan_updates = 0, direction_updates = 0;
    double gravity_start = -1, gravity_sq = 0, gyro_sq = 0, last_lines = -1, reference = 0, pending = 0, yaw = 0;
    double anchor_t = 0, direction_t = -10;
    bool gravity_ready = false, anchored = false, have_frame = false, direction_valid = false;
    cv::Vec3d observed_direction = {0,0,0}, direction_axis = {0,0,0};
    double direction_angle = 0, anchor_position[3] = {};
    static cv::Matx33d matrix(const M3 &r) { return cv::Matx33d(r.a); }
    static cv::Vec3d unit(cv::Vec3d v) { return v / std::max(cv::norm(v), 1e-12); }
    static double periodic(double a) { return .25 * std::atan2(std::sin(4*a), std::cos(4*a)); }
    static double clamp(double x, double a, double b) { return std::max(a,std::min(b,x)); }
    void init(double fx,double fy,double cx,double cy,const M3 &bc) {
        K = {fx,0,cx,0,fy,cy,0,0,1}; Ki=K.inv(); Rbc=bc;
        detector=cv::createLineSegmentDetector(cv::LSD_REFINE_NONE);
    }
    void gravity(double t,const double *packet,int n,const M3 &raw) {
        // Lock gravity only after a quiet, near-1g observed interval. No assumed world Z.
        if(gravity_ready) return;
        if(gravity_start<0) gravity_start=t;
        for(int i=0;i<n;++i) {
            const double *p=packet+7*i;
            cv::Vec3d a(p[1],p[2],p[3]), w(p[4],p[5],p[6]);
            double an=cv::norm(a);
            if(!std::isfinite(an) || !std::isfinite(cv::norm(w))) { ++gravity_bad; continue; }
            gyro_sum+=w; gyro_sq+=w.dot(w);
            a=matrix(raw)*a; gravity_sum+=a; gravity_sq+=a.dot(a); ++gravity_n;
        }
        if(t-gravity_start<.8) return;
        if(gravity_n>=80 && gravity_bad==0) {
            cv::Vec3d mean=gravity_sum/gravity_n;
            if(std::abs(cv::norm(mean)-9.81)<.3 && gravity_sq/gravity_n-mean.dot(mean)<.4
               && cv::norm(gyro_sum/gravity_n)<.1
               && gyro_sq/gravity_n-(gyro_sum/gravity_n).dot(gyro_sum/gravity_n)<.04) {
                up=unit(mean);
                cv::Vec3d seed=std::abs(up[0])<.8 ? cv::Vec3d(1,0,0):cv::Vec3d(0,1,0);
                ex=unit(seed-up*up.dot(seed)); ey=up.cross(ex); gravity_ready=true;
            }
        }
        if(!gravity_ready) { gravity_start=t; gravity_n=gravity_bad=0; gravity_sq=gyro_sq=0; gravity_sum=gyro_sum=cv::Vec3d(0,0,0); }
    }
    // Exposed independently for geometry tests. Each plane is K^T (p1 x p2), then rotated to world.
    bool observe_planes(const std::vector<cv::Vec3d> &planes,const std::vector<int> &regions,
                        const M3 &world_camera) {
        if(!gravity_ready) return false;
        std::vector<double> angles;
        std::vector<int> cells;
        for(size_t i=0;i<planes.size();++i) {
            cv::Vec3d n=unit(matrix(world_camera)*planes[i]);
            if(std::abs(n.dot(up))<.04) continue; // vertical-line planes cannot identify a horizontal axis
            cv::Vec3d d=unit(up.cross(n));
            angles.push_back(std::atan2(d.dot(ey),d.dot(ex))); cells.push_back(regions[i]);
        }
        if(angles.size()<8) { stable=0; return false; }
        int best=0; double candidate=0;
        for(int k=0;k<180;++k) {
            double a=k*(PI/2)/180; int count=0;
            for(double b:angles) if(std::abs(periodic(b-a))<.05236) ++count;
            if(count>best) { best=count; candidate=a; }
        }
        bool bins[16]={}; int occupied=0, axes[2]={}; double c=0,s=0;
        for(size_t i=0;i<angles.size();++i) if(std::abs(periodic(angles[i]-candidate))<.05236) {
            c+=std::cos(4*angles[i]); s+=std::sin(4*angles[i]);
            int b=std::max(0,std::min(15,cells[i])); if(!bins[b]) { bins[b]=true; ++occupied; }
            int axis=int(std::llround((angles[i]-candidate)/(PI/2))); ++axes[(axis%2+2)%2];
        }
        lines_used=best;
        if(best<8 || best<.55*angles.size() || occupied<4 || axes[0]<3 || axes[1]<3) { stable=0; return false; }
        double angle=.25*std::atan2(s,c);
        if(stable && std::abs(periodic(angle-pending))>.05236) stable=0;
        pending=angle; ++stable;
        if(stable<3) return false;
        if(!anchored) { reference=angle; anchored=true; return false; }
        double error=periodic(reference-angle)-yaw;
        // A different room orientation or ambiguous jump rejects the observation; no axis snapping.
        if(std::abs(error)>.174533) return false;
        yaw+=clamp(.15*error,-.008727,.008727);
        correction=exp_so3(up[0]*yaw,up[1]*yaw,up[2]*yaw); ++manhattan_updates;
        return true;
    }
    M3 attitude(double t,const uint8_t *rgb,int w,int h,const M3 &raw,const double *packet,int n) {
#ifdef STRUCT_MANHATTAN
        gravity(t,packet,n,raw);
        if(gravity_ready && (last_lines<0 || t-last_lines>=.2-1e-8)) {
            last_lines=t;
            cv::Mat gray; cv::cvtColor(cv::Mat(h,w,CV_8UC3,const_cast<uint8_t*>(rgb)),gray,cv::COLOR_RGB2GRAY);
            std::vector<cv::Vec4f> lines; detector->detect(gray,lines);
            // Bound structural work, favor long segments; no random sampler modifies the base RNG.
            std::sort(lines.begin(),lines.end(),[](const cv::Vec4f&a,const cv::Vec4f&b){return std::hypot(a[2]-a[0],a[3]-a[1])>std::hypot(b[2]-b[0],b[3]-b[1]);});
            std::vector<cv::Vec3d> planes; std::vector<int> cells;
            for(const auto &l:lines) {
                if(planes.size()==96) break;
                if(std::hypot(l[2]-l[0],l[3]-l[1])<24) continue;
                planes.push_back(K.t()*cv::Vec3d(l[0],l[1],1).cross(cv::Vec3d(l[2],l[3],1)));
                cells.push_back(std::min(3,int(2*(l[0]+l[2])/w))+4*std::min(3,int(2*(l[1]+l[3])/h)));
            }
            observe_planes(planes,cells,mul(raw,Rbc));
        }
#else
        (void)t; (void)rgb; (void)w; (void)h; (void)packet; (void)n;
#endif
        return mul(correction,raw);
    }
    bool direction(const cv::Mat &current,const M3 &Rc) {
        std::vector<cv::Point2f> a,b,back;
        for(int y=0;y<4;++y) for(int x=0;x<4;++x) {
            cv::Rect cell(x*current.cols/4,y*current.rows/4,current.cols/4,current.rows/4);
            std::vector<cv::Point2f> found;
            cv::goodFeaturesToTrack(previous(cell).clone(),found,10,.003,5);
            for(auto p:found) a.emplace_back(p.x+cell.x,p.y+cell.y);
        }
        if(a.size()<30) return false;
        cv::Matx33d rel=matrix(mul(tr(anchor_R),Rc));
        std::vector<cv::Point2f> guess;
        cv::perspectiveTransform(a,guess,K*rel.t()*Ki); b=guess;
        std::vector<uchar> status,returned; std::vector<float> errors;
        cv::calcOpticalFlowPyrLK(previous,current,a,b,status,errors,{21,21},3,{cv::TermCriteria::COUNT+cv::TermCriteria::EPS,30,.01},cv::OPTFLOW_USE_INITIAL_FLOW);
        back=a;
        cv::calcOpticalFlowPyrLK(current,previous,b,back,returned,errors,{21,21},3,{cv::TermCriteria::COUNT+cv::TermCriteria::EPS,30,.01},cv::OPTFLOW_USE_INITIAL_FLOW);
        std::vector<cv::Point2f> old,now; std::vector<double> flow; bool cells[16]={}; int occupied=0;
        for(size_t i=0;i<a.size();++i) if(status[i] && returned[i] && cv::norm(back[i]-a[i])<.8 && b[i].x>=0 && b[i].y>=0 && b[i].x<current.cols && b[i].y<current.rows) {
            old.push_back(a[i]); now.push_back(b[i]); flow.push_back(cv::norm(b[i]-guess[i]));
            int cell=std::min(3,int(4*a[i].x/current.cols))+4*std::min(3,int(4*a[i].y/current.rows));
            if(!cells[cell]) {cells[cell]=true; ++occupied;}
        }
        if(old.size()<30 || occupied<5) return false;
        std::sort(flow.begin(),flow.end()); if(flow[flow.size()/2]<2) return false;
        cv::Mat mask,rotation,translation;
        uint64_t saved_rng=cv::theRNG().state;
        try {
            cv::theRNG().state=217;
            cv::Mat E=cv::findEssentialMat(old,now,cv::Mat(K),cv::RANSAC,.999,1.,500,mask);
            if(E.rows!=3 || E.cols!=3) {cv::theRNG().state=saved_rng; return false;}
            int inliers=cv::recoverPose(E,old,now,cv::Mat(K),rotation,translation,mask);
            cv::theRNG().state=saved_rng;
            if(inliers<30 || inliers<.6*old.size()) return false;
        } catch(const cv::Exception &) {cv::theRNG().state=saved_rng; return false;}
        return direction_rays(old,now,mask,rel);
    }
    bool direction_rays(const std::vector<cv::Point2f>&old,const std::vector<cv::Point2f>&now,
                        const cv::Mat &mask,const cv::Matx33d &rel) {
        cv::Matx33d normal=cv::Matx33d::zeros(); std::vector<cv::Vec3d> xo,xn;
        for(size_t i=0;i<old.size();++i) if(mask.at<uchar>(int(i))) {
            cv::Vec3d o=Ki*cv::Vec3d(old[i].x,old[i].y,1), p=rel*(Ki*cv::Vec3d(now[i].x,now[i].y,1));
            cv::Vec3d row=unit(p.cross(o)); normal+=row*row.t(); xo.push_back(o); xn.push_back(p);
        }
        cv::Vec3d values; cv::Matx33d vectors; cv::eigen(normal,values,vectors);
        if(values[1]<1e-3 || values[2]>.2*values[1]) return false;
        cv::Vec3d d(vectors(2,0),vectors(2,1),vectors(2,2));
        int positive=0,negative=0;
        for(size_t i=0;i<xo.size();++i) {
            double aa=xo[i].dot(xo[i]),ab=-xo[i].dot(xn[i]),bb=xn[i].dot(xn[i]),ac=xo[i].dot(d),bc=-xn[i].dot(d),det=aa*bb-ab*ab;
            if(det<1e-12) continue;
            double l1=(bb*ac-ab*bc)/det,l2=(aa*bc-ab*ac)/det;
            positive+=(l1>0 && l2>0); negative+=(l1<0 && l2<0);
        }
        if(std::max(positive,negative)<.7*xo.size()) return false;
        if(negative>positive) d=-d;
        observed_direction=unit(matrix(anchor_R)*d); return true;
    }
    void velocity(double t,const uint8_t *rgb,int w,int h,const M3 &R,const double *position,double *v) {
#ifdef STRUCT_DIRECTION
        M3 Rc=mul(R,Rbc);
        cv::Mat gray; cv::cvtColor(cv::Mat(h,w,CV_8UC3,const_cast<uint8_t*>(rgb)),gray,cv::COLOR_RGB2GRAY);
        if(!have_frame || t-anchor_t>=.5-1e-8) {
            if(have_frame) {
                direction_valid=false;
                if(direction(gray,Rc)) {
                    cv::Vec3d predicted(position[0]-anchor_position[0],position[1]-anchor_position[1],position[2]-anchor_position[2]);
                    if(cv::norm(predicted)>=.05) {
                        predicted=unit(predicted); double angle=std::acos(clamp(predicted.dot(observed_direction),-1.,1.));
                        if(angle>.0001 && angle<PI/4) {
                            direction_axis=unit(predicted.cross(observed_direction));
                            direction_angle=std::min(.25*angle,PI/18); direction_t=t; direction_valid=true; ++direction_updates;
                        }
                    }
                }
            }
            gray.copyTo(previous); anchor_R=Rc; anchor_t=t; have_frame=true;
            std::copy(position,position+3,anchor_position);
        }
        // Rotate subsequent velocity smoothly; no past position or output is rewritten.
        if(direction_valid && t-direction_t<=1.) {
            double angle=direction_angle*std::exp(-(t-direction_t)/.5);
            M3 D=exp_so3(direction_axis[0]*angle,direction_axis[1]*angle,direction_axis[2]*angle);
            double result[3]; mv(D,v,result); std::copy(result,result+3,v);
        }
#else
        (void)t;(void)rgb;(void)w;(void)h;(void)R;(void)position;(void)v;
#endif
    }
};
}
