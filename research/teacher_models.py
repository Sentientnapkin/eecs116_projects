"""Causal residual CNN, explicit local correspondence, and GRU/SSM teachers.

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
        self.sensor = nn.Sequential(nn.Linear(51 + 3*self.attitude, 64), nn.SiLU(), nn.Linear(64, 64), nn.SiLU())
        self.projection = nn.Sequential(nn.Linear(visual_size + 64, cfg["embedding"]),
                                        nn.LayerNorm(cfg["embedding"]), nn.SiLU())
        self.image_size = (cfg["height"], cfg["width"])
        self.frame_chunk = cfg.get("frame_chunk", 16)

    def forward(self, images, imu, R=None):
        if self.attitude:
            imu = torch.cat((imu.float(), R[..., 2, :].float()), dim=-1)  # world z in body axes
        # Channels: current, gyro-warped short history, long history, two masks.
        batch, steps, _, height, width = images.shape
        flat = images.reshape(batch*steps, 5, height, width).float()/255
        if self.blind:  # ablation: same network, images replaced by mid-gray with zero masks
            flat = torch.cat((torch.full_like(flat[:, :3], .5), torch.zeros_like(flat[:, 3:])), dim=1)
        if (height, width) != self.image_size:
            flat = F.interpolate(flat, size=self.image_size, mode="bilinear", align_corners=False)
        outputs = []
        sensors = self.sensor(imu.float().reshape(batch*steps, -1))
        for begin in range(0, len(flat), self.frame_chunk):
            x = flat[begin:begin+self.frame_chunk]
            f = self.cnn((x[:, :3] - .5).reshape(-1, 1, *self.image_size))
            f = f.reshape(len(x), 3, *f.shape[1:])
            cur, short, long = f.unbind(1)
            masks = F.interpolate(x[:, 3:], size=cur.shape[-2:], mode="bilinear", align_corners=False)
            components = [cur, (cur-short)*masks[:, :1], (cur-long)*masks[:, 1:]]
            if self.use_correlation:
                components += [correlate(cur, short, self.radius)*masks[:, :1],
                               correlate(cur, long, self.radius)*masks[:, 1:]]
            components.append(masks)
            spatial = F.adaptive_avg_pool2d(torch.cat(components, dim=1), self.grid).flatten(1)
            outputs.append(self.projection(torch.cat((spatial, sensors[begin:begin+len(x)]), dim=1)))
        return torch.cat(outputs).reshape(batch, steps, -1)


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


class Teacher(nn.Module):
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

    def forward(self, images, imu, state=None, R=None):
        z = self.visual(images, imu, R)
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
        return self.output(y), state
