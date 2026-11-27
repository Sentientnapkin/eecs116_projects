"""Detached, resumable plan runner (nohup setsid). Stages: A screens -> B auto-replicates (+v1val) -> C summary.
Every eval is skipped if evals/an_NAME__POOL.json exists. results.tsv gets one rep.py line per eval / rep-mean; logs/stage_X.done markers."""
import subprocess,os,time,re,json
D='/data/backups/rganapa/Sebastian/gen3/agents/anchors';G='/data/backups/rganapa/Sebastian/gen3';os.chdir(D)
V='/data/backups/rganapa/Sebastian/venv-teacher/bin/python'
Z='PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0'
ACE='MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=4.0 AN_CEF=6';SN='SN=1 NS_GCOST=1'
def log(m): open('logs/autopilot.log','a').write(time.strftime('%H:%M:%S ')+m+'\n')
def defs(n):
    f=f'builds/{n}/flags.txt'
    return open(f).read().strip() if os.path.exists(f) else None
def run(n,pool,d=None,src=None):
    out=f'{G}/evals/an_{n}__{pool}.json'
    if os.path.exists(out): return
    if not os.path.exists(f'builds/{n}/solution.wasm'):
        full=Z+' '+d if d is not None else None
        src=src or ('base_sn.c' if 'SN=1' in full else 'base.c')
        p=subprocess.run(['python3','mk.py',n,full,src],capture_output=True,text=True)
        if p.returncode: log(f'BUILD FAIL {n}: {p.stdout[-300:]}{p.stderr[-300:]}');return
    while float(open('/proc/loadavg').read().split()[0])>170: time.sleep(60)
    for t in (1,2):
        with open(f'logs/{n}__{pool}.log','w') as lg:
            r=subprocess.run([V,'-B','evalpool.py',f'an_{n}',f'agents/anchors/builds/{n}/solution.wasm',f'agents/anchors/pools/{pool}','14'],cwd=G,stdout=lg,stderr=subprocess.STDOUT)
        if r.returncode==0: break
    log(f'done {n} {pool}');score(n,pool)
def score(spec,pool):
    p=subprocess.run([V,'rep.py',f'--pool={pool}',spec],capture_output=True,text=True)
    line=p.stdout.strip()
    if line: open('results.tsv','a').write(pool+'\t'+line+'\n')
    return line
def parse(line):
    m=re.search(r'd ([+-][0-9.]+) .*peak ([0-9.]+)M.*area ([+-][0-9.]+)',line);return (float(m.group(1)),float(m.group(2)),float(m.group(3))) if m else (9,9,-9)
def rep3(n):
    d=defs(n).replace(Z,'').strip()
    run(n+'_r1','v3val',d+' PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0');run(n+'_r2','v3val',d+' PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0')
    run(n,'v1val');s=score(f'{n}+{n}_r1+{n}_r2','v3val');open('NOTES.md','a').write(f'- AUTO 3rep {n}: {s}\n- AUTO v1val {n}: {score(n,"v1val")}\n')
    return s
# ---- stage A: screens (single v3val runs)
A=[('snace6g33',f'{SN} {ACE} GOV_B=3.3e6'),('snace6g30',f'{SN} {ACE} GOV_B=3.0e6'),('snace6g27',f'{SN} {ACE} GOV_B=2.7e6'),
   ('snace6d3',f'{SN} MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=3.0 AN_CEF=6'),('snace6d6',f'{SN} MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=6.0 AN_CEF=6'),
   ('snace6mc7',f'{SN} MAX_CLONES=7 MAX_OBS=10 AN_ACE=1 AN_DTH=4.0 AN_CEF=6'),
   ('ace6e1',f'{ACE} EDGE=1 EDGE_MYTH=10.0'),('snace6e1',f'{SN} {ACE} EDGE=1 EDGE_MYTH=10.0'),
   ('ace6p1b2',f'{ACE} LV_PERIOD=1 TC_GAP=0 AN_NETB=2e6'),('ace6ps2',f'{ACE} LV_PSCALE=2.0')]
if not os.path.exists('logs/stage_A.done'):
    for n,d in A: run(n,'v3val',d)
    open('logs/stage_A.done','w').write('ok\n');open('NOTES.md','a').write('- AUTO stage A (screens) done, lines in results.tsv\n')
# ---- stage B: replicate ace6 + snace6 always, plus stage-A runs with d < -0.02 and single-run area > snace6's (+0.215) - best 3 by area
if not os.path.exists('logs/stage_B.done'):
    cand=[]
    for n,_ in A:
        if os.path.exists(f'{G}/evals/an_{n}__v3val.json'):
            dd,pk,ar=parse(score(n,'v3val'))
            if dd<-0.02 and ar>0.215: cand.append((ar,n))
    todo=['snace6','ace6']+[n for _,n in sorted(cand,reverse=True)[:3]]
    log('stage B replicate '+' '.join(todo))
    for n in todo: rep3(n)
    open('logs/stage_B.done','w').write(' '.join(todo)+'\n')
open('logs/autopilot.done','w').write('ok\n');log('ALL DONE')
