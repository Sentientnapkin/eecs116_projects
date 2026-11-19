"""Shared causal image history and NumPy guest inference."""
from collections import deque

import cv2
import numpy as np

from orientation import Orientation, exp_so3, rotation_proposal

CHANNELS = {
    "imu": [], "triple_raw": [0,1,7,4,8], "pair_raw": [0, 1, 4], "pair_derot": [0, 2, 5],
    "triple_derot": [0, 2, 3, 5, 6], "pair_derot+imu": [0, 2, 5],
    "triple_derot+imu": [0, 2, 3, 5, 6],
}


def portable_warp(frame, inverse, pixels, fast=False):
    """Inverse bilinear sampling with a zero border and 1/32-pixel coordinates."""
    h, w = frame.shape
    source = inverse @ pixels
    depth = source[2]
    valid_depth = (np.abs(depth) > 1e-12)
    xy = source[:2] / np.where(valid_depth, depth, 1.)
    fixed = np.floor(np.clip(xy, -2, max(h,w)+2)*32 + .500000001).astype(np.int32)
    x, y = fixed // 32
    dx, dy = fixed % 32
    if fast:
        coordinates = (fixed//32).T.reshape(h,w,2).astype(np.int16)
        fractions = (dy*32+dx).reshape(h,w).astype(np.uint16)
        stacked = np.stack((frame, np.full_like(frame,255)), axis=-1)
        result = cv2.remap(stacked, coordinates, fractions, cv2.INTER_LINEAR)
        return result[...,0], np.where(result[...,1]==255,255,0).astype(np.uint8)
    weight_sum = np.zeros(len(x), dtype=np.int32)
    value_sum = weight_sum.copy()
    for i, j, weight in ((0,0,(32-dx)*(32-dy)), (1,0,dx*(32-dy)),
                         (0,1,(32-dx)*dy), (1,1,dx*dy)):
        u, v = x+i, y+j
        valid = valid_depth & (u>=0) & (u<w) & (v>=0) & (v<h)
        weight = np.where(valid, weight, 0)
        value_sum += frame[np.clip(v,0,h-1), np.clip(u,0,w-1)] * weight
        weight_sum += weight
    image = ((value_sum+512)//1024).astype(np.uint8).reshape(h,w)
    mask = np.where(weight_sum*255+512>=1024*255, 255, 0).astype(np.uint8).reshape(h,w)
    return image, mask


class Inputs:
    def __init__(self, cfg, K, shape, R_bc):
        self.cfg = cfg
        self.width, self.height = cfg["width"], cfg["height"]
        h, w = shape
        sx, sy = self.width / w, self.height / h
        self.K = np.array([[K["fx"] * sx, 0, (K["cx"] + .5) * sx - .5],
                           [0, K["fy"] * sy, (K["cy"] + .5) * sy - .5], [0, 0, 1.]])
        self.inverse = np.linalg.inv(self.K)
        self.R_bc = R_bc
        self.orient = Orientation(cfg)
        self.history = deque()
        self.previous_image = None
        self.previous_time = None
        self.last_calibration = None
        self.rotation_probe = None
        self.trace = None
        self.pixels = None
        if self.cfg.get("portable_pixels"):
            yy, xx = np.indices((self.height,self.width))
            self.pixels = np.stack((xx.ravel(), yy.ravel(), np.ones(xx.size)))
        self.mask = np.full((self.height, self.width), 255, dtype=np.uint8)

    def step(self, t, image, packet, variant=None):
        available = image is not None
        if not available:
            image = np.zeros((self.height,self.width),dtype=np.uint8)
        if image.ndim == 3:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        cur = cv2.resize(image, (self.width, self.height), interpolation=cv2.INTER_AREA)
        if self.trace is not None:
            self.trace["resized"] = cur
        difference = (np.abs(cur.astype(np.float32)-self.previous_image).mean()/255
                      if self.previous_image is not None else 0)
        if not available or self.previous_image is None:
            difference = float("inf") if not available else difference
        dt = 0. if self.previous_time is None else t-self.previous_time
        self.previous_time, self.previous_image = t, cur if available else None
        if self.trace is not None:
            previous = t if self.orient.previous is None else self.orient.previous
            self.trace["integration_intervals"] = np.diff(
                np.r_[previous, np.maximum.accumulate(np.clip(packet[:,0], previous, t)), t])
            self.trace["image_difference"] = difference if np.isfinite(difference) else -1.
        previous_checks = self.orient.checked_windows
        previous_rejections = self.orient.rejected_windows
        R = self.orient.step(t, packet, difference)
        if (self.cfg.get("reliability") and self.orient.checked_windows != previous_checks
                and self.orient.rejected_windows == previous_rejections):
            self.last_calibration = t
        if self.rotation_probe:
            R = self.rotation_probe.step(t, image, R, self.orient.bias)
            self.orient.R = R
        gyro = packet[:, 4:7].mean(0) - self.orient.total_bias if len(packet) else np.zeros(3)
        imu = np.r_[packet[:, 1:4].mean(0)/9.81 if len(packet) else np.zeros(3),
                    gyro, packet[:, 1:7].std(0) if len(packet) else np.zeros(6),
                    float(bool(len(packet))), dt, self.K[0, 0]/self.width].astype(np.float32)
        if self.cfg.get("ordered_packet"):
            ends = t-dt + dt*np.arange(1,5)/4
            bins = np.minimum(np.searchsorted(ends,packet[:,0]-1e-8),3)
            pieces = []
            for i in range(4):
                samples = packet[bins==i,1:]
                if len(samples):
                    mean = samples.mean(0)
                    mean[:3] /= 9.81
                    mean[3:] -= self.orient.total_bias
                else:
                    mean = np.zeros(6)
                pieces.extend([*mean, min(len(samples)/4,1.)])
            imu = np.r_[imu,pieces,self.orient.bias,self.orient.learned_bias,
                        float(self.orient.activated),float(available)].astype(np.float32)
        blank = np.zeros_like(cur)
        if variant == "imu":
            return np.empty((0, self.height, self.width), np.uint8), imu, R, gyro
        images = [cur, blank, blank, blank, blank, blank, blank]
        images += [blank,blank]
        matches = 0
        for index, age in enumerate(self.cfg["baselines"]):
            if variant is not None and index == 1 and not variant.startswith("triple"):
                break
            match = next((row for row in reversed(self.history) if row[0] <= t-age+1e-8), None)
            if match is None:
                continue
            matches += 1
            _, frame, previous_R = match
            if index == 0:
                images[1], images[4] = frame, self.mask
            if index == 1 and len(images)>7:
                images[7],images[8] = frame,self.mask
            if variant in ("pair_raw","triple_raw"):
                continue
            rotation = self.R_bc.T @ R.T @ previous_R @ self.R_bc
            homography = self.K @ rotation @ self.inverse
            if self.trace is not None:
                self.trace[f"homography_{index}"] = homography
            shape = (self.width, self.height)
            if self.pixels is None:
                images[2+index] = cv2.warpPerspective(frame, homography, shape)
                valid = cv2.warpPerspective(self.mask, homography, shape)
                images[5+index] = np.where(valid == 255, 255, 0).astype(np.uint8)
            else:
                inverse = self.K @ rotation.T @ self.inverse
                images[2+index], images[5+index] = portable_warp(
                    frame, inverse, self.pixels, self.cfg.get("portable_pixels") == "remap")
        if available:
            self.history.append((t, cur, R))
        age = self.cfg["baselines"][-1]
        while len(self.history) > 2 and self.history[1][0] <= t-age+1e-8:
            self.history.popleft()
        if self.cfg.get("reliability"):
            time_since = 1. if self.last_calibration is None else min((t-self.last_calibration)/4, 1.)
            imu = np.r_[imu, time_since, min((t-self.orient.origin)/2,1.), matches/2,
                        min(len(packet)/10,1.)].astype(np.float32)
        selected = images if variant is None else [images[i] for i in CHANNELS[variant]]
        return np.stack(selected), imu, R, gyro


def linear(x, w, key):
    return w[key+".weight"] @ x + w.get(key+".bias", 0.)


class Temporal:
    def __init__(self, kind, weights, zero_initial_state=False):
        self.kind, self.w = kind, weights
        self.zero_initial_state = zero_initial_state
        self.state = None

    def step(self, x, dt):
        w = self.w
        if self.kind == "frame":
            return linear(x, w, "out")
        if self.kind == "gru":
            if self.state is None:
                self.state = np.zeros(w["gru.bias_hh_l0"].size // 3, dtype=np.float32)
            ir, iz, n = np.split(w["gru.weight_ih_l0"] @ x + w["gru.bias_ih_l0"], 3)
            hr, hz, hn = np.split(w["gru.weight_hh_l0"] @ self.state + w["gru.bias_hh_l0"], 3)
            r = 1 / (1 + np.exp(-np.clip(ir+hr, -60, 60)))
            z = 1 / (1 + np.exp(-np.clip(iz+hz, -60, 60)))
            self.state = (1-z) * np.tanh(n+r*hn) + z*self.state
        else:
            value = x if self.kind == "ema" else linear(x, w, "inp")
            rate = 2. if self.kind == "ema" else np.exp(np.clip(w["log_rate"],-4,5))
            if self.state is None:
                self.state = np.zeros_like(value) if self.zero_initial_state else value
            else:
                step = dt
                if self.kind == "selective":
                    step = step * np.logaddexp(0, linear(x,w,"gate")+.5413)
                a = np.exp(-step * rate)
                self.state = a * self.state + (1-a) * value
        return linear(np.concatenate((x, self.state)), w, "out")


def convolution(x, weights, bias, padding):
    size = weights.shape[-1]
    x = np.pad(x, ((0, 0), (padding, padding), (padding, padding)))
    # Gather strided neighborhoods without relying on optional NumPy wrappers.
    height, width = (x.shape[1]-size)//2+1, (x.shape[2]-size)//2+1
    shape = (x.shape[0], height, width, size, size)
    c, h, w = x.strides
    patches = np.lib.stride_tricks.as_strided(x, shape=shape, strides=(c, 2*h, 2*w, h, w))
    patches = patches.transpose(1, 2, 0, 3, 4).reshape(height*width, -1)
    result = patches @ weights.reshape(weights.shape[0], -1).T + bias
    return result.T.reshape(weights.shape[0], height, width)


class Predictor:
    def __init__(self, variant, encoder, kind=None, temporal=None, settings=None):
        self.variant, self.encoder = variant, encoder
        self.settings = settings or {}
        self.trace = None
        self.head = Temporal(kind, temporal, self.settings.get("zero_initial_state", False)) if kind else None

    def step(self, images, imu):
        w = self.encoder
        if "sensor.weight" in w:
            packet = imu if self.settings["packet_mode"]=="ordered" else np.r_[imu[:15],imu[-8:]]
            x = np.maximum(0,linear(packet,w,"sensor"))
        else:
            x = imu[:15] if self.variant == "imu" or self.variant.endswith("+imu") else imu[14:15]
        if len(images):
            image = images.astype(np.float32)/255-.5
            for name, padding in (("conv.0", 2), ("conv.2", 1)):
                image = np.maximum(0, convolution(image, w[name+".weight"], w[name+".bias"], padding))
            x = np.concatenate((image.ravel(), x))
        feature = np.maximum(0, linear(x, w, "encode"))
        output = self.head.step(feature, imu[13]) if self.head else linear(feature, w, "head")
        if self.trace is not None:
            self.trace.update(embedding=feature, prediction=output)
            if self.head and self.head.state is not None:
                self.trace["state"] = self.head.state
        return output


class RotationCorrection:
    def __init__(self, camera, R_bc, method, coefficients):
        sx, sy = 160/camera["width"], 120/camera["height"]
        self.K = np.array([[camera["fx"]*sx, 0, (camera["cx"]+.5)*sx-.5],
                           [0, camera["fy"]*sy, (camera["cy"]+.5)*sy-.5], [0,0,1.]])
        self.R_bc, self.method, self.coefficients = R_bc, method, coefficients
        self.anchor = None
        self.accepted = 0
        self.windows = 0

    def step(self, t, image, R, bias):
        if self.anchor is not None and t-self.anchor[0] < .5-1e-8:
            return R
        frame = cv2.resize(image, (160,120), interpolation=cv2.INTER_AREA)
        if self.anchor is not None:
            anchor_t, anchor_frame, anchor_R = self.anchor
            _, gated, delta = rotation_proposal(anchor_frame, frame, self.K, self.R_bc,
                                                 anchor_R.T @ R, bias, t-anchor_t,
                                                 self.method, self.coefficients)
            self.windows += 1
            self.accepted += gated
            if gated:
                R = R @ exp_so3(delta)
        self.anchor = t, frame, R
        return R


def quaternion(R):
    axis = cv2.Rodrigues(R)[0].ravel()
    angle = np.linalg.norm(axis)
    vector = axis * (np.sin(angle/2)/angle) if angle > 1e-10 else axis/2
    return np.r_[vector, np.cos(angle/2)]


class Estimator:
    """VIOBench ABI with the first observed camera as the pose origin."""
    frame_width = 320

    def __init__(self, camera, model, cfg):
        T = np.asarray(camera["T_cam_imu"])
        self.R_bc = T[:3, :3].T
        self.offset = -self.R_bc @ T[:3, 3]
        self.inputs = Inputs(cfg, camera, (camera["height"], camera["width"]), self.R_bc)
        if model.get("rotation_method"):
            self.inputs.rotation_probe = RotationCorrection(camera, self.R_bc, model["rotation_method"],
                                                             model.get("rotation_weights"))
        self.settings = model.get("settings") or {}
        self.model = Predictor(model["variant"], model["encoder"], model["kind"], model["temporal"], self.settings)
        self.reset_seconds = self.settings.get("reset_seconds")
        self.last_reset = None
        self.last_velocity = None
        self.position = np.zeros(3)
        self.trace = None

    def step(self, t, frame, packet):
        if self.trace is not None:
            import hashlib
            self.inputs.trace = self.model.trace = self.trace
            self.trace.update(time=t, packet=packet, intrinsics=self.inputs.K,
                              delivered=hashlib.sha256(frame.tobytes()).hexdigest() if frame is not None else None)
        stage = self.settings.get("profile_stage")
        if stage=="abi":
            return np.array([0,0,0,0,0,0,1,0,0,0,0,0,0],dtype=float)
        if self.last_velocity is None:
            packet = packet[:0]
        input_variant = "imu" if stage in ("orientation","resize") else self.model.variant
        image = None if stage=="orientation" else frame
        images, imu, R, gyro = self.inputs.step(t,image,packet,input_variant)
        if self.last_reset is None or (self.reset_seconds and t-self.last_reset>=self.reset_seconds):
            self.last_reset = t
            if self.model.head:
                self.model.head.state = None
        output = (np.zeros(3) if stage in ("orientation","resize","warp") else self.model.step(images,imu))
        if self.trace is not None:
            orientation = self.inputs.orient
            self.trace.update(images=images, imu=imu, rotation=R,
                              calibrated=orientation.activated, cal_bias=orientation.bias.copy(),
                              learned_bias=orientation.learned_bias.copy(), accepted=orientation.accepted_at)
        vb = output[:3]
        if self.settings.get("feedback") and len(output)>3:
            self.inputs.orient.update_feedback(.12*np.tanh(output[3:]),imu[13],bool(len(packet) and frame is not None))
        velocity = R @ vb
        if self.last_velocity is not None:
            self.position += .5 * self.inputs_dt(t) * (velocity+self.last_velocity)
        self.last_t, self.last_velocity = t, velocity
        camera = self.R_bc.T @ (self.position + R @ self.offset-self.offset)
        if self.trace is not None:
            self.trace.update(camera=camera, body_position=self.position.copy())
        q = quaternion(self.R_bc.T @ R @ self.R_bc)
        angular = packet[-1, 4:7] - self.inputs.orient.total_bias if len(packet) else gyro
        return np.r_[camera, q, self.R_bc.T @ (vb + np.cross(angular, self.offset)),
                     self.R_bc.T @ angular]

    def inputs_dt(self, t):
        return t - self.last_t
