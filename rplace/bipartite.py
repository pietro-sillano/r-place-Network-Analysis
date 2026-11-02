"""Build the artwork-user bipartite network.

An edge (art, user, n_pixels) means that `user` placed `n_pixels` pixels inside `art`
during the analysis window.

Artworks are often nested (small art on top of a flag). By default a pixel belongs only to
the smallest atlas artwork containing it, so that users of the small art are not counted
as users of the flag, which would link the flag to everything those users painted.
With nested=False a pixel counts for every artwork containing it (the original behaviour).

Usage: python -m rplace.bipartite random100   (see SELECTIONS for the presets)
"""
import argparse
import json

import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from . import config
from .atlas import _rasterize_bbox, load_artworks, rasterize, select_artworks
from .trim import load_trimmed

# Presets used in the project. The original 25/100 random artworks were drawn without a
# seed, so they cannot be recovered exactly; these are reproducible re-draws.
SELECTIONS = {
    "random25": dict(n=25, min_area=5000, max_area=100_000),
    "random100": dict(n=100, min_area=5000, max_area=100_000),
    "flags": dict(name_pattern="Flag of Ukraine|Flag of France|Flag of Spain|Nordic Union",
                  min_area=1000, max_area=100_000),
}


def build_edges(pixels: pd.DataFrame, artworks: pd.DataFrame, all_artworks=None, nested=True) -> pd.DataFrame:
    """Edges for `artworks`; with nested=True, overlaps are resolved against `all_artworks`."""
    flat = pixels["y"].to_numpy(np.int64) * config.CANVAS_SIZE + pixels["x"].to_numpy(np.int64)
    users = pixels["user_id"].to_numpy()

    if not nested:
        edges = []
        for art, outline in enumerate(tqdm(artworks["outline"], desc="artworks")):
            inside = rasterize(outline).ravel()[flat]
            u, n = np.unique(users[inside], return_counts=True)
            edges.append(pd.DataFrame({"art": art, "user": u, "n_pixels": n}))
        return pd.concat(edges, ignore_index=True)

    # label every canvas pixel with its smallest artwork: paint the largest first
    all_artworks = artworks if all_artworks is None else all_artworks
    selected = dict(zip(artworks["atlas_id"], range(len(artworks))))
    labels = np.full(config.CANVAS_SIZE**2, -1, dtype=np.int32)
    for atlas_id, outline in tqdm(all_artworks.sort_values("area", ascending=False)[["atlas_id", "outline"]]
                                  .itertuples(index=False), total=len(all_artworks), desc="artworks"):
        x0, y0, crop = _rasterize_bbox(outline)
        ys, xs = crop.nonzero()
        labels[(ys + y0) * config.CANVAS_SIZE + xs + x0] = selected.get(atlas_id, -1)

    art = labels[flat]
    inside = art >= 0
    counts = pd.DataFrame({"art": art[inside], "user": users[inside]}).value_counts()
    return counts.rename("n_pixels").reset_index().sort_values(["art", "user"], ignore_index=True)


def edges_path(tag):
    return config.OUTPUT_DIR / f"bipartite_{tag}.parquet"


def artworks_path(tag):
    return config.OUTPUT_DIR / f"artworks_{tag}.csv"


def build(tag: str, window=(config.WINDOW_BEGIN, config.WINDOW_END), seed=config.SEED, nested=True):
    all_artworks = load_artworks(window)
    artworks = select_artworks(all_artworks, seed=seed, **SELECTIONS[tag])
    pixels = load_trimmed(columns=["user_id", "x", "y"], window=window)
    edges = build_edges(pixels, artworks, all_artworks, nested)

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    edges.to_parquet(edges_path(tag), index=False)
    artworks.assign(outline=artworks["outline"].map(json.dumps)).rename_axis("art").to_csv(artworks_path(tag))
    print(f"{len(artworks)} artworks, {edges['user'].nunique():,} users, {len(edges):,} edges")
    return artworks, edges


def load(tag: str, min_pixels=1):
    """Artworks table and edges with at least `min_pixels` pixels."""
    artworks = pd.read_csv(artworks_path(tag), index_col="art", converters={"outline": json.loads})
    edges = pd.read_parquet(edges_path(tag))
    return artworks, edges[edges["n_pixels"] >= min_pixels].reset_index(drop=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("selection", choices=SELECTIONS)
    p.add_argument("--begin", type=int, default=config.WINDOW_BEGIN)
    p.add_argument("--end", type=int, default=config.WINDOW_END)
    p.add_argument("--seed", type=int, default=config.SEED)
    p.add_argument("--count-overlaps", action="store_true",
                   help="a pixel counts for every artwork containing it, not only the smallest")
    args = p.parse_args()
    build(args.selection, (args.begin, args.end), args.seed, nested=not args.count_overlaps)
