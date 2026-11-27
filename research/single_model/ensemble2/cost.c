#include "common.h"
#include "models.h"
/* Initial estimates, replaced by measured job models after diagnostic replay. */
static int ens_model(int job,int a,int b,int c,int bound) {
    unsigned key=((unsigned)job<<24)+((unsigned)a<<16)+((unsigned)b<<8)+(unsigned)c;
    int lo=0,hi=sizeof ens_models/sizeof ens_models[0];
    while(lo<hi){int mid=(lo+hi)/2;if(ens_models[mid].key<key)lo=mid+1;else hi=mid;}
    if(lo<(int)(sizeof ens_models/sizeof ens_models[0]) && ens_models[lo].key==key)
        return bound?ens_models[lo].bound:ens_models[lo].mean;
    switch(job) {
    case 1:return 3000;
    case 2:return 22000;
    case 3:return 14000;
    case 4:return 9000;
    case 5:
        return a<32?11000:a<56?90000:a<60?90000:a<62?50000:a<74?110000:a<86?160000:a<92?140000:a<95?120000:200000;
    case 6:return 211200;
    case 7:return 350000;
    case 8:return 3500*a+30000;
    case 9:return 250000;
    case 10:return 180000;
    case 11:return 30000;
    case 12:case 13:return 7000;
    case 14:return 16000;
    case 15:return (c%4==2?7000*a*a+10000:1300*a*a+12000);
    case 16:return 9000+450*a*b+110*a*a+12*a*a*a;
    case 17:return 9000+(c?0:450*a*b+110*a*a+12*a*a*a)+160*a*b+3*a*b*b;
    case 18:return 180000;
    case 19:return 20000;
    case 20:return 6000;
    case 21:return a>b-18?10000+7*a*(b-18)*(b-18):1000;
    default:return 10000;
    }
}
int ens_bound(int j,int a,int b,int c){return ens_model(j,a,b,c,1);}
int ens_estimate(int j,int a,int b,int c){
    if(ens_role){switch(j){case 6:return 153700;case 7:return 6500;case 8:return 7500;case 9:return 3500;case 10:return 6500;}}
    return ens_model(j,a,b,c,0);
}
static int depth, ids[32],args[32][3];
void ens_meter(int job,int a,int b,int c) {
    if(depth<32){ids[depth]=job;args[depth][0]=a;args[depth][1]=b;args[depth][2]=c;}
    depth++;
    ens_mark(job+ens_role*1000,a,b,c);
}
void ens_meter_end(void) {
    depth--;
    if(depth==0)ens_cost+=ens_estimate(ids[depth],args[depth][0],args[depth][1],args[depth][2]);
    ens_mark(-(ids[depth]+ens_role*1000),args[depth][0],args[depth][1],args[depth][2]);
}
void ens_meter_args(int a,int b,int c){args[depth-1][0]=a;args[depth-1][1]=b;args[depth-1][2]=c;}
