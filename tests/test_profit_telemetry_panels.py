"""The 2026-11-03 telemetry panels render on a migrated DB (dd.safe would otherwise hide an error)."""

import dashboard_data as dd


def test_panels_render_without_error(convexity_db, tmp_path):
    ex = dd.execution_panel(convexity_db)
    assert ex["summary"]["all"]["approvals"] == 0 and ex["rows"] == []
    iv = dd.iv_history_panel(convexity_db, tmp_path / "cache")
    assert iv["rows"] == [] and iv["status"].startswith("percentiles accruing")
    att = dd.attention_panel(tmp_path / "cache")
    assert att["rows"] == [] and att["records"] == 0
    cx = dd.capex_cycle_panel(tmp_path / "cache")
    assert cx["rows"] == [] and cx["as_of"] is None
    fa = dd.falsifier_panel({"universe": {"themes": {"cyber_sase": ["NTSK"]}}})
    assert "error" not in fa and isinstance(fa["waiting"], list)
