#!/bin/bash
# import_flights.sh /mnt/c/Users/alexa/Downloads/flights_gpu : copy GPU-made flight groups into ~/data/night/<group>/
SRC=$1
for g in "$SRC"/*/; do
  name=$(basename "$g"); [ "$name" = logs ] || [ "$name" = _test ] && continue
  n=$(ls "$g"*.zip 2>/dev/null | wc -l); [ "$n" -gt 0 ] || continue
  mkdir -p "$HOME/data/night/$name" && cp -n "$g"*.zip "$HOME/data/night/$name/" && echo "$name: $n flights"
done
