"""Greedy-to-per-name-cap convexity sizing: caps, book budget, concurrency, edge cases."""

from convexity_sizing import convexity_position_size

BASE = dict(account_equity=100_000.0, book_fraction=0.10, per_name_fraction=0.01,
            max_open_positions=15)


def test_greedy_to_per_name_cap():
    d = convexity_position_size(**BASE, open_positions_count=0, open_premium_total=0.0,
                                entry_premium_per_share=2.0)  # $200/contract
    # greedy: alloc = min(per-name cap 1000, book 10000) = 1000 → 5 contracts ($1000).
    assert d.contracts == 5
    assert d.total_premium == 1000.0


def test_fcx_like_pricey_wing_now_opens_one():
    # The live regression: a ~$758/contract long-dated wing was vetoed by the old flat slice
    # ($667); greedy-to-cap (alloc $1000) now affords exactly 1 contract.
    d = convexity_position_size(**BASE, open_positions_count=0, open_premium_total=0.0,
                                entry_premium_per_share=7.58)
    assert d.contracts == 1
    assert d.total_premium == 758.0


def test_per_name_cap_binds_even_with_big_book():
    d = convexity_position_size(account_equity=100_000.0, book_fraction=0.50,
                                per_name_fraction=0.01, max_open_positions=15,
                                open_positions_count=0, open_premium_total=0.0,
                                entry_premium_per_share=2.0)
    # big book, but per-name cap 1000 binds → 5 contracts ($1000).
    assert d.total_premium <= 1000.0 + 1e-6
    assert d.contracts == 5


def test_max_open_positions_blocks():
    d = convexity_position_size(**BASE, open_positions_count=15, open_premium_total=0.0,
                                entry_premium_per_share=2.0)
    assert d.contracts == 0
    assert any("max_open_positions" in r for r in d.reasons)


def test_book_exhausted_blocks():
    d = convexity_position_size(**BASE, open_positions_count=3, open_premium_total=10_000.0,
                                entry_premium_per_share=2.0)
    assert d.contracts == 0
    assert any("book budget exhausted" in r for r in d.reasons)


def test_book_remaining_binds_below_one_contract():
    # Only $400 left in the book and a $758 contract → can't afford one (book bounds the cap).
    d = convexity_position_size(**BASE, open_positions_count=5, open_premium_total=9_600.0,
                                entry_premium_per_share=7.58)
    assert d.contracts == 0
    assert any("< one contract" in r for r in d.reasons)


def test_contract_pricier_than_per_name_cap():
    # $11/share = $1100/contract > $1000 per-name cap → cannot afford one.
    d = convexity_position_size(**BASE, open_positions_count=0, open_premium_total=0.0,
                                entry_premium_per_share=11.0)
    assert d.contracts == 0
    assert any("< one contract" in r for r in d.reasons)


def test_nonpositive_inputs():
    assert convexity_position_size(account_equity=0.0, book_fraction=0.1, per_name_fraction=0.01,
                                   max_open_positions=15, open_positions_count=0,
                                   open_premium_total=0.0, entry_premium_per_share=2.0).contracts == 0
    assert convexity_position_size(**BASE, open_positions_count=0, open_premium_total=0.0,
                                   entry_premium_per_share=0.0).contracts == 0


def test_total_never_exceeds_per_name_cap():
    for prem in (0.5, 1.0, 2.0, 3.3, 5.0):
        d = convexity_position_size(**BASE, open_positions_count=0, open_premium_total=0.0,
                                    entry_premium_per_share=prem)
        assert d.total_premium <= 100_000.0 * 0.01 + 1e-6


# ── cluster_remaining bound (PREREG §5 amendment) ────────────────────────────────────────────────

def test_cluster_remaining_none_is_identical_to_no_cluster():
    base = convexity_position_size(**BASE, open_positions_count=0, open_premium_total=0.0,
                                   entry_premium_per_share=2.0)
    clustered = convexity_position_size(**BASE, open_positions_count=0, open_premium_total=0.0,
                                        entry_premium_per_share=2.0, cluster_remaining=None)
    assert clustered == base  # frozen dataclass equality — byte-identical when unclustered


def test_cluster_cap_exhausted_blocks():
    d = convexity_position_size(**BASE, open_positions_count=2, open_premium_total=2_000.0,
                                entry_premium_per_share=2.0, cluster_remaining=0.0)
    assert d.contracts == 0
    assert any("cluster cap exhausted" in r for r in d.reasons)


def test_cluster_remaining_below_one_contract_blocks():
    # Cluster has $300 left, but a $758 contract can't fit — the cluster is the binding cap.
    d = convexity_position_size(**BASE, open_positions_count=2, open_premium_total=2_000.0,
                                entry_premium_per_share=7.58, cluster_remaining=300.0)
    assert d.contracts == 0
    assert any("cluster" in r for r in d.reasons)


def test_cluster_is_the_tightest_of_the_three_caps():
    # per-name $1000, book huge, cluster $250 → cluster binds → 1 contract ($200).
    d = convexity_position_size(**BASE, open_positions_count=0, open_premium_total=0.0,
                                entry_premium_per_share=2.0, cluster_remaining=250.0)
    assert d.contracts == 1 and d.total_premium == 200.0
    assert "cluster left" in d.reasons[0]


def test_cluster_allows_bounded_partial():
    # Cluster room $500 (< per-name $1000); $200 contracts → 2 ($400), cluster-bounded partial.
    d = convexity_position_size(**BASE, open_positions_count=1, open_premium_total=500.0,
                                entry_premium_per_share=2.0, cluster_remaining=500.0)
    assert d.contracts == 2 and d.total_premium == 400.0
