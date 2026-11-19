"""Compare frozen-encoder temporal heads with matched endpoint and displacement losses."""
import argparse
import json
from pathlib import Path
from functools import lru_cache

import numpy as np
import torch
from torch import nn

from learned_probe import (digest, fit, network, open_run, predictions, read_inputs,
                           score, tensor, write)


def scan(gain, update):
    """Inclusive associative scan for h[k] = gain[k] * h[k-1] + update[k]."""
    offset = 1
    while offset < len(update):
        update = torch.cat((update[:offset], update[offset:] + gain[offset:] * update[:-offset]))
        gain = torch.cat((gain[:offset], gain[offset:] * gain[:-offset]))
        offset *= 2
    return update


class Head(nn.Module):
    def __init__(self, kind, n=32, hidden=16, outputs=3, zero_initial_state=False):
        super().__init__()
        self.kind = kind
        self.zero_initial_state = zero_initial_state
        if kind in ("ssm", "selective"):
            self.inp = nn.Linear(n, hidden)
            self.log_rate = nn.Parameter(torch.log(torch.linspace(.5, 8., hidden)))
        if kind == "selective":
            self.gate = nn.Linear(n,hidden)
        if kind == "gru":
            self.gru = nn.GRU(n, hidden)
        self.out = nn.Linear(n * 2 if kind == "ema" else n if kind == "frame" else n+hidden, outputs)

    def forward(self, x, dt):
        if self.kind == "frame":
            return self.out(x)
        if self.kind == "gru":
            h, _ = self.gru(x[:, None])
            return self.out(torch.cat((x, h[:, 0]), dim=1))
        value = x if self.kind == "ema" else self.inp(x)
        rate = 2. if self.kind == "ema" else self.log_rate.clamp(-4,5).exp()
        step = dt[:, None]
        if self.kind == "selective":
            step = step * nn.functional.softplus(self.gate(x)+.5413)
        a = torch.exp(-step*rate).expand_as(value)
        a = torch.cat((torch.zeros_like(a[:1]), a[1:]))
        update = (1-a)*value
        if self.zero_initial_state:
            update = torch.cat((torch.zeros_like(update[:1]), update[1:]))
        h = scan(a, update)
        return self.out(torch.cat((x, h), dim=1))


def winner(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["variant"], []).extend(s["ate"] for s in r["rows"])
    return min(groups, key=lambda k: np.mean(groups[k]))


@torch.no_grad()
def predict(head, row):
    t = row["times"]
    dt = np.diff(t, prepend=t[0])
    return head(tensor(row["features"]), tensor(dt)).numpy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("visual_run", type=Path)
    parser.add_argument("--head", choices=("frame","ema","ssm","gru","selective"), action="append")
    args = parser.parse_args()
    torch.set_num_threads(4)
    previous = json.loads((args.visual_run/"manifest.json").read_text())
    if previous["status"] != "completed":
        raise ValueError("visual run must be complete")
    visual = json.loads((args.visual_run/"scores.json").read_text())
    selected = winner(visual)
    cfg, sources = previous["config"], previous["datasets"]
    directory, manifest = open_run("temporal", cfg, sources)
    manifest.update(visual_run=str(args.visual_run), visual_manifest_sha256=digest(args.visual_run/"manifest.json"),
                    selected_visual=selected, heads=args.head or ["frame","ema","ssm","gru"])
    print(directory, selected, flush=True)
    try:
        train, dev = [read_inputs(sources[k], cfg) for k in ("train", "development")]
        moving = read_inputs(sources["development"], cfg, crop=5.)
        records = []
        for seed in cfg["seeds"]:
            checkpoint = next(r for r in visual if r["seed"] == seed and r["variant"] == selected)
            if digest(checkpoint["checkpoint"]) != checkpoint["sha256"]:
                raise ValueError("visual checkpoint hash changed")
            encoder = network(checkpoint["checkpoint"])
            for row in train+dev+moving:
                row["features"] = predictions(encoder, row, features=True)
            for kind in args.head or ("frame", "ema", "ssm", "gru"):
                torch.manual_seed(seed)
                head = Head(kind)
                losses = fit(head, train, cfg, seed, cfg["head_epochs"], "features")
                rows = [score(row, predict(head, row)) for row in dev]
                reset_rows = [score(row, predict(head, row)) for row in moving]
                exported = {k: v.detach().numpy() for k, v in head.state_dict().items()}
                from streaming import Temporal
                stream = Temporal(kind, exported)
                row = dev[0]
                dt = np.diff(row["times"], prepend=row["times"][0])
                streamed = np.stack([stream.step(x, elapsed) for x, elapsed in zip(row["features"], dt)])
                expected = predict(head, row)
                maximum = float(np.max(np.abs(expected-streamed)))
                if maximum > 1e-5:
                    raise ValueError(f"streaming parity failed ({kind}): {maximum}")
                path = directory/f"{kind}-{seed}.pt"
                torch.save({"state": head.state_dict(), "kind": kind, "encoder": checkpoint["checkpoint"]}, path)
                records.append({"variant": kind, "seed": seed, "checkpoint": str(path), "sha256": digest(path),
                                "encoder": checkpoint["checkpoint"], "encoder_sha256": checkpoint["sha256"],
                                "parameters": sum(p.numel() for p in head.parameters()), "loss": losses,
                                "rows": rows, "moving_start": reset_rows, "stream_max_error": maximum})
                write(directory/"scores.json", records)
                print(kind, seed, np.mean([r["ate"] for r in rows]), flush=True)
        manifest["status"] = "completed"
    except BaseException as error:
        manifest.update(status="failed", error=repr(error))
        raise
    finally:
        write(directory/"manifest.json", manifest)




class Joint(nn.Module):
    def __init__(self, settings):
        super().__init__()
        from learned_probe import Net
        self.settings = settings
        self.encoder = Net(settings["variant"], model_cfg=settings)
        self.head = Head(settings["kind"], settings["embedding"], settings["hidden"],
                         6 if settings.get("bias_head") else 3, settings.get("zero_initial_state", False))

    def forward(self, images, imu):
        return self.head(self.encoder.features(images,imu),imu[:,13])


def joint_model(net):
    net.eval()
    return {"variant":net.settings["variant"],"kind":net.settings["kind"],
            "encoder":{k:x.detach().numpy() for k,x in net.encoder.state_dict().items()},
            "temporal":{k:x.detach().numpy() for k,x in net.head.state_dict().items()},
            "settings":net.settings.copy()}


@lru_cache(maxsize=8)
def raw_flight(path,crop):
    from common import Flight
    return Flight(path,crop)


def exact_joint(net, parent, cfg, crop=0., feedback=True):
    from pairs import sensor_rows, added_gyro, disturbance_seed
    from streaming import Estimator
    f = raw_flight(parent["path"],crop)
    T = np.linalg.inv(f.T_bc)
    h,w = f.frames[0].shape[:2]
    camera = {**f.K,"width":w,"height":h,"T_cam_imu":T}
    model = joint_model(net)
    model["settings"]["feedback"] = feedback and model["settings"].get("feedback",False)
    estimator = Estimator(camera,model,cfg)
    outputs, rotations, estimates = [],[],[]
    for t,frame,packet in sensor_rows(f,cfg):
        outputs.append(estimator.step(t,frame,packet))
        orientation=estimator.inputs.orient
        rotations.append(orientation.R.copy())
        estimates.append(orientation.total_bias.copy())
    output = np.asarray(outputs)
    valid = np.isfinite(output).all(axis=1)
    invalid = np.flatnonzero(~valid)
    if len(invalid):
        output[invalid[0]:] = [0,0,0,0,0,0,1,0,0,0,0,0,0]
    rot = np.asarray(rotations)
    angle = (np.einsum("nij,nij->n",rot,f.R[0].T@f.R)-1)/2
    error = np.linalg.norm(output[:,:3]-f.cam_gt,axis=1)
    speed = np.linalg.norm(f.v,axis=1)
    turn = np.linalg.norm(f.w,axis=1)
    def rms(mask):
        return float(np.sqrt(np.mean(error[mask]**2))) if mask.any() else None
    from common import sim3_ate
    cal = estimator.inputs.orient.accepted_at
    index = int(np.searchsorted(f.ft,cal)) if cal is not None else None
    result={"path":parent["path"],"scene":parent["scene"],"domain":parent.get("domain","proxy"),
            "ate":rms(speed>=0),"sim3":sim3_ate(output[:,:3],f.cam_gt),
            "orientation_rmse_rad":float(np.sqrt(np.mean(np.arccos(np.clip(angle,-1,1))**2))),
            "startup_ate":rms(f.ft<=1),"hover_ate":rms(speed<.15),"moving_ate":rms(speed>=.15),
            "turn_ate":rms(turn>.25),"late_ate":rms(f.ft>=f.ft[-1]/2),
            "frames":len(output),"filled_frames":len(output)-int(invalid[0]) if len(invalid) else 0,
            "calibration_accepted_at":cal,"calibration_while_moving":bool(speed[index]>.15) if index is not None else None,
            "calibration_while_turning":bool(turn[index]>.12) if index is not None else None,
            "duration_s":float(f.ft[-1]),"initial_speed":float(speed[0])}
    return result,np.asarray(estimates),added_gyro(f.ft,cfg.get("disturbance"),disturbance_seed(parent["path"],cfg))


def estimated_bias_rotations(R, bias, times):
    """Differentiable small-angle trajectory correction to the cached gyro chain."""
    elapsed=torch.diff(times,prepend=times[:1])
    current=(R @ bias[...,None]).squeeze(-1)
    prev=torch.cat((torch.zeros_like(current[:1]),current[:-1]))
    # Same forward-only 0.8 s bias adaptation used at deployment.
    gain=torch.exp(-elapsed[:,None]/.8).expand_as(prev)
    applied=scan(gain,(1-gain)*prev)
    world_bias=(applied*elapsed[:,None]).cumsum(0)
    angle=-world_bias.clamp(-1,1)
    x,y,z=angle.unbind(-1)
    zero=torch.zeros_like(x)
    cross=torch.stack((zero,-z,y,z,zero,-x,-y,x,zero),dim=-1).reshape(-1,3,3)
    return torch.matrix_exp(cross) @ R


def fit_joint(net, train, dev, cfg, seed, epochs, frozen=False, validator=None):
    import time
    from learned_probe import inputs, displacement_loss
    rng = np.random.default_rng(seed)
    opt = torch.optim.AdamW((p for p in net.parameters() if p.requires_grad),lr=.0015)
    history,best_state,best = [],None,float("inf")
    settings = net.settings
    started=time.monotonic()
    for epoch in range(1,epochs+1):
        net.train()
        losses=[]
        for i in rng.permutation(len(train)):
            row=train[i]
            starts=list(range(0,len(row["v"])-1,cfg["joint"]["chunk"]))
            cap=cfg["joint"].get("chunks_per_parent")
            if cap and cap<len(starts):
                offset=(epoch-1+int(i))%len(starts)
                starts=[starts[(offset+j)%len(starts)] for j in range(cap)]
            for start in starts:
                burn=min(start,cfg["joint"]["burn_in"])
                end=start+cfg["joint"]["chunk"]
                win=slice(start-burn,end)
                imu=tensor(row["imu"][win])
                y=tensor(row["v"][win])
                R=tensor(row["R"][win])
                times=tensor(row["times"][win]-row["times"][win][0])
                output=net.head(tensor(row["features"][win]),imu[:,13]) if frozen else net(
                    *inputs(row,settings["variant"],win))
                pred=output[:,:3]
                loss=displacement_loss(pred,y,R,times,cfg,burn)
                if settings.get("teacher_weight"):
                    loss=loss+settings["teacher_weight"]*displacement_loss(
                        pred,tensor(row["teacher_velocity"][win]),R,times,cfg,burn)
                if settings.get("bias_head"):
                    bias=.12*torch.tanh(output[:,3:])
                    loss=loss+12*nn.functional.smooth_l1_loss(bias[burn:],tensor(row["bias_target"][win])[burn:],beta=.02)
                    delta_R=estimated_bias_rotations(R,bias,times)
                    corrected=(delta_R @ pred[...,None]).squeeze(-1)
                    truth=(tensor(row["R_truth"][win]) @ y[...,None]).squeeze(-1)
                    # Bring truth into the cached integration gauge at the chunk start.
                    truth=(R[0] @ tensor(row["R_truth"][win][0]).T @ truth.T).T
                    I=torch.eye(3).expand(len(y),3,3)
                    loss=loss+.2*displacement_loss(corrected,truth,I,times,cfg,burn)
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(),1.)
                opt.step()
                losses.append(float(loss.detach()))
        net.eval()
        with torch.no_grad():
            if validator:
                val=validator(net)
            else:
                val=np.mean([joint_score(net,row)["ate"] for row in dev])
        history.append({"epoch":epoch,"train_loss":float(np.mean(losses)),"dev_ate":float(val),
                        "seconds":time.monotonic()-started})
        if val<best-1e-5:
            best,best_epoch=val,epoch
            best_state={k:p.clone() for k,p in net.state_dict().items()}
        if epoch-best_epoch>=cfg["joint"]["patience"]:
            break
    net.load_state_dict(best_state)
    net.eval()
    return history


@torch.no_grad()
def joint_score(net,row):
    from learned_probe import inputs
    x,imu=inputs(row,net.settings["variant"],slice(None))
    out=net(x,imu).numpy()[:,:3]
    return score(row,out)


def joint_roster(data_run, limit_proxy):
    from collections import defaultdict
    from pairs import digest
    roster={}
    for split,folder in (("train","train"),("development","val")):
        by_scene=defaultdict(list)
        for p in sorted(Path(f"data/{folder}").glob("base-*.npz")):
            with np.load(p) as data:
                by_scene[str(data["scene"])].append(p)
        parents=[]
        for scene,paths in sorted(by_scene.items()):
            for path in paths[:limit_proxy if split=="train" else 1]:
                parents.append({"path":str(path),"scene":scene,"sha256":digest(path),"domain":"proxy"})
        roster[split]=parents
    if data_run:
        manifest=json.loads((data_run/"manifest.json").read_text())
        for split in ("train","development"):
            roster[split].extend(manifest.get("datasets",{}).get(split,[]))
    if {r["scene"] for r in roster["train"]} & {r["scene"] for r in roster["development"]}:
        raise ValueError("joint experiment scene overlap")
    return roster


def joint_main():
    from pairs import config
    parser=argparse.ArgumentParser(description="Expanded-data CNN and CNN–IMU SSM milestones")
    parser.add_argument("--data-run",type=Path)
    parser.add_argument("--screen-run",type=Path)
    parser.add_argument("--finalists",type=Path)
    parser.add_argument("--proxy-parents",type=int,default=2)
    parser.add_argument("--chunks-per-parent",type=int)
    parser.add_argument("--epochs",type=int)
    parser.add_argument("--phase",choices=("screen","finalists","feedback-smoke","native-bias","teacher"),required=True)
    args=parser.parse_args()
    torch.set_num_threads(4)
    cfg=config()
    cfg.update(policy="rolling",ordered_packet=True,horizons=cfg["joint"]["horizons"])
    if args.chunks_per_parent is not None:
        if args.chunks_per_parent<1:
            parser.error("--chunks-per-parent must be positive")
        cfg["joint"]["chunks_per_parent"]=args.chunks_per_parent
    if args.epochs is not None:
        if not 1<=args.epochs<=cfg["joint"]["max_epochs"]:
            parser.error("--epochs is outside the configured compute cap")
        cfg["joint"]["epochs"]=args.epochs
    sources=joint_roster(args.data_run,args.proxy_parents)
    if args.phase=="feedback-smoke":
        sources["train"]=sources["train"][::2][:4]
        sources["development"]=sources["development"][:3]
        cfg["joint"]["epochs"]=6
    if args.phase=="native-bias":
        if not args.data_run:
            parser.error("native-bias needs --data-run")
        sources={key:[row for row in value if row["domain"]=="benchmark"] for key,value in sources.items()}
        cfg["joint"]["epochs"]=min(cfg["joint"]["epochs"],6)
        cfg["joint"]["chunks_per_parent"]=1
    if args.data_run and not any(p["domain"]=="benchmark" for p in sources["development"]):
        raise ValueError("native development data is not ready")
    if args.data_run:
        eval_parents=[r for r in sources["development"] if r["domain"]=="benchmark"]
    else:
        eval_parents=sources["development"]
    directory,manifest=open_run(f"joint-{args.phase}",cfg,sources)
    manifest.update(native_data_run=str(args.data_run) if args.data_run else None,
                    validation_roster=eval_parents, proxy_parents_per_training_scene=args.proxy_parents,
                    screen_run=str(args.screen_run) if args.screen_run else None)
    write(directory/"manifest.json",manifest)
    print(directory,flush=True)
    records=[]
    try:
        def train_candidate(name, settings, cfg, train, valid, seed, init=None, freeze=False, exact=False):
            net=Joint(settings)
            if init:
                matching = {k: v for k,v in init.items()
                            if k in net.encoder.state_dict() and v.shape == net.encoder.state_dict()[k].shape}
                net.encoder.load_state_dict(matching,strict=False)
            if freeze:
                net.encoder.requires_grad_(False)
                from learned_probe import inputs
                with torch.no_grad():
                    for row in train:
                        x,imu=inputs(row,settings["variant"],slice(None))
                        row["features"]=torch.cat([net.encoder.features(x[i:i+256],imu[i:i+256])
                                                   for i in range(0,len(x),256)]).numpy()
            validator=None
            if exact and settings.get("feedback"):
                def validator(model):
                    scores=[exact_joint(model,r,cfg)[0]["ate"] for r in eval_parents]
                    return np.mean(scores)
            history=fit_joint(net,train,valid,cfg,seed,cfg["joint"]["epochs"],freeze,validator)
            checkpoint=directory/f"{name}-{seed}.pt"
            torch.save({"state":net.state_dict(),"settings":settings,"config":cfg},checkpoint)
            rows=[joint_score(net,x) for x in valid] if not exact else [exact_joint(net,p,cfg)[0] for p in eval_parents]
            record=dict(model=name,seed=seed,checkpoint=str(checkpoint),sha256=digest(checkpoint),settings=settings,
                        config=cfg,history=history,rows=rows,parameters=sum(p.numel() for p in net.parameters()),
                        train_parents=len({r["path"] for r in train}),closed_loop=exact)
            records.append(record)
            write(directory/"scores.json",records)
            print(name,seed,round(np.mean([r["ate"] for r in rows]),4),flush=True)
            return net
        base=dict(variant="triple_derot",kind="ema",width=32,height=24,embedding=48,hidden=64,capacity=1)
        if args.phase=="teacher":
            if not args.finalists:
                raise ValueError("teacher phase requires a completed finalist run")
            peer_manifest=json.loads((args.finalists/"manifest.json").read_text())
            if peer_manifest["status"]!="completed":
                raise ValueError("finalist run is incomplete")
            prior=json.loads((args.finalists/"scores.json").read_text())
            families=("ema","ssm")
            family=min(families,key=lambda name:np.mean([x["ate"] for row in prior if row["model"]==name for x in row["rows"]]))
            matched=sorted((row for row in prior if row["model"]==family),key=lambda row:np.mean([x["ate"] for x in row["rows"]]))
            reference=matched[len(matched)//2]
            sources=peer_manifest["datasets"]
            if sources!=manifest["datasets"]:
                raise ValueError("teacher and finalist dataset rosters differ")
            data_cfg={**reference["config"],"joint":cfg["joint"]}
            data=read_inputs(sources["train"],data_cfg)
            dev=read_inputs(eval_parents,data_cfg)
            teacher_settings={**reference["settings"],"capacity":2,"embedding":64,"hidden":96}
            torch.manual_seed(0)
            teacher=train_candidate("teacher",teacher_settings,data_cfg,data,dev,0,exact=True)
            teacher_record=records[-1]
            manifest.update(teacher_checkpoint_sha256=teacher_record["sha256"],
                            finalist_source_sha256=reference["sha256"],teacher_targets="training parents only")
            from learned_probe import inputs
            with torch.no_grad():
                for row in data:
                    row["teacher_velocity"]=teacher(*inputs(row,teacher_settings["variant"],slice(None))).numpy()[:,:3]
            for name,w in (("student-labels",0.),("student-motion",.5)):
                for seed in cfg["joint"]["seeds"]:
                    torch.manual_seed(seed)
                    settings={**reference["settings"],"capacity":.5,"embedding":32,"hidden":32,
                              "kind":"ema","teacher_weight":w}
                    train_candidate(name,settings,data_cfg,data,dev,seed,exact=True)
        elif args.phase in ("feedback-smoke","native-bias"):
            stress={**cfg,"disturbance":"changing"}
            native=args.phase=="native-bias"
            data=read_inputs(sources["train"],cfg)+read_inputs(sources["train"][::2] if native else sources["train"],stress)
            dev=read_inputs(eval_parents,cfg)
            for name in ("ema","selective","bias"):
                for seed in cfg["joint"]["seeds"] if native else cfg["joint"]["seeds"][:2]:
                    torch.manual_seed(seed)
                    settings={**base,"kind":"ema" if name=="ema" else "selective","packet_mode":"ordered"}
                    if name=="bias":
                        settings.update(feedback=True,bias_head=True)
                    net=train_candidate(name,settings,cfg,data,dev,seed,exact=True)
                    row=records[-1]
                    row["moving_stress"]=[]
                    for episode in eval_parents:
                        values,bias,added=exact_joint(net,episode,stress,crop=5.)
                        _,clean,_=exact_joint(net,episode,cfg,crop=5.)
                        values["added_bias_rmse_rad_s"]=float(np.sqrt(np.mean((bias-clean-added)**2)))
                        if name=="bias":
                            disabled=exact_joint(net,episode,stress,crop=5.,feedback=False)
                            values["disabled_feedback_ate"]=disabled[0]["ate"]
                            _,clean_disabled,_=exact_joint(net,episode,cfg,crop=5.,feedback=False)
                            values["disabled_added_bias_rmse_rad_s"]=float(
                                np.sqrt(np.mean((disabled[1]-clean_disabled-added)**2)))
                        row["moving_stress"].append(values)
                    if native:
                        row["startup_policy"]=[exact_joint(net,r,{**cfg,"policy":"startup"})[0] for r in eval_parents]
                        if name=="bias":
                            row["disabled_feedback"]=[exact_joint(net,r,cfg,feedback=False)[0] for r in eval_parents]
                    write(directory/"scores.json",records)
            manifest["scope"]=("native-only calibration pilot, before expanded-data selection" if native else
                               "small proxy closed-loop test of the feedback path; separate from finalist selection")
        elif args.phase=="screen":
            for name,changes in (("subset",{}),("expanded",{}),("wider",{"capacity":2}),("resolution",{"width":48,"height":36}),
                                 ("raw",{"variant":"triple_raw"})):
                settings={**base,**changes}
                spec={**cfg,"width":settings["width"],"height":settings["height"]}
                train_parents=sources["train"]
                if name=="subset":
                    train_parents=list({r["scene"]:r for r in reversed(train_parents) if r["domain"]=="proxy"}.values())
                train=read_inputs(train_parents,spec)
                dev=read_inputs(eval_parents,spec)
                for seed in cfg["joint"]["seeds"][:2]:
                    torch.manual_seed(seed)
                    train_candidate(name,settings,spec,train,dev,seed)
            ranking={name:np.mean([x["ate"] for r in records if r["model"]==name for x in r["rows"]])
                     for name in ("expanded","wider","resolution","raw")}
            winner=min(ranking,key=ranking.get)
            chosen=next(r for r in records if r["model"]==winner and r["seed"]==0)
            spec=chosen["config"]
            train,dev=read_inputs(sources["train"],spec),read_inputs(eval_parents,spec)
            for seed in cfg["joint"]["seeds"][:2]:
                source=next(r for r in records if r["model"]==winner and r["seed"]==seed)
                pretrained=Joint(source["settings"])
                pretrained.load_state_dict(torch.load(source["checkpoint"],weights_only=True)["state"])
                for kind in ("frame","ema","ssm","selective","gru"):
                    torch.manual_seed(seed)
                    settings={**source["settings"],"kind":kind}
                    train_candidate(f"frozen-{kind}",settings,spec,train,dev,seed,pretrained.encoder.state_dict(),True)
            manifest.update(selected_visual=winner,visual_ranking=ranking)
        else:
            if args.screen_run is None:
                raise ValueError("finalists need a completed screen run")
            screen=json.loads((args.screen_run/"manifest.json").read_text())
            screened=json.loads((args.screen_run/"scores.json").read_text())
            if screen["status"]!="completed":
                raise ValueError("screen is incomplete")
            model="frozen-"+min(("ssm","selective"),key=lambda k:np.mean([x["ate"] for r in screened if r["model"]==f"frozen-{k}" for x in r["rows"]]))
            chosen=next(r for r in screened if r["model"]==model)
            spec={**chosen["config"],"policy":"rolling","joint":cfg["joint"]}
            train=read_inputs(sources["train"],spec)
            clean_dev=read_inputs(eval_parents,spec)
            stress={**spec,"disturbance":"changing"}
            mixed=(train+read_inputs(sources["train"][::4],stress)+
                   read_inputs(sources["train"][2::8],{**spec,"disturbance":"constant"}))
            # Equivalent training for the full control and fused SSM. Disabled feedback is scored on the same weights.
            variants=[("ema",{"kind":"ema","packet_mode":"ordered"}),
                      ("proxy_ema",{"kind":"ema","packet_mode":"ordered"}),
                      ("ssm",{"packet_mode":"ordered"}),
                      ("summary",{"packet_mode":"summary"}),
                      ("bias",{"packet_mode":"ordered","bias_head":True,"feedback":True}),
                      ("vision",{}),("imu",{"variant":"imu","packet_mode":"ordered"})]
            for name,extra in variants:
                seeds=cfg["joint"]["seeds"] if name in ("ema","ssm","bias") else cfg["joint"]["seeds"][:2]
                for seed in seeds:
                    torch.manual_seed(seed)
                    settings={**chosen["settings"],**extra}
                    train_set=mixed if name in ("ema","ssm","summary","bias") else train
                    if name=="proxy_ema":
                        train_set=[row for row in mixed if row["tier"]!="benchmark"]
                    pretrain=next(r for r in screened if r["model"]==model and r["seed"]==seed%2)
                    reference=Joint(pretrain["settings"])
                    reference.load_state_dict(torch.load(pretrain["checkpoint"],weights_only=True)["state"])
                    net=train_candidate(name,settings,spec,train_set,clean_dev,seed,
                                        reference.encoder.state_dict(),exact=True)
                    rec=records[-1]
                    rec["moving_stress"]=[]
                    for parent in eval_parents:
                        row,pred,added=exact_joint(net,parent,stress,crop=5.)
                        if name=="bias":
                            _,clean_bias,_=exact_joint(net,parent,spec,crop=5.)
                            row["added_bias_rmse_rad_s"]=float(np.sqrt(np.mean((pred-clean_bias-added)**2)))
                            row["disabled_feedback_ate"]=exact_joint(net,parent,stress,crop=5.,feedback=False)[0]["ate"]
                        rec["moving_stress"].append(row)
                    if name in ("ema","ssm","bias"):
                        rec["startup_policy"]=[exact_joint(net,parent,{**spec,"policy":"startup"})[0] for parent in eval_parents]
                    if name=="bias":
                        rec["disabled_feedback"]=[exact_joint(net,parent,spec,feedback=False)[0] for parent in eval_parents]
                    if name=="ssm":
                        net.settings["reset_seconds"]=1.
                        rec["reset_1s"]=[exact_joint(net,parent,spec)[0] for parent in eval_parents]
                        net.settings.pop("reset_seconds")
                    write(directory/"scores.json",records)
            manifest["screen_run"]=str(args.screen_run)
            manifest["screen_manifest_sha256"]=digest(args.screen_run/"manifest.json")
        manifest["status"]="completed"
    except BaseException as e:
        manifest.update(status="failed",error=repr(e))
        raise
    finally:
        write(directory/"manifest.json",manifest)


if __name__ == "__main__":
    import sys
    if sys.argv[1:2]==["--joint"]:
        sys.argv.pop(1)
        joint_main()
    else:
        main()
