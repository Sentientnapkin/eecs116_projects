#!/bin/bash
until pgrep -f "python.*runset[.]py p15" >/dev/null; do sleep 5; done
sleep 3
for p in $(pgrep -f "python.*runset[.]py p15"); do kill $p; done
