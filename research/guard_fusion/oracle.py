"""Hindsight bounds only. These use truth scores and are never deployable guests."""
import argparse
from itertools import combinations
import json
from pathlib import Path
import numpy as np
from .evaluate import summary
from .guards import SOURCE_NAMES


def compute(rows):
    single=np.array([[r['singles'][s] for s in SOURCE_NAMES] for r in rows])
    result={'status':'bound, not a guest','metric':'mean_unaligned_ate_m',
        'singles':{s:summary(single[:,i]) for i,s in enumerate(SOURCE_NAMES)},
        'oracle3':summary(single.min(1)),
        'best_source_counts':{s:int(np.sum(single.argmin(1)==i)) for i,s in enumerate(SOURCE_NAMES)},
        'pairs':{},'all_above_3m':[]}
    for i,j in combinations(range(3),2):
        result['pairs'][SOURCE_NAMES[i]+'+'+SOURCE_NAMES[j]]=summary(np.minimum(single[:,i],single[:,j]))
    for r,a in zip(rows,single):
        if np.all(a>3):
            result['all_above_3m'].append({'episode':r['episode'],'ates':dict(zip(SOURCE_NAMES,a.tolist()))})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rows',type=Path,default=Path('research/results/eval/guard-fusion/rows-s217.json'))
    p.add_argument('--out',type=Path,default=Path('research/results/eval/guard-fusion/oracle.json'))
    args=p.parse_args()
    report=compute(json.loads(args.rows.read_text())['rows'])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('singles','all_above_3m')},indent=2))

if __name__=='__main__':
    main()
