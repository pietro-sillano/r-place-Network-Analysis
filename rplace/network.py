"""Artwork-artwork networks from the bipartite artwork-user network.

Raw shared-user counts mostly reflect artwork size (two big artworks share many users by
chance), so besides the classic projections we compute:

* normalised similarities (Jaccard, cosine) and the Newman collaboration weight;
* a statistically validated network (Tumminello et al., PLoS ONE 2011): the overlap of
  two artworks is compared with a hypergeometric null model in which users are spread at
  random, and only pairs with significantly more shared users than expected (after FDR
  correction) are kept. `lift` = observed / expected shared users is the effect size;
* the disparity-filter backbone (Serrano et al., PNAS 2009) of any weighted projection;
* a spatial control: neighbouring artworks share users also because of border fights
  and misplaced pixels, so we flag adjacent pairs and can rerun everything without them.

Communities are found with Leiden (modularity) on the projections, or directly on the
bipartite network (bipartite CPM), which avoids the information lost by projecting.

Usage: python -m rplace.network random100 [--min-pixels 3]
"""
import argparse

import igraph as ig
import leidenalg as la
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from scipy import sparse, stats
from scipy.ndimage import binary_dilation

from . import bipartite, config
from .atlas import rasterize


def biadjacency(edges: pd.DataFrame, n_arts: int) -> sparse.csr_matrix:
    """Binary art x user matrix (users re-indexed 0..n_users-1)."""
    users = pd.factorize(edges["user"])[0]
    data = np.ones(len(edges))
    return sparse.csr_matrix((data, (edges["art"], users)), shape=(n_arts, users.max() + 1))


def projections(edges: pd.DataFrame, n_arts: int) -> pd.DataFrame:
    """All artwork pairs (i < j) with similarity weights and the null-model test."""
    B = biadjacency(edges, n_arts)
    n_users = B.shape[1]
    art_deg = np.asarray(B.sum(axis=1)).ravel()
    user_deg = np.asarray(B.sum(axis=0)).ravel()

    shared = (B @ B.T).toarray()
    # Newman (2001): each user contributes 1/(k_u - 1) to every pair of its artworks
    inv = np.divide(1.0, user_deg - 1, out=np.zeros(n_users), where=user_deg > 1)
    newman = (B @ sparse.diags(inv) @ B.T).toarray()

    i, j = np.triu_indices(n_arts, k=1)
    o, ni, nj = shared[i, j], art_deg[i], art_deg[j]
    expected = ni * nj / n_users

    def ratio(a, b):  # 0 for artworks without users
        return np.divide(a, b, out=np.zeros(len(a)), where=b > 0)

    pairs = pd.DataFrame({
        "i": i, "j": j,
        "shared": o.astype(int),
        "newman": newman[i, j],
        "jaccard": ratio(o, ni + nj - o),
        "cosine": ratio(o, np.sqrt(ni * nj)),
        "expected": expected,
        "lift": ratio(o, expected),
        # P(X >= o) under the hypergeometric null
        "pvalue": stats.hypergeom.sf(o - 1, n_users, ni, nj),
    })
    pairs["qvalue"] = stats.false_discovery_control(pairs["pvalue"].clip(lower=1e-300))
    return pairs


def validated(pairs: pd.DataFrame, q=0.01) -> pd.DataFrame:
    """Pairs sharing significantly more users than the null model predicts."""
    return pairs[(pairs["qvalue"] < q) & (pairs["lift"] > 1)].reset_index(drop=True)


def disparity_backbone(pairs: pd.DataFrame, weight: str, alpha=0.05) -> pd.DataFrame:
    """Keep edges that are significant for at least one endpoint (Serrano et al. 2009)."""
    p = pairs[pairs[weight] > 0]
    both = pd.concat([p[["i", weight]].rename(columns={"i": "n"}), p[["j", weight]].rename(columns={"j": "n"})])
    strength = both.groupby("n")[weight].sum()
    degree = both.groupby("n").size()

    def alpha_of(node):
        k = p[node].map(degree)
        return np.where(k > 1, (1 - p[weight] / p[node].map(strength)) ** (k - 1), 1.0)

    keep = np.minimum(alpha_of("i"), alpha_of("j")) < alpha
    return p[keep].reset_index(drop=True)


def spatial_neighbours(artworks: pd.DataFrame, radius=3) -> set[tuple[int, int]]:
    """Pairs (i < j) of artworks that overlap or are within `radius` pixels of each other."""
    footprint = np.ones((2 * radius + 1, 2 * radius + 1), dtype=bool)
    masks, grown = [], []
    for outline in artworks["outline"]:
        m = rasterize(outline)
        masks.append(np.flatnonzero(m))
        grown.append(np.flatnonzero(binary_dilation(m, footprint)))
    return {(i, j)
            for i in range(len(masks)) for j in range(i + 1, len(masks))
            if np.intersect1d(grown[i], masks[j], assume_unique=True).size}


def leiden(pairs: pd.DataFrame, n_arts: int, weight=None, seed=config.SEED) -> np.ndarray:
    """Modularity communities of the projected network (isolated nodes get their own)."""
    g = ig.Graph(n=n_arts, edges=list(zip(pairs["i"], pairs["j"])))
    w = None if weight is None else pairs[weight].to_list()
    part = la.find_partition(g, la.ModularityVertexPartition, weights=w, seed=seed)
    return np.array(part.membership)


def leiden_bipartite(edges: pd.DataFrame, n_arts: int, resolution=None, seed=config.SEED) -> np.ndarray:
    """Communities found on the bipartite network itself (bipartite CPM, leidenalg docs).

    `resolution` defaults to the bipartite density: communities must be denser than average.
    Returns the community of each artwork.
    """
    users = pd.factorize(edges["user"])[0] + n_arts
    g = ig.Graph(n=users.max() + 1, edges=list(zip(edges["art"], users)))
    g.vs["type"] = [i >= n_arts for i in range(g.vcount())]
    if resolution is None:
        resolution = g.ecount() / (n_arts * (g.vcount() - n_arts))
    p01, p0, p1 = la.CPMVertexPartition.Bipartite(g, resolution_parameter_01=resolution)
    opt = la.Optimiser()
    opt.set_rng_seed(seed)
    opt.optimise_partition_multiplex([p01, p0, p1], layer_weights=[1, -1, -1])
    return np.array(p01.membership[:n_arts])


def circos(pairs: pd.DataFrame, n_arts: int, weight: str, groups=None, labels=None,
           max_edges=None, ax=None):
    """Nodes on a circle (grouped by community), edges as curves through the centre.

    Width and opacity grow with `weight`; `max_edges` only thins the drawing, never the analysis.
    """
    ax = ax or plt.subplots(figsize=(10, 10))[1]
    groups = np.zeros(n_arts, int) if groups is None else np.asarray(groups)
    order = np.lexsort((np.arange(n_arts), groups))
    angle = np.empty(n_arts)
    angle[order] = np.linspace(0, 2 * np.pi, n_arts, endpoint=False)
    pos = np.column_stack([np.cos(angle), np.sin(angle)])

    p = pairs.nlargest(max_edges, weight) if max_edges else pairs
    if len(p):
        w = p[weight].to_numpy(float)
        w = (w - w.min()) / (np.ptp(w) or 1)
        for (a, b), wi in zip(p[["i", "j"]].to_numpy(), w):
            path = Path([pos[a], pos[a] * 0.1 + pos[b] * 0.1, pos[b]], [Path.MOVETO, Path.CURVE3, Path.CURVE3])
            ax.add_patch(PathPatch(path, fc="none", ec="grey", lw=0.5 + 3 * wi, alpha=0.3 + 0.5 * wi))

    cmap = plt.get_cmap("tab20")
    ax.scatter(pos[:, 0], pos[:, 1], c=[cmap(g % 20) for g in groups], s=80, zorder=3, edgecolors="k", lw=0.5)
    if labels is not None:
        for (x, y), a, text in zip(pos, angle, labels):
            deg = np.degrees(a)
            flip = 90 < deg < 270
            ax.text(1.06 * x, 1.06 * y, text, fontsize=6, rotation=deg + 180 * flip,
                    ha="right" if flip else "left", va="center", rotation_mode="anchor")
    ax.set(xlim=(-1.6, 1.6), ylim=(-1.6, 1.6), aspect="equal")
    ax.set_axis_off()
    return ax


def describe_communities(artworks: pd.DataFrame, membership) -> str:
    out = []
    for c in np.unique(membership):
        names = artworks["name"].to_numpy()[membership == c]
        out.append(f"## community {c} ({len(names)})\n" + "\n".join(names))
    return "\n\n".join(out)


def analyse(tag: str, min_pixels=3, q=0.01, radius=3):
    artworks, edges = bipartite.load(tag, min_pixels)
    n = len(artworks)
    names = artworks["name"].str.slice(0, 30).to_numpy()

    pairs = projections(edges, n)
    near = spatial_neighbours(artworks, radius)
    pairs["neighbours"] = [(i, j) in near for i, j in zip(pairs["i"], pairs["j"])]
    pairs.assign(name_i=names[pairs["i"]], name_j=names[pairs["j"]]).to_csv(
        config.OUTPUT_DIR / f"pairs_{tag}.csv", index=False)

    val = validated(pairs, q)
    val["log_lift"] = np.log(val["lift"])
    far = val[~val["neighbours"]]
    backbone = disparity_backbone(pairs, "shared")

    comms = pd.DataFrame({
        "name": artworks["name"],
        "shared": leiden(pairs[pairs["shared"] > 0], n, "shared"),
        "validated": leiden(val, n, "log_lift"),
        "validated_no_neighbours": leiden(far, n, "log_lift"),
        "bipartite": leiden_bipartite(edges, n),
        "backbone": leiden(backbone, n, "shared"),
    })
    comms.rename_axis("art").to_csv(config.OUTPUT_DIR / f"communities_{tag}.csv")
    (config.OUTPUT_DIR / f"communities_{tag}.txt").write_text(
        describe_communities(artworks, comms["validated"].to_numpy()))

    nmi = lambda a, b: ig.compare_communities(comms[a].to_list(), comms[b].to_list(), method="nmi")
    print(f"{n} artworks, {edges['user'].nunique():,} users, {len(edges):,} edges (>= {min_pixels} pixels)")
    print(f"pairs with shared users: {(pairs['shared'] > 0).sum()} / {len(pairs)}")
    print("how much each weight just follows artwork size (Spearman with expected overlap):",
          pairs[["shared", "newman", "jaccard", "lift"]].corrwith(pairs["expected"], method="spearman")
          .round(2).to_dict())
    print(f"validated pairs (q < {q}): {len(val)}, of which spatial neighbours: {val['neighbours'].sum()}"
          f" ({val['neighbours'].mean():.0%}; neighbours are {pairs['neighbours'].mean():.0%} of all pairs)")
    print("median lift of pairs sharing users, neighbours: {:.2f}  others: {:.2f}".format(
        *pairs[pairs["shared"] > 0].groupby("neighbours")["lift"].median().reindex([True, False])))
    print(f"communities: shared={comms['shared'].nunique()} validated={comms['validated'].nunique()} "
          f"no-neighbours={comms['validated_no_neighbours'].nunique()} bipartite={comms['bipartite'].nunique()}")
    print(f"NMI validated vs no-neighbours: {nmi('validated', 'validated_no_neighbours'):.2f}, "
          f"validated vs bipartite: {nmi('validated', 'bipartite'):.2f}, shared vs validated: {nmi('shared', 'validated'):.2f}")

    outdir = config.FIG_DIR / "projections"
    outdir.mkdir(parents=True, exist_ok=True)
    labels = names if n <= 100 else None
    for fname, p, weight, groups in [
        ("shared", pairs[pairs["shared"] > 0], "shared", comms["shared"]),
        ("validated", val, "log_lift", comms["validated"]),
        ("validated_no_neighbours", far, "log_lift", comms["validated_no_neighbours"]),
        ("backbone", backbone, "shared", comms["backbone"]),
    ]:
        ax = circos(p, n, weight, groups, labels, max_edges=10 * n)
        ax.figure.savefig(outdir / f"{tag}_{fname}.png", dpi=200, bbox_inches="tight")
        plt.close(ax.figure)
    return pairs, comms


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("selection", choices=bipartite.SELECTIONS)
    p.add_argument("--min-pixels", type=int, default=3)
    p.add_argument("--q", type=float, default=0.01, help="FDR threshold of the validated network")
    p.add_argument("--radius", type=int, default=3, help="pixels within which artworks are neighbours")
    args = p.parse_args()
    analyse(args.selection, args.min_pixels, args.q, args.radius)
