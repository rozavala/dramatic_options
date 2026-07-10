"""Forward-catalyst grounding channel — the pinned-item store + per-cycle render selection.

PREREG_FORWARD_CATALYST_GROUNDING (FROZEN 2026-07-09, PR #167; ratification in
``records/2026-07-09_channel_prereg_freeze.md``). §1 GROUND, NEVER PERMISSION: this module
supplies dated, public, citation-checkable forward evidence to the council's ``ContextPack``.
It never scores, never gates, never admits, never sizes — a channel-grounded candidate still
needs the same §10.7 tri-criteria judgment, the same IV gate, the same caps.

**Item source (§3):** operator-pinned entries in a git-tracked JSON file (the §11 register
precedent) — never LLM-authored (``generated`` provenance is reserved and REFUSED here; an item
carrying it is counted malformed and logged at ERROR — the F-b halt is the operator's same-day
act, this guard is the tripwire). Classes per §2 (exhaustive):

- ``a`` — statutory/regulatory dated events (``event_date`` REQUIRED)
- ``c`` — dated program/procurement milestones (``event_date`` REQUIRED)
- ``d`` — published input-commodity prices (``event_date`` MUST be null — a fictitious date
  would be instrument-shaped data entry, exactly what F-b exists to catch; §2)
- ``b`` — filed forward commitments — EXCLUDED by §2 (one home: the fundamentals corpus).

**§4 anti-silent-dormancy counters** accumulate across a cycle's ``items_asof`` calls and are
stamped into ``runs.note`` by the orchestrator: ``rendered_n / expired_n / malformed_n /
stale_flagged_n``. (§4's fifth counter, ``reverse_conversion_n``, is a property of the §6
paired-contrast probe — it joins the stamp from the probe harness PR; absent ≠ zero, so it is
NOT emitted as a hardcoded 0 here.)

**Fail-soft (§7):** a missing/unreadable file, a malformed item, an expired item — none of it
ever blocks a cycle; the block degrades to absent, counted. Kill-before-spend unchanged.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

REQUIRED_KEYS = ("symbol", "class", "claim", "source", "as_of", "expires", "provenance")
DATED_CLASSES = ("a", "c")   # event_date REQUIRED (§2)
CURRENT_CLASSES = ("d",)     # event_date must be null (§2)


def _parse_date(v) -> datetime | None:
    """ISO date/datetime → datetime (date-only → midnight). None on anything else."""
    if not isinstance(v, str) or not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


def naive_utc(dt: datetime) -> datetime:
    """Normalize a render-time ``as_of`` for comparison against pinned item dates.

    Item dates are naive calendar dates (UTC-midnight by convention); the LIVE clock hands an
    AWARE datetime — comparing them raises TypeError (found by the first live probe run,
    2026-07-10; the L1 path would have degraded fail-soft to an absent block, silently). Aware →
    convert to UTC and strip; naive → unchanged. Hours-level drift is immaterial against the
    7-day class-(d) expiry and the 365-day eligibility window. Shared with
    ``council.paired_contrast`` — one normalization, two comparison sites, zero drift."""
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


class ForwardCatalysts:
    """Per-cycle provider: construct once per cycle, call ``items_asof`` per candidate, then
    read ``.counters`` for the §4 ``runs.note`` stamp. Duck-typed for ``build_context_pack``.

    ``max_items`` = K (§10 default 3) · ``staleness_days`` = N (§10 default 30) ·
    ``max_block_chars`` enforces the §7 ≤400-token pack bound (~4 chars/token → 1600)."""

    def __init__(self, path: str = "forward_catalysts.json", *, max_items: int = 3,
                 staleness_days: int = 30, max_block_chars: int = 1600):
        self.max_items = int(max_items)
        self.staleness_days = int(staleness_days)
        self.max_block_chars = int(max_block_chars)
        self.rendered_n = 0
        self.expired_n = 0
        self.malformed_n = 0
        self.stale_flagged_n = 0
        self._items = self._load(path)

    # ── load + §2 schema validation (malformed → counted, skipped, never raised) ─────────────

    def _load(self, path: str) -> list[dict]:
        try:
            raw = json.loads(Path(path).read_text())
        except FileNotFoundError:
            log.info("forward_catalysts: no pin file at %s — channel live but empty.", path)
            return []
        except Exception as e:  # noqa: BLE001 — §7 fail-soft: a bad file never blocks a cycle
            log.error("forward_catalysts: unreadable pin file %s (%s) — block absent this cycle.",
                      path, e)
            return []
        items = raw.get("items") if isinstance(raw, dict) else None
        if not isinstance(items, list):
            log.error("forward_catalysts: pin file %s has no 'items' list — block absent.", path)
            return []
        valid = []
        for it in items:
            if self._validate(it):
                valid.append(it)
            else:
                self.malformed_n += 1
        return valid

    def _validate(self, it) -> bool:
        if not isinstance(it, dict) or any(not it.get(k) for k in REQUIRED_KEYS):
            log.warning("forward_catalysts: item missing required keys (§2) — malformed: %r", it)
            return False
        cls = it.get("class")
        if cls not in DATED_CLASSES + CURRENT_CLASSES:
            # class (b) lands here BY DESIGN — §2 excludes it (one home: the fundamentals corpus).
            log.warning("forward_catalysts: class %r not in §2 {a,c,d} — malformed: %s",
                        cls, it.get("claim"))
            return False
        if it.get("provenance") != "operator":
            # 'generated' is reserved (§3, no LLM-authored facts) — the F-b tripwire.
            log.error("forward_catalysts: non-operator provenance %r (F-b: LLM-authored/unknown "
                      "items halt the channel — operator audit required): %s",
                      it.get("provenance"), it.get("claim"))
            return False
        if _parse_date(it.get("as_of")) is None or _parse_date(it.get("expires")) is None:
            log.warning("forward_catalysts: unparseable as_of/expires — malformed: %s",
                        it.get("claim"))
            return False
        ed = it.get("event_date")
        if cls in DATED_CLASSES and _parse_date(ed) is None:
            log.warning("forward_catalysts: class %s requires an ISO event_date (§2) — "
                        "malformed: %s", cls, it.get("claim"))
            return False
        if cls in CURRENT_CLASSES and ed is not None:
            log.warning("forward_catalysts: class d must carry event_date=null (§2 — a "
                        "fictitious date is instrument-shaped entry) — malformed: %s",
                        it.get("claim"))
            return False
        return True

    # ── per-candidate render selection ────────────────────────────────────────────────────────

    def items_asof(self, symbol: str, as_of: datetime) -> list[dict]:
        """The ≤K items that RENDER for one candidate at ``as_of`` (point-in-time: pinned in the
        past, not yet expired). Deterministic order: (a)/(c) by nearest ``event_date``, then (d)
        by most recent ``as_of``. Counters accumulate; §7 char bound enforced by truncation."""
        sym = symbol.upper()
        as_of = naive_utc(as_of)  # the live clock is tz-aware; item dates are naive calendar dates
        live: list[dict] = []
        for it in self._items:
            if str(it.get("symbol", "")).upper() != sym:
                continue
            pinned = _parse_date(it["as_of"])
            if pinned > as_of:
                # PIT discipline: a pin dated in the future is an entry error, not evidence.
                log.warning("forward_catalysts: %s item pinned in the future (%s > render %s) — "
                            "malformed.", sym, it["as_of"], as_of.isoformat())
                self.malformed_n += 1
                continue
            if as_of >= _parse_date(it["expires"]):
                # §3: an item past `expires` drops from the pack — never silently.
                self.expired_n += 1
                continue
            if (as_of - pinned) > timedelta(days=self.staleness_days):
                # §3 re-verification flag: counted + still renders (fail-soft); the flag is the
                # operator's standing check, never rendered to the model (no judgment nudge).
                self.stale_flagged_n += 1
            live.append(it)

        dated = sorted((i for i in live if i["class"] in DATED_CLASSES),
                       key=lambda i: (i["event_date"], i["as_of"]))
        current = sorted((i for i in live if i["class"] in CURRENT_CLASSES),
                         key=lambda i: i["as_of"], reverse=True)
        chosen = (dated + current)[: self.max_items]
        if len(dated) + len(current) > self.max_items:
            log.info("forward_catalysts: %s has %d eligible items, K=%d rendered (§10).",
                     sym, len(dated) + len(current), self.max_items)

        # §7 pack token bound (≤400 tokens ≈ max_block_chars): truncate trailing items, log.
        out: list[dict] = []
        used = 0
        for it in chosen:
            cost = len(it["claim"]) + len(it["source"]) + 64  # rendered-line overhead bound
            if used + cost > self.max_block_chars and out:
                log.warning("forward_catalysts: %s block over the §7 char bound — %d item(s) "
                            "truncated.", sym, len(chosen) - len(out))
                break
            used += cost
            out.append(it)
        self.rendered_n += len(out)
        return out

    def counters(self) -> dict:
        """The §4 anti-silent-dormancy counters for the cycle's ``runs.note`` stamp."""
        return {"rendered_n": self.rendered_n, "expired_n": self.expired_n,
                "malformed_n": self.malformed_n, "stale_flagged_n": self.stale_flagged_n}
