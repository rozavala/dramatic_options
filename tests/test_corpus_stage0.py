"""Stage-0 corpus: the capital-raise (424B5/S-1) adapter + the §2 no-price import guard.

The §2 guard is package-level (audits every ``corpus/*.py``) — it covers future source modules too.
"""

import ast
import pathlib
from datetime import UTC, datetime

from corpus.capital_raises import enumerate_capital_raises
from data.cache import PointInTimeCache

# Synthetic quarterly full-index in the real whitespace-anchored layout (form / company / CIK /
# ISO date / edgar path). Includes an S-1/A (must be EXCLUDED for form=S-1 — exact match) and a
# non-registration form (ignored).
_HEADER = (
    "Description:           Master Index of EDGAR Dissemination Feed by Form Type\n"
    "Form Type   Company Name                       CIK      Date Filed  File Name\n"
    "----------------------------------------------------------------------------\n"
)
_Q1 = _HEADER + (
    "424B5   ACME CAPITAL CORP   899629   2026-03-02   edgar/data/899629/0001104659-26-028897.txt\n"
    "S-1   NEWCO BIO INC   333333   2026-03-10   edgar/data/333333/0001000000-26-000010.txt\n"
    "S-1/A   NEWCO BIO INC   333333   2026-03-12   edgar/data/333333/0001000000-26-000012.txt\n"
    "8-K   SOME OTHER CO   111111   2026-02-01   edgar/data/111111/0000000000-26-000001.txt\n"
)


class _FakeEdgar:
    def __init__(self, by_quarter):
        self._by_quarter = by_quarter

    def fetch_form_index(self, year, quarter):
        return self._by_quarter[(year, quarter)]


def test_enumerate_merges_424b5_and_exact_s1(tmp_path):
    cache = PointInTimeCache(tmp_path)
    recs = enumerate_capital_raises(
        datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC),
        edgar=_FakeEdgar({(2026, 1): _Q1}), cache=cache, cache_dir=tmp_path,
    )
    # 424B5 + EXACT S-1 only (S-1/A excluded, 8-K ignored), sorted by (date_filed, form, accession)
    assert [(r["form"], r["cik"]) for r in recs] == [
        ("424B5", "0000899629"),   # 2026-03-02
        ("S-1", "0000333333"),     # 2026-03-10
    ]
    # structural-only fields — NO price/IV/momentum keys
    assert set(recs[0]) == {"ts", "cik", "company", "accession", "file", "date_filed", "form"}


def test_enumerate_fail_soft_without_edgar(tmp_path):
    # A corpus-source hiccup (no edgar client / offline) must yield [] — never raise (the scheduled
    # Stage-0 assembly fail-soft, mirroring data/ adapters).
    cache = PointInTimeCache(tmp_path)
    assert enumerate_capital_raises(
        datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC),
        edgar=None, cache=cache, cache_dir=tmp_path,
    ) == []


def test_corpus_forbids_price_imports():
    # §2 (PREREG_THEME_GENERATION_STUB Stage 0): corpus modules carry NO prices/IV/momentum/sentiment,
    # enforced at the INPUT layer (auditable, not prompt-hopeful) → they import no market/price source.
    forbidden = ("data.market", "data.alpaca_client", "data.convexity_data", "alpaca")
    pkg = pathlib.Path(__file__).resolve().parents[1] / "corpus"
    for f in sorted(pkg.glob("*.py")):
        mods: list[str] = []
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.Import):
                mods += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
        bad = [m for m in mods if any(m == p or m.startswith(p + ".") for p in forbidden)]
        assert not bad, f"{f.name}: §2 corpus prohibition — forbidden import(s) {bad}"
