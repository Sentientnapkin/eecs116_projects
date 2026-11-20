"""Batched, resumable generation driver for the holdout set (runs native_campaign.py generate unmodified).
python gen_driver.py ROSTER.json [--workers 24] [--batch 120]
Before each batch: picks GPUs (7 + any of 1-6 with util<20% and <20 GB used; GPU 0 never), waits while load > 150.
Already generated flights (zip present in gen/raw-holdout/bench) are skipped, so a crash/restart resumes.
"""
import argparse, json, os, subprocess, sys, time
R = '/data/backups/rganapa/Sebastian'; RES = R + '/eecs116_projects/research'; OUT = R + '/gen/raw-holdout'
LOG = OUT + '/logs/driver.log'

def log(m):
    with open(LOG, 'a') as f: f.write(time.strftime('%F %T ') + m + '\n')
    print(m, flush=True)

def gpus():
    q = subprocess.run(['nvidia-smi', '--query-gpu=index,utilization.gpu,memory.used', '--format=csv,noheader,nounits'], capture_output=True, text=True).stdout
    ok = [7]
    for line in q.strip().splitlines():
        i, u, m = [int(x) for x in line.split(',')]
        if 1 <= i <= 6 and u < 20 and m < 20000: ok.append(i)
    return sorted(set(ok))

def load():
    return float(open('/proc/loadavg').read().split()[0])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('roster'); ap.add_argument('--workers', type=int, default=24); ap.add_argument('--batch', type=int, default=120)
    a = ap.parse_args()
    roster = json.load(open(a.roster))['flights']
    for attempt in range(3):
        todo = [f for f in roster if not os.path.exists(f"{OUT}/bench/{f['id']}.zip")]
        log(f'{a.roster}: attempt {attempt} todo {len(todo)}/{len(roster)}')
        if not todo: break
        for b in range(0, len(todo), a.batch):
            chunk = todo[b:b + a.batch]
            while load() > 150:
                log(f'load {load():.0f} > 150, sleeping'); time.sleep(120)
            g = gpus(); log(f'batch {b // a.batch}: {len(chunk)} flights on GPUs {g}')
            path = f'{OUT}/cfg/batch_current.json'; json.dump({'flights': chunk}, open(path, 'w'))
            procs = []
            for w in range(a.workers):
                env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(g[w % len(g)]), CUDAARCHS='90', HYPERLUX_CACHE_DIR='/dev/shm/sebastian-holdout/hyperlux-hl',
                           VIOBENCH_CACHE='/dev/shm/sebastian-holdout/viobench-c', TMPDIR=R + '/tmp', CONTA_CACHE=R + '/gen/conta', VIOBENCH_SPOOL=R + '/gen/spool',
                           XDG_CACHE_HOME=R + '/gen/xdg', HF_HOME=R + '/hf', PATH=R + '/venv-sim/bin:/usr/local/cuda/bin:' + os.environ['PATH'])
                cmd = [R + '/venv-sim/bin/python', 'native_campaign.py', 'generate', '--gen-roster', path, '--gen-raw', OUT, '--worker', str(w), '--workers', str(a.workers)]
                procs.append(subprocess.Popen(cmd, cwd=RES, env=env, stdout=open(f'{OUT}/logs/worker{w}.log', 'a'), stderr=subprocess.STDOUT))
            for p in procs: p.wait()
            done = sum(os.path.exists(f"{OUT}/bench/{f['id']}.zip") for f in roster)
            log(f'batch {b // a.batch} finished; {done}/{len(roster)} zips present')
    left = [f['id'] for f in roster if not os.path.exists(f"{OUT}/bench/{f['id']}.zip")]
    log(f'DONE {a.roster}; failed/unavailable: {len(left)} {left[:10]}')
main()
