#!/bin/bash
# Short test flight with the autopilot's pacing loosened, to find settings that reach ~1 m/s like the hidden set.
cd "$HOME" && source .venv/bin/activate
X='static constexpr T CRUISE_SPEED_MIN = 1.5; static constexpr T CRUISE_SPEED_MAX = 2.5; static constexpr T MAX_ACCELERATION = 2.0; static constexpr T MAX_JERK = 5.0; static constexpr T MAX_YAW_RATE = 1.6; static constexpr T ROADMAP_SPACING = 2.5; static constexpr T CONNECTION_DISTANCE = 10.0;'
rm -rf data/probe_agile2
VIOBENCH_TASK_EXTRA="$X" viobench simulate -o data/probe_agile2 --hover 0 --episodes 1 --seed 900 --duration 20 --no-video --scene-names ProcTHOR-Train-7 ProcTHOR-Train-44 > probe.log 2>&1
grep -E "crashed|wrote|rror" probe.log | tail -3
python /mnt/c/Users/alexa/Projects/eecs116_vio/proto/flight_stats.py data/probe_agile2 2>&1 | grep -v conta
