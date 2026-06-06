"""Correlation-cluster taxonomy (PREREG §5 amendment): resolution, fail-closed validation, inert defaults."""

import pytest

from dramatic_options import clusters
from dramatic_options.clusters import ClusterConfigError


def _cfg(clusters_map, *, cluster_fraction=0.02, per_name_fraction=0.01):
    return {"convexity_book": {"per_name_fraction": per_name_fraction,
                               "cluster_fraction": cluster_fraction, "clusters": clusters_map}}


def test_loads_and_resolves_case_insensitively():
    cmap = clusters.load_cluster_map(_cfg({"power": ["VRT", "pwr"], "defense": ["RKLB"]}))
    assert cmap["power"] == frozenset({"VRT", "PWR"})       # members upper-cased
    assert clusters.cluster_of("pwr", cmap) == "power"      # lookup case-insensitive
    assert clusters.cluster_of("RKLB", cmap) == "defense"
    assert clusters.cluster_of("AAPL", cmap) is None        # unclustered → singleton (cap inert)
    assert clusters.members_of("power", cmap) == frozenset({"VRT", "PWR"})
    assert clusters.members_of("unknown", cmap) == frozenset()


def test_absent_or_empty_map_is_inert():
    assert clusters.load_cluster_map({"convexity_book": {}}) == {}
    assert clusters.load_cluster_map({}) == {}
    assert clusters.load_cluster_map(_cfg({})) == {}


def test_comment_key_is_skipped():
    cmap = clusters.load_cluster_map(_cfg({"_comment": "doc only", "power": ["VRT"]}))
    assert set(cmap) == {"power"}


def test_overlap_raises_fail_closed():
    with pytest.raises(ClusterConfigError, match="two clusters"):
        clusters.load_cluster_map(_cfg({"a": ["VRT", "PWR"], "b": ["PWR"]}))


def test_cluster_fraction_below_per_name_raises():
    # A cluster must be able to hold >=1 full-size name (else every clustered name is un-openable).
    with pytest.raises(ClusterConfigError, match="cluster_fraction"):
        clusters.load_cluster_map(_cfg({"a": ["VRT"]}, cluster_fraction=0.005, per_name_fraction=0.01))


def test_bad_member_types_raise():
    with pytest.raises(ClusterConfigError):
        clusters.load_cluster_map(_cfg({"a": "VRT"}))   # not a list
    with pytest.raises(ClusterConfigError):
        clusters.load_cluster_map(_cfg({"a": [123]}))   # not strings


def test_shipped_config_taxonomy_is_a_valid_partition():
    from dramatic_options import config_loader
    config_loader.load_config.cache_clear()
    cmap = clusters.load_cluster_map(config_loader.load_config())
    config_loader.load_config.cache_clear()
    assert {"ai_capex_power", "space_defense"} <= set(cmap)
    all_syms = [s for ms in cmap.values() for s in ms]
    assert len(all_syms) == len(set(all_syms))                      # disjoint (uniqueness held)
    assert clusters.cluster_of("RKLB", cmap) == "space_defense"     # routed by driver
    assert clusters.cluster_of("VRT", cmap) == "ai_capex_power"
    assert clusters.cluster_of("FCX", cmap) is None                 # FCX deliberately unclustered
