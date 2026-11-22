#!/bin/bash
# usage: bash pyrun.sh SET script.py [args]  -- run a proto script on a named episode set (sets.sh) inside WSL
cd "$(dirname "$0")" && source "$HOME/.venv/bin/activate" && source ./sets.sh
set_name=$1; script=$2; shift 2
python "$script" ${!set_name} "$@" 2>&1 | grep -v '^conta:'
