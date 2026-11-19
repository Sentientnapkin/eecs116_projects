"""Extract only causally delivered sensors and calibration, never trajectory truth."""
import argparse
import json
from pathlib import Path
import numpy as np
from viobench.tools.datasets.storage import read_episode

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("archive", type=Path); p.add_argument("output", type=Path)
p.add_argument("--frames", type=int, default=1200)
p.add_argument("--crop", type=float, default=0.)
a = p.parse_args()
e = read_episode(a.archive)
first = int(np.searchsorted(e.frame_times, e.frame_times[0] + a.crop - 1e-8))
indices = np.arange(first, min(first + a.frames, e.num_frames))
camera, images = e.adapt((320, 240))
absolute = e.frame_times[indices]; origin = absolute[0]
packets, offsets = [], [0]
for j, i in enumerate(indices):
    packet = e.imu_window(i).copy() if j else np.empty((0, 7), dtype=np.float64)
    packet[:, 0] -= origin
    packets.append(packet); offsets.append(offsets[-1] + len(packet))
a.output.parent.mkdir(parents=True, exist_ok=True)
np.savez_compressed(a.output, frames=np.stack([images[int(i)] for i in indices]), times=absolute-origin, absolute_times=absolute,
                    packet_offsets=np.asarray(offsets), packets=np.concatenate(packets),
                    camera_json=np.asarray(json.dumps(camera)), T_bc=e.T_body_camera,
                    archive=np.asarray(str(a.archive)))
print(a.output, len(indices), "sensor-only frames", flush=True)
