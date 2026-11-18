"""Render development ablations and measured guest accuracy/fuel."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from learned_probe import open_run, write

COLORS = {"ema":"#217785", "ssm":"#3a54ae", "bias":"#b85c23", "bias-disabled":"#9674a5",
          "ssm-nominal":"#546e7a", "ssm-expanded":"#66318c", "ssm-reliability":"#dc7b25",
          "ssm-zero-initial":"#9c4499", "ema-expanded":"#147544",
          "previous-ema":"#6a8d42", "previous-student":"#82694b"}


def save(fig, directory, name):
    fig.savefig(directory/f"{name}.png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def robustness_figures(matrix, directory):
    rows = json.loads((matrix/"flights.json").read_text())
    conditions = ["clean","constant","changing","gaps","jitter","original-combined"]
    labels = ["Clean","Constant gyro","Changing gyro","Image gaps","IMU jitter","Combined"]
    fig, axes = plt.subplots(1,2,figsize=(11,4.1), layout="constrained")
    for model in ("ema","ssm","bias","bias-disabled"):
        groups = [[r for r in rows if r["model"]==model and r["crop_s"]==5 and r["condition"]==c]
                  for c in conditions]
        for ax, metric in zip(axes,("ate","ate_increase")):
            ax.plot(labels, [np.mean([r[metric] for r in g]) for g in groups], "o-",
                    label=model, color=COLORS[model])
    for ax, title, label in zip(axes, ("Absolute error","Change from matched clean crop"),
                               ("Mean unaligned ATE (m)","Mean paired ATE increase (m)")):
        ax.set(title=title,ylabel=label)
        ax.tick_params(axis="x",rotation=25)
        ax.grid(axis="y",alpha=.2)
    axes[0].legend(frameon=False)
    fig.suptitle("Five-second moving start · six development flights, three seeds")
    save(fig,directory,"stress-conditions")

    fig, axes = plt.subplots(2,3,figsize=(13.2,7.3), layout="constrained")
    grid = np.linspace(0,24,241)
    for row_axes, condition in zip(axes, ("clean","original-combined")):
        for model in ("ema","ssm"):
            traces = []
            for row in rows:
                if (row["crop_s"],row["condition"],row["model"])!=(5,condition,model):
                    continue
                target = f"{row['scene']}-5-{condition}-{model}-{row['seed']}.npz"
                with np.load(matrix/target) as trace:
                    traces.append([np.interp(grid,trace["t"],trace[k])
                                   for k in ("position_error_m","velocity_error_m_s","attitude_error_rad")])
            for ax, mean, name in zip(row_axes,np.mean(traces,axis=0),
                                      ("Position error (m)","Velocity error (m/s)","Attitude error (rad)")):
                ax.plot(grid,mean,label=model,color=COLORS[model])
                ax.set(xlabel="Elapsed time after reset (s)",ylabel=name,title=condition.replace("original-",""))
                ax.axvspan(0,3,color="#e8edf5",alpha=.65)
                ax.grid(axis="y",alpha=.2)
    axes[0,0].legend(frameon=False)
    save(fig,directory,"error-over-time")


def curves(runs, directory):
    fig, axes = plt.subplots(1,2,figsize=(11,4.2), layout="constrained")
    seen = set()
    for run in runs:
        for record in json.loads((run/"scores.json").read_text()):
            model, seed = record["model"],record["seed"]
            history = record["history"]
            steps = np.cumsum([r["optimizer_steps"] for r in history])
            for ax, metric, ylabel in zip(axes, ("nominal_ate","stress_ate"),
                                         ("Nominal development ATE (m)","Moving-start development ATE (m)")):
                ax.plot(steps,[r[metric] for r in history],marker=".",color=COLORS[model],
                        linestyle=("-","--",":")[seed],label=model if model not in seen else None,alpha=.85)
                ax.set(xlabel="Training optimizer steps",ylabel=ylabel)
                ax.grid(axis="y",alpha=.2)
            seen.add(model)
    axes[0].legend(frameon=False,fontsize=8)
    save(fig,directory,"learning-curves")


def frontier(guest, directory):
    from robust_deploy import write_paired
    rows = json.loads((guest/"guest.json").read_text())
    for row in rows:
        if "peak_fuel_frame" not in row:
            path = guest/f"{row['model']}-{row['scene']}-{row['regime']}"/"outputs.npz"
            with np.load(path) as trace:
                row["peak_fuel_frame"] = int(np.argmax(trace["fuel"]))
    write_paired(directory/"guest-paired.csv",rows)
    names = list(dict.fromkeys(row["model"] for row in rows))
    fig, ax = plt.subplots(figsize=(8,5.2),layout="constrained")
    counts = set()
    table = []
    for name in names:
        group = [r for r in rows if r["model"]==name and r["regime"]=="nominal"]
        if not group:
            continue
        counts.add(len(group))
        x, y = max(r["peak_fuel"] for r in group)/1e6, float(np.mean([r["ate"] for r in group]))
        ax.scatter(x,y,s=50,color=COLORS.get(name,"#333333"),label=name)
        table.append({"model":name,"mean_nominal_ate":y,"peak_nominal_fuel":round(x*1e6)})
    # A label legend avoids overlaps between models with essentially identical fuel.
    ax.legend(frameon=False,fontsize=8)
    ax.grid(alpha=.2)
    ax.set(xlabel="Maximum measured fuel per frame (millions)",ylabel="Mean per-flight unaligned ATE (m)",
           title=f"Nominal guest accuracy and fuel · {min(counts)} flights per model")
    save(fig,directory,"nominal-accuracy-fuel")
    write(directory/"nominal-frontier.json",table)
    stress = [r for r in rows if r["regime"]!="nominal"]
    if not stress:
        return
    regimes = list(dict.fromkeys(row["regime"] for row in stress))
    fig, ax = plt.subplots(figsize=(9,4.5),layout="constrained")
    offsets = np.arange(len(names))*.85/len(names)-.425
    for offset,name in zip(offsets,names):
        values = [np.mean([r["ate"] for r in stress if r["regime"]==regime and r["model"]==name])
                  for regime in regimes]
        ax.bar(np.arange(len(regimes))+offset,values,width=.8/len(names),label=name,color=COLORS.get(name))
    ax.set(xticks=np.arange(len(regimes)),xticklabels=regimes,ylabel="Mean per-flight unaligned ATE (m)",
           title="Guest trajectory stress comparison")
    ax.legend(frameon=False,fontsize=8)
    ax.grid(axis="y",alpha=.2)
    save(fig,directory,"guest-stress")


def plot(args):
    directory, manifest = open_run("robust-plots", {}, {
        "matrix":str(args.matrix),"training":[str(p) for p in args.training],"guest":str(args.guest)})
    if args.matrix:
        robustness_figures(args.matrix,directory)
    if args.training:
        curves(args.training,directory)
    if args.guest:
        frontier(args.guest,directory)
    manifest["status"] = "completed"
    write(directory/"manifest.json",manifest)
    print(directory,flush=True)
