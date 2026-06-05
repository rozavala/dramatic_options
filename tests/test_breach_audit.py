"""breach_audit — the INDEPENDENT cluster-cap recompute (T4-unlock condition #3).

Hand-checked value tests (anti-HARK, PREREG_CONVEXITY_CALIBRATION §6): the cap is
account_equity·cluster_fraction = 100000·0.02 = $2000 for ai_capex_power.
"""

from __future__ import annotations

import breach_audit
import state

CONFIG = {
    "convexity_book": {
        "account_equity": 100000.0, "cluster_fraction": 0.02, "per_name_fraction": 0.01,
        "clusters": {"ai_capex_power": ["VRT", "PWR", "GEV"], "space_defense": ["RKLB", "KTOS"]},
    }
}
CAP = 2000.0  # 100000 * 0.02


def _pos(conn, symbol, total_premium, *, opened_at, run_id=None, status="open"):
    pid = state.record_convexity_position(
        conn, run_id=run_id, opened_at=opened_at, theme="ai_compute", symbol=symbol, direction="bullish",
        structure_kind="long_call", contract_symbol=f"{symbol}C", expiry="2027-01-15", strike=100.0,
        dte=300, moneyness=0.25, contracts=1, entry_premium_per_contract=total_premium,
        total_premium=total_premium, status=status,
    )
    return pid


def test_empty_book_is_vacuous(convexity_db):
    r = breach_audit.audit_cluster_breaches(convexity_db, CONFIG)
    assert r["n_admissions"] == 0
    assert r["n_clustered_admissions"] == 0
    assert r["n_breaches"] == 0
    assert r["vacuous"] is True  # 0 breaches over 0 admissions is NOT a pass


def test_within_cap_zero_breaches(convexity_db):
    _pos(convexity_db, "VRT", 800.0, opened_at="2026-06-01T00:00:00+00:00")
    _pos(convexity_db, "PWR", 800.0, opened_at="2026-06-02T00:00:00+00:00")
    r = breach_audit.audit_cluster_breaches(convexity_db, CONFIG)
    assert r["n_clustered_admissions"] == 2
    assert r["n_breaches"] == 0
    assert r["vacuous"] is False  # 2 real clustered admissions stayed within $1600 <= $2000


def test_over_cap_one_breach(convexity_db):
    # VRT(t1)=1500 alone is fine; PWR(t2)=1500 pushes the cluster to 3000 > 2000 at PWR's admission.
    _pos(convexity_db, "VRT", 1500.0, opened_at="2026-06-01T00:00:00+00:00")
    _pos(convexity_db, "PWR", 1500.0, opened_at="2026-06-02T00:00:00+00:00")
    r = breach_audit.audit_cluster_breaches(convexity_db, CONFIG)
    assert r["n_clustered_admissions"] == 2
    assert r["n_breaches"] == 1
    b = r["breaches"][0]
    assert b["symbol"] == "PWR"
    assert b["cluster"] == "ai_capex_power"
    assert b["committed"] == 3000.0
    assert b["cap"] == CAP


def test_stamped_cap_overrides_config(convexity_db):
    # A position within the config cap ($800 <= $2000) but over a TIGHTER then-live STAMPED cap ($500).
    pid = _pos(convexity_db, "VRT", 800.0, opened_at="2026-06-01T00:00:00+00:00")
    state.record_convexity_eval(
        convexity_db, run_id=None, as_of="2026-06-01T00:00:00+00:00", theme="ai_compute", symbol="VRT",
        direction="bullish", decision="open", position_id=pid,
        cluster_state={"cluster": "ai_capex_power", "premium": 0.0, "cap": 500.0,
                       "equity": 100000.0, "remaining": 500.0},
    )
    r = breach_audit.audit_cluster_breaches(convexity_db, CONFIG)
    assert r["n_breaches"] == 1
    assert r["breaches"][0]["cap"] == 500.0  # used the stamped then-live cap, not the config $2000


def test_unclustered_is_inert(convexity_db):
    _pos(convexity_db, "ZZZZ", 9000.0, opened_at="2026-06-01T00:00:00+00:00")  # not in any cluster
    r = breach_audit.audit_cluster_breaches(convexity_db, CONFIG)
    assert r["n_admissions"] == 1
    assert r["n_clustered_admissions"] == 0
    assert r["n_breaches"] == 0
    assert r["vacuous"] is True  # the cap is inert for an unclustered singleton


def test_closed_mate_not_counted_after_close(convexity_db):
    # VRT closes before PWR opens → not co-live → no breach even though each is 1500.
    vid = _pos(convexity_db, "VRT", 1500.0, opened_at="2026-06-01T00:00:00+00:00")
    state.close_convexity_position(convexity_db, vid, exit_price=0.0, realized_pnl=-1500.0,
                                   reason="expiry", as_of="2026-06-01T12:00:00+00:00")
    _pos(convexity_db, "PWR", 1500.0, opened_at="2026-06-02T00:00:00+00:00")
    r = breach_audit.audit_cluster_breaches(convexity_db, CONFIG)
    assert r["n_breaches"] == 0  # VRT (closed_at < PWR.opened_at) is not committed at PWR's admission
