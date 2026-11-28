#!/bin/bash
# heavy.sh CMD [ARGS...] : run a heavy WSL job (training, big eval, video/feature caching) under the shared lock,
# so only one runs at a time across all agents and sessions. WSL is capped at 10 GB; parallel heavy jobs get killed.
#   wsl.exe bash /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/heavy.sh ~/.venv_gru/bin/python mlp_fit.py
exec 9> "$HOME/data/.heavy.lock"
echo "waiting for the heavy-job lock..."; flock 9; echo "lock taken $(date +%T): $*"
"$@"
