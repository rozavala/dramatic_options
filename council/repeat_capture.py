"""#456 capture: the ContextPack + strategist-prompt hash the repeat-read probe replays (PREREG_COUNCIL_GATE_SEPARATION
§10.12; records/2026-11-14_council_repeat_probe_armA_PREREG.md §4).

Nothing persists a pack today, and rebuilding one later is not guaranteed to match (the corpus refetches on a new
filing, the analyst meter reads a live endpoint). So, behind ``council.repeat_probe.enabled`` (default off), the
council path serializes each strategist-reaching candidate's pack at L1 time. The serialization is lossless and is
CHECKED at capture time: a pack that does not round-trip to an equal object rendering the same block is not
captured (the caller logs a WARNING; the council of record never sees any of this).

Measurement only: nothing here is read by the council, the gates, sizing or any entry.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime
from typing import Any

from council.context import ContextPack

PACK_CODEC_VERSION = 1


def prompt_sha256(text: str) -> str:
    """The full sha256 hexdigest of a rendered prompt (the probe compares its rebuilt text against this)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pack_to_json(pack: ContextPack) -> str:
    """Serialize a ContextPack to JSON. ``as_of`` is an ISO string (offset kept); every other field is JSON-native
    (lists of str, dicts from the corpus/catalyst providers, ints, bools, None)."""
    d: dict[str, Any] = dataclasses.asdict(pack)
    d["as_of"] = pack.as_of.isoformat() if pack.as_of is not None else None
    return json.dumps({"v": PACK_CODEC_VERSION, "pack": d}, sort_keys=True, ensure_ascii=False, allow_nan=False)


def pack_from_json(text: str) -> ContextPack:
    """Inverse of ``pack_to_json``. Raises on an unknown codec version or a field ContextPack does not have."""
    blob = json.loads(text)
    if blob.get("v") != PACK_CODEC_VERSION:
        raise ValueError(f"unknown pack codec version {blob.get('v')!r}")
    d = dict(blob["pack"])
    if d.get("as_of") is not None:
        d["as_of"] = datetime.fromisoformat(d["as_of"])
    return ContextPack(**d)


def capture_record(pack: ContextPack, strategist_user: str) -> dict:
    """``{"pack_json", "prompt_sha256"}`` for one candidate. Raises (→ the caller's WARNING, no capture) when the
    pack does not round-trip to an equal pack that renders the identical prompt block."""
    text = pack_to_json(pack)
    back = pack_from_json(text)
    if back != pack or back.as_prompt_block() != pack.as_prompt_block():
        raise ValueError("ContextPack does not round-trip losslessly")
    return {"pack_json": text, "prompt_sha256": prompt_sha256(strategist_user)}
