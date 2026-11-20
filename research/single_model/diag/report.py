import sys, json
sys.argv=['x','diag_counters1']
exec(open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/diag/stats.py').read())
EF=json.loads((ROOT/'research/results/single_model/diag_counters1/early_frames.json').read_text())
for r in rows:
    r.update(EF[r['ep']])
    r['att_rate_2s']=r['trifail_2s']/max(r['att_2s'],1)
    r['gate_rate_2s']=r['gaterej_2s']/max(r['att_2s']-r['trifail_2s'],1)
    r['succ_5s']=r['used_5s']/max(r['att_5s'],1)
    r['speed_p50']=r['speed_p10_p50_p90'][1]
def auc(x,y):  # P(x_bad > x_good)
    x=np.asarray(x,float); y=np.asarray(y,bool)
    ok=np.isfinite(x); x=x[ok]; y=y[ok]
    r=np.argsort(np.argsort(x))+1.
    n1=y.sum(); n0=(~y).sum()
    return (r[y].sum()-n1*(n1+1)/2)/(n1*n0)
def best_thr(x,y):
    x=np.asarray(x,float); y=np.asarray(y,bool); best=(0,None,None)
    for t in np.unique(x[np.isfinite(x)]):
        for sg in (1,-1):
            pred=(sg*x>=sg*t); acc=((pred==y).mean())
            if acc>best[0]: best=(acc,t,sg)
    return best
import math
def run(sl, lab_thr=3.0):
    S=sel(sl); ates=col(S,'ate'); bad=ates>lab_thr
    print(f"\n=== {sl} mid  n={len(S)}  bad(ATE>{lab_thr})={bad.sum()}  mean ATE good {ates[~bad].mean():.2f} bad {ates[bad].mean():.2f}")
    feats=['true_tilt0','v0_true','w0_true','tilt_err0','Pv0','dark_fraction','flat_fraction','dark2','flat2','std2','mean2','std_min','mean_min','speed_p50','hover_fraction','turning_fraction',
           'first_msckf_frame','live_mean_1s','live3_mean_1s','live3_mean_2s','att_2s','used_2s','trifail_2s','att_rate_2s','gate_rate_2s','zupt_2s','dvprior_2s','dvvis_2s','used_5s','succ_5s','baerr_2s']
    res=[]
    for k in feats:
        x=col(S,k)
        a=auc(x,bad); acc,t,sg=best_thr(x,bad)
        res.append((abs(a-.5),k,a,np.nanmean(x[~bad]),np.nanmean(x[bad]),acc,t,sg))
    for _,k,a,g,b,acc,t,sg in sorted(res,reverse=True):
        print(f"{k:18s} AUC {a:.2f} good {g:8.3f} bad {b:8.3f}  best thr {'>=' if sg>0 else '<='}{t:.3f} acc {acc:.2f}")
    return S,bad
S,bad=run('search'); 
Sv,badv=run('val')
# error decomposition on search mid, by class
def dec(S,bad,T):
    print(f"\n-- position error decomposition at {T}s, search mid (signed projections on actual error dir, m)")
    for lab,m in (('all',np.ones(len(S),bool)),('good',~bad),('bad',bad)):
        out=[]
        for k in ('act','proj_v0','proj_tilt','proj_bias','proj_corr'):
            kk=f'ep_{k}_{T}s' if k!='act' else f'ep_act_{T}s'
            out.append(np.nanmean(col(S,kk)[m]))
        nrm=[np.nanmean(col(S,f'ep_norm_{k}_{T}s')[m]) for k in ('v0','tilt','bias','corr')]
        print(f"{lab:5s} |err| {out[0]:.2f} = v0 {out[1]:+.2f} + tilt {out[2]:+.2f} + bias {out[3]:+.2f} + corr {out[4]:+.2f}   (norms v0 {nrm[0]:.2f} tilt {nrm[1]:.2f} bias {nrm[2]:.2f} corr {nrm[3]:.2f})")
for T in (1,2,5): dec(S,bad,T)
for T in (2,5): dec(Sv,badv,T)
# time course of velocity error and tilt
print('\n-- time course (search mid) mean over flights')
for lab,m in (('good',~bad),('bad',bad)):
    print(lab, 'verr', [round(float(np.nanmean(col(S,f'verr_{t}s')[m])),2) for t in (1,2,5,10)], 'tilt err deg',[round(float(np.nanmean(col(S,f'tilt_err_{t}s')[m])),1) for t in (0,)]+[round(float(np.nanmean(col(S,f'tilt_err_{t}s')[m])),1) for t in (1,2,5,10)],
          'ba err',[round(float(np.nanmean(col(S,f'baerr_{t}s')[m])),3) for t in (1,2,5,10)], 'speed_true',[round(float(np.nanmean(col(S,f'speed_true_{t}s')[m])),2) for t in (1,2,5,10)], 'speed_est',[round(float(np.nanmean(col(S,f'speed_est_{t}s')[m])),2) for t in (1,2,5,10)])
# direction vs magnitude of initial vel error: filter starts ~0 so error = true v0
print('\n-- initial velocity: est speed mean', np.nanmean(col(S,'v0_est')).round(3), ' true speed', np.nanmean(col(S,'v0_true')).round(3), ' err/true', np.nanmean(col(S,'v0_err')/col(S,'v0_true')).round(3))
# static for reference
St=sel('search','static'); print('static search: v0_true',np.nanmean(col(St,'v0_true')).round(3),'true_tilt0',np.nanmean(col(St,'true_tilt0')).round(2),'tilt_err0',np.nanmean(col(St,'tilt_err0')).round(2),'tilt_err2s',np.nanmean(col(St,'tilt_err_2s')).round(2),'verr2s',np.nanmean(col(St,'verr_2s')).round(2),'used_5s',np.nanmean(col(St,'used_5s')).round(1),'first_msckf',np.nanmean(col(St,'first_msckf_frame')).round(1))
# correlation between true tilt0 and err at 2s within good/all
for k in ('true_tilt0','v0_true','w0_true'):
    for t in ('verr_2s','tilt_err_2s','ep_act_2s','ep_act_5s','ate'):
        print(k,t,'corr',np.round(np.corrcoef(np.nan_to_num(col(S,k)),np.nan_to_num(col(S,t)))[0,1],2),end=' | ')
    print()
print('\n--- per-flight (search mid) sorted by ATE')
print('ate  tilt0 v0 w0 | flat5 dark5 mean5 | live3_2 att2 tri2 gate2 used2 | att5 used5 | tilt2 tilt5 | verr2 verr5 | firstM')
for r in sorted(S,key=lambda r:-r['ate']):
    print(f"{r['ate']:5.1f} {r['true_tilt0']:5.1f} {r['v0_true']:4.2f} {r['w0_true']:4.2f} | {r['flat5']:.2f} {r['dark5']:.2f} {r['mean5']:5.0f} | {r['live3_mean_2s']:4.1f} {r['att_2s']:3d} {r['trifail_2s']:3d} {r['gaterej_2s']:3d} {r['used_2s']:3d} | {r['att_5s']:3d} {r['used_5s']:3d} | {r.get('tilt_err_2s',np.nan):4.1f} {r.get('tilt_err_5s',np.nan):4.1f} | {r.get('verr_2s',np.nan):4.2f} {r.get('verr_5s',np.nan):4.2f} | {r['first_msckf_frame']}")
