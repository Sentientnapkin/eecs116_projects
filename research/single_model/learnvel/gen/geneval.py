"""geneval.py ROSTER OUTDIR [workers]: unmodified native_campaign.py generate, zips kept (eval pools)."""
import json, os, subprocess, sys
R = '/data/backups/rganapa/Sebastian'; RES = R + '/eecs116_projects/research'
roster, OUT, W = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 16
os.makedirs(OUT + '/logs', exist_ok=True); g = [0, 3, 4, 5, 6, 7]; procs = []
for w in range(W):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(g[w % len(g)]), CUDAARCHS='90', HYPERLUX_CACHE_DIR='/dev/shm/sebastian-holdout/hyperlux-hl',
               VIOBENCH_CACHE='/dev/shm/sebastian-holdout/viobench-c', TMPDIR=R + '/tmp', CONTA_CACHE=R + '/gen/conta', VIOBENCH_SPOOL=R + '/gen/spool',
               XDG_CACHE_HOME=R + '/gen/xdg', HF_HOME=R + '/hf', PATH=R + '/venv-sim/bin:/usr/local/cuda/bin:' + os.environ['PATH'])
    procs.append(subprocess.Popen([R + '/venv-sim/bin/python', 'native_campaign.py', 'generate', '--gen-roster', os.path.abspath(roster), '--gen-raw', OUT, '--worker', str(w), '--workers', str(W)],
                                  cwd=RES, env=env, stdout=open(f'{OUT}/logs/worker{w}.log', 'a'), stderr=subprocess.STDOUT))
for p in procs: p.wait()
print('done')
