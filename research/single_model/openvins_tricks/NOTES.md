# openvins_tricks notes
Full write-up: research_notes/GP MSCKF micro optimizations and edge cases/openvins_estimator_tricks.md
Files: ox.c (on fgt.c), oy.c (on inventive/adopted.c), ob.c (on frontend/adopted_fbh.c = B6), ob_arms.patch (diff vs B6), job.sh/job2.sh/run.sh/queue*.txt, cmprep.py (3-replicate compare), fcmp.py (fresh compare), logs log_*.
Arms table (B6, fresh d / search 3-rep d): OC +0.085 / +0.152; FEJ-att +0.026 / +0.079; FEJ-pos +1.24 / +1.26; FEJ H+F +1.244 / +1.409; BLR40 +0.036 / +0.033; MID +0.026 / +0.049. Nothing adopted; no patch.
Key diagnostic: H n_yaw (current poses) = 1e-16 relative -> Jacobian correct; roundoff perturbation alone moves search mean 0.845 -> 0.909.
