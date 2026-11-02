"""Paths and constants shared by the whole pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
FIG_DIR = ROOT / "assets" / "plot"

RAW_CSV = DATA_DIR / "2022_place_canvas_history.csv.gzip"
TRIMMED = DATA_DIR / "reddit_trimmed.parquet"
ATLAS = DATA_DIR / "atlas.json"

CANVAS_SIZE = 2000

# First pixel placed in r/place 2022 (UTC). Every timestamp in the trimmed dataset is
# "minutes since this instant".
# NOTE: the original pipeline used 1648806250 = 09:44:10 UTC, 3 hours earlier, so the
# old minute values are 180 larger than the ones produced now.
START_TIME = "2022-04-01 12:44:10.315"

# The place-atlas splits the event into periods of ~30 minutes, period 1 starting at
# the first pixel. Used to pick which version of an artwork's outline to use.
ATLAS_PERIOD_MINUTES = 30

# Default analysis window (minutes since START_TIME): from the second canvas expansion
# to the start of the final whiteout. These are the old BEGIN=3270 / ENDING=4908 shifted
# by -180; `rplace.stats.canvas_phases` recomputes them from the data.
WINDOW_BEGIN = 3090
WINDOW_END = 4728

WHITE = 31  # colour index of #FFFFFF, the only colour allowed during the whiteout

SEED = 42
