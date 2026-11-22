#!/bin/bash
# one overnight flight: one_flight.sh GROUP STYLE SEED SCENE "EXTRA ARGS"
cd "$HOME" && source .venv/bin/activate
GROUP=$1; STYLE=$2; SEED=$3; SCENE=$4; EXTRA=$5
case $STYLE in
  agile2) X='static constexpr T CRUISE_SPEED_MIN = 1.5; static constexpr T CRUISE_SPEED_MAX = 2.5; static constexpr T MAX_ACCELERATION = 2.0; static constexpr T MAX_JERK = 5.0; static constexpr T MAX_YAW_RATE = 1.6; static constexpr T ROADMAP_SPACING = 2.5; static constexpr T CONNECTION_DISTANCE = 10.0;';;
  vfast)  X='static constexpr T CRUISE_SPEED_MIN = 2.5; static constexpr T CRUISE_SPEED_MAX = 3.5; static constexpr T MAX_ACCELERATION = 3.0; static constexpr T MAX_JERK = 8.0; static constexpr T MAX_YAW_RATE = 1.6; static constexpr T ROADMAP_SPACING = 3.5; static constexpr T CONNECTION_DISTANCE = 14.0;';;
  jerky)  X='static constexpr T CRUISE_SPEED_MIN = 1.0; static constexpr T CRUISE_SPEED_MAX = 3.0; static constexpr T MAX_ACCELERATION = 3.5; static constexpr T MAX_JERK = 12.0; static constexpr T MAX_YAW_RATE = 1.6; static constexpr T PHASE_ACCELERATION = 0.8; static constexpr T PHASE_JERK = 2.0; static constexpr T ROADMAP_SPACING = 2.5; static constexpr T CONNECTION_DISTANCE = 10.0;';;
  medium) X='static constexpr T CRUISE_SPEED_MIN = 0.8; static constexpr T CRUISE_SPEED_MAX = 1.5; static constexpr T MAX_ACCELERATION = 1.2; static constexpr T MAX_JERK = 3.0; static constexpr T MAX_YAW_RATE = 1.2; static constexpr T ROADMAP_SPACING = 1.5; static constexpr T CONNECTION_DISTANCE = 6.0;';;
esac
OUT=data/night/$GROUP; mkdir -p $OUT logs_night
LOG=logs_night/$GROUP-$SCENE.log
ls $OUT/sim-$SCENE-*.zip >/dev/null 2>&1 && { echo "skip $GROUP $SCENE (exists)"; exit 0; }
start=$(date +%s)
VIOBENCH_SPOOL=$HOME/spool_${GROUP}_${SCENE} VIOBENCH_TASK_EXTRA="$X" timeout 2400 viobench simulate -o $OUT --episodes 1 --seed $SEED --duration 60 --no-video $EXTRA --scene-names $SCENE > $LOG 2>&1
code=$?
rm -rf "$HOME/spool_${GROUP}_${SCENE}"
echo "$(date +%H:%M) $GROUP $SCENE exit=$code $(( ($(date +%s)-start)/60 )) min" | tee -a logs_night/progress.txt
