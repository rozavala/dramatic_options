"""#403 — a council role citing a date it was SHOWN (a filing date) is quoting the evidence, not inventing it.

Option A (operator word 2026-10-31): full ISO dates are checked whole against the dates rendered in the agent's prompt
block; an unshown date flags once; the figure pool stays date-free so a fabricated bare number still flags. Stamp
``quote_filter = musd_billions_v1+iso_dates_v1``. The discovery framer keeps the pre-#403 scan."""

from __future__ import annotations

import dataclasses
import inspect
import json
import random

import orchestrator
from council.context import synthetic_context_pack
from council.debate import run_candidate
from council.filters import apply_filter, authenticity_scan, rendered_dates
from council.router import FakeRouter
from themes import Theme

SMR = Theme("nuclear", "SMR", "bullish", "small modular reactors")
FUND = [{"concept": "revenue", "metric": "qtr_yoy", "value": -0.62, "latest_musd": 8.1, "base_musd": 21.3,
         "period_end": "2026-06-30", "filed": "2026-08-07"}]


def _pack():
    return dataclasses.replace(synthetic_context_pack(SMR), fundamentals=FUND)


def _council(texts):
    return apply_filter(texts, _pack(), confidence="MODERATE", accept_rendered_dates=True)


def test_citing_a_rendered_filing_date_no_longer_dampens():
    conf, res = _council(["The revenue collapse (-62.0%) is from a filing dated 2026-06-30"])
    assert (conf, res.flagged) == ("MODERATE", 0)
    conf, res = _council(["revenue -62.0% ($8.1M vs $21.3M); period 2026-06-30, filed 2026-08-07"])  # verbatim line
    assert (conf, res.flagged) == ("MODERATE", 0)


def test_an_unrendered_date_flags_once_not_three_fragments():
    conf, res = _council(["the contract award lands on 2026-12-15"])
    assert conf == "LOW" and res.details == ["unsupported date: 2026-12-15"]


def test_a_fabricated_bare_number_still_flags_the_pool_gains_no_date_digits():
    # "2026", "06", "30" exist in the pack only inside the rendered date — they must not become citable figures.
    conf, res = _council(["management guided 2026 units and 30 reactors"])
    assert conf == "LOW" and res.details == ["unsupported figure: 2026", "unsupported figure: 30"]


def test_rendered_dates_are_what_the_prompt_block_shows():
    pack = _pack()
    assert {"2026-06-30", "2026-08-07"} <= rendered_dates(pack)
    assert all(d in pack.as_prompt_block() for d in rendered_dates(pack))


def test_a_forward_catalyst_date_is_still_accepted():
    item = {"symbol": "SMR", "class": "a", "claim": "EPA rule takes effect", "event_date": "2026-11-16",
            "source": "Federal Register 2026-19071", "as_of": "2026-10-30", "expires": "2026-11-23"}
    pack = dataclasses.replace(_pack(), forward_catalysts=[item])
    conf, res = apply_filter(["the rule takes effect 2026-11-16"], pack, confidence="MODERATE", accept_rendered_dates=True)
    assert (conf, res.flagged) == ("MODERATE", 0)


def test_the_framer_path_is_byte_identical_to_the_pre_403_scan():
    pack, text = _pack(), ["from a filing dated 2026-06-30"]
    conf, res = apply_filter(text, pack, confidence="MODERATE")            # default: the framer's call
    assert conf == "LOW" and res.details == ["unsupported figure: 2026", "unsupported figure: 06",
                                             "unsupported figure: 30"]
    assert authenticity_scan(text, "x").details == res.details             # dates=None ≡ the old scan


def _responder(role, system, user):
    if role == "proposer":
        return json.dumps({"theme": "t", "symbol": "SMR", "direction": "bullish", "structural_vs_fad": "structural",
                           "inflection_thesis": "the 2026-06-30 quarter shows the turn", "confidence": "HIGH",
                           "cited": ["period 2026-06-30, filed 2026-08-07"]})
    if role == "adversary":
        return json.dumps({"counter_case": "the filing dated 2026-08-07 shows revenue -62.0%", "weakest_point": "w",
                           "is_fad": False, "already_consensus": False, "inflection_passed": False,
                           "confidence": "MODERATE", "cited": []})
    return json.dumps({"include": True, "conviction": "MODERATE", "direction": "bullish",
                       "summary": "its latest filing (2026-06-30 quarter, filed 2026-08-07) shows the driver",
                       "weakest_point": "one quarter", "structural_vs_fad": "structural",
                       "under_narrated": True, "at_inflection": True})


def test_all_three_council_roles_accept_the_dates_they_were_shown():
    prop = run_candidate(SMR, _pack(), FakeRouter(responder=_responder), rng=random.Random(0))
    by_role = {a.role: a for a in prop.agent_outputs}
    assert {r: a.flagged_unsupported for r, a in by_role.items()} == {"proposer": 0, "adversary": 0, "strategist": 0}
    assert by_role["strategist"].confidence == "MODERATE" and prop.conviction == "MODERATE"   # stays at the floor


def test_the_run_stamp_names_the_filter_version():
    assert 'mix["quote_filter"] = "musd_billions_v1+iso_dates_v1"' in inspect.getsource(orchestrator)
