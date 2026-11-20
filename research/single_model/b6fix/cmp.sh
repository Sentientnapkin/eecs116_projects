#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
/data/backups/rganapa/Sebastian/venv-teacher/bin/python -B research/single_model/frontend/cmprep2.py fe2_fbh "$@" 2>&1 | grep -v "^$"
