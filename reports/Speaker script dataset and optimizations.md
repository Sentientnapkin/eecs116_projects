# Speaker script: dataset and GP + MSCKF optimization slides (~5–6 min)

## 1. Dataset Creation (~60 s)
"Our first GP + MSCKF scored 0.75 meters on the public episodes. On the server it scored 3.2 meters, more than four times worse. When we looked at the server's published stats, the reason was clear: server flights cover about 60 meters of path per minute, while the public flights cover only about 18. So the public set wasn't representative. And to train any learned component, we needed thousands of flights, not ten.

So we built our own dataset with the same simulator the course uses. We rendered HSSD houses and ProcTHOR rooms, generated both hover starts and starts where the drone is already flying, and raised the planner's speed limits to get server-like 40-to-80-meter paths. We then checked our holdout against the server's published numbers. Path length was 59.4 versus 59.6 meters, and room size was 4.70 versus 4.69 meters, so the two match closely."

## 2. Dataset Splits (~40 s)
"We aimed to split by room, but it wasn't perfect: some holdout rooms also appear in some of our earlier training and tuning flights, so we can't rule out a small benefit from that. About 1,900 flights are for training the learned models. About 1,600 are for tuning, which is where we compare ideas and pick settings, with separate dev and confirm halves. And 240 are a holdout we treat as a final exam: each finished build gets scored on it exactly once. Inside the tuning set we also built a deliberately hard slice of fast flights in rooms with almost no texture, because that's where the server kept beating us."

## 3. Startup & Velocity Net (~60 s)
"The first big problem was the start. The filter began every flight assuming zero velocity, so when the drone was already flying, it locked in a large error in the first few seconds and never recovered.

Our first fix was a startup gate. From the first IMU readings, we detect whether the drone is moving. If it is, we assume it's flying forward at a typical speed. If it's hovering, we use that still moment to estimate the sensor biases and gravity. That alone took the server error from 3.22 to 1.24 meters, a 61 percent cut.

But a guess can be wrong. So we replaced it with a small neural network: about 105 thousand parameters, written in plain C. It looks at two low-resolution frames and outputs the drone's velocity along with how confident it is. It runs once, around frame five, and the filter treats it as just another measurement. On the holdout that cut error from 0.88 to 0.74 meters, and almost all of the gain came on mid-flight starts."

## 4. Re-anchoring, Robustness & Fuel (~75 s)
"Next, flights still drifted later on, when the camera lost track of things. So whenever the filter's own velocity uncertainty goes above 0.25 meters per second, we re-run the net and re-anchor the velocity. We also re-linearize and update a second time when the state moves a lot. That brought the holdout to 0.56 meters, and the server to 0.78.

Then we turned to fuel, because the score rewards low compute as much as low error. We moved feature tracking and patch matching to integer SIMD. We also added a per-frame budget governor: since only the most expensive frame counts, any optional work that doesn't fit in this frame waits for the next one. Peak compute dropped about five times, from 17 million to 4 million operations per frame, at the same accuracy.

Along the way, an ablation showed our old movement gate had become harmful, so we removed it. We also added an IMU sanitizer and a watchdog so bad sensor data can never crash an episode. The server error was 0.95 meters at 4 million. That's slightly worse on error, but with four times less fuel our score went up."

## 5. Wall Geometry & Periodic Velocity (~75 s)
"The server's remaining errors came from fast flights in rooms with blank walls. With almost nothing to track, the filter's estimate of its own tilt drifted by 2 to 10 degrees. A tilt error makes the filter subtract gravity in slightly the wrong direction, which looks like sideways acceleration, so the velocity runs away.

But even blank rooms have straight edges. So we track long edges as 3-D lines, and we assume the room is box-shaped. Vertical lines then tell the filter its tilt directly, and horizontal lines tell it its heading. That was our biggest single gain since the learned net: the holdout went from 0.49 to 0.38 meters, and the hard flights improved by about a quarter.

Finally, we found the velocity net is actually worse than the filter on average, but about twice as good exactly when the filter fails, and its mistakes fade within a second. So instead of trusting it rarely and strongly, we re-anchor every half second with a wide uncertainty. Many weak corrections beat a few strong ones, and the hard flights improved another 9 percent. We then replaced the numeric derivatives in the line code with exact formulas, which kept the same accuracy and brought fuel back down to about 4.2 million.

Our final submission scored 0.633 meters at 4.17 million operations per frame. That's our best result, at roughly a thousandth of the compute of OpenVINS and VINS-Mono."
