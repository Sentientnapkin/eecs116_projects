# Manhattan yaw anchor prototype

This is a bounded experimental C++ state module, not yet connected to the guest. It accepts
line directions from a future calibrated/gravity-rectified front end, rejects weak or spatially
concentrated evidence, requires three stable observations, and applies a capped, low-gain yaw
correction. Reset restores the first-camera relative frame. It never uses velocity direction.

Important limitation: raw image line angle alone does not determine world yaw. The caller must
provide gravity-rectified line directions and a candidate yaw residual derived from calibrated
camera geometry. The current `update` function illustrates temporal acceptance/gain only; its
residual calculation is a placeholder and must be replaced before any replay or deployment.
No accuracy or fuel evaluation has been run.
