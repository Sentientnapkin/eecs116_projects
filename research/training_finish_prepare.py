"""Annotate the isolated runtime-repaired input dataset before training identity is frozen."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=ROOT/'results/loop/training-finish/kf_grid_native/n2/manifest.json'
d=json.loads(p.read_text())
d['runtime_repair']='Reject OpenCV essential/recoverPose cv2.error as unavailable visual measurement; original aborted.'
d['sources']['attitude_bias.py']=hashlib.sha256((ROOT/'attitude_bias.py').read_bytes()).hexdigest()
p.write_text(json.dumps(d,indent=1)+'\n')
print(hashlib.sha256(p.read_bytes()).hexdigest())
