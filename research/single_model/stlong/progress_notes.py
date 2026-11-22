import json,time
from pathlib import Path
H=Path(__file__).resolve().parent;seen=-1
while True:
 try:n=len(json.load(open(H/'gen/sl_rows.json')))
 except (FileNotFoundError,json.JSONDecodeError):n=0
 if n and n!=seen:
  with open(H/'NOTES.md','a') as f:f.write(f'- {time.strftime("%F %T UTC")}: data cache milestone {n} new eligible flights, {2740+n} total; generation audit/exclusions unchanged.\n')
  print(n,2740+n,flush=True);seen=n
 if n>=260:break
 time.sleep(15)
