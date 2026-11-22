# Frozen episode lists. TUNE: everything I adjust settings on. TEST: never tuned on, only for the final check.
TUNE="$HOME/data/agile_a/sim-ProcTHOR-Train-3-0000.zip $HOME/data/agile_a/sim-ProcTHOR-Train-12-0000.zip $HOME/data/agile_a/sim-ProcTHOR-Train-31-0000.zip $HOME/data/agile_a/sim-ProcTHOR-Train-58-0000.zip $HOME/data/agile_a/sim-ProcTHOR-Train-90-0000.zip $HOME/data/public/sim-ProcTHOR-Train-1-0006.zip $HOME/data/fast/sim-ProcTHOR-Train-20-0000.zip $HOME/data/fast/sim-ProcTHOR-Train-44-0000.zip $HOME/data/fast/sim-ProcTHOR-Train-77-0000.zip $HOME/data/fast/sim-ProcTHOR-Train-101-0000.zip"
TEST="$HOME/data/mixed $HOME/data/fast/sim-ProcTHOR-Train-25-0000.zip $HOME/data/fast/sim-ProcTHOR-Train-88-0000.zip"
TEST_MIXED="$HOME/data/mixed"
TEST_FAST="$HOME/data/fast/sim-ProcTHOR-Train-25-0000.zip"
TEST_LAST="$HOME/data/fast/sim-ProcTHOR-Train-88-0000.zip $HOME/data/mixed/sim-ProcTHOR-Train-33-0000.zip $HOME/data/mixed/sim-ProcTHOR-Train-95-0000.zip"
ALL="$HOME/data/agile_a $HOME/data/public $HOME/data/fast $HOME/data/mixed"
HELDOUT="$HOME/data/mixed $HOME/data/fast/sim-ProcTHOR-Train-25-0000.zip $HOME/data/fast/sim-ProcTHOR-Train-88-0000.zip"
PROBE="$HOME/data/probe_agile2"
AGILE2="$HOME/data/agile2"
N=$HOME/data/night
NIGHT="$N/match $N/match2 $N/medium $N/jerky $N/jerky_wide $N/vfast $N/fov90 $N/fov150 $N/hover $N/hssd_vfast"
JERKY="$N/jerky $N/jerky_wide"
BAD="$N/fov150/sim-ProcTHOR-Train-106-0000.zip $N/match/sim-ProcTHOR-Train-128-0000.zip $N/vfast/sim-ProcTHOR-Train-146-0000.zip $N/vfast/sim-ProcTHOR-Train-155-0000.zip $N/vfast/sim-ProcTHOR-Train-166-0000.zip $N/fov90/sim-ProcTHOR-Train-197-0000.zip"
NIGHT_ALL=$(for d in $HOME/data/night/*/; do ls $d*.zip >/dev/null 2>&1 && echo -n "$d "; done)
