"""Forward-catalyst grounding channel — PR1 (ContextPack block + §4 counters). Offline.

PREREG_FORWARD_CATALYST_GROUNDING (frozen 2026-07-09). The load-bearing invariants:
§1 ground-never-permission (`grounded` untouched) · §2 schema (class b excluded; event_date
required for a/c, null for d) · §3 expiry/staleness/provenance discipline · §4 counters +
origin scope v0 (hand-seed only; sentinel/framer packs byte-unchanged) · §7 fail-soft + bounds.
Every counter/render value hand-checked (the anti-HARK value-test discipline).
"""

import json
from datetime import datetime

from council import agents
from council.context import ContextPack, build_context_pack, sentinel_context_pack
from data.forward_catalysts import ForwardCatalysts
from themes import Theme

AS_OF = datetime(2026, 7, 15, 19, 45)

HAND = Theme("bead_buildout", "ADTN", "bullish", "BEAD construction-start expression")
SENT = Theme("disc_theme", "ADTN", "bullish", "discovery hypothesis (markers-grounded)",
             source="sentinel", markers={"momentum": 1.2, "price": 10.0, "adv_usd": 5e6})


def _write(tmp_path, items):
    p = tmp_path / "fc.json"
    p.write_text(json.dumps({"items": items}))
    return str(p)


def _item(**kw):
    """A valid class-(c) item; override to break specific §2 fields."""
    base = {"symbol": "ADTN", "class": "c",
            "claim": "State X announced BEAD construction start for 2026-09-15",
            "event_date": "2026-09-15",
            "source": "State X broadband office announcement 2026-06-20",
            "as_of": "2026-07-01", "expires": "2026-09-22", "provenance": "operator"}
    base.update(kw)
    return base


# ── loader + §2 schema validation ─────────────────────────────────────────────

def test_valid_items_load_and_render(tmp_path):
    fc = ForwardCatalysts(_write(tmp_path, [
        _item(),
        _item(**{"class": "a"}, claim="45Z credit steps down", event_date="2027-01-01",
              expires="2027-01-08"),
        _item(**{"class": "d"}, claim="APT domestic print RMB 720k/t", event_date=None,
              expires="2026-07-20"),
    ]))
    items = fc.items_asof("ADTN", AS_OF)
    assert len(items) == 3 and fc.counters() == {
        "rendered_n": 3, "expired_n": 0, "malformed_n": 0, "stale_flagged_n": 0}
    # Deterministic order (§4): dated (a)/(c) by nearest event_date, then (d).
    assert [i["class"] for i in items] == ["c", "a", "d"]


def test_class_b_and_unknown_classes_are_malformed(tmp_path):
    # §2: class (b) is EXCLUDED — one home for filed lines (the fundamentals corpus).
    fc = ForwardCatalysts(_write(tmp_path, [_item(**{"class": "b"}), _item(**{"class": "x"})]))
    assert fc.items_asof("ADTN", AS_OF) == [] and fc.counters()["malformed_n"] == 2


def test_event_date_rules_per_class(tmp_path):
    # (a)/(c) REQUIRE an ISO event_date; (d) MUST carry null (a fictitious date is
    # instrument-shaped entry — §2/F-b).
    fc = ForwardCatalysts(_write(tmp_path, [
        _item(event_date=None),                                  # c, missing → malformed
        _item(event_date="soon"),                                # c, unparseable → malformed
        _item(**{"class": "d"}, event_date="2026-09-15"),        # d, dated → malformed
    ]))
    assert fc.items_asof("ADTN", AS_OF) == [] and fc.counters()["malformed_n"] == 3


def test_generated_provenance_refused(tmp_path):
    # §3: no LLM-authored facts — 'generated' is reserved; the F-b tripwire refuses it.
    fc = ForwardCatalysts(_write(tmp_path, [_item(provenance="generated")]))
    assert fc.items_asof("ADTN", AS_OF) == [] and fc.counters()["malformed_n"] == 1


def test_missing_keys_malformed(tmp_path):
    it = _item()
    del it["source"]
    fc = ForwardCatalysts(_write(tmp_path, [it]))
    assert fc.counters()["malformed_n"] == 1


# ── §3 temporal discipline ────────────────────────────────────────────────────

def test_expired_item_drops_counted(tmp_path):
    fc = ForwardCatalysts(_write(tmp_path, [_item(expires="2026-07-10")]))  # < AS_OF
    assert fc.items_asof("ADTN", AS_OF) == []
    assert fc.counters() == {"rendered_n": 0, "expired_n": 1, "malformed_n": 0,
                             "stale_flagged_n": 0}


def test_stale_item_flags_but_renders(tmp_path):
    # as_of 2026-06-01 → 44d old at render > N=30 → flagged AND rendered (§3 fail-soft).
    fc = ForwardCatalysts(_write(tmp_path, [_item(as_of="2026-06-01")]))
    assert len(fc.items_asof("ADTN", AS_OF)) == 1
    assert fc.counters()["stale_flagged_n"] == 1 and fc.counters()["rendered_n"] == 1


def test_future_pin_is_malformed(tmp_path):
    # PIT: an item pinned AFTER render as_of is an entry error, never evidence.
    fc = ForwardCatalysts(_write(tmp_path, [_item(as_of="2026-08-01")]))
    assert fc.items_asof("ADTN", AS_OF) == [] and fc.counters()["malformed_n"] == 1


def test_missing_file_is_live_but_empty(tmp_path):
    fc = ForwardCatalysts(str(tmp_path / "nope.json"))
    assert fc.items_asof("ADTN", AS_OF) == [] and fc.counters()["rendered_n"] == 0


def test_unreadable_file_fails_soft(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    fc = ForwardCatalysts(str(p))
    assert fc.items_asof("ADTN", AS_OF) == []


# ── §7/§10 bounds ─────────────────────────────────────────────────────────────

def test_k_bound_takes_nearest_dated_first(tmp_path):
    items = [_item(event_date=f"2026-09-{d:02d}", expires=f"2026-10-{d:02d}",
                   claim=f"milestone {d}") for d in (20, 10, 15, 25)]
    fc = ForwardCatalysts(_write(tmp_path, items), max_items=3)
    out = fc.items_asof("ADTN", AS_OF)
    assert [i["event_date"] for i in out] == ["2026-09-10", "2026-09-15", "2026-09-20"]
    assert fc.counters()["rendered_n"] == 3  # the 4th never renders, K=3


def test_char_bound_truncates_trailing_items(tmp_path):
    items = [_item(claim="x" * 900, event_date=f"2026-09-{d:02d}", expires="2026-10-01")
             for d in (10, 11, 12)]
    fc = ForwardCatalysts(_write(tmp_path, items), max_block_chars=1600)
    assert len(fc.items_asof("ADTN", AS_OF)) == 1  # item 2 would breach 1600 → truncated


def test_items_asof_accepts_tz_aware_as_of(tmp_path):
    # The LIVE clock hands an aware datetime (the first live probe run raised TypeError on the
    # naive/aware comparison). Expiry/staleness/PIT must all evaluate identically.
    from datetime import UTC
    fc = ForwardCatalysts(_write(tmp_path, [_item()]))
    assert len(fc.items_asof("ADTN", AS_OF.replace(tzinfo=UTC))) == 1
    fc2 = ForwardCatalysts(_write(tmp_path, [_item(expires="2026-07-10")]))
    assert fc2.items_asof("ADTN", AS_OF.replace(tzinfo=UTC)) == [] and fc2.counters()["expired_n"] == 1


def test_symbol_scoping_and_counter_accumulation(tmp_path):
    fc = ForwardCatalysts(_write(tmp_path, [
        _item(), _item(symbol="KMT", **{"class": "d"}, event_date=None, expires="2026-07-20",
                       claim="APT print"),
    ]))
    assert len(fc.items_asof("ADTN", AS_OF)) == 1
    assert len(fc.items_asof("KMT", AS_OF)) == 1
    assert fc.items_asof("NVDA", AS_OF) == []
    assert fc.counters()["rendered_n"] == 2  # accumulates across the cycle's calls


# ── ContextPack render + §1/§5 invariants ─────────────────────────────────────

def _pack(**kw):
    base = dict(symbol="ADTN", theme="bead_buildout", direction="bullish",
                operator_thesis="t", headlines=["BEAD award moved 12%"], coverage_count=1,
                has_numeric=True, as_of=AS_OF)
    base.update(kw)
    return ContextPack(**base)


def test_block_renders_after_fundamentals_with_iso_dates():
    p = _pack(fundamentals=[{"concept": "revenue", "metric": "qtr_yoy", "value": 0.12,
                             "latest_musd": 10, "base_musd": 9, "period_end": "2026-03-31",
                             "filed": "2026-05-01"}],
              forward_catalysts=[_item()])
    block = p.as_prompt_block()
    assert "FORWARD_CATALYSTS (dated public evidence, operator-pinned):" in block
    # The ISO event_date renders verbatim — the §3 load-bearing figure / §8 cite token.
    assert "[program milestone; event date 2026-09-15]" in block
    assert "pinned 2026-07-01" in block
    assert block.index("FUNDAMENTALS:") < block.index("FORWARD_CATALYSTS")


def test_class_a_and_d_render_kinds():
    p = _pack(forward_catalysts=[
        _item(**{"class": "a"}, claim="45Z steps down", event_date="2027-01-01"),
        _item(**{"class": "d"}, claim="APT RMB 720k/t", event_date=None),
    ])
    block = p.as_prompt_block()
    assert "[statutory event; event date 2027-01-01] 45Z steps down" in block
    assert "[input-price print] APT RMB 720k/t" in block


def test_empty_block_is_byte_identical():
    # §4: default-empty ⇒ the pre-channel pack renders byte-for-byte.
    assert _pack().as_prompt_block() == _pack(forward_catalysts=[]).as_prompt_block()
    assert "FORWARD_CATALYSTS" not in _pack().as_prompt_block()


def test_grounded_is_never_touched_by_catalysts():
    # §1 GROUND-NEVER-PERMISSION: an ungrounded hand-seed with a catalyst STAYS ungrounded
    # (a grounded-flip would be permission — explicitly not this channel's behavior change).
    p = _pack(headlines=[], coverage_count=0, has_numeric=False,
              forward_catalysts=[_item()])
    assert p.grounded is False
    assert "GROUNDING: INSUFFICIENT" in p.as_prompt_block()


def test_malformed_item_in_pack_renders_to_nothing_never_raises():
    p = _pack(forward_catalysts=[{"class": "c", "claim": "", "source": None}, {"junk": 1}])
    block = p.as_prompt_block()  # must not raise (§7 fail-soft inside run_candidate)
    assert "FORWARD_CATALYSTS" not in block


# ── origin scope v0: hand-seed only (§5-read safety / framer leash) ───────────

class _FakeCatalysts:
    def __init__(self):
        self.calls = []

    def items_asof(self, symbol, as_of):
        self.calls.append(symbol)
        return [_item(symbol=symbol)]

    def counters(self):
        return {"rendered_n": len(self.calls), "expired_n": 0, "malformed_n": 0,
                "stale_flagged_n": 0}


def test_build_context_pack_hand_seed_gets_block():
    fc = _FakeCatalysts()
    p = build_context_pack(HAND, news=None, as_of=AS_OF, catalysts=fc)
    assert p.forward_catalysts and fc.calls == ["ADTN"]
    assert "FORWARD_CATALYSTS" in p.as_prompt_block()


def test_build_context_pack_sentinel_never_touches_channel():
    # The sentinel branch returns BEFORE the channel fetch — provider never called,
    # pack byte-identical to a no-channel sentinel pack (§5-read safety).
    fc = _FakeCatalysts()
    with_ch = build_context_pack(SENT, news=None, as_of=AS_OF, catalysts=fc)
    without = build_context_pack(SENT, news=None, as_of=AS_OF)
    assert fc.calls == [] and with_ch.forward_catalysts == []
    assert with_ch.as_prompt_block() == without.as_prompt_block()


def test_framer_pack_byte_identical():
    # The T3 framer calls sentinel_context_pack directly — no channel parameter even exists.
    p = sentinel_context_pack(SENT, as_of=AS_OF)
    assert p.forward_catalysts == [] and "FORWARD_CATALYSTS" not in p.as_prompt_block()


def test_channel_provider_error_fails_soft():
    class _Boom:
        def items_asof(self, symbol, as_of):
            raise RuntimeError("boom")

    p = build_context_pack(HAND, news=None, as_of=AS_OF, catalysts=_Boom())
    assert p.forward_catalysts == []
    assert any("forward_catalysts error" in n for n in p.notes)


# ── the §4 stamps (runs.note counters + the model_mix capability stamp) ───────

def test_stamp_writes_counters_and_capability(convexity_db):
    import orchestrator
    import state
    from council.router import FakeRouter

    run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    fc = _FakeCatalysts()
    fc.items_asof("ADTN", AS_OF)  # rendered_n=1
    orchestrator._stamp_council_health(
        convexity_db, run_id, {"forward_catalysts": {"enabled": True}}, FakeRouter(),
        catalysts=fc)
    row = convexity_db.execute("SELECT note, model_mix FROM runs WHERE id=?", (run_id,)).fetchone()
    # Hand-checked §4 stamp: 1 rendered, everything else 0; capability stamp per the prereg.
    assert "fwd_catalysts: rendered=1 expired=0 malformed=0 stale_flagged=0" in row["note"]
    assert json.loads(row["model_mix"])["forward_catalysts"] == "forward_catalyst_v1"


def test_stamp_omits_capability_when_channel_disabled(convexity_db):
    import orchestrator
    import state
    from council.router import FakeRouter

    run_id = state.record_run(convexity_db, mode="TEST", equity=None, note="t")
    orchestrator._stamp_council_health(convexity_db, run_id, {}, FakeRouter(), catalysts=None)
    row = convexity_db.execute("SELECT note, model_mix FROM runs WHERE id=?", (run_id,)).fetchone()
    assert "fwd_catalysts" not in (row["note"] or "")
    assert "forward_catalysts" not in json.loads(row["model_mix"])


# ── PR2: the §8 shared tokenizer + the §3 authenticity-filter extension ───────

def test_cite_tokens_iso_dates_and_distinctive_figures():
    from council.context import catalyst_cite_tokens
    toks = catalyst_cite_tokens([_item(
        claim="APT hit RMB 720k/t, EU $2,900-3,180/mtu; up 9.5% since 2026; 45Z unaffected",
        event_date="2026-09-15")])
    # Hand-checked: full ISO dates (event_date, as_of, the source's inline date) are tokens.
    assert "2026-09-15" in toks and "2026-07-01" in toks and "2026-06-20" in toks
    # Multi-digit figures kept, comma-normalized; decimals kept.
    assert "720" in toks and "2900" in toks and "3180" in toks and "9.5" in toks
    # §8 distinctiveness: bare years and small integers EXCLUDED (the (i)→(ii) misroute guard).
    assert "2026" not in toks and "45" not in toks and "15" not in toks


def test_cite_tokens_bare_year_vs_large_number_boundary():
    from council.context import catalyst_cite_tokens
    toks = catalyst_cite_tokens([_item(claim="capacity 2100 MW by 2099, floor 1900 units",
                                       source="src")])
    # 2100 is NOT a plausible year (>2099) → kept; 2099 and 1900 are bare years → excluded.
    assert "2100" in toks and "2099" not in toks and "1900" not in toks


def test_cite_tokens_malformed_item_yields_nothing():
    from council.context import catalyst_cite_tokens
    assert catalyst_cite_tokens([{"claim": None}, {}, {"claim": 42}]) == []


def test_filter_supports_block_citations():
    from council.filters import apply_filter
    p = _pack(forward_catalysts=[_item(
        claim="APT print RMB 720k/t confirmed", event_date="2026-09-15")])
    # A strategist citing the event date + a claim figure + a quoted claim span must NOT flag.
    conf, res = apply_filter(
        ['inflection dated 2026-09-15; the "APT print RMB 720k/t confirmed" evidence holds'],
        p, confidence="HIGH")
    assert conf == "HIGH" and res.flagged == 0


def test_filter_still_flags_fabrications_with_block_present():
    from council.filters import apply_filter
    p = _pack(forward_catalysts=[_item()])
    conf, res = apply_filter(["margins will hit 87.5% on the catalyst"], p, confidence="HIGH")
    assert conf == "MODERATE" and res.flagged == 1  # 87.5 appears nowhere in the evidence


def test_evidence_text_unchanged_without_catalysts():
    from council.filters import evidence_text
    # Empty channel ⇒ the pre-channel evidence pool byte-for-byte (framer/sentinel packs safe).
    assert evidence_text(_pack()) == evidence_text(_pack(forward_catalysts=[]))


# ── the frozen-prompt seam (§1: the channel rides the pack, never the prompt) ─

def test_council_prompts_unchanged_by_this_pr():
    import hashlib
    shas = [hashlib.sha256(s.encode()).hexdigest()[:16]
            for s in (agents._COMMON, agents.ADVERSARY_SYSTEM, agents.STRATEGIST_SYSTEM)]
    assert shas == ["d96f18ebc865a384", "dc3d21ca8f6444cb", "ecbf363c9802289d"]
