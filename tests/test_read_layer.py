"""The frozen read-layer pins (read_layer.py) — every number hand-checked against the
2026-07-04 pre-reg (leg-aware §1, blocked §2, calendar+floor §3, ledger coercions/matching §4)."""

from __future__ import annotations

import json

import pytest

import read_layer as rl
import state

# ── §1 leg-aware band ────────────────────────────────────────────────────────────────────────────


def test_haircut_leg_aware_hand_checked():
    # expiry-settled: entry leg only → 14 / 1.125 = 12.4444…
    assert rl.haircut_multiple(14.0, "expiry") == pytest.approx(12.44444, abs=1e-4)
    # market close: both legs → 14 × 0.875 / 1.125 = 10.8888…
    assert rl.haircut_multiple(14.0, "profit_take_10x") == pytest.approx(10.88888, abs=1e-4)
    # unknown reason takes BOTH legs — the conservative direction, pinned.
    assert rl.haircut_multiple(1.0, None) == pytest.approx(0.77777, abs=1e-4)
    # a total loss is 0 under every column.
    assert rl.haircut_multiple(0.0, "expiry") == 0.0


def test_band_two_columns():
    rows = [(10.0, "expiry"), (0.0, "expiry"), (2.0, "profit_take_10x")]
    b = rl.band(rows)
    assert b["frictionless"]["n"] == 3 and b["frictionless"]["max"] == 10.0
    assert b["conservative"]["max"] == pytest.approx(10.0 / 1.125, abs=1e-6)
    assert b["conservative"]["p50"] == pytest.approx(2.0 * 0.875 / 1.125, abs=1e-6)


# ── §2 cluster-blocked CI ────────────────────────────────────────────────────────────────────────


def test_cluster_blocked_ci_blocks_and_instability():
    cmap = {"nuclear": ["UUUU", "NXE"], "silver": ["AG", "HL"]}
    rows = [("UUUU", 1.0), ("NXE", 2.0), ("AG", 3.0), ("HL", 4.0), ("FRO", 5.0)]
    ci = rl.cluster_blocked_ci(rows, cmap, iters=200, seed=1)
    # nuclear + silver + the FRO singleton = 3 blocks → n=5, n_blocks=3, unstable (<5).
    assert ci["n"] == 5 and ci["n_blocks"] == 3 and ci["unstable"] is True
    assert ci["point"] == 5.0  # p95 of 5 values = the max
    assert ci["lo"] <= ci["point"] <= ci["hi"]
    assert rl.cluster_blocked_ci([], cmap)["unstable"] is True


# ── §3 calendar + floor ──────────────────────────────────────────────────────────────────────────


def test_resolution_calendar_expiry_minus_21(convexity_db):
    state.record_shadow_position(
        convexity_db, run_id=None, origin="sentinel", opened_at="2026-07-02T19:48:00+00:00",
        theme="t", symbol="UUUU", direction="bullish", structure_kind="C",
        contract_symbol="UUUU270115C00030000", expiry="2027-01-15", strike=30.0, dte=197,
        moneyness=0.25, contracts=4, entry_premium_per_contract=240.5, total_premium=962.0,
        entry_spot=24.0)
    cal = rl.resolution_calendar(convexity_db)
    # HAND-CHECKED: 2027-01-15 − 21d = 2026-12-25.
    assert cal["shadow"]["n_open"] == 1 and cal["shadow"]["earliest"] == "2026-12-25"
    assert cal["shadow"]["by_month"] == {"2026-12": 1}
    assert cal["real"]["n_open"] == 0


def test_directional_floor_verbatim():
    cmap = {"a": ["A1", "A2"], "b": ["B1"], "c": ["C1"]}
    ten_a = [(s, 1.0) for s in ("A1", "A2", "B1", "C1", "A1", "A2", "B1", "C1", "A1", "B1")]
    below = rl.directional_floor(ten_a[:9], ten_a, cmap)
    assert below["met"] is False and below["verdict"] == rl.ACCRUING
    met = rl.directional_floor(ten_a, ten_a, cmap)
    assert met["met"] is True and met["clusters_a"] == 3


# ── §4 ledger coercions + variants + matching ───────────────────────────────────────────────────


def _fields(**kw):
    base = {"include": True, "conviction": "MODERATE", "structural_vs_fad": "structural",
            "under_narrated": True, "at_inflection": True}
    base.update(kw)
    return rl._strategist_fields(json.dumps({"strategist": base}))


def test_coercions_pinned():
    f = _fields()
    assert f["structural"] is True and f["missing"] is False
    assert _fields(structural_vs_fad="fad")["structural"] is False
    # the missing class: absent field ⇒ None + missing=True (never coerced to false)
    raw = json.dumps({"strategist": {"include": True, "conviction": "MODERATE",
                                     "under_narrated": True, "at_inflection": True}})
    f2 = rl._strategist_fields(raw)
    assert f2["structural"] is None and f2["missing"] is True
    # non-deliberated rows (no strategist stage) → None
    assert rl._strategist_fields(json.dumps({"dropped": "x"})) is None


def test_variants_hand_checked():
    pl = _fields()  # the PL shape: include ∧ MODERATE ∧ all three true
    assert all(rl._variant_pass(pl, v) for v in ("V1", "V2", "V4"))
    assert rl._variant_pass(pl, "V3") is False  # V3 floor is HIGH
    two_of_three = _fields(at_inflection=False)
    assert rl._variant_pass(two_of_three, "V1") is True   # any 2 of 3
    assert rl._variant_pass(two_of_three, "V2") is True   # structural ∧ under_narrated
    assert rl._variant_pass(two_of_three, "V4") is False  # the actual mandate
    only_structural = _fields(at_inflection=False, under_narrated=False)
    assert rl._variant_pass(only_structural, "V1") is False
    no_include = _fields(include=False)
    assert not any(rl._variant_pass(no_include, v) for v in ("V1", "V2", "V3", "V4"))


def test_ledger_matching_symbol_and_direction(convexity_db):
    convexity_db.execute("INSERT OR IGNORE INTO runs (id, started_at, mode) VALUES (1,'2026-07-01','PAPER')")
    # A V4-passing deliberated proposal on PL-bullish, 2026-07-01.
    state.record_council_proposal(
        convexity_db, run_id=1, as_of="2026-07-01T19:47:00+00:00", theme="t", symbol="PL",
        direction="bullish", conviction="MODERATE", structural_vs_fad="structural",
        weakest_point=None,
        rationale={"strategist": {"include": True, "conviction": "MODERATE",
                                  "structural_vs_fad": "structural", "under_narrated": True,
                                  "at_inflection": True}},
        strategist_summary=None, cost_usd=0.0, model_mix={}, status="traded")
    # Shadow rows: a CLOSED PL-bullish within ±5td (matches, resolved) and a PL-bearish (must NOT match).
    pid = state.record_shadow_position(
        convexity_db, run_id=1, origin="sentinel", opened_at="2026-06-29T19:48:00+00:00",
        theme="t", symbol="PL", direction="bullish", structure_kind="C",
        contract_symbol="PL270115C00040000", expiry="2027-01-15", strike=40.0, dte=200,
        moneyness=0.25, contracts=1, entry_premium_per_contract=690.0, total_premium=690.0,
        entry_spot=32.0)
    convexity_db.execute(
        "UPDATE shadow_positions SET status='closed', realized_multiple=3.0, exit_reason='expiry' "
        "WHERE id=?", (pid,))
    state.record_shadow_position(
        convexity_db, run_id=1, origin="sentinel", opened_at="2026-07-01T19:48:00+00:00",
        theme="t", symbol="PL", direction="bearish", structure_kind="P",
        contract_symbol="PL270115P00025000", expiry="2027-01-15", strike=25.0, dte=200,
        moneyness=0.25, contracts=1, entry_premium_per_contract=300.0, total_premium=300.0,
        entry_spot=32.0)
    led = rl.mandate_ledger(convexity_db)
    v4 = led["variants"]["V4"]
    # HAND-CHECKED: 1 deliberated, 0 missing; V4 set = {PL}; matched to the CLOSED bullish row
    # (multiple 3.0, expiry) — the bearish same-symbol row is direction-blocked.
    assert led["n_deliberated"] == 1 and led["n_missing_class"] == 0
    assert v4["n_set"] == 1 and v4["match_rate"] == 1.0
    assert v4["matched"] == [("PL", 3.0, "expiry")]
    assert v4["by_vintage"] == {"v1_2a": 1, "v2b": 0}


def test_read_layer_never_touches_booking():
    import inspect

    src = inspect.getsource(rl)
    for forbidden in ("record_shadow_position", "record_fixed_basket_position", "submit",
                      "record_convexity_position", "import broker"):
        assert forbidden not in src
