#!/usr/bin/env bash
# Whole pipeline, from the raw download to the figures. Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f data/2022_place_canvas_history.csv.gzip ] || scripts/download.sh
[ -f data/reddit_trimmed.parquet ] || python -m rplace.trim   # ~20 GB csv -> parquet

python -m rplace.stats                  # assets/plot/*.png
for selection in random25 random100; do
    python -m rplace.bipartite "$selection"   # output/bipartite_*.parquet, output/artworks_*.csv
    python -m rplace.network "$selection"     # output/pairs_*, output/communities_*, assets/plot/projections/*
done
