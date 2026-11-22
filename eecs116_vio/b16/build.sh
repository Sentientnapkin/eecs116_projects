#!/bin/bash
# build.sh SRC NAME [DEF=VAL ...] -> ~/ws_m/ms_NAME.wasm (-O3, same recipe as the submitted B16)
SRC=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/$1; shift
cd ~ && SRC=$SRC FLAGS=-O3 bash /mnt/c/Users/alexa/Projects/eecs116_vio/msckf/build_m.sh "$@"
