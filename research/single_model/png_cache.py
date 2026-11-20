"""Bit-identical decoded-frame cache for the pinned viobench evaluator (speed only; results unchanged).

Wraps viobench.tools.datasets.storage.decode_png: key = blake2b(PNG bytes) + channel count; value = the exact
array the original decoder returned, stored as .npy on tmpfs. First use decodes and stores; later runs (any variant,
any agent) read the array back. Disable with VIOBENCH_PNG_CACHE=0.
"""
import hashlib, os
import numpy as np

CACHE = os.environ.get('VIOBENCH_PNG_CACHE_DIR', '/dev/shm/sebastian-vio/png-cache')


def install():
    if os.environ.get('VIOBENCH_PNG_CACHE', '1') == '0':
        return
    from viobench.tools.datasets import storage
    original = storage.decode_png
    if getattr(original, '_cached', False):
        return

    def decode_png(data, channels):
        key = hashlib.blake2b(bytes(data), digest_size=16).hexdigest() + f'_{channels}'
        path = os.path.join(CACHE, key[:2], key + '.npy')
        try:
            return np.load(path)
        except (FileNotFoundError, ValueError, OSError, EOFError):
            pass
        array = original(data, channels)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f'{path}.{os.getpid()}.tmp'
            with open(tmp, 'wb') as f:
                np.save(f, array)
            os.replace(tmp, path)
        except OSError:
            pass
        return array

    decode_png._cached = True
    storage.decode_png = decode_png
