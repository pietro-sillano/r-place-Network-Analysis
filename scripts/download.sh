#!/usr/bin/env bash
# Download the official r/place 2022 canvas history (~12 GB gzip) into data/.
# The file is kept compressed: rplace.trim reads it directly.
set -euo pipefail
cd "$(dirname "$0")/../data"

URL=https://placedata.reddit.com/data/canvas-history/2022_place_canvas_history.csv.gzip
curl -L -C - -o 2022_place_canvas_history.csv.gzip "$URL"

# The place-atlas (artwork outlines) is already versioned in data/atlas.json.
