"""seed_ceiling_check.py — the free, offline candidate-universe ceiling check (PREREG_SEEDED_GENERATOR §10).

The #109 ``slice_feasible`` guard checks source-class EXISTENCE (necessary — does the slice have a non-ETF
entity-resolvable source?). This checks candidate-universe NON-EMPTINESS + mechanism-alignment (sufficient):
for a seed theme, list the entity-resolvable second-order source's recipients MINUS the theme's ETF, sorted
by award size, so the operator can eyeball whether any are **quiet, public, ticker-mappable** names — vs
narrated primes + private entities. If the residual is all primes/private, a bounded-live spend would return
a structural/up-chain negative (the corpus source's skew, not the generator's ceiling) — learnable here for
$0. This is the pre-check that would have killed nuclear_fuel before its criterion froze.

Read-only over the PIT cache (no fetch, no spend):

    PYTHONPATH=. python scripts/seed_ceiling_check.py space_smallcap
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from corpus.content import load_content, read_coords, restrict_to_theme  # noqa: E402
from corpus.etf_constituents import SOURCE as ETF_SOURCE  # noqa: E402
from corpus.federal_awards import SOURCE as AWARDS_SOURCE  # noqa: E402
from generator.score import second_order_sources  # noqa: E402

# Per entity-bearing source: the record field carrying the company entity + a magnitude field for ranking.
# Extend for customer_concentration / capital_raises when option (b) routes them theme-scoped.
_ENTITY_FIELD: dict[str, tuple[str, str | None]] = {AWARDS_SOURCE: ("recipient", "amount")}


def _norm(s: str | None) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper())
    s = re.sub(r"\b(CORP|CORPORATION|INC|INCORPORATED|LLC|CO|COMPANY|LTD|LP|SYSTEMS|TECHNOLOGIES|TECH|"
               r"GROUP|HOLDINGS|THE)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _load(cache: Path, source: str, key: str) -> list[dict]:
    p = cache / source / f"{key}.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    return d["records"] if isinstance(d, dict) and "records" in d else d


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    seed = argv[0] if argv else "space_smallcap"
    cache = Path(argv[1]) if len(argv) > 1 else Path("data/cache")
    content = load_content()
    config = json.loads(Path("config.json").read_text()) if Path("config.json").exists() else {}

    so = second_order_sources(seed, content=content, config=config)
    if not so:
        print(f"{seed}: no entity-resolvable second-order source — INFEASIBLE (slice_feasible refuses; "
              f"don't spend).")
        return 0

    coords = read_coords(restrict_to_theme(content, seed), config)
    etf: set[str] = set()
    for src, key in coords:
        if src == ETF_SOURCE:
            for c in _load(cache, src, key):
                etf.add(_norm(c.get("name")))
                if c.get("symbol"):
                    etf.add(c["symbol"].upper())

    residual: dict[str, dict] = {}
    for src, key in coords:
        if src in _ENTITY_FIELD:
            name_field, amt_field = _ENTITY_FIELD[src]
            for r in _load(cache, src, key):
                k = _norm(r.get(name_field))
                if not k or k in etf:
                    continue
                residual.setdefault(k, {"raw": r.get(name_field), "amt": 0.0})
                residual[k]["amt"] += (r.get(amt_field) or 0.0) if amt_field else 0.0

    print(f"=== ceiling check: {seed} · second-order={sorted(so)} · residual (minus ETF) = "
          f"{len(residual)} distinct ===")
    print("EYEBALL: any QUIET + PUBLIC + ticker-mappable names? (primes = narrated → Stage-2 fails; "
          "private = untradeable). All-primes/private ⇒ a spend returns the up-chain negative — don't.")
    for _k, v in sorted(residual.items(), key=lambda x: -x[1]["amt"])[:30]:
        print(f"  {v['amt'] / 1e9:8.2f}B  {v['raw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
