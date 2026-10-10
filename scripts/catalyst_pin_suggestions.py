"""Weekly forward-catalyst PIN SUGGESTIONS from the Federal Register (read-only; the operator pins).

The forward-catalyst channel (PREREG_FORWARD_CATALYST_GROUNDING) renders operator-pinned, dated items. Its first
class-(a) pin — the EPA power-plant rule (FR 2026-19071, effective 2026-11-16) — came from reading the digest's
agency feeds by hand. This makes that read systematic (operator decision 2026-10-06, in place of the FDA / DoD
source proposals): every FINAL RULE published recently by an agency the digest already follows whose
EFFECTIVE DATE is still ahead — exactly the class-(a) shape (a statutory event with an ISO date).

Discipline:
  • Suggestions only. Nothing is pinned, scored or ranked; rows sort by effective date. The operator reads the
    rule and pins in ``forward_catalysts.json`` with a citable source, or doesn't (charter §3b; channel §3).
  • A rule is listed only when its title or abstract LITERALLY hits a basket keyword; the basket tag is that
    hit — a routing hint, not a relevance claim. Routine rule classes (airworthiness directives, state
    implementation plans, airspace/route changes, marketing orders) are dropped by title, and both skips are
    COUNTED in the output, never silent. The first unfiltered run listed every rule from every agency — a list
    that needs ranking to be useful, which the reach charter forbids.
  • Read-only: the keyless public Federal Register API; no DB, no keys, no write except ``--out`` (a records .md).

    python scripts/catalyst_pin_suggestions.py                  # print the table
    python scripts/catalyst_pin_suggestions.py --out records/2026-10-11_catalyst_pin_suggestions.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FR_URL = "https://www.federalregister.gov/api/v1/documents.json"
UA = "Mozilla/5.0 (compatible; dramatic-options-digest/0.1)"

# Routine rule classes — high-volume, never a thesis catalyst. Dropped by title, counted.
ROUTINE_TITLE = re.compile(
    r"^(Airworthiness Directives|Air Plan Approvals?|Approval and Promulgation of (?:Air Quality )?"
    r"Implementation Plans|IFR Altitudes|Establishment of .*Route|Amendment of .*Airspace|"
    r"Modification of .*Airspace|Revocation of .*Airspace|Safety Zone|Special Local Regulation|"
    r"Drawbridge Operation|.* Grown in )", re.I)

# Literal keyword → basket. Word-boundary, case-insensitive. Kept short and concrete on purpose.
KEYWORDS: dict[str, tuple[str, ...]] = {
    "nuclear_fuel": ("uranium", "reactor", "nuclear", "enrichment", "spent fuel", "small modular"),
    "grid_equipment": ("transformer", "transmission", "interconnection", "grid", "energy storage", "switchgear"),
    "ai_compute": ("data center", "datacenter", "generating unit", "power plant", "electric utilit"),
    "refrigerant_transition": ("refrigerant", "hydrofluorocarbon", "HFC", "AIM Act"),
    "ag_cycle_trough": ("fertilizer", "farm", "crop", "agricultural", "phosphate", "potash"),
    "space_smallcap": ("launch", "reentry", "satellite", "spectrum", "direct-to-device", "space"),
    "space_defense": ("defense", "missile", "launch"),
    "fiber_buildout": ("broadband", "BEAD", "fiber", "middle mile"),
    "copper_supply": ("copper", "critical mineral"),
    "silver_deficit": ("silver", "photovoltaic", "solar"),
    "seaborne_freight": ("vessel", "maritime", "shipping", "tanker"),
    "mrna_oncology": ("oncology", "cancer", "biologic"),
}


def basket_tags(text: str) -> list[str]:
    """The baskets whose keywords literally appear in ``text`` (sorted, unique). No hit → no tag."""
    tags: set[str] = set()
    for basket, words in KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(w)}", text, re.I) for w in words):
            tags.add(basket)
    return sorted(tags)


def suggest(rows: list[dict], baskets: dict[str, list[str]], today: date, *, horizon_days: int = 365,
            pinned_docs: set[str] | None = None, skipped: dict[str, int] | None = None) -> list[dict]:
    """Pure: Federal Register rows → suggestion rows, sorted by effective date, deduplicated by document number.
    Keeps only final rules effective after ``today`` and within ``horizon_days`` whose title/abstract hits a
    universe basket's keyword, minus the routine classes. ``skipped`` (if given) counts the rules dropped as
    ``routine`` / ``no_keyword``. Already-pinned documents are marked, not dropped."""
    out: dict[str, dict] = {}
    skip = skipped if skipped is not None else {}
    skip.setdefault("routine", 0)
    skip.setdefault("no_keyword", 0)
    end = today + timedelta(days=horizon_days)
    for r in rows:
        doc, eff = str(r.get("document_number") or ""), str(r.get("effective_on") or "")
        if not doc or not eff or str(r.get("type") or "Rule") != "Rule":
            continue
        try:
            eff_d = date.fromisoformat(eff[:10])
        except ValueError:
            continue
        if not (today < eff_d <= end) or doc in out:
            continue
        slugs = [a.get("slug") for a in (r.get("agencies") or []) if isinstance(a, dict) and a.get("slug")]
        title = " ".join(str(r.get("title") or "").split())
        if ROUTINE_TITLE.search(title):
            skip["routine"] += 1
            continue
        tags = [b for b in basket_tags(f"{title} {r.get('abstract') or ''}") if b in baskets]
        if not tags:
            skip["no_keyword"] += 1
            continue
        out[doc] = {
            "document_number": doc, "effective_on": eff_d.isoformat(), "title": title,
            "agencies": slugs, "published": str(r.get("publication_date") or ""), "url": str(r.get("html_url") or ""),
            "baskets": tags, "names": sorted({n for b in tags for n in baskets.get(b, [])}),
            "pinned": doc in (pinned_docs or set()),
        }
    return sorted(out.values(), key=lambda x: (x["effective_on"], x["document_number"]))


def fetch(slugs: list[str], since: date, today: date, *, timeout: float = 30) -> tuple[list[dict], list[str]]:
    """Final rules published since ``since`` with an effective date after ``today``, per agency. Fail-soft per slug."""
    rows: list[dict] = []
    errors: list[str] = []
    fields = ("document_number", "title", "type", "effective_on", "publication_date", "abstract", "html_url",
              "agencies")
    for slug in slugs:
        q = [("conditions[agencies][]", slug), ("conditions[type][]", "RULE"),
             ("conditions[effective_date][gte]", (today + timedelta(days=1)).isoformat()),
             ("conditions[publication_date][gte]", since.isoformat()), ("per_page", "100")]
        q += [("fields[]", f) for f in fields]
        try:
            req = urllib.request.Request(f"{FR_URL}?{urllib.parse.urlencode(q)}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — fixed public https host
                rows += json.loads(resp.read()).get("results") or []
        except Exception as e:  # noqa: BLE001 — one failed agency never blocks the others
            errors.append(f"{slug}: {type(e).__name__}: {e}")
    return rows, errors


def render(sugs: list[dict], *, today: date, since: date, errors: list[str],
           skipped: dict[str, int] | None = None) -> str:
    lines = [f"# Forward-catalyst pin suggestions — {today.isoformat()}", "",
             f"Final rules published {since.isoformat()} → {today.isoformat()} by the digest's Federal Register "
             "agencies, effective after today, whose title or abstract literally names a basket keyword. "
             "**Suggestions only — nothing is pinned.** The basket column is that keyword hit — a routing hint, "
             "not a relevance claim. Read the rule; pin in `forward_catalysts.json` with the FR document as the "
             "source, or skip.", ""]
    if not sugs:
        lines.append("_No final rule with a future effective date in the window._")
    else:
        lines += ["| effective | FR doc | title | agency | baskets (names) | pinned |", "|---|---|---|---|---|---|"]
        for s in sugs:
            names = ", ".join(s["names"]) or "—"
            tags = ", ".join(s["baskets"]) or "—"
            title = s["title"].replace("|", "/")
            lines.append(f"| {s['effective_on']} | [{s['document_number']}]({s['url']}) | {title} | "
                         f"{', '.join(s['agencies'])} | {tags} ({names}) | {'yes' if s['pinned'] else ''} |")
    sk = skipped or {}
    lines += ["", f"Skipped: {sk.get('routine', 0)} routine rule(s) (airworthiness directives, state plans, airspace, "
              f"marketing orders) · {sk.get('no_keyword', 0)} with no basket keyword."]
    if errors:
        lines += ["", "**Fetch errors (agency skipped):** " + "; ".join(errors)]
    return "\n".join(lines) + "\n"


def _universe_baskets() -> dict[str, list[str]]:
    cfg = json.loads((REPO / "config.json").read_text())
    return {k: sorted(v) for k, v in (cfg.get("universe", {}).get("themes") or {}).items() if not k.startswith("_")}


def _pinned_docs() -> set[str]:
    try:
        items = json.loads((REPO / "forward_catalysts.json").read_text()).get("items") or []
    except Exception:  # noqa: BLE001
        return set()
    return {m.group(0) for it in items for m in re.finditer(r"\b20\d\d-\d{5}\b", str(it.get("source") or ""))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=14, help="publication lookback (default 14)")
    ap.add_argument("--horizon", type=int, default=365, help="max days ahead for the effective date")
    ap.add_argument("--out", help="also write the table to this records .md path")
    args = ap.parse_args(argv)
    today = date.today()
    since = today - timedelta(days=args.days)
    feeds = json.loads((REPO / "digest_feeds.json").read_text())
    slugs = list((feeds.get("agency") or {}).get("federal_register_agencies") or [])
    rows, errors = fetch(slugs, since, today)
    skipped: dict[str, int] = {}
    sugs = suggest(rows, _universe_baskets(), today, horizon_days=args.horizon, pinned_docs=_pinned_docs(),
                   skipped=skipped)
    text = render(sugs, today=today, since=since, errors=errors, skipped=skipped)
    print(text)
    if args.out:
        Path(args.out).write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
