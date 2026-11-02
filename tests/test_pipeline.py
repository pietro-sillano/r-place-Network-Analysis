import json
import os
import time

import numpy as np
import pandas as pd
import pytest

from rplace import atlas, bipartite, config, network, stats, trim


def raw_csv(path):
    rows = [
        ("2022-04-01 12:44:10.315 UTC", "userA", "#FFFFFF", "10,20"),
        ("2022-04-01 12:45:11 UTC", "userB", "#000000", "1999,0"),     # no milliseconds
        ("2022-04-01 14:44:11.000 UTC", "userA", "#FF4500", "0,1999"),
        ("2022-04-01 14:44:11.000 UTC", "admin", "#000000", "1,2,3,4"),  # rectangle
        ("2022-04-01 14:44:11.000 UTC", "admin", "#000000", "{X: 424, Y: 336, R: 6}"),  # circle
    ]
    pd.DataFrame(rows, columns=["timestamp", "user_id", "pixel_color", "coordinate"]).to_csv(path, index=False)


@pytest.mark.parametrize("tz", ["UTC", "Europe/Rome", "America/Los_Angeles"])
def test_trim_is_timezone_independent(tmp_path, tz, monkeypatch):
    monkeypatch.setenv("TZ", tz)
    time.tzset()
    raw_csv(tmp_path / "raw.csv")
    df = trim.trim(tmp_path / "raw.csv", tmp_path / "out.parquet")
    assert df["timestamp"].tolist() == [0, 1, 120]
    assert df["user_id"].tolist() == [0, 1, 0]
    assert df["pixel_color"].tolist() == [31, 0, 25]
    assert df[["x", "y"]].values.tolist() == [[10, 20], [1999, 0], [0, 1999]]
    assert df.dtypes.to_dict() == pd.read_parquet(tmp_path / "out.parquet").dtypes.to_dict()
    monkeypatch.delenv("TZ")
    time.tzset()


def test_rasterize_orientation():
    # 20 pixels wide (x), 5 high (y): a transposed mask would be tall instead of wide
    mask = atlas.rasterize([[100, 300], [120, 300], [120, 305], [100, 305]])
    ys, xs = mask.nonzero()
    assert xs.min() >= 100 and xs.max() <= 120 and ys.min() >= 300 and ys.max() <= 305
    assert mask[302, 110] and not mask[110, 302]


def test_parse_periods():
    assert atlas.parse_periods("121, 133-135, T") == {121, 133, 134, 135}
    assert atlas.parse_periods("T") == set()
    paths = {"1-50": [[0, 0], [1, 0], [1, 1]], "109-166, T": [[5, 5], [9, 5], [9, 9]]}
    assert atlas.outline_for_window(paths, (3240, 4000)) == paths["109-166, T"]
    assert atlas.outline_for_window(paths, (0, 100)) == paths["1-50"]
    assert atlas.outline_for_window(paths, (2000, 2100)) is None


def test_stats():
    df = pd.DataFrame({"timestamp": [0, 0, 5, 9], "user_id": [0, 0, 1, 2], "pixel_color": [1, 2, 3, 31],
                       "x": [1500, 3, 3, 0], "y": [0, 1200, 1200, 0]})
    hm = stats.heatmap(df)
    assert hm[1200, 3] == 2 and hm[0, 1500] == 1 and hm.sum() == 4
    assert stats.pixels_per_user(df).to_dict() == {1: 2, 2: 1}
    assert stats.canvas_phases(df) == {"first_expansion": 0, "second_expansion": 0, "whiteout": 6, "end": 9}


def planted(rng, n_groups=3, arts_per_group=4, users_per_group=400):
    """Each user paints mostly in the artworks of its own group."""
    rows = []
    n_arts = n_groups * arts_per_group
    for g in range(n_groups):
        for u in range(users_per_group):
            user = g * users_per_group + u
            own = rng.choice(arts_per_group, 2, replace=False) + g * arts_per_group
            for a in [*own, rng.integers(n_arts)]:
                rows.append((a, user, rng.integers(1, 10)))
    edges = pd.DataFrame(rows, columns=["art", "user", "n_pixels"]).drop_duplicates(["art", "user"])
    return edges, n_arts, np.repeat(np.arange(n_groups), arts_per_group)


def test_network_recovers_planted_communities():
    edges, n, truth = planted(np.random.default_rng(0))
    pairs = network.projections(edges, n)
    assert len(pairs) == n * (n - 1) / 2
    assert ((pairs["jaccard"] >= 0) & (pairs["jaccard"] <= 1)).all()

    val = network.validated(pairs)
    assert (truth[val["i"]] == truth[val["j"]]).all()
    val = val.assign(log_lift=np.log(val["lift"]))
    for membership in [network.leiden(val, n, "log_lift"), network.leiden_bipartite(edges, n)]:
        assert np.allclose(pd.crosstab(membership, truth).max(axis=1).sum(), n)

    backbone = network.disparity_backbone(pairs, "shared", alpha=0.2)
    assert 0 < len(backbone) <= (pairs["shared"] > 0).sum()


def test_spatial_neighbours():
    arts = pd.DataFrame({"outline": [
        [[0, 0], [10, 0], [10, 10], [0, 10]],
        [[12, 0], [20, 0], [20, 10], [12, 10]],     # 2 px to the right of the first
        [[500, 500], [510, 500], [510, 510], [500, 510]],
    ]})
    assert network.spatial_neighbours(arts, radius=3) == {(0, 1)}
    assert network.spatial_neighbours(arts, radius=1) == set()


def test_end_to_end(tmp_path, monkeypatch):
    """Synthetic canvas + atlas through bipartite.build and network.analyse."""
    rng = np.random.default_rng(1)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(config, "FIG_DIR", tmp_path / "fig")
    (tmp_path / "fig").mkdir()

    # 6 square artworks of 80x80 in a row, artworks 2k and 2k+1 share a community of users
    entries, pixels = [], []
    for a in range(6):
        x0 = 100 + a * 200
        entries.append({"id": str(a), "name": f"art {a}",
                        "path": {"109-166, T": [[x0, 100], [x0 + 80, 100], [x0 + 80, 180], [x0, 180]]}})
    for user in range(900):
        g = user % 3
        for a in [2 * g, 2 * g + 1, rng.integers(6)]:
            x0 = 100 + a * 200
            for _ in range(4):
                pixels.append((3500, user, 0, x0 + rng.integers(2, 78), 100 + rng.integers(2, 78)))
    atlas_path = tmp_path / "atlas.json"
    atlas_path.write_text(json.dumps(entries))
    pq = tmp_path / "trimmed.parquet"
    pd.DataFrame(pixels, columns=["timestamp", "user_id", "pixel_color", "x", "y"]).astype(
        {"timestamp": "uint16", "user_id": "uint32", "pixel_color": "uint8", "x": "uint16", "y": "uint16"}
    ).to_parquet(pq)

    monkeypatch.setattr(atlas.load_artworks, "__defaults__", (atlas.load_artworks.__defaults__[0], atlas_path))
    monkeypatch.setattr(bipartite, "load_trimmed", lambda **kw: trim.load_trimmed(pq, **kw))
    monkeypatch.setitem(bipartite.SELECTIONS, "test", dict(min_area=100))

    arts, edges = bipartite.build("test")
    assert len(arts) == 6
    # every pixel lies inside exactly one artwork
    assert edges["n_pixels"].sum() == len(pixels)

    pairs, comms = network.analyse("test", min_pixels=1)
    truth = arts["name"].str[-1].astype(int).to_numpy() // 2
    assert np.allclose(pd.crosstab(comms.set_index("name").loc[arts["name"], "validated"].to_numpy(), truth)
                       .max(axis=1).sum(), 6)
    assert (tmp_path / "fig" / "projections" / "test_validated.png").exists()


def test_nested_artworks_count_for_the_smallest():
    arts = pd.DataFrame({
        "atlas_id": ["flag", "small", "other"],
        "outline": [[[0, 0], [100, 0], [100, 50], [0, 50]],      # flag
                    [[10, 10], [20, 10], [20, 20], [10, 20]],    # small art on top of the flag
                    [[500, 500], [520, 500], [520, 520], [500, 520]]],
        "area": [5000, 100, 400],
    })
    pixels = pd.DataFrame({"user_id": [0, 1, 1, 2], "x": [50, 15, 15, 510], "y": [40, 15, 15, 510]})
    edges = bipartite.build_edges(pixels, arts.iloc[[0, 2]].reset_index(drop=True), arts)
    # user 1 painted only inside "small" (not selected): it is not a contributor of the flag
    assert edges.values.tolist() == [[0, 0, 1], [1, 2, 1]]
    edges = bipartite.build_edges(pixels, arts.iloc[[0, 2]].reset_index(drop=True), nested=False)
    assert edges.values.tolist() == [[0, 0, 1], [0, 1, 2], [1, 2, 1]]
