"""Artwork outlines from the r/place atlas (data/atlas.json).

Each atlas entry can have several outlines, keyed by the atlas periods in which they
are valid, e.g. {"56-108": [...], "109-166, T": [...]} ("T" = the final whiteout).
"""
import json
import re

import numpy as np
import pandas as pd
from matplotlib.path import Path

from . import config


def parse_periods(key: str) -> set[int]:
    """'121, 133-136, T' -> {121, 133, 134, 135, 136}. 'T' (whiteout) is ignored."""
    periods = set()
    for part in key.split(","):
        part = part.strip()
        if m := re.fullmatch(r"(\d+)-(\d+)", part):
            periods.update(range(int(m[1]), int(m[2]) + 1))
        elif part.isdigit():
            periods.add(int(part))
    return periods


def minute_to_period(minute: float) -> int:
    return int(minute // config.ATLAS_PERIOD_MINUTES) + 1


def outline_for_window(paths: dict, window: tuple[int, int]):
    """The outline valid for the largest part of `window`, or None if absent in it."""
    wanted = set(range(minute_to_period(window[0]), minute_to_period(window[1] - 1) + 1))
    best, best_overlap = None, 0
    for key, outline in paths.items():
        overlap = len(parse_periods(key) & wanted)
        if overlap > best_overlap and len(outline) >= 3:
            best, best_overlap = outline, overlap
    return best


def _rasterize_bbox(outline, size=config.CANVAS_SIZE):
    """Pixels inside the polygon, tested only within its bounding box: (x0, y0, mask[y, x])."""
    outline = np.asarray(outline, dtype=float)
    x0, y0 = np.clip(np.floor(outline.min(axis=0)).astype(int), 0, size - 1)
    x1, y1 = np.clip(np.ceil(outline.max(axis=0)).astype(int), 0, size - 1)
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
    inside = Path(outline).contains_points(np.column_stack([xs.ravel(), ys.ravel()]))
    return x0, y0, inside.reshape(xs.shape)


def rasterize(outline, size=config.CANVAS_SIZE) -> np.ndarray:
    """Boolean mask of the pixels inside a polygon given as [[x, y], ...].

    The mask is indexed mask[y, x] (row = y), like an image of the canvas.
    """
    x0, y0, crop = _rasterize_bbox(outline, size)
    mask = np.zeros((size, size), dtype=bool)
    mask[y0:y0 + crop.shape[0], x0:x0 + crop.shape[1]] = crop
    return mask


def load_artworks(window=(config.WINDOW_BEGIN, config.WINDOW_END), path=config.ATLAS) -> pd.DataFrame:
    """One row per artwork present during `window`, with its outline and area in pixels."""
    with open(path) as f:
        atlas = json.load(f)

    rows = []
    for entry in atlas:
        outline = outline_for_window(entry["path"], window)
        if outline is None:
            continue
        rows.append({
            "atlas_id": entry["id"],
            "name": entry["name"],
            "outline": outline,
            "area": int(_rasterize_bbox(outline)[2].sum()),
        })
    df = pd.DataFrame(rows)
    return df[df["area"] > 0].sort_values("area", ascending=False, ignore_index=True)


def select_artworks(artworks: pd.DataFrame, n=None, min_area=0, max_area=np.inf,
                    name_pattern=None, seed=config.SEED) -> pd.DataFrame:
    """Filter by area and/or name regex, then sample `n` of them reproducibly."""
    sel = artworks[(artworks["area"] > min_area) & (artworks["area"] < max_area)]
    if name_pattern is not None:
        sel = sel[sel["name"].str.contains(name_pattern)]
    if n is not None and n < len(sel):
        sel = sel.sample(n, random_state=seed)
    return sel.reset_index(drop=True)
