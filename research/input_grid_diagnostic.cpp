#include <cmath>
#include <algorithm>
#include <cstdint>
#include <cstring>
namespace odo {
struct M3 {
    double a[9];
    double operator()(int r, int c) const { return a[r * 3 + c]; }
    double &operator()(int r, int c) { return a[r * 3 + c]; }
};
inline M3 eye() { return {{1, 0, 0, 0, 1, 0, 0, 0, 1}}; }
inline M3 mul(const M3 &x, const M3 &y) {
    M3 r;
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j) r(i, j) = x(i, 0) * y(0, j) + x(i, 1) * y(1, j) + x(i, 2) * y(2, j);
    return r;
}
inline M3 tr(const M3 &x) { M3 r; for (int i = 0; i < 3; ++i) for (int j = 0; j < 3; ++j) r(i, j) = x(j, i); return r; }
inline void mv(const M3 &m, const double *v, double *out) {
    for (int i = 0; i < 3; ++i) out[i] = m(i, 0) * v[0] + m(i, 1) * v[1] + m(i, 2) * v[2];
}
inline M3 exp_so3(double x, double y, double z) {
    const double a = std::sqrt(x * x + y * y + z * z);
    M3 k = {{0, -z, y, z, 0, -x, -y, x, 0}}, kk = mul(k, k), r = eye();
    double s1, s2;
    if (a < 1e-8) { s1 = 1; s2 = 0.5; } else { s1 = std::sin(a) / a; s2 = (1 - std::cos(a)) / (a * a); }
    for (int i = 0; i < 9; ++i) r.a[i] += s1 * k.a[i] + s2 * kk.a[i];
    return r;
}

}
#include "native_odometry/input_grid_attitude.hpp"
static odo::InputGridAttitude grid;
extern "C" {
void ig_init(const double *K,const double *rbc) {
 odo::M3 r; std::copy(rbc,rbc+9,r.a); grid.init(K[0],K[4],K[2],K[5],r);
}
void ig_gray(const uint8_t *rgb,int w,int h,uint8_t *out) {
 cv::Mat gray(h,w,CV_8UC1,out);cv::cvtColor(cv::Mat(h,w,CV_8UC3,const_cast<uint8_t*>(rgb)),gray,cv::COLOR_RGB2GRAY);
}
void ig_step(double t,const uint8_t *rgb,int w,int h,const double *packet,int n,int first,double *out) {
 grid.step(t,rgb,w,h,packet,n,first);
 std::copy(grid.R.a,grid.R.a+9,out);std::copy(grid.bias,grid.bias+3,out+9);std::copy(grid.P,grid.P+3,out+12);
 out[15]=grid.decided;out[16]=grid.accepted;out[17]=grid.rejected;out[18]=grid.window_done;
 out[19]=grid.last_delta[0];out[20]=grid.last_delta[1];out[21]=grid.last_delta[2];out[22]=grid.measurement_valid;
 out[23]=grid.track_count;out[24]=grid.occupied_cells;out[25]=grid.median_flow;
}
int ig_measure(const uint8_t *first,const uint8_t *last,int w,int h,const double *relative,double *out) {
 grid.anchor=cv::Mat(h,w,CV_8UC1,const_cast<uint8_t*>(first));grid.current=cv::Mat(h,w,CV_8UC1,const_cast<uint8_t*>(last));
 cv::Matx33d rel;std::copy(relative,relative+9,rel.val);cv::Vec3d delta;double sigma=0;
 bool ok=grid.measure(rel,delta,sigma);
 for(int i=0;i<3;++i)out[i]=delta[i];out[3]=sigma;out[4]=grid.track_count;out[5]=grid.median_flow;
 return ok;
}
}
