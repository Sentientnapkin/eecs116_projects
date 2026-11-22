"""Run the C solution (csol/solution/solution.c, compiled for the host) inside the Python harness.

The C code keeps its state in static variables, so every episode loads its own copy of the shared library.
Build the library first:  bash csol/build_host.sh   (inside WSL)
"""
import ctypes
import json
import os
import shutil
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.join(os.path.expanduser("~"), "ws_c", "libvio_host.so")
_copies = 0


class CSolution:
    frame_width = 320

    def __init__(self, config, library=LIBRARY):
        global _copies
        _copies += 1
        path = os.path.join(tempfile.gettempdir(), f"libvio_{os.getpid()}_{_copies}.so")
        shutil.copy(library, path)
        self.lib = ctypes.CDLL(path, mode=os.RTLD_LOCAL if hasattr(os, "RTLD_LOCAL") else 0)
        os.unlink(path)  # the loaded copy stays valid
        self.lib.init.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
        self.lib.step.argtypes = [ctypes.c_double, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p]
        self.lib.debug_window_data.restype = ctypes.POINTER(ctypes.c_double)
        self.lib.debug_flow_speed.restype = ctypes.c_double
        text = json.dumps({k: (np.asarray(v).tolist() if isinstance(v, np.ndarray) else v) for k, v in config.items()}).encode()
        if self.lib.init(text, len(text)) != 0:
            raise RuntimeError("init failed")
        self.out = np.zeros(13)
        self.stats = {}

    def step(self, t, frame, imu):
        frame = np.ascontiguousarray(frame, dtype=np.uint8)
        imu = np.ascontiguousarray(imu, dtype=np.float64)
        status = self.lib.step(float(t), frame.ctypes.data, imu.ctypes.data, len(imu), self.out.ctypes.data)
        if status != 0:
            raise RuntimeError("step failed")
        return self.out.copy()

    def windows(self):
        """(n, 12) rows: t0, t1, points, parallax, d[3], t_cam[3], used, moving."""
        n = self.lib.debug_window_count()
        if n == 0:
            return np.zeros((0, 12))
        return np.ctypeslib.as_array(self.lib.debug_window_data(), shape=(n * 12,)).reshape(n, 12).copy()
