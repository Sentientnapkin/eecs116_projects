"""Slide figures for the cheap IMU guest (slides 13-16). ~/.venv_gru/bin/python make_figs.py -> fig_*.png here.
Data: holdout/stand-in/server numbers from our runs; one holdout flight replayed with the linear and submitted MLP models."""
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import fit_cheap as fc

for f in ("segoeui.ttf", "segoeuib.ttf"):
    p = f"/mnt/c/Windows/Fonts/{f}"
    if os.path.exists(p): font_manager.fontManager.addfont(p)
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 13, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#555555", "axes.labelcolor": "#222222", "xtick.color": "#333333", "ytick.color": "#333333"})
GREY, ORANGE, BLUE, INK = "#A6A6A6", "#E8743B", "#4A86E8", "#222222"
DPI = 220


def bars_results():
    groups = ["Our holdout\n(240 flights)", "19 closest\nlocal stand-ins", "Server\n(12 hidden flights)"]
    zero, v1, v2 = [4.70, 4.22, 4.69], [2.56, 4.90, 7.79], [2.76, 3.25, 5.16]
    x = np.arange(3); w = 0.26
    fig, ax = plt.subplots(figsize=(5.2, 3.9))
    for i, (vals, c, lab) in enumerate([(zero, GREY, "Output zero"), (v1, ORANGE, "1st MLP"), (v2, BLUE, "2nd MLP (stand-ins held out)")]):
        b = ax.bar(x + (i - 1) * w, vals, w, color=c, label=lab, zorder=2)
        for r, v in zip(b, vals):
            ax.text(r.get_x() + r.get_width() / 2, v + 0.12, f"{v:.2f}", ha="center", va="bottom", fontsize=10.5, color=INK)
    ax.set_xticks(x, groups); ax.set_ylabel("Mean ATE (m)"); ax.set_ylim(0, 9)
    ax.yaxis.grid(True, color="#E6E6E6", zorder=0); ax.tick_params(axis="x", length=0)
    ax.legend(frameon=False, fontsize=10.5, loc="upper left")
    fig.tight_layout(); fig.savefig(f"{HERE}/fig_results.png", dpi=DPI); plt.close(fig)


def server_per_flight():
    R = os.path.join(os.path.dirname(os.path.dirname(HERE)), "server_results")
    ep = lambda i: {e["hash"][:4]: e["metrics"] for e in json.load(open(f"{R}/{i}.json"))["results"]["episodes"]}
    a, b = ep("fbd48a479fe639a2"), ep("049eb610e7b78afc")
    keys = sorted(a, key=lambda k: a[k]["distance_travelled"])
    x = np.arange(len(keys)); w = 0.4
    fig, ax = plt.subplots(figsize=(5.4, 3.9))
    ax.bar(x - w / 2, [a[k]["ate_rmse"] for k in keys], w, color=ORANGE, label="1st MLP (7.79 m mean)", zorder=2)
    ax.bar(x + w / 2, [b[k]["ate_rmse"] for k in keys], w, color=BLUE, label="2nd MLP (5.16 m mean)", zorder=2)
    ax.axhline(4.69, color="#555555", ls="--", lw=1.3, zorder=3, label="Output zero (4.69 m mean)")
    ax.set_xticks(x, [f"{a[k]['distance_travelled']:.0f}" for k in keys], fontsize=10.5)
    ax.set_xlabel("Hidden flight, by path length (m)"); ax.set_ylabel("ATE (m)")
    ax.yaxis.grid(True, color="#E6E6E6", zorder=0); ax.tick_params(axis="x", length=0); ax.set_ylim(0, 16.5)
    ax.legend(frameon=False, fontsize=10.5, loc="upper right")
    fig.tight_layout(); fig.savefig(f"{HERE}/fig_server_flights.png", dpi=DPI); plt.close(fig)


def trajectory():
    m = dict(np.load("/home/alexa/data/model_submitted.npz"))
    wl = np.load(os.path.join(os.path.dirname(HERE), "weights.npy")).reshape(3, 10)
    best = None
    for f in fc.load("~/data/imucache/ho"):
        R, X = fc.prep(f); C = f["cam"]
        path = lambda v: np.vstack([np.zeros(3), np.cumsum(fc.DT * np.einsum("kij,kj->ki", R, v), 0)])
        pl = path(X @ wl.T)
        pm = path(X @ m["Wv"].T + np.maximum(X[:, 1:] @ m["W1"].T + m["B1"], 0) @ m["W2"].T)
        al, am = [np.sqrt(((p - C) ** 2).sum(1).mean()) for p in (pl, pm)]
        z = np.sqrt((C ** 2).sum(1).mean())
        score = abs(am - 2.3) + abs((al - am) - 1.0) + (0 if 3.5 < z < 6 else 5) + (0 if f["name"].startswith("fast-") else 5)   # a typical flight, not a cherry-pick
        if best is None or score < best[0]: best = (score, f["name"], C, pl, pm, al, am, z)
    _, name, C, pl, pm, al, am, z = best
    print("trajectory flight:", name, f"linear {al:.2f} MLP {am:.2f} zero {z:.2f}")
    fig, ax = plt.subplots(figsize=(4.8, 4.8))
    ax.plot(C[:, 0], C[:, 2], color=INK, lw=2.2, label="True path")
    ax.plot(pl[:, 0], pl[:, 2], color=GREY, lw=1.8, label=f"Linear rule (ATE {al:.1f} m)")
    ax.plot(pm[:, 0], pm[:, 2], color=ORANGE, lw=1.8, label=f"Linear + MLP (ATE {am:.1f} m)")
    ax.plot(0, 0, "o", color=INK, ms=7); ax.annotate("start", (0, 0), xytext=(6, -14), textcoords="offset points", fontsize=11)
    ax.set_aspect("equal", adjustable="datalim"); ax.set_xlabel("x, right of start (m)"); ax.set_ylabel("z, ahead of start (m)")
    ax.grid(True, color="#EEEEEE"); ax.legend(frameon=False, fontsize=10.5, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=1)
    ax.set_title("One holdout flight, seen from above", fontsize=12.5, color=INK)
    fig.tight_layout(); fig.savefig(f"{HERE}/fig_trajectory.png", dpi=DPI); plt.close(fig)
    return name


def pipeline():
    steps = [("Read gyro", "2 of 10 IMU rows, camera axes", "~55"),
             ("Orientation", "add up small turns (quaternion)", "~145"),
             ("Features", "fast + slow averages, |slow|", "~80"),
             ("Velocity", "linear rule + 16-unit ReLU MLP", "~1,840"),
             ("Integrate", "rotate to start frame, step 0.05 s", "~130")]
    fig, ax = plt.subplots(figsize=(4.4, 4.6)); ax.set_xlim(0, 10); ax.set_ylim(0, 10.4); ax.axis("off")
    h, gap, top = 1.45, 0.55, 10.0
    for i, (t, d, fu) in enumerate(steps):
        y = top - h - i * (h + gap); hot = t == "Velocity"
        ax.add_patch(FancyBboxPatch((0.2, y), 7.0, h, boxstyle="round,pad=0.02,rounding_size=0.25",
                                    fc="#FCEBDD" if hot else "#F4F6F9", ec=ORANGE if hot else "#B9C2CF", lw=1.6))
        ax.text(0.55, y + h * 0.64, t, fontsize=13.5, fontweight="bold", color=INK, va="center")
        ax.text(0.55, y + h * 0.28, d, fontsize=10.5, color="#444444", va="center")
        ax.text(9.8, y + h / 2, fu, fontsize=13, fontweight="bold", color=ORANGE if hot else BLUE, va="center", ha="right")
        if i < len(steps) - 1:
            ax.annotate("", xy=(3.7, y - gap + 0.04), xytext=(3.7, y - 0.04), arrowprops=dict(arrowstyle="-|>", color="#8A94A3", lw=1.5))
    ax.text(9.8, top + 0.2, "fuel", fontsize=11, color="#555555", ha="right")
    ax.text(0.2, -0.1, "Total measured: 2,261 fuel per frame (per-step numbers approx.)", fontsize=10, color="#555555")
    fig.tight_layout(); fig.savefig(f"{HERE}/fig_pipeline.png", dpi=DPI); plt.close(fig)


if __name__ == "__main__":
    bars_results(); server_per_flight(); pipeline(); trajectory()
    print("ok")
