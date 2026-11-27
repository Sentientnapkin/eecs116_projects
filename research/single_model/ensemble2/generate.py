"""Generate an isolated shared-front-end experiment from the frozen submission.

The submitted file is never edited. Each transformation is anchored and asserted.
Generated C is reviewable; the secondary keeps independent observations, covariance,
map, priors and network state. The front end follows the primary's predictions.
"""
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'linejac/final/gslv_linejac_arith.c'
ABI=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native/viobench_abi.h')

def spans(s,name):
    # Lex strings/comments so braces in comments cannot truncate a function.
    pat=rf'^(?:static )?(?:inline )?(?:int32_t|int|void|double)\s+{name}\([^\n]*\)\s*\{{'
    for m in list(re.finditer(pat,s,re.M)):
        start=s.index('{',m.start(),m.end()); depth=1; end=start+1
        token=re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]',re.S)
        for t in token.finditer(s,start+1):
            if t.group()=='{':depth+=1
            elif t.group()=='}':depth-=1
            if depth==0:end=t.end();break
        assert depth==0,name
        yield m.start(),start,end

def change(s,name,fn):
    for a,b,c in reversed(list(spans(s,name))):s=s[:a]+fn(s[a:b],s[b+1:c-1])+s[c:]
    return s

def repl(s,a,b,n=1):
    assert s.count(a)>=n,(a,s.count(a));return s.replace(a,b,n)

def instrument(s):
    # Work units are calibrated against Wasmtime fuel, never wall-clock time.
    jobs={
      'propagate':(1,'D','0','0'), 'propagate_cov':(2,'D','0','0'),
      'imu_measurements':(3,'D','0','0'), 'lc_step':(4,'lc_frame','0','0'),
      'ns_do':(5,'k','D','0'), 'build_pyramid':(6,'0','0','0'),
      'track_all':(7,'0','0','0'), 'line_track_all':(8,'line_alive()','0','0'),
      'detect':(9,'0','0','0'), 'line_detect':(10,'0','0','0'),
      'add_clone':(11,'D','0','0'), 'record_observations':(12,'0','0','0'),
      'line_record':(13,'0','0','0'), 'vision_zupt':(14,'D','0','0'),
      'feature_rows':(15,'o_in->n','D','o_in->edge+4*(g_dx!=0)'),
      'solve_dx':(16,'k','D','0'), 'update':(17,'k','D','upd_reuse'),
      'map_relocalize':(18,'D','0','0'), 'remove_oldest_clone':(19,'D','0','0'),
      'hz_watch':(20,'D','0','0'), 'ens_qr':(21,'nrows','D','0'),
    }
    # Cleanup attributes cover early returns and allow profiling nested updates.
    for name,(j,a,b,c) in jobs.items():
        def wrap(head,body,j=j,a=a,b=b,c=c):
            return head+'{\n    int ens_scope __attribute__((cleanup(ens_scope_end))) = ens_scope_begin('+f'{j},{a},{b},{c}'+');\n'+body+'}'
        s=change(s,name,wrap)
    return s

def primary(s):
    # Snapshot physical track fields without copying a filter's observation history.
    s=repl(s,'static void line_track_all(int cur, const double *Rrel) {',
      (HERE/'front.h').read_text()+'\nstatic void line_track_all(int cur, const double *Rrel) {')
    s=change(s,'build_pyramid',lambda h,b:h+'{'+b+'\nens_copy(ens_frame->pyramid[0],pyr[which][0],IMG_W*IMG_H);ens_copy(ens_frame->pyramid[1],pyr[which][1],IMG_W*IMG_H/4);\n}')
    s=change(s,'track_all',lambda h,b:h+'{'+b+'\nens_capture_points(); ens_frame->tracked=1; ens_frame->klt_calls=gov_klt_cnt;ens_meter_args(gov_klt_cnt,0,0);\n}')
    s=change(s,'line_track_all',lambda h,b:h+'{'+b+'\nens_capture_lines(); ens_frame->line_tracked=1;\n}')
    s=repl(s,'t->alive = 1; t->x = bx; t->y = by; t->obs.n = 0; t->fx_ = t->fy_ = 0;',
      't->alive = 1; t->x = bx; t->y = by; t->obs.n = 0; t->fx_ = t->fy_ = 0;\nens_frame->point_new[t-tracks]=1; ens_frame->born[t-tracks]=ens_point(t);')
    s=repl(s,'lines[slot] = T; done = 1;',
      'lines[slot] = T; done = 1; ens_frame->line_new[slot]=1; ens_frame->line_born[slot]=ens_line(&T);')
    s=change(s,'detect',lambda h,b:h+'{'+b+'\nens_frame->det_cells=gov_ncell;ens_meter_args(gov_ncell,0,0);\n}')
    s=change(s,'line_detect',lambda h,b:h+'{ens_frame->line_detected=1;\n'+b+'}')
    return s

def secondary(s):
    s=repl(s,'static void line_track_all(int cur, const double *Rrel) {',
      (HERE/'front.h').read_text()+'\nstatic void line_track_all(int cur, const double *Rrel) {')
    s=change(s,'build_pyramid',lambda h,b:h+'{ens_copy(pyr[which][0],ens_frame->pyramid[0],IMG_W*IMG_H);ens_copy(pyr[which][1],ens_frame->pyramid[1],IMG_W*IMG_H/4);}')
    s=change(s,'track_all',lambda h,b:h+'{ens_replay_points();}')
    s=change(s,'line_track_all',lambda h,b:h+'{ens_replay_lines();}')
    s=change(s,'detect',lambda h,b:h+'{ens_replay_point_births();}')
    s=change(s,'line_detect',lambda h,b:h+'{ens_replay_line_births();}')
    s=change(s,'init',lambda h,b:h+'{upd_reuse=0;g_dx=0;\n'+b+'}')
    # Keep the original initialization/pre-propagation and post-step guard code.
    a,b,c=next(spans(s,'step'));body=s[b+1:c-1]
    pre,post=body.split('    tc_rows = 0;\n    vision(frame);',1)
    pre=pre.replace('return VIOBENCH_STATUS_OK;', 'return 1;')
    pre+='\n    tc_rows=0; return 0;\n'
    post=repl(post,'for (int u = 0; u < units && lc_active && !lc_applied && ns_pos < NS_STEPS; u++) { if (NS_DELAY && ns_pos >= 16 && lc_frame < LC_K + NS_DELAY) break; if (!ns_do(ns_pos)) break; ns_pos++; }',
      'ens_net_units=units;')
    # Separate choosing units (governor side effects) from executing them.
    split='    if (0)\n#endif\n'
    net,tail=post.split(split,1)
    s=s[:a]+s[c:]
    s+='\nstatic int ens_net_units; static double ens_out[13];\n'
    s+='static int ens_pre(double t,const uint8_t *frame,const double *imu,int32_t imu_count,double *out) {'+pre+'}\n'
    s+='static void ens_choose_net(void) {'+net+'\n    (void)0;\n#endif\n}\n'
    s+='static int ens_post(double t,const uint8_t *frame,const double *imu,int32_t imu_count,double *out) {\n    if(0)\n'+tail+'}\n'
    s+='\n'+(HERE/'secondary.h').read_text()
    return s

def main():
    s=BASE.read_text()
    # Extract the batch QR so it is an explicit schedulable job.
    a,b,c=next(spans(s,'build_rows')); body=s[b+1:c-1]
    split=body.index('    if (nrows > tc_rows)')
    qr='static int ens_qr(int nrows) {\n'+body[split:]+'}\n'
    s=s[:a]+qr+s[a:b+1]+body[:split]+'    return ens_qr(nrows);\n}'+s[c:]
    s=s.replace('#include "viobench_abi.h"','#include "abi_private.h"\n#include "common.h"\n#include "meter.h"')
    assert 'common.h' in s
    private=ABI.read_text().replace('__attribute__((export_name(#name)))','')
    (HERE/'abi_private.h').write_text(private)
    for role,fn in [('primary',primary),('secondary',secondary)]:
        out=fn(s)
        out=instrument(out)
        # Both translation units are private; wrapper.c owns the public ABI.
        for name in ('init','step','alloc','abi_version','frame_width'):
            out=re.sub(r'\b'+name+r'\b','ens_'+role+'_'+name,out)
        if role=='secondary':out='#define PIXEL_STD ENS2_PIXEL\n'+out
        (HERE/(role+'.c')).write_text(out)

if __name__=='__main__':main()
