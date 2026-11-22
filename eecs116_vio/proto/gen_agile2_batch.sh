#!/bin/bash
# Eight 60 s flights with the fastest autopilot settings we found (sparser waypoints, higher cruise).
cd "$HOME" && source .venv/bin/activate
X='static constexpr T CRUISE_SPEED_MIN = 1.5; static constexpr T CRUISE_SPEED_MAX = 2.5; static constexpr T MAX_ACCELERATION = 2.0; static constexpr T MAX_JERK = 5.0; static constexpr T MAX_YAW_RATE = 1.6; static constexpr T ROADMAP_SPACING = 2.5; static constexpr T CONNECTION_DISTANCE = 10.0;'
VIOBENCH_TASK_EXTRA="$X" viobench simulate -o data/agile2 --hover 0 --episodes 1 --seed 1000 --duration 60 --no-video \
  --scene-names ProcTHOR-Train-9 ProcTHOR-Train-27 ProcTHOR-Train-52 ProcTHOR-Train-71 ProcTHOR-Train-109 ProcTHOR-Train-133 ProcTHOR-Train-151 ProcTHOR-Train-170 \
  > "$HOME/agile2.log" 2>&1
echo "exit=$? $(ls data/agile2/*.zip | wc -l) flights" >> "$HOME/agile2.log"
