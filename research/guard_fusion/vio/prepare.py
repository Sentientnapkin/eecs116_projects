"""Make isolated, reproducible VIO source variants from the pinned checkout."""
from pathlib import Path
import argparse, shutil, hashlib, json, difflib
ROOT = Path(__file__).resolve().parents[3]
PIN = Path('/data/backups/rganapa/Sebastian/viobench-provided-openvins/viobench/solution/examples/native')

def replace(s, old, new):
    if old not in s: raise RuntimeError('missing patch context: '+old[:100])
    return s.replace(old,new,1)

def vins(s):
    s=replace(s,'    Pose camera0;','''    Pose camera0;
    // Recovery uses a new local initialization epoch and a persistent ABI gauge.
    // No optimized state from before a reset is reused as a new estimator prior.
    Pose recovery_origin;
    Pose last_output;
    Vec3 last_output_velocity = Vec3::Zero(); // first-camera axes
    bool restarted = false, recovering = false, injected_reset = false;
    double recovery_time = 0;
    long frame_count = 0;''')
    s=replace(s,'        if (state.estimator) throw std::runtime_error("init called twice");','        state = State{}; // init is a full deterministic reset, including recovery state')
    s=replace(s,'        estimator.processImage(observations, header);','''        estimator.processImage(observations, header);
#ifdef VIO_FAULT_RESET_SECONDS
        if (!state.injected_reset && state.output_ready && time - state.first_time >= VIO_FAULT_RESET_SECONDS) {
            estimator.clearState();
            estimator.setParameter();
            state.injected_reset = true;
            std::fprintf(stderr, "TEL forced_reset t=%.6f\\n", time);
        }
#endif
        ++state.frame_count;
#ifdef VIO_TELEMETRY
        std::fprintf(stderr, "TEL vins f=%ld t=%.6f solver=%d tracks=%zu features=%zu bg=%.6f ba=%.6f\\n",
                     state.frame_count, time, int(estimator.solver_flag), observations.size(), estimator.f_manager.feature.size(),
                     estimator.Bgs[WINDOW_SIZE].norm(), estimator.Bas[WINDOW_SIZE].norm());
#endif''')
    s=replace(s,'            if (state.output_ready) throw std::runtime_error("estimator reset after initialization; original camera frame was lost");','''            if (state.output_ready) {
                // The estimator deliberately rebooted; retain the last camera pose
                // in the ABI gauge and start a new bounded local IMU history.
                state.recovery_origin = state.last_output;
                state.recovery_origin.position += state.last_output_velocity * (time - state.last_time);
                state.recovery_time = state.first_time = time;
                state.initial_rotation.setIdentity();
                state.history.assign(1, latest);
                state.output_ready = false;
                state.restarted = state.recovering = true;
                std::fprintf(stderr, "TEL vins_recovery t=%.6f\\n", time);
            }''')
    # last_time currently updated before reset branch; need previous dt preserve.
    s=replace(s,'        state.last_time = time;','        const double previous_frame_time = state.last_time;\n        state.last_time = time;')
    s=replace(s,'state.last_output_velocity * (time - state.last_time)','state.last_output_velocity * (time - previous_frame_time)')
    s=replace(s,'                state.output_ready = true;','''                if (state.recovering && estimator.Vs[WINDOW_SIZE].norm() > 6.0) {
                    // An implausible dynamic initializer is not a metric recovery.
                    // Continue the bounded prediction while it refines its scale.
                } else {
                    if (state.recovering) {
                        const double age = time - state.recovery_time;
                        state.recovery_origin.position += state.last_output_velocity * (1.0 - std::exp(-age));
                        state.recovery_origin.rotation *= state.R_camera_imu * state.initial_rotation * state.R_camera_imu.transpose();
                        // Anchor the current optimized camera, never backintegrate
                        // a second uncertain velocity to the reboot exposure.
                        state.camera0 = camera_pose(estimator.Rs[WINDOW_SIZE], estimator.Ps[WINDOW_SIZE]);
                    }
                    state.output_ready = true;
                    state.recovering = false;
                }''')
    s=replace(s,'                state.history.clear();','                if (state.output_ready) state.history.clear();')
    s=replace(s,'            for (int i = 0; i < 4; ++i) out[i + 3] = orientation.coeffs()[i];','''            for (int i = 0; i < 4; ++i) out[i + 3] = orientation.coeffs()[i];
            if (state.recovering) {
                // Previous metric velocity expires over one second; never amplify
                // uncertain inertial translation during a fresh initialization.
                const double age = time - state.recovery_time;
                const double decay = std::exp(-age);
                state.last_output.rotation = state.recovery_origin.rotation * orientation.toRotationMatrix();
                state.last_output.position = state.recovery_origin.position + state.last_output_velocity * (1.0 - decay);
                const Eigen::Quaterniond recovered(state.last_output.rotation);
                const Vec3 v_camera = state.last_output.rotation.transpose() * state.last_output_velocity * decay;
                for (int i = 0; i < 3; ++i) { out[i] = state.last_output.position[i]; out[i + 7] = v_camera[i]; }
                for (int i = 0; i < 4; ++i) out[i + 3] = recovered.coeffs()[i];
            }''')
    s=replace(s,'        const Vec3 position = state.camera0.rotation.transpose() * (camera.position - state.camera0.position);','        Vec3 position = state.camera0.rotation.transpose() * (camera.position - state.camera0.position);')
    s=replace(s,'        orientation.normalize();\n        if (orientation.w()', '''        orientation.normalize();
        if (state.restarted) {
            position = state.recovery_origin.position + state.recovery_origin.rotation * position;
            orientation = Eigen::Quaterniond(state.recovery_origin.rotation) * orientation;
            orientation.normalize();
        }
        state.last_output = {orientation.toRotationMatrix(), position};
        if (orientation.w()''')
    s=replace(s,'        const Vec3 angular_velocity = state.R_camera_imu * omega;\n        for (int i = 0;', '        const Vec3 angular_velocity = state.R_camera_imu * omega;\n        state.last_output_velocity = state.last_output.rotation * velocity;\n        for (int i = 0;')
    return s

def openvins(s):
    s=replace(s,'    bool anchored = false;','''
    bool anchored = false;
    double last_visual_time = -1;
    Eigen::Vector3d last_graph_velocity = Eigen::Vector3d::Zero();
    double last_graph_time = -1;
    bool graph_guarded = false;''')
    old='''        if (graph.state_at(t, smoothed)) {
            rotation = ov_core::quat_2_Rot(smoothed.head<4>());
            position = smoothed.segment<3>(4);
            velocity = rotation * smoothed.segment<3>(7);
            gyro_bias = smoothed.segment<3>(10);
        }'''
    new='''        if (graph.state_at(t, smoothed)) {
            bool accept_graph = true;
#ifdef VIO_OUTPUT_GUARD
            // Output-only intervention: graph optimization and image tracking
            // stay independent. A rejected graph falls back to its live EKF.
            const Eigen::Matrix3d graph_R = ov_core::quat_2_Rot(smoothed.head<4>());
            const Eigen::Vector3d graph_v = smoothed.segment<3>(7);
            const double speed = graph_v.norm();
            const double dt = state.last_graph_time >= 0 ? t - state.last_graph_time : 0;
            const bool implausible = !smoothed.allFinite() || speed > 6.0 ||
                (dt > 0 && (graph_v - state.last_graph_velocity).norm() > 12.0 * dt);
            if (graph.last_visual_factors > 0) state.last_visual_time = t;
            const bool visual_starved = graph.optimizations > 0 && state.last_visual_time >= 0 && t - state.last_visual_time > 1.0;
            accept_graph = !(implausible || visual_starved);
            // Keep derivative history tied to this graph, not its fallback.
            // Only the primary graph owns history; conservative output has its
            // own speed gate so two streams never mix derivative histories.
            if (!is_conservative) {
                state.last_graph_velocity = graph_v;
                state.last_graph_time = t;
                state.graph_guarded = !accept_graph;
            }
            if (is_conservative) accept_graph = smoothed.allFinite() && speed <= 6.0;
#endif
            if (accept_graph) {
                rotation = ov_core::quat_2_Rot(smoothed.head<4>());
                position = smoothed.segment<3>(4);
                velocity = rotation * smoothed.segment<3>(7);
                gyro_bias = smoothed.segment<3>(10);
            }
        }'''
    s=replace(s,old,new)
    s=replace(s,'        output_to_abi(combined, out);','''
#ifdef VIO_TELEMETRY
        const double spread = std::max({(chain.position-anchor.position).norm(),
            (chain.position-conservative.position).norm(), (anchor.position-conservative.position).norm()});
        std::fprintf(stderr, "TEL ov f=%ld t=%.6f init=%d/%d factors=%zu/%zu/%zu cost=%.6g/%.6g/%.6g spread=%.6f guarded=%d/%d\\n",
            chain_state.frames, t, int(chain_state.vio->started()), int(anchor_state.vio->started()),
            chain_state.vio->smoother.last_visual_factors, anchor_state.vio->smoother.last_visual_factors,
            chain_state.vio->conservative->last_visual_factors,
            chain_state.vio->smoother.last_final_cost, anchor_state.vio->smoother.last_final_cost,
            chain_state.vio->conservative->last_final_cost, spread,
            int(chain_state.graph_guarded), int(anchor_state.graph_guarded));
#endif
        output_to_abi(combined, out);''')
    return s

def telemetry_only(name, original, patched):
    if name == 'vins_mono':
        text=replace(original,'    Pose camera0;','    Pose camera0;\n    long frame_count = 0;')
        begin=patched.index('        ++state.frame_count;')
        end=patched.index('#endif',begin)+len('#endif')
        text=replace(text,'        estimator.processImage(observations, header);','        estimator.processImage(observations, header);\n'+patched[begin:end])
    else:
        text=replace(original,'    bool anchored = false;','    bool anchored = false;\n    bool graph_guarded = false;')
        begin=patched.index('#ifdef VIO_TELEMETRY',patched.index('int32_t step('))
        end=patched.index('#endif',begin)+len('#endif')
        text=replace(text,'        output_to_abi(combined, out);',patched[begin:end]+'\n        output_to_abi(combined, out);')
    return text

def main():
    p=argparse.ArgumentParser(); p.add_argument('--out',default='/dev/shm/sebastian-vio/guard-fixes'); a=p.parse_args()
    dest=Path(a.out); dest.mkdir(parents=True,exist_ok=True)
    manifest={}
    for name, patch in [('vins_mono',vins),('openvins',openvins)]:
        src=PIN/name; out=dest/name
        if not out.exists(): shutil.copytree(src,out,ignore=shutil.ignore_patterns('build'))
        old=(src/'solution.cpp').read_text(); new=patch(old); (out/'solution.cpp').write_text(new)
        diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/solution.cpp',tofile='b/solution.cpp'))
        (ROOT/'research/guard_fusion/vio'/f'{name}.patch').write_text(diff)
        telemetry = telemetry_only(name, old, new)
        tel_diff=''.join(difflib.unified_diff(old.splitlines(True),telemetry.splitlines(True),fromfile='a/solution.cpp',tofile='b/solution.cpp'))
        (ROOT/'research/guard_fusion/telemetry'/f'{name}.patch').write_text(tel_diff)
        manifest[name]={'source':str(src),'source_sha256':hashlib.sha256(old.encode()).hexdigest(),'patched_sha256':hashlib.sha256(new.encode()).hexdigest(),'out':str(out)}
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
