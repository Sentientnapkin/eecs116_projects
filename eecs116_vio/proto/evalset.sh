#!/bin/bash
# usage: bash evalset.sh TUNE|TEST [run.py arguments...]   (runs inside WSL with the viobench venv)
cd "$(dirname "$0")" && source "$HOME/.venv/bin/activate" && source ./sets.sh
set_name=$1; shift
python run.py ${!set_name} "$@" 2>&1 | grep -v '^conta:'
