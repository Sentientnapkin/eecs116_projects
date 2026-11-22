"""Preserve first completed batch, then use freed GPUs without interrupting training."""
import json,os,signal,subprocess,time
from pathlib import Path
H=Path(__file__).resolve().parent
while True:
 try:n=len(json.load(open(H/'gen/sl_rows.json')))
 except (FileNotFoundError,json.JSONDecodeError):n=0
 if n:break
 time.sleep(5)
j=json.load(open(H/'logs/jobs.json'));pid=j['generation_gpu']
try: assert os.getpgid(pid)==pid;os.killpg(pid,signal.SIGTERM)
except ProcessLookupError:pass
time.sleep(2)
with open(H/'NOTES.md','a') as f:f.write(f'- First generation batch saved ({n} flights). Restarted generator to spread remaining work across freed GPUs1–4 while respecting pilot reservations; stop after >=260 new safe flights (>=3000total), then release all GPUs for final training.\n')
subprocess.run(['python3',str(H/'launch.py'),'--venv','venv-sim','generation_multi','--','python',str(H/'gen/driver.py'),str(H/'gen/roster_c400.json'),'--workers','36','--batch','72','--prep_workers','16'],check=True)
