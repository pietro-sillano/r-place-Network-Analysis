"""Descriptive statistics of the dataset and the figures in assets/plot.

Usage: python -m rplace.stats
"""
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config
from .atlas import load_artworks
from .trim import load_trimmed


def pixels_per_user(df: pd.DataFrame) -> pd.Series:
    """Number of users (value) that placed k pixels (index)."""
    return df["user_id"].value_counts().value_counts().sort_index()


def heatmap(df: pd.DataFrame) -> np.ndarray:
    """Number of times each pixel was changed, indexed [y, x]."""
    flat = df["y"].to_numpy(np.int64) * config.CANVAS_SIZE + df["x"].to_numpy(np.int64)
    return np.bincount(flat, minlength=config.CANVAS_SIZE**2).reshape(config.CANVAS_SIZE, config.CANVAS_SIZE)


def pixels_per_minute(df: pd.DataFrame) -> pd.Series:
    return df["timestamp"].value_counts().sort_index()


def canvas_phases(df: pd.DataFrame) -> dict:
    """Key instants (minutes) derived from the data itself."""
    return {
        "first_expansion": int(df.loc[df["x"] >= 1000, "timestamp"].min()),
        "second_expansion": int(df.loc[df["y"] >= 1000, "timestamp"].min()),
        "whiteout": int(df.loc[df["pixel_color"] != config.WHITE, "timestamp"].max()) + 1,
        "end": int(df["timestamp"].max()),
    }


def _loglog_scatter(series, xlabel, ylabel, xscale="log"):
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.plot(series.index, series.to_numpy(), "o", ms=3)
    ax.set(xscale=xscale, yscale="log", xlabel=xlabel, ylabel=ylabel)
    return fig


def plot_heatmap(hm):
    fig, ax = plt.subplots(figsize=(10, 9))
    # origin="upper": y grows downwards, as on the r/place canvas
    im = ax.imshow(np.maximum(hm, 1), norm=colors.LogNorm(vmin=1, vmax=hm.max()), cmap="plasma")
    fig.colorbar(im, ax=ax, extend="max", label="changes")
    ax.set_title("Heatmap of most modified tiles")
    ax.set_axis_off()
    return fig


def make_figures(outdir=config.FIG_DIR):
    df = load_trimmed()
    print(canvas_phases(df))

    hm = heatmap(df)
    print("most modified pixel (y, x):", np.unravel_index(hm.argmax(), hm.shape), hm.max())
    print("pixels never modified:", int((hm == 0).sum()))

    figs = {
        "number_of_tiles.png": _loglog_scatter(pixels_per_user(df), "Pixels placed per user", "Number of users",
                                               xscale="linear"),
        "heatmap.png": plot_heatmap(hm),
        "time_distribution.png": _loglog_scatter(pixels_per_minute(df), "Time [min]", "Pixels changed",
                                                 xscale="linear"),
        "area_distribution.png": _loglog_scatter(load_artworks(window=(0, config.WINDOW_END))["area"].value_counts().sort_index(),
                                                 "Area in pixels", "Number of artworks"),
    }
    figs["time_distribution.png"].axes[0].set_yscale("linear")
    for name, fig in figs.items():
        fig.savefig(outdir / name, dpi=200, bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    make_figures()
