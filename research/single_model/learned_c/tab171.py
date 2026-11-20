"""Per-flight table of a run_variant run on the 171 (fold 4 flights are dropped here, never printed): tables/s171_<name>.json"""
import json, sys
from pathlib import Path
R = Path('research/results/single_model')
name = sys.argv[1]
f = json.load(open('research/single_model/learned_c/feats.json'))
sc = sorted((R / name / 'eval').glob('*/scores.json'))[0]
rows = [dict(episode=r['episode'], ate=r.get('ate_full'), peak_fuel=r.get('peak_fuel_per_frame'), filled=r.get('filled_full')) for r in json.load(open(sc))['rows'] if r['episode'] in f]
Path('research/single_model/learned_c/tables').mkdir(exist_ok=True)
json.dump(rows, open(f'research/single_model/learned_c/tables/s171_{name}.json', 'w')); print(name, len(rows))
