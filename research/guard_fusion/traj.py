"""Read saved guests without changing evaluator filling or coordinate conventions.

Inference code receives sources only. Truth, split tags and saved scores are for
evaluation and must never be passed to a guard's step method.
"""
import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

SRC = Path(os.environ.get('VIOBENCH_SRC', '/dev/shm/sebastian-vio/viobench'))
sys.path.insert(0, str(SRC))
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.runner.metrics import fill_missing_states, valid_states
from viobench.tools.runner.score import load_estimates

BASE = Path('/data/backups/rganapa/Sebastian')
DEFAULT_SELECTED = BASE / 'baselines/bench-fast/selected'
DEFAULT_RAW = BASE / 'gen/raw-fast/selected'
DEFAULT_GUESTS = {'vins': 'vins_mono-f368cf2c', 'openvins': 'openvins-c6cd96bc',
                  'n2': 'n2_kfinputs_s217-8b05b203'}
INIT = re.compile(r'initialized at t=([0-9.]+)')


@lru_cache(maxsize=64)
def _scores(path):
    return json.loads(Path(path).read_text())


def guest_dir(selected_dir, guest_key):
    root = Path(selected_dir)
    exact = root / DEFAULT_GUESTS.get(guest_key, guest_key)
    if exact.is_dir():
        return exact
    candidates = sorted(p for p in root.glob(guest_key + '-*') if p.is_dir())
    if len(candidates) != 1:
        raise ValueError(f'{guest_key}: expected exactly one guest directory, found {candidates}')
    return candidates[0]


def list_episodes(selected_dir=DEFAULT_SELECTED):
    """Use declared inputs, never silently intersect the successfully scored rows."""
    data = _scores(str(guest_dir(selected_dir, 'vins') / 'scores.json'))
    return sorted(Path(p).stem for p in data['guest']['archives'])


def load_truth(raw_dir, episode):
    archive = Path(raw_dir) / f'{episode}.zip'
    e = read_episode(archive, frames='none')
    return np.asarray(e.frame_times), np.asarray(e.ground_truth_state()), e.meta


def load_guest(selected_dir, guest_key, episode, times):
    folder = guest_dir(selected_dir, guest_key)
    paths = sorted((folder / episode / 'report/logs').glob('*/estimate.tum'))
    if len(paths) > 1:
        raise ValueError(f'Ambiguous estimate logs: {folder / episode}')
    # A missing guest episode is a failed stream, not an excluded evaluation row.
    raw = load_estimates(paths[0], times) if paths else np.full((len(times), 13), np.nan)
    valid = valid_states(raw)
    states = fill_missing_states(raw)
    stdout = (paths[0].parent / 'stdout.txt').read_text(errors='replace') if paths and (paths[0].parent / 'stdout.txt').exists() else ''
    stderr = (paths[0].parent / 'stderr.txt').read_text(errors='replace') if paths and (paths[0].parent / 'stderr.txt').exists() else ''
    match = INIT.search(stdout)
    init_s = float(match.group(1)) if match else None
    # Learned streams are ready from the first valid sensor frame.
    if guest_key.startswith(('n2', 'bd0', 'b_d0')) and init_s is None:
        init_s = float(times[0])
    return {'t': times, 'T': poses_to_matrices(states), 'states': states,
            'raw_states': raw, 'twist': states[:, 7:], 'valid': valid,
            'init_s': init_s, 'stdout': stdout, 'stderr': stderr,
            'filled_frames': int((~valid).sum()), 'path': str(paths[0]) if paths else None}


def load_episode(selected_dir=DEFAULT_SELECTED, raw_dir=DEFAULT_RAW, episode=None, guests=None):
    if episode is None:
        raise ValueError('episode is required')
    guests = guests or DEFAULT_GUESTS
    t, truth, meta = load_truth(raw_dir, episode)
    sources = {name: load_guest(selected_dir, key, episode, t) for name, key in guests.items()}
    audit_path = Path(raw_dir).parent / 'bench' / f'{episode}.json'
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
    tags = {key: audit.get(key, meta.get(key)) for key in ('group', 'catalog', 'scene')}
    tags.update(start_type='mid' if episode.startswith('fastmid-') else 'static', source_pool='raw-fast')
    reference = {}
    for name, key in guests.items():
        rows = _scores(str(guest_dir(selected_dir, key) / 'scores.json'))['rows']
        reference[name] = next((r.get('ate_full') for r in rows if r['episode'] == episode), None)
    return {'episode': episode, 't': t, 'truth': truth, 'sources': sources,
            'tags': tags, 'reference_scores': reference}
