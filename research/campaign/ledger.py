"""Immutable predeclarations and per-job mkdir claims (no shared append file)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import time
import uuid

STALE_SECONDS = 15 * 60


def utc_now(): return datetime.now(timezone.utc).isoformat()


def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def write_spec(root, spec):
    required = ('arm', 'parent', 'hypothesis', 'build', 'train', 'eval', 'gate', 'preflight', 'resources', 'overfit')
    if any(k not in spec for k in required): raise ValueError(f'spec requires {required}')
    if spec['eval'].get('workers', 160) > 160: raise ValueError('evaluation worker cap is 160')
    if spec['gate'].get('metric') != 'mean_unaligned_ate_m': raise ValueError('gate must use raw unaligned ATE')
    if not spec['gate'].get('declared_at'): raise ValueError('gate declaration timestamp required')
    declared = datetime.fromisoformat(spec['gate']['declared_at'].replace('Z', '+00:00'))
    if declared.tzinfo is None or declared > datetime.now(timezone.utc): raise ValueError('invalid declaration time')
    name = spec.get('name', 'experiment')
    for component in (spec['arm'], name):
        if not component or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in component):
            raise ValueError('arm/name must be safe path components')
    digest = hashlib.sha256(canonical(spec)).hexdigest()
    exp_id = f"{spec['arm']}-{name}-{digest[:8]}"
    path = Path(root)/spec['arm']/(exp_id+'.json'); path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical({**spec, 'exp_id': exp_id, 'spec_sha256': digest}) + b'\n'
    try:
        with path.open('xb') as handle: handle.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload: raise ValueError(f'immutable spec collision: {path}')
    return path


class Claim:
    """Exclusive ownership is an atomic directory creation, safe across NFS clients.

    Heartbeats replace a token-specific file atomically. Stale claims are surfaced,
    never automatically stolen: a paused worker may still be alive. An operator may
    archive the stale directory after checking its host/PID, then resume the task.
    """
    def __init__(self, root, key, stale_seconds=STALE_SECONDS):
        self.path = Path(root)/hashlib.sha256(key.encode()).hexdigest()
        self.key = key; self.token = uuid.uuid4().hex; self.stale_seconds = stale_seconds
        self.owned = False

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try: self.path.mkdir()
        except FileExistsError:
            state = self.inspect()
            raise FileExistsError(f"claim {'stale' if state['stale'] else 'active'}: {self.path} {state}")
        self.owned = True
        (self.path/'owner.json').write_text(json.dumps({'token': self.token, 'key': self.key, 'pid': os.getpid(), 'host': socket.gethostname(), 'created_at': utc_now()}))
        self.heartbeat()
        return self

    def inspect(self):
        owner_path = self.path/'owner.json'
        try: owner = json.loads(owner_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError): owner = {}
        stamp = self.path/(owner.get('token', '')+'.heartbeat')
        try: modified = stamp.stat().st_mtime
        except FileNotFoundError: modified = self.path.stat().st_mtime
        return {**owner, 'stale': time.time()-modified > self.stale_seconds, 'heartbeat_age_seconds': time.time()-modified}

    def _assert_owner(self):
        if not self.owned or json.loads((self.path/'owner.json').read_text())['token'] != self.token:
            raise RuntimeError('claim ownership lost')

    def heartbeat(self):
        self._assert_owner()
        temporary = self.path/(self.token+'.tmp')
        temporary.write_text(utc_now())
        temporary.replace(self.path/(self.token+'.heartbeat'))

    def release(self):
        self._assert_owner()
        (self.path/(self.token+'.heartbeat')).unlink()
        (self.path/'owner.json').unlink()
        self.path.rmdir(); self.owned = False

    def __enter__(self): return self.acquire()
    def __exit__(self, *_): self.release()


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('spec'); p.add_argument('--root', default='campaign/specs')
    a = p.parse_args(); print(write_spec(a.root, json.loads(Path(a.spec).read_text())))


if __name__ == '__main__': main()
