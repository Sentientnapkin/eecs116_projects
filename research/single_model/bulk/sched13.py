import os, subprocess, time
os.chdir('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/bulk')
running = {}
def load(): return float(open('/proc/loadavg').read().split()[0])
while True:
    for n, p in list(running.items()):
        if p.poll() is not None: del running[n]
    jobs = [l.strip() for l in open('jobs13.txt') if l.strip() and not l.startswith('#')]
    pending = [j for j in jobs if not os.path.exists('logs/' + j.split('|')[0] + '.171.txt')]
    if os.path.exists('STOPSCHED'): break
    # count externally running ev.sh too
    ext = int(subprocess.run("ps -eo args | grep -c '[.]/ev13.sh'", shell=True, capture_output=True, text=True).stdout.strip() or 0)
    if pending and ext < 2 and load() < 150:
        parts = (pending[0].split('|') + ['', ''])[:3]
        n, d, sr = parts
        running[n] = subprocess.Popen(['./ev13.sh', n, d] + ([sr] if sr else []))
        time.sleep(20)
    else:
        time.sleep(15)
