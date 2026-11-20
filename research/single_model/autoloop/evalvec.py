"""Evaluate one parameter vector (separate process, so env such as PNG cache is per job).
  python -m research.single_model.autoloop.evalvec JOB.json     JOB = {hash, vec, stage: search|freshA|freshB, reps, workers, keep}
Writes results/<hash>.<stage>.json containing VISIBLE selected flights only (folds 0-3) or the fresh split rows. Fold 4 rows are dropped
before anything is stored or printed; run_variant.report() (which writes sealed_aggregate.json) is never called."""
import hashlib, json, os, shutil, sys, time
from pathlib import Path

from research.single_model import run_variant as RV
from research.single_model.autoloop import params as P

HERE = Path(__file__).resolve().parent
RES = HERE / 'results'; POOLS = HERE / 'pools'
NUDGES = [1.0, 1.01, 0.99]                          # replicate r0 = the vector itself; r1/r2 nudge PIXEL_STD and DETECT_MIN_SCORE by +-1 %


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pool(stage):
    d = POOLS / stage
    if not d.exists():
        d.mkdir(parents=True)
        cats = json.loads((HERE / 'categories.json').read_text())
        sp = stage[-1]
        for e in cats['fresh_cats'][sp]['all']:
            os.symlink(os.path.realpath(f'/data/backups/rganapa/Sebastian/tmp/fresh_pool/{e}.zip'), d / f'{e}.zip')
    return d


def run_one(name, text, workers, episodes):
    out = RV.OUT / name; out.mkdir(parents=True, exist_ok=True)
    (out / 'in.c').write_text(text)
    wasm = RV.build(out / 'in.c', RV.CMAKE_DEFAULT, '', name)
    sc = RV.run_guest_fast(wasm, episodes, out / 'eval', workers=workers, name=name)
    return wasm, json.loads(Path(sc).read_text())['rows'], sc


def main():
    job = json.loads(Path(sys.argv[1]).read_text())
    if job['stage'] != 'search':
        os.environ['VIOBENCH_PNG_CACHE'] = '0'      # fresh pool: PNG cache off, as fresh/run_fresh.py
    h = job['hash']; vec = job['vec']; stage = job['stage']; t0 = time.time()
    RES.mkdir(exist_ok=True)
    cats = json.loads((HERE / 'categories.json').read_text())
    res = dict(hash=h, stage=stage, vec=P.norm(vec), flights={}, fuel={}, p95={}, med={}, errors=[], wasm_size=[], wasm_sha=[], src_sha=[])
    if stage == 'search':
        keep = set(cats['visible']); reps = job['reps']; episodes = RV.EPISODES
    else:
        keep = set(cats['fresh_cats'][stage[-1]]['all']); reps = 1; episodes = pool(stage)
    for i in range(reps):
        name = f'loop_{h}_r{i}' if stage == 'search' else f'loop_{h}_{stage}'
        text = P.render(vec, NUDGES[i])
        res['src_sha'].append(hashlib.sha256(text.encode()).hexdigest())
        try:
            wasm, rows, sc = run_one(name, text, job.get('workers', 24), episodes)
        except SystemExit as e:
            res['errors'].append(f'build/run failed r{i}: {str(e)[-300:]}'); break
        res['wasm_sha'].append(sha(wasm)); res['wasm_size'].append(Path(wasm).stat().st_size)
        for r in rows:
            e = r['episode']
            if e not in keep: continue                      # drops fold-4 (sealed) rows before anything is kept
            ok = r.get('ate_full') is not None and not r.get('error') and r.get('completed') and not r.get('filled_full')
            if not ok: res['errors'].append(f'{e} r{i}: invalid row'); ate = 50.0
            else: ate = float(r['ate_full'])
            res['flights'].setdefault(e, []).append(ate)
            res['fuel'].setdefault(e, []).append(r.get('peak_fuel_per_frame'))
            res['p95'].setdefault(e, []).append(r.get('p95_fuel_per_frame'))
            res['med'].setdefault(e, []).append(r.get('median_fuel_per_frame'))
        if stage == 'search' and i == 0 and h == job.get('ref_hash'):
            pass
        if not (stage == 'search' and i == 0 and job.get('keep')):
            shutil.rmtree(RV.OUT / name / 'eval', ignore_errors=True)
            if i > 0 or stage != 'search': shutil.rmtree(RV.OUT / name, ignore_errors=True)
        # drop the evaluator's per-digest compile cache (not for the reference wasm, others may use it)
        if res['wasm_sha'][-1] != P.GATE_WASM_SHA:
            shutil.rmtree(Path('/dev/shm/sebastian-vio/guard-cache') / res['wasm_sha'][-1], ignore_errors=True)
    res['wall_s'] = time.time() - t0; res['finished'] = time.time()
    tmp = RES / f'{h}.{stage}.json.tmp'; tmp.write_text(json.dumps(res)); tmp.replace(RES / f'{h}.{stage}.json')
    print('done', h, stage, f'{res["wall_s"]:.0f}s errors={len(res["errors"])}', flush=True)

if __name__ == '__main__':
    main()
