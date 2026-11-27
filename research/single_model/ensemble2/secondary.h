/* Explicit resumable back end. Each tick executes one bounded job. No stack,
 * host buffer, or primary state is borrowed across frames. */
static EnsFrame *ens_input;
static int ens_phase, ens_nb, ens_rw, ens_cur, ens_cloned, ens_full;
static int ens_it, ens_b, ens_nrows, ens_k, ens_k0, ens_net_left;
static double ens_noise, ens_dx[MAXD], ens_dxn[MAXD], ens_reff[MAXD];
static double ens_H0[MAXD*MAXD], ens_r0[MAXD], ens_rn0;

static void ens_vision_begin(void) {
    gov_vis=1;gov_klt_cnt=0;ens_cloned=0;
    int prev=cur_pyr;ens_cur=1-cur_pyr;
    build_pyramid(ens_input->rgb,ens_cur);gov_used+=GC_PYR;map_img=ens_cur;
    double Rwc_now[9];m3mul(R,R_bc,Rwc_now);
    track_all(prev,ens_cur,Rwc_now);gov_klt_cnt=ens_input->klt_calls;gov_used+=gov_klt_cnt*GC_KLT;
    if(edge_on()) {
        double Rr[9];m3tmul(Rwc_now,Rwc_prev,Rr);edge_track_all(ens_cur,Rr);
        gov_used+=edge_alive()*GC_EDGE;
    }
    clone_every=CLONE_EVERY;min_obs=MIN_OBS;tri_min_eig=TRI_MIN_EIG;chi2_z=CHI2_Z;
    frame_no++;
    if(++frames_since_clone>=clone_every) {
        frames_since_clone=0;mp_adds=0;
        add_clone();record_observations();edge_record();vision_zupt();ens_cloned=1;
        gov_used+=GC_CLONE;
    }
    /* Keep the original governor's virtual FE charge although its work is shared. */
}

static void ens_batch_begin(void) {
    int cap=GOV_FREE_ROW?100000:gov_rows_cap();if(cap>ROWCAP)cap=ROWCAP;
    if(NS_HOLD && lc_active && !lc_applied && tc_nanch==0 && frame_no<NS_HOLD_MAX)cap=0;
    if(GOV_PRUNE) {
        int w=0;
        for(int q=0;q<nlost;q++) {
            Obs *o=&lost[q];int k=0;
            for(int j=0;j<o->n;j++)if(clone_index(o->cid[j])>=0) {
                o->cid[k]=o->cid[j];o->x[k]=o->x[j];o->y[k]=o->y[j];k++;
            }
            o->n=k;if(k>=MIN_OBS){if(w!=q)lost[w]=*o;w++;}
        }
        nlost=w;
    }
    int nb=0,rw=0,tk=0;
    while(tk<nlost && nb<MAX_BATCH) {
        int m=gov_fit(&lost[tk],rw,cap);if(!m)break;rw+=2*m-3;
        if(m==lost[tk].n){batch[nb++]=lost[tk];tk++;}
        else {gov_split(&lost[tk],m,&batch[nb]);batch[nb].tid=-1;nb++;if(lost[tk].n<MIN_OBS)tk++;break;}
    }
    memmove(lost,lost+tk,(nlost-tk)*sizeof(Obs));nlost-=tk;
    if(nlost>LOST_KEEP){memmove(lost,lost+nlost-LOST_KEEP,LOST_KEEP*sizeof(Obs));nlost=LOST_KEEP;}
    ens_full=nclones>MAX_CLONES;
    if(ens_full) {
        int oldest=clones[0].id;
        for(int i=0;i<MAX_TRACKS && nb<MAX_BATCH;i++) {
            Obs *o=&tracks[i].obs;
            if(tracks[i].alive && o->n>=min_obs && o->cid[0]==oldest)gov_take_track(i,&rw,cap,&nb);
        }
        nb=edge_take_b(batch,nb,1,&rw,cap);
    } else {
        if(nclones==MAX_CLONES) {
            int nin=clone_every-1>0?clone_every-1:1;
            int ph=frames_since_clone-1;if(ph<0)ph=0;ph%=nin;
            int oldest=clones[0].id;
            for(int i=ph;i<MAX_TRACKS && nb<MAX_BATCH;i+=nin) {
                Obs *o=&tracks[i].obs;
                if(tracks[i].alive && o->n>=min_obs && o->cid[0]==oldest)gov_take_track(i,&rw,cap,&nb);
            }
        }
        if(EDGE_GSPREAD) {
            if(!ens_cloned){int nin=clone_every-1>0?clone_every-1:1;int ph=frames_since_clone-1;if(ph<0)ph=0;
                nb=edge_take_phb(batch,nb,ph%nin,nin,&rw,cap);}
        } else if(ens_cloned)nb=edge_take_b(batch,nb,0,&rw,cap);
    }
    ens_nb=nb;ens_rw=rw;cur_rw=rw;
    ens_noise=(PIXEL_STD/fx)*(PIXEL_STD/fx);
    memset(ens_dx,0,sizeof ens_dx);save_state();ens_it=0;ens_k0=0;ens_rn0=0;
    ens_nrows=0;ens_b=0;
}

static void ens_vision_end(void) {
    if(ens_nb)gov_used+=GC_BATCH+ens_rw*GC_ROW;
    if(ens_full) {
        int oldest=clones[0].id;remove_oldest_clone();edge_drop_clone(oldest);
        for(int i=0;i<MAX_TRACKS;i++) {
            Obs *o=&tracks[i].obs;int k=0;
            for(int j=0;j<o->n;j++)if(o->cid[j]!=oldest){o->cid[k]=o->cid[j];o->x[k]=o->x[j];o->y[k]=o->y[j];k++;}o->n=k;
        }
    }
    tc_rows=ens_rw;gov_nb=ens_nb;
    int left=GOV_FREE_DET?1000:(int)((GOV_B-gov_used-(lc_active&&!lc_applied?NS_RESERVE:0))/GC_CELL);
    gov_cells=left<0?0:left>DET_BUDGET?DET_BUDGET:left;gov_ncell=0;
    detect(ens_cur);gov_ncell=ens_input->det_cells;gov_used+=gov_ncell*GC_CELL;
    if(ens_input->line_detected){edge_detect(ens_cur);gov_used+=EDGE_GCDET;}
    cur_pyr=ens_cur;m3mul(R,R_bc,Rwc_prev);
    if(ens_cloned)gov_maptries=MAP_TRY;
    gov_mapdid=0;
}

void ens_secondary_start(EnsFrame *f){ens_input=f;ens_phase=1;}
void ens_secondary_output(double *out){memcpy(out,ens_out,sizeof ens_out);}

int ens_secondary_need(void) {
    switch(ens_phase) {
    case 1:return 550000;
    case 2:return 330000;
    case 3:return 40000;
    case 4:return ens_b<ens_nb?ens_bound(15,batch[ens_b].n,D,batch[ens_b].edge+4*(ens_it!=0)):1000;
    case 5:return ens_bound(21,ens_nrows,D,0)+25000;
    case 6:return ens_bound(16,ens_k,D,0)+20000;
    case 7:return ens_bound(17,ens_k,D,upd_reuse)+10000;
    case 8:return 80000;
    case 9:return 300000;
    case 10:return 10000;
    case 11:return ens_bound(5,ns_pos,D,0)+3000;
    case 12:return 30000;
    default:return 0;
    }
}

int ens_secondary_tick(int budget) {
    int need=ens_secondary_need();if(need>budget)return 0;
    ens_frame=ens_input;
    int phase_before=ens_phase;double cost_before=ens_cost;
    ens_mark(90,ens_phase,need,ens_input->sequence);
    switch(ens_phase) {
    case 1:
        if(ens_pre(ens_input->t,ens_input->rgb,ens_input->imu,ens_input->count,ens_out)){ens_phase=0;break;}
        ens_phase=2;break;
    case 2:ens_vision_begin();ens_phase=3;break;
    case 3:ens_batch_begin();ens_phase=ens_nb?4:8;break;
    case 4:
        if(ens_b<ens_nb) {
            g_dx=ens_it?ens_dx:0;g_cur_b=ens_b;if(!g_dx)gflag[ens_b]=0;
            feature_rows(&batch[ens_b],&ens_nrows);g_dx=0;ens_b++;
        } else ens_phase=5;
        break;
    case 5:
        ens_k=ens_qr(ens_nrows);
        if(!ens_k){if(ens_it)restore_state();ens_phase=8;break;}
        for(int a=0;a<ens_k;a++) {
            double q=rbig[a];if(ens_it)for(int j=CORE;j<D;j++)q+=Hbig[a*MAXD+j]*ens_dx[j];ens_reff[a]=q;
        }
        if(ITER_MAXF>0 && ens_nb>ITER_MAXF){ens_phase=7;break;}
        if(ITER_BACK>0) {
            double rn=0;for(int a=0;a<ens_k;a++)rn+=rbig[a]*rbig[a];rn/=ens_k;
            if(ens_it==0){ens_rn0=rn;ens_k0=ens_k;
                for(int a=0;a<ens_k;a++){ens_r0[a]=ens_reff[a];memcpy(ens_H0+a*MAXD,Hbig+a*MAXD,D*sizeof(double));}}
            else if(rn>ITER_BACK*ens_rn0){restore_state();ens_k=ens_k0;
                memcpy(ens_reff,ens_r0,ens_k*sizeof(double));memcpy(Hbig,ens_H0,sizeof ens_H0);ens_phase=7;break;}
        }
        if(ens_it)restore_state();ens_phase=ens_it==ITER_UPD-1?7:6;break;
    case 6:
        if(!solve_dx(ens_reff,Hbig,ens_k,ens_noise,ens_dxn)){ens_phase=ens_it?7:8;break;}
        if(ens_it==0 && ITER_TH>0) {
            double nn=0;for(int j=0;j<D;j++)nn+=ens_dxn[j]*ens_dxn[j];
            if(sqrt(nn)<ITER_TH || (IT2_GOV&&gov_used+GC_BATCH+cur_rw*(GC_ROW+GC_IT2)>GOV_B)) {
                if(F_REUSE)upd_reuse=1;ens_phase=7;break;
            }
        }
        memcpy(ens_dx,ens_dxn,D*sizeof(double));restore_state();inject(ens_dx);
        ens_it++;ens_b=0;ens_nrows=0;ens_phase=4;break;
    case 7:update(ens_reff,Hbig,ens_k,ens_noise,INFINITY);ens_phase=8;break;
    case 8:ens_vision_end();ens_phase=9;break;
    case 9:
        if(gov_maptries>0 && GOV_B-gov_used>GC_MAP){map_relocalize(1);gov_maptries--;gov_used+=GC_MAP;gov_mapdid=1;}
        ens_phase=10;break;
    case 10:ens_choose_net();ens_net_left=ens_net_units;ens_phase=11;break;
    case 11:
        if(ens_net_left>0 && lc_active && !lc_applied && ns_pos<NS_STEPS && !(NS_DELAY && ns_pos>=16 && lc_frame<LC_K+NS_DELAY)) {
            if(ns_do(ns_pos)){ns_pos++;ens_net_left--;}else ens_phase=12;
        } else ens_phase=12;
        break;
    case 12:ens_post(ens_input->t,ens_input->rgb,ens_input->imu,ens_input->count,ens_out);ens_phase=0;break;
    }
    ens_mark(91,ens_phase,need,ens_input->sequence);
    /* Reserve the largest measured atomic job before starting it; charge its
     * work estimate afterwards so rejected features do not consume a full fit. */
    int overhead=phase_before==1?12000:phase_before==2?3000:phase_before==3?6000:
        phase_before==5?20000:phase_before==6?16000:phase_before==8?16000:phase_before==12?3000:1000;
    extern int ens_charged;
    ens_charged=(int)(ens_cost-cost_before)+overhead;
    return ens_phase?1:2;
}
