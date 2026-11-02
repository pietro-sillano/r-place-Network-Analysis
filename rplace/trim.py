"""Shrink the raw r/place 2022 dump (~20 GB csv) into a compact parquet file.

Output columns:
    timestamp    uint16  minutes since the first pixel (config.START_TIME)
    user_id      uint32  dense integer id (0..n_users-1)
    pixel_color  uint8   index into COLORS
    x, y         uint16  canvas coordinates

Admin moderation actions (rectangles and circles) are dropped.

Usage: python -m rplace.trim [--input RAW] [--output PARQUET]
"""
import argparse

import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from . import config

COLORS = [
    "#000000", "#00756F", "#009EAA", "#00A368", "#00CC78", "#00CCC0", "#2450A4", "#3690EA",
    "#493AC1", "#515252", "#51E9F4", "#6A5CFF", "#6D001A", "#6D482F", "#7EED56", "#811E9F",
    "#898D90", "#94B3FF", "#9C6926", "#B44AC0", "#BE0039", "#D4D7D9", "#DE107F", "#E4ABFF",
    "#FF3881", "#FF4500", "#FF99AA", "#FFA800", "#FFB470", "#FFD635", "#FFF8B8", "#FFFFFF",
]
COLOR_TO_KEY = {c: i for i, c in enumerate(COLORS)}

CHUNK_SIZE = 5_000_000


def parse_timestamps(ts: pd.Series) -> np.ndarray:
    """'2022-04-04 00:53:51.577 UTC' -> whole minutes since config.START_TIME (explicitly UTC)."""
    t = pd.to_datetime(ts.str.removesuffix(" UTC"), format="ISO8601", utc=True)
    seconds = (t - pd.Timestamp(config.START_TIME, tz="UTC")).dt.total_seconds()
    minutes = np.floor(seconds.to_numpy() / 60)
    if minutes.min() < 0 or minutes.max() > np.iinfo(np.uint16).max:
        raise ValueError("timestamp outside the expected r/place 2022 range")
    return minutes.astype(np.uint16)


def process_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    # Regular placements are "x,y"; admin tools use "x1,y1,x2,y2" or "{X: .., Y: .., R: ..}".
    chunk = chunk[chunk["coordinate"].str.fullmatch(r"\d+,\d+")]
    xy = chunk["coordinate"].str.split(",", expand=True).astype(np.uint16)

    colors = chunk["pixel_color"].map(COLOR_TO_KEY)
    if colors.isna().any():
        raise ValueError(f"unknown colours: {chunk.loc[colors.isna(), 'pixel_color'].unique()}")

    return pd.DataFrame({
        "timestamp": parse_timestamps(chunk["timestamp"]),
        # 64-bit hash instead of a python dict of 10M strings: collisions are ~1e-6 likely
        "user_hash": pd.util.hash_pandas_object(chunk["user_id"], index=False).to_numpy(),
        "pixel_color": colors.to_numpy(np.uint8),
        "x": xy[0].to_numpy(),
        "y": xy[1].to_numpy(),
    })


def trim(infile=config.RAW_CSV, outfile=config.TRIMMED) -> pd.DataFrame:
    chunks = []
    with pd.read_csv(
        infile,
        usecols=["timestamp", "user_id", "pixel_color", "coordinate"],
        dtype=str,
        chunksize=CHUNK_SIZE,
        compression="gzip" if str(infile).endswith(("gz", "gzip")) else None,
    ) as reader:
        for chunk in tqdm(reader, desc="chunks"):
            chunks.append(process_chunk(chunk))

    df = pd.concat(chunks, ignore_index=True)
    df.insert(1, "user_id", pd.factorize(df.pop("user_hash"))[0].astype(np.uint32))
    df = df.sort_values("timestamp", kind="stable", ignore_index=True)

    print(f"{len(df):,} pixels, {df['user_id'].max() + 1:,} users")
    df.to_parquet(outfile, index=False)
    return df


def load_trimmed(path=config.TRIMMED, columns=None, window=None) -> pd.DataFrame:
    """Load the trimmed dataset, optionally only rows with window[0] <= timestamp < window[1]."""
    filters = None
    if window is not None:
        filters = [("timestamp", ">=", window[0]), ("timestamp", "<", window[1])]
    return pd.read_parquet(path, columns=columns, filters=filters)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default=config.RAW_CSV)
    p.add_argument("--output", default=config.TRIMMED)
    args = p.parse_args()
    trim(args.input, args.output)
