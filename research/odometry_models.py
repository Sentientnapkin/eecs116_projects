"""Causal residual CNN, explicit local correspondence, and GRU/SSM odometry heads.

The SSM is a portable input-dependent diagonal state-space block, not an
implementation or performance claim for the published Mamba architecture.
"""
import torch
from torch import nn
from torch.nn import functional as F


class Residual(nn.Module):
    def __init__(self, cin, cout, stride=1):
        super().__init__()
        self.body = nn.Sequential(nn.Conv2d(cin, cout, 3, stride, 1, bias=False),
                                  nn.GroupNorm(4, cout), nn.SiLU(),
                                  nn.Conv2d(cout, cout, 3, 1, 1, bias=False), nn.GroupNorm(4, cout))
        self.skip = nn.Conv2d(cin, cout, 1, stride, bias=False) if cin != cout or stride != 1 else nn.Identity()

    def forward(self, x):
        return F.silu(self.body(x) + self.skip(x))


def correlate(current, previous, radius=2):
    """Per-pixel normalized feature correlations at a local grid of offsets."""
    a, b = F.normalize(current, dim=1), F.normalize(previous, dim=1)
    h, w = a.shape[-2:]
    # Shifted slices instead of unfold: identical output, and no CPU col2im fallback on MPS.
    b = F.pad(b, (radius,)*4)
    k = 2*radius + 1
    return torch.stack([(a*b[..., i:i+h, j:j+w]).sum(1) for i in range(k) for j in range(k)], dim=1)


class VisualMotion(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        channels = cfg.get("channels", [24, 48, 96, 128])
        layers, previous = [], 1
        for i, channels_out in enumerate(channels):
            layers.append(Residual(previous, channels_out, 2 if i < 3 else 1))
            previous = channels_out
        self.cnn = nn.Sequential(*layers)
        self.radius = cfg.get("correlation_radius", 2)
        self.use_correlation = cfg.get("correlation", True)
        self.grid = (3, 4)
        correlation_channels = 2*(2*self.radius+1)**2 if self.use_correlation else 0
        visual_size = (3*previous + correlation_channels + 2) * 12
        # Optional AirIO-style attitude encoding: estimated gravity direction in body axes.
        self.attitude = cfg.get("attitude_input", False)
        self.blind = cfg.get("blind", False)
        # Ablation: zero the direct IMU features except the frame interval (column 13). Gyro still
        # enters through the derotated image history, and attitude still integrates the output.
        self.imu_blind = cfg.get("imu_blind", False)
        self.sensor = nn.Sequential(nn.Linear(51 + 3*self.attitude, 64), nn.SiLU(), nn.Linear(64, 64), nn.SiLU())
        self.projection = nn.Sequential(nn.Linear(visual_size + 64, cfg["embedding"]),
                                        nn.LayerNorm(cfg["embedding"]), nn.SiLU())
        self.image_size = (cfg["height"], cfg["width"])
        self.frame_chunk = cfg.get("frame_chunk", 16)
        # Iterative refinement with the correlation signal needs the full local volumes.
        self.keep_volumes = (cfg.get("refine_iters", 0) > 0 and self.use_correlation
                             and "corr" in cfg.get("refine_signals", ["inertial", "corr"]))

    def forward(self, images, imu, R=None):
        if self.imu_blind:
            keep = torch.zeros(imu.shape[-1], device=imu.device); keep[13] = 1
            imu = imu.float()*keep
        if self.attitude:
            imu = torch.cat((imu.float(), R[..., 2, :].float()), dim=-1)  # world z in body axes
        # Channels: current, gyro-warped short history, long history, two masks.
        batch, steps, _, height, width = images.shape
        flat = images.reshape(batch*steps, 5, height, width).float()/255
        if self.blind:  # ablation: same network, images replaced by mid-gray with zero masks
            flat = torch.cat((torch.full_like(flat[:, :3], .5), torch.zeros_like(flat[:, 3:])), dim=1)
        if (height, width) != self.image_size:
            flat = F.interpolate(flat, size=self.image_size, mode="bilinear", align_corners=False)
        outputs, kept = [], []
        sensors = self.sensor(imu.float().reshape(batch*steps, -1))
        for begin in range(0, len(flat), self.frame_chunk):
            x = flat[begin:begin+self.frame_chunk]
            f = self.cnn((x[:, :3] - .5).reshape(-1, 1, *self.image_size))
            f = f.reshape(len(x), 3, *f.shape[1:])
            cur, short, long = f.unbind(1)
            masks = F.interpolate(x[:, 3:], size=cur.shape[-2:], mode="bilinear", align_corners=False)
            components = [cur, (cur-short)*masks[:, :1], (cur-long)*masks[:, 1:]]
            if self.use_correlation:
                short_corr = correlate(cur, short, self.radius)
                long_corr = correlate(cur, long, self.radius)
                components += [short_corr*masks[:, :1], long_corr*masks[:, 1:]]
                if self.keep_volumes:  # (frames, 2 baselines, offsets, h, w), plus current features
                    kept.append((torch.stack((short_corr, long_corr), 1), masks, cur))
            components.append(masks)
            spatial = F.adaptive_avg_pool2d(torch.cat(components, dim=1), self.grid).flatten(1)
            outputs.append(self.projection(torch.cat((spatial, sensors[begin:begin+len(x)]), dim=1)))
        embedding = torch.cat(outputs).reshape(batch, steps, -1)
        volumes = None
        if self.keep_volumes:
            volumes = tuple(torch.cat(parts).reshape(batch, steps, *parts[0].shape[1:]) for parts in zip(*kept))
        return embedding, volumes


class SelectiveBlock(nn.Module):
    def __init__(self, width, states):
        super().__init__()
        self.norm = nn.LayerNorm(width)
        self.input = nn.Linear(width, width*2)
        self.parameters_in = nn.Linear(width, width + states*2)
        self.log_rate = nn.Parameter(torch.linspace(-2, 2, states).repeat(width, 1))
        self.skip = nn.Parameter(torch.ones(width))
        self.output = nn.Linear(width, width)
        self.width, self.states = width, states

    def forward(self, x, dt, memory=None):
        u, gate = self.input(self.norm(x)).chunk(2, dim=-1)
        u = F.silu(u)
        delta, b, c = torch.split(self.parameters_in(u), [self.width, self.states, self.states], dim=-1)
        # dt is observed elapsed time; the first observation can initialize memory.
        delta = F.softplus(delta).clamp(.05, 5) * dt.clamp(min=.001).unsqueeze(-1)
        rate = self.log_rate.clamp(-4, 4).exp()
        h = x.new_zeros(x.shape[0], self.width, self.states) if memory is None else memory
        outputs = []
        for i in range(x.shape[1]):
            a = torch.exp(-delta[:, i, :, None]*rate)
            drive = u[:, i, :, None]*torch.tanh(b[:, i, None, :])
            h = a*h + (1-a)*drive
            y = (h*torch.tanh(c[:, i, None, :])).sum(-1)/(self.states**.5) + self.skip*u[:, i]
            outputs.append(y*F.silu(gate[:, i]))
        return x + self.output(torch.stack(outputs, dim=1)), h


class ResidualGRU(nn.Module):
    """Pre-norm residual GRU layer at the stream width, so depth can grow without the
    vanishing path of a plain stacked GRU."""
    def __init__(self, width):
        super().__init__()
        self.norm, self.gru = nn.LayerNorm(width), nn.GRU(width, width, batch_first=True)

    def forward(self, x, h=None):
        y, h = self.gru(self.norm(x), h)
        return x + y, h


GRAVITY = (0., 0., -9.81)  # world z-up, as common.G
# Body (x fwd, y left, z up) -> camera (x right, y down, z fwd); the T_bc rotation of every shard.
R_BC = ((0., 0., 1.), (-1., 0., 0.), (0., -1., 0.))


class Refiner(nn.Module):
    """RAFT/DPVO-style iterative velocity refinement, causal and fixed-size per frame.

    After the head's initial body velocity v0, K shared-weight GRU-cell iterations each read a
    discrepancy for the current estimate and add a velocity correction:
      - inertial: previous refined world velocity + gravity-compensated accelerometer
        integration over the frame interval, minus the estimate (body axes);
      - corr: the encoder's local correlation volumes (current vs gyro-derotated 0.25 s / 1 s
        history) resampled where the estimate predicts each feature cell came from, with a
        per-cell inverse depth predicted from the current features (depth-free otherwise).
    The update operator's hidden state starts from the head output every frame; only the previous
    refined world velocity crosses frames, so time advances once per observation.
    """
    def __init__(self, cfg, context, volumes):
        super().__init__()
        self.iters = cfg["refine_iters"]
        self.signals = cfg.get("refine_signals", ["inertial", "corr"])
        if not self.signals or set(self.signals) - {"inertial", "corr"}:
            raise ValueError("refine_signals must select inertial, corr, or both")
        if "inertial" in self.signals and cfg.get("imu_blind", False):
            raise ValueError("Inertial refinement requires IMU input")
        if "corr" in self.signals and (volumes is None or volumes[1] < 1):
            raise ValueError("Correlation refinement requires local correlations with positive radius")
        self.use_corr = volumes is not None
        hidden = cfg.get("refine_hidden", 64)
        size = 3 + 2  # estimate, packet/previous flags
        if "inertial" in self.signals:
            size += 3
        if self.use_corr:
            channels, radius = volumes
            self.radius = radius
            self.ages = cfg.get("refine_ages", [.25, 1.])  # history baselines (configs/sensor.json)
            if len(self.ages) != 2 or any(age <= 0 for age in self.ages):
                raise ValueError("refine_ages must specify two positive history ages")
            self.depth = nn.Conv2d(channels, 1, 1)
            nn.init.zeros_(self.depth.weight); nn.init.constant_(self.depth.bias, -.5)  # softplus ~ 0.47 /m
            size += 2*9*12  # 2 baselines x 3x3 lookup, pooled to the 3x4 grid
            self.register_buffer("R_bc", torch.tensor(R_BC), persistent=False)
        self.register_buffer("gravity", torch.tensor(GRAVITY), persistent=False)
        self.image_height, self.image_width = cfg["height"], cfg["width"]
        self.init = nn.Linear(context, hidden)
        self.input = nn.Sequential(nn.Linear(size + context, hidden), nn.SiLU())
        self.cell = nn.GRUCell(hidden, hidden)
        self.delta = nn.Linear(hidden, 3)
        nn.init.zeros_(self.delta.weight); nn.init.zeros_(self.delta.bias)  # start at the head estimate

    def lookup(self, volume, mask, depth, v, fx):
        """volume (B,2,k*k,h,w), mask (B,2,h,w), depth (B,h,w) inverse depth, v (B,3) body m/s."""
        b, _, _, h, w = volume.shape
        k = 2*self.radius + 1
        sx, sy = self.image_width/w, self.image_height/h
        ys = (torch.arange(h, device=v.device)+.5)*sy - self.image_height/2
        xs = (torch.arange(w, device=v.device)+.5)*sx - self.image_width/2
        xn, yn = xs/fx[:, None], ys/fx[:, None]
        steps = torch.tensor([-1., 0., 1.], device=v.device)
        near = torch.stack(torch.meshgrid(steps, steps, indexing="ij")[::-1], -1).reshape(1, 3, 3, 2)
        features = []
        for index, age in enumerate(self.ages):
            d = (v @ self.R_bc)*age  # camera displacement over the baseline, camera axes
            # Static point: previous-frame position minus current position (normalized coordinates).
            dx = depth*(d[:, 0, None, None] - xn[:, None, :]*d[:, 2, None, None])
            dy = depth*(d[:, 1, None, None] - yn[:, :, None]*d[:, 2, None, None])
            # Offsets in feature cells -> the volume's [-radius, radius] grid, then a 3x3 neighbourhood.
            ox, oy = dx*fx[:, None, None]/sx, dy*fx[:, None, None]/sy
            grid = torch.stack((ox, oy), -1).reshape(b*h*w, 1, 1, 2)
            grid = (grid + near)/self.radius
            sampled = F.grid_sample(volume[:, index].permute(0, 2, 3, 1).reshape(b*h*w, 1, k, k), grid,
                                    align_corners=True, padding_mode="zeros")
            sampled = sampled.reshape(b, h, w, 9).permute(0, 3, 1, 2)*mask[:, index, None]
            features.append(F.adaptive_avg_pool2d(sampled, (3, 4)).flatten(1))
        return torch.cat(features, 1)

    def forward(self, v0, context, imu, R, state, volumes=None):
        """v0 (B,T,3) head estimate, context (B,T,C) head features, imu (B,T,51), R (B,T,3,3) or
        None, state None or (previous refined world velocity (B,3), has-previous flag (B,1)).
        Returns every estimate (K+1,B,T,3), initial first, and the new state."""
        batch, steps, _ = v0.shape
        if R is None:
            R = torch.eye(3, device=v0.device).expand(batch, steps, 3, 3)
        R = R.float()
        if state is None:
            state = (v0.new_zeros(batch, 3), v0.new_zeros(batch, 1))
        previous, seen = state
        imu = imu.float()
        dt, packet = imu[..., 13:14], imu[..., 12:13]
        force = imu[..., 0:3]*9.81  # mean specific force over the frame interval, body axes
        if self.use_corr:
            volume, mask, features = volumes
            depth = F.softplus(self.depth(features.flatten(0, 1))).reshape(batch, steps, *features.shape[-2:])
            fx = (imu[..., 14]*self.image_width).clamp_min(1e-6)
        estimates = [[] for _ in range(self.iters+1)]
        for t in range(steps):
            rotation = R[:, t]
            v, c = v0[:, t], context[:, t]
            flags = torch.cat((packet[:, t], seen), 1)
            if "inertial" in self.signals:
                gravity = self.gravity @ rotation  # world gravity in body axes (R^T g)
                previous_body = (previous.detach().unsqueeze(1) @ rotation).squeeze(1)
                predicted = previous_body + (force[:, t] + gravity)*(packet[:, t]*dt[:, t])
            h = torch.tanh(self.init(c))
            estimates[0].append(v)
            for k in range(self.iters):
                current = v.detach()
                parts = [current, flags]
                if "inertial" in self.signals:
                    parts.append(((predicted - current)*seen).clamp(-3, 3))
                if self.use_corr:
                    parts.append(self.lookup(volume[:, t], mask[:, t], depth[:, t], current, fx[:, t]))
                h = self.cell(self.input(torch.cat(parts + [c], 1)), h)
                v = v + self.delta(h)
                estimates[k+1].append(v)
            previous = (rotation @ v.detach().unsqueeze(-1)).squeeze(-1)
            seen = torch.ones_like(seen)
        return torch.stack([torch.stack(e, 1) for e in estimates]), (previous, seen)


class OdometryNet(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = dict(cfg)
        self.visual = VisualMotion(cfg)
        self.kind = cfg["head"]
        d = cfg["embedding"]
        if self.kind == "gru":
            self.temporal = nn.GRU(d, cfg["hidden"], cfg["layers"], batch_first=True)
            nout = cfg["hidden"]
        elif self.kind == "ssm":
            self.temporal = nn.ModuleList([SelectiveBlock(d, cfg["states"]) for _ in range(cfg["layers"])])
            nout = d
        elif self.kind == "gru_res":
            self.temporal = nn.ModuleList([ResidualGRU(d) for _ in range(cfg["layers"])])
            nout = d
        elif self.kind == "gru_ssm":
            # Hybrid: residual GRU layers first, then selective SSM blocks, at the same width.
            self.temporal = nn.ModuleList([ResidualGRU(d) for _ in range(cfg.get("gru_layers", 1))] +
                                          [SelectiveBlock(d, cfg["states"]) for _ in range(cfg.get("ssm_layers", 1))])
            nout = d
        elif self.kind == "ema":
            nout = d*2
        else:
            raise ValueError(f"Unknown head: {self.kind}")
        self.output = nn.Sequential(nn.LayerNorm(nout), nn.Linear(nout, 128), nn.SiLU(), nn.Linear(128, 3))
        self.refiner = None
        if cfg.get("refine_iters", 0) > 0:  # opt-in; created last so other initializations are unchanged
            volumes = (cfg.get("channels", [24, 48, 96, 128])[-1], self.visual.radius) if self.visual.keep_volumes else None
            self.refiner = Refiner(cfg, nout, volumes)

    def forward(self, images, imu, state=None, R=None, iterations=False):
        """Body velocity per frame and the streaming state. With refinement, `iterations=True`
        returns every estimate (K+1,B,T,3) for the per-iteration loss instead of the final one."""
        if self.refiner is not None:
            head_state, refine_state = (None, None) if state is None else state
            y, head_state, volumes = self.head(images, imu, head_state, R)
            v0 = self.output(y)
            every, refine_state = self.refiner(v0, y, imu, R, refine_state, volumes)
            return (every if iterations else every[-1]), (head_state, refine_state)
        y, state, _ = self.head(images, imu, state, R)
        return self.output(y), state

    def head(self, images, imu, state, R):
        z, volumes = self.visual(images, imu, R)
        dt = imu[..., 13].float()
        if self.kind == "gru":
            y, state = self.temporal(z, state)
        elif self.kind in ("ssm", "gru_res", "gru_ssm"):
            previous = [None]*len(self.temporal) if state is None else state
            y, state = z, []
            for block, h in zip(self.temporal, previous):
                y, h = block(y, dt, h) if isinstance(block, SelectiveBlock) else block(y, h)
                state.append(h)
        else:
            h = z[:, 0] if state is None else state
            ys = []
            for i in range(z.shape[1]):
                a = torch.exp(-2*dt[:, i, None])
                h = a*h+(1-a)*z[:, i]
                ys.append(torch.cat((z[:, i], h), dim=-1))
            y, state = torch.stack(ys, dim=1), h
        return y, state, volumes
