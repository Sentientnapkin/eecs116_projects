/* Included after Track and LineT definitions, in each private translation unit. */
_Static_assert(MAX_TRACKS==60 && EDGE_N==32 && EDGE_LS==3 && LEVELS==2,"snapshot layout");
static EnsPoint ens_point(const Track *t) {
    return (EnsPoint){t->alive,t->x,t->y,t->fx_,t->fy_};
}
static EnsLine ens_line(const LineT *l) {
    EnsLine v; memcpy(&v,l,sizeof v); return v;
}
_Static_assert(sizeof(EnsLine)==__builtin_offsetof(LineT,obs),"line prefix");
static void ens_capture_points(void) {
    for(int i=0;i<MAX_TRACKS;i++) ens_frame->points[i]=ens_point(&tracks[i]);
}
static void ens_capture_lines(void) {
    for(int i=0;i<EDGE_N;i++) ens_frame->lines[i]=ens_line(&lines[i]);
}
static void ens_replay_points(void) {
    for(int i=0;i<MAX_TRACKS;i++) {
        Track *t=&tracks[i]; const EnsPoint *v=&ens_frame->points[i];
        if(t->alive && !v->alive && t->obs.n>=min_obs && nlost<2*MAX_TRACKS) {
            lost[nlost]=t->obs; lost[nlost++].tid=-1;
        }
        t->alive=v->alive;t->x=v->x;t->y=v->y;t->fx_=v->dx;t->fy_=v->dy;
    }
}
static void ens_replay_lines(void) {
    for(int i=0;i<EDGE_N;i++) {
        if(lines[i].alive && !ens_frame->lines[i].alive) line_kill(&lines[i]);
        memcpy(&lines[i],&ens_frame->lines[i],sizeof(EnsLine));
    }
}
static void ens_replay_point_births(void) {
    for(int i=0;i<MAX_TRACKS;i++) if(ens_frame->point_new[i]) {
        Track *t=&tracks[i]; const EnsPoint *v=&ens_frame->born[i];
        t->alive=v->alive;t->x=v->x;t->y=v->y;t->fx_=v->dx;t->fy_=v->dy;t->obs.n=0;
    }
}
static void ens_replay_line_births(void) {
    for(int i=0;i<EDGE_N;i++) if(ens_frame->line_new[i]) {
        memset(&lines[i],0,sizeof lines[i]);
        memcpy(&lines[i],&ens_frame->line_born[i],sizeof(EnsLine));
        lines[i].obs.edge=2;lines[i].obs.tid=-1;
    }
}
