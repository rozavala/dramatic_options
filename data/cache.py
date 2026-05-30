"""Point-in-time on-disk cache (plan §B2) — the backtest reproducibility backbone.

The cache stores, per ``(source, key)``, a **superset payload**: every record fetched for
that entity, each carrying its own record timestamp, together with a ``coverage_through``
high-water mark (the latest instant the fetch is known to be complete to).

The crucial design choice (and the one the reviewer flagged): **as-of reads filter on the
records' own timestamps, NOT on when the fetch happened.** A single wide fetch of "all news
for JOBY through 2025-12-31" can therefore serve *any* ``as_of <= coverage_through`` by
filtering — so offline replay is deterministic and independent of which fetches happened to
run. Asking for an ``as_of`` beyond ``coverage_through`` is a miss (the caller must widen the
fetch, or, in offline mode, it errors).

Records are plain dicts with an ISO-8601 ``"ts"`` field (UTC). Storage is one JSON file per
``(source, key)`` under ``<cache_dir>/<source>/<key>.json`` — inspectable and diff-friendly.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TS_FIELD = "ts"


class CacheMiss(RuntimeError):
    """Raised in offline mode when the cache cannot satisfy a read."""


def _parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp to an aware UTC datetime."""
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _to_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


_KEY_SAFE = re.compile(r"[^A-Za-z0-9._-]")


class PointInTimeCache:
    """Filesystem cache with as-of read semantics.

    ``offline=True`` forbids network refills: a read that the cache can't satisfy raises
    ``CacheMiss`` instead of signalling the caller to fetch.
    """

    def __init__(self, cache_dir: str | Path, *, offline: bool = False) -> None:
        self.root = Path(cache_dir)
        self.offline = offline
        # Max record timestamp surfaced by the most recent read() — the engine asserts
        # this never exceeds the as_of it queried (a lookahead tripwire, plan §B / §B8).
        self.last_max_ts: datetime | None = None
        # Running max across ALL read() calls since the last reset — lets the engine guard
        # every read in a panel build, not just the last one.
        self.running_max_ts: datetime | None = None

    def reset_running_max(self) -> None:
        self.running_max_ts = None

    # ── paths ─────────────────────────────────────────────────────────────
    def _path(self, source: str, key: str) -> Path:
        safe = _KEY_SAFE.sub("_", str(key))
        return self.root / source / f"{safe}.json"

    # ── read ──────────────────────────────────────────────────────────────
    def coverage_through(self, source: str, key: str) -> datetime | None:
        """The high-water mark the stored superset is complete to, or None if absent."""
        path = self._path(source, key)
        if not path.exists():
            return None
        meta = json.loads(path.read_text())
        ct = meta.get("coverage_through")
        return _parse_ts(ct) if ct else None

    def has_coverage(self, source: str, key: str, as_of: datetime) -> bool:
        ct = self.coverage_through(source, key)
        return ct is not None and _to_utc(as_of) <= ct

    def read(self, source: str, key: str, as_of: datetime) -> list[dict[str, Any]]:
        """Return records with ``ts <= as_of`` from the stored superset.

        Records are returned sorted by ``ts`` ascending. Updates ``last_max_ts``. Raises
        ``CacheMiss`` if there is no payload or ``as_of`` exceeds the coverage high-water
        mark (the data isn't known to be complete that far — never silently truncate).
        """
        as_of = _to_utc(as_of)
        path = self._path(source, key)
        if not path.exists():
            raise CacheMiss(f"no cache payload for {source}/{key}")
        meta = json.loads(path.read_text())
        ct = meta.get("coverage_through")
        if ct is None or as_of > _parse_ts(ct):
            raise CacheMiss(
                f"{source}/{key} covered through {ct}, asked as_of {as_of.isoformat()}"
            )
        records = [r for r in meta.get("records", []) if _parse_ts(r[TS_FIELD]) <= as_of]
        records.sort(key=lambda r: r[TS_FIELD])
        self.last_max_ts = _parse_ts(records[-1][TS_FIELD]) if records else None
        if self.last_max_ts is not None:
            if self.running_max_ts is None or self.last_max_ts > self.running_max_ts:
                self.running_max_ts = self.last_max_ts
        return records

    def read_between(
        self,
        source: str,
        key: str,
        start: datetime | None,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Records with ``start < ts <= end`` (start exclusive, None = open lower bound).

        **Label-only / forward-window accessor.** Unlike ``read``, this deliberately does
        NOT update ``last_max_ts`` and does NOT enforce the coverage high-water mark — it is
        used to compute strictly-forward return labels (`t → t+h`), which are allowed to see
        the future because they are never fed back as features (plan no-lookahead contract,
        item 4). Returns what's available (possibly empty near the end of data).
        """
        start = _to_utc(start) if start is not None else None
        end = _to_utc(end)
        path = self._path(source, key)
        if not path.exists():
            return []
        meta = json.loads(path.read_text())
        out = []
        for r in meta.get("records", []):
            ts = _parse_ts(r[TS_FIELD])
            if ts <= end and (start is None or ts > start):
                out.append(r)
        out.sort(key=lambda r: r[TS_FIELD])
        return out

    # ── write ─────────────────────────────────────────────────────────────
    def write(
        self,
        source: str,
        key: str,
        records: list[dict[str, Any]],
        *,
        coverage_through: datetime,
    ) -> None:
        """Store/replace the superset payload for ``(source, key)``.

        Every record must carry an ISO ``ts`` field. ``coverage_through`` is the instant the
        fetch is complete to (typically the fetch window's ``end``). Refused in offline mode.
        """
        if self.offline:
            raise CacheMiss(f"offline cache cannot write {source}/{key}")
        for r in records:
            if TS_FIELD not in r:
                raise ValueError(f"record missing '{TS_FIELD}': {r!r}")
            _parse_ts(r[TS_FIELD])  # validate parseable
        path = self._path(source, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "source": source,
            "key": str(key),
            "coverage_through": _to_utc(coverage_through).isoformat(),
            "fetched_at": datetime.now(UTC).isoformat(),
            "records": sorted(records, key=lambda r: r[TS_FIELD]),
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, default=str))
        tmp.replace(path)  # atomic
