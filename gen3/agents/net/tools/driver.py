"""driver.py [workers] [--once]: stream HF viobench-stage3 TRAIN flights -> C-matched cache (learned_c/prep2 pipeline) -> delete raw zip.
Cache: agents/net/cache/train/<id>.npz ; meta: agents/net/cache/train_meta.jsonl (manifest row per cached flight). Never touches val/test splits.
Loops: re-reads manifest every 20 min, processes new train rows (quality ok)."""
import os, sys, json, time, csv
from pathlib import Path
from multiprocessing import Pool
os.environ.setdefault('HF_HOME', '/data/backups/rganapa/Sebastian/hf')
sys.path.insert(0, '/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learned_c')
sys.path.insert(0, '/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/learned')
import prep2
A = Path('/data/backups/rganapa/Sebastian/gen3/agents/net')
prep2.CACHE = A / 'cache/train'; RAW = A / 'raw'; META = A / 'cache/train_meta.jsonl'; BAD = A / 'cache/train_bad.jsonl'
REPO = 'SentientNapkin/viobench-stage3'

def manifest():
    from huggingface_hub import hf_hub_download
    p = hf_hub_download(REPO, 'manifest.csv', repo_type='dataset', force_download=True)
    return [r for r in csv.DictReader(open(p)) if r['split'] == 'train']

def one(r):
    from huggingface_hub import hf_hub_download
    t0 = time.time(); name = r['id']
    try:
        assert r['split'] == 'train' and '/train/' in r['path']
        z = Path(hf_hub_download(REPO, r['path'], repo_type='dataset', local_dir=str(RAW)))
        t1 = time.time()
        prep2.one(dict(name=name, dir=str(z.parent), role='train'))
        z.unlink()
        return r, 'ok', round(t1 - t0), round(time.time() - t1)
    except Exception as e:
        try:
            for p in RAW.rglob(name + '.zip*'): p.unlink()
        except Exception: pass
        return r, 'ERR %r' % e, 0, 0

if __name__ == '__main__':
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    prep2.CACHE.mkdir(parents=True, exist_ok=True); RAW.mkdir(exist_ok=True)
    while True:
        done = set()
        if META.exists(): done = {json.loads(l)['id'] for l in open(META)}
        bad = {}
        if BAD.exists():
            for l in open(BAD): b = json.loads(l); bad[b['id']] = bad.get(b['id'], 0) + 1
        try: rows = manifest()
        except Exception as e: print('manifest fail', e, flush=True); time.sleep(300); continue
        todo = [r for r in rows if r['id'] not in done and bad.get(r['id'], 0) < 2 and r['quality'] == 'ok']
        print(time.strftime('%H:%M'), 'train rows', len(rows), 'cached', len(done), 'todo', len(todo), flush=True)
        if todo:
            with Pool(W) as p:
                for r, st, td, tp in p.imap_unordered(one, todo):
                    if st == 'ok':
                        with open(META, 'a') as f: f.write(json.dumps(r) + '\n')
                    else:
                        with open(BAD, 'a') as f: f.write(json.dumps(dict(id=r['id'], err=st)) + '\n')
                    print(r['id'], r['roster_version'], st, 'dl', td, 'prep', tp, flush=True)
        if '--once' in sys.argv: break
        time.sleep(1200)
