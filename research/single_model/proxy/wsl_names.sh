cd /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/research/single_model/proxy
~/.venv/bin/python -c "
import json
from viobench.tools.datasets.generate.simulation import hssd_scenes
v=hssd_scenes('val'); json.dump(sorted(v), open('hssd_val.json','w')); print(len(v))
from viobench.tools.datasets import episode
import inspect; src=inspect.getsource(episode); i=src.find('ground_truth'); print(src[i-200:i+600])
"
