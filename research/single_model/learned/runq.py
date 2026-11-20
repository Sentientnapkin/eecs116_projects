"""Run a job list across GPUs 1-6: python runq.py jobs.txt  (one train.py arg string per line, with --name)."""
import subprocess, sys, os, threading, queue
PY = '/data/backups/rganapa/Sebastian/venv-teacher/bin/python'
jobs = [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith('#')]
q = queue.Queue(); [q.put(j) for j in jobs]
gpus = [int(x) for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else '1,2,3,4,5,6'.split(','))]
assert 0 not in gpus
def work(g):
    while True:
        try: j = q.get_nowait()
        except queue.Empty: return
        name = j.split('--name')[1].split()[0]
        if os.path.exists(f'runs/{name}/result.json'): continue
        os.makedirs('logs', exist_ok=True)
        with open(f'logs/{name}.log', 'w') as f:
            subprocess.run(f'CUDA_VISIBLE_DEVICES={g} OMP_NUM_THREADS=4 {PY} -B train.py {j}', shell=True, stdout=f, stderr=subprocess.STDOUT)
ts = [threading.Thread(target=work, args=(g,)) for g in gpus]; [t.start() for t in ts]; [t.join() for t in ts]
