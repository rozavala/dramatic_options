# 2026-07-17 — newsletters round 2 (operator's expanded list) + the Bluesky-leg probe negative

## A. The Bluesky-leg candidate dies on a $0 probe (queued build → measured negative)

The 2026-07-16 X handle audit removed Doug Dawson (fiber) and Hugh Lewis (smallsat) — both
deleted their X accounts, both "now post on Bluesky only." The queued build was a keyless
Bluesky ingestion leg for them. The probe (keyless public AppView API,
`public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed`, run 2026-07-17) falsified the premise:

- **Dawson's Bluesky is an abandoned link-mirror**: every post is a bare URL to his blog
  (potsandpansbyccg.com), and the posts STOP 2026-02-18. The live channel is the blog itself —
  WordPress RSS, posts ~daily (newest 2026-07-16 at probe time), parses under the harness UA +
  `digest.parse_feed`, browser-UA 200. → **Re-routed as a newsletters feed** ("POTs and PANs
  (Doug Dawson)", fiber_broadband). Provenance: the PERSON is the operator's X-pond priority
  pick (2026-07-16); the ROUTE (blog RSS after X deletion) is CC-pinned, operator-vetoable.
- **Lewis has no viable keyless route**: his Bluesky profile RSS serves only 2 items, newest
  2025-07-02, and OMITS his 2026-03-12 posts (Bluesky's profile RSS is a shallow window); the
  full AppView JSON shows his true cadence is ~quarterly — below any yield bar even if
  ingested. → **Unreachable for now, no row added, nothing guessed.** Revisit only if he
  resumes regular posting or more of the pond migrates to Bluesky (at which point the AppView
  leg — NOT the RSS route — is the build, with an ingestion-side engagement-field strip: the
  AppView always returns likeCount/repostCount, unlike X's field selection).

**Disposition: the Bluesky-leg build is CLOSED as scoped** — one target re-routed onto
existing machinery at zero code, the other unreachable. The negative is corpus-bounded (these
two accounts, this API surface, 2026-07-17), not "Bluesky is useless."

## B. Round 2 verification (the operator's expanded list, delivered 2026-07-17)

Standard unchanged from #194: harness-UA fetch + `digest.parse_feed` + fresh newest item;
browser-UA HTTP 200. Full results in `digest_feeds.json` `_comment_newsletters`.

**ADDED (6):** FreightCaviar (freight, fresh 07-15) · Supply Chain Dive (freight, site-wide
/feeds/news/ — the logistics topic feed 404s; SCD is logistics-centric; fresh 07-16) · POWER
Magazine (grid, fresh 07-16) · NucNet (nuclear, fresh 07-16) · SpaceNews launch **section**
(smallsat/launch, fresh 07-17 — the /tag/smallsat feed is stale since 2026-02; browser-UA
read 429 during the probe burst = IP rate-limit, not UA-gating) · POTs and PANs (fiber, §A).

**SKIPPED with reasons:**
- **Utility Dive — the cross-channel self-corroboration flag.** Already live in trade_press
  (same `utilitydive.com/feeds/news/`). Listing one feed in two channels would let a single
  publisher satisfy the survivor-cards ≥2-distinct-channels corroboration rule (#203) by
  itself. Not added; if the operator prefers it AS a newsletter, the right move is a MOVE,
  not a copy.
- World Nuclear News + World Nuclear Association: already pinned (one feed,
  world-nuclear-news.org/rss — WNA's news arm, per the 07-16 derivation note).
- Mining Journal: `/feeds/rss` exists (robots.txt confirms the path family) but serves
  malformed XML — parse fails at source; fail-closed, not pinned.
- Metals & Mining Review, Argus Metals, BryceTech: no feed at any standard path, no
  autodiscovery (Argus is subscription market-intelligence; BryceTech is a consultancy site).
- FOA, Flexport, Grid Brief, SpaceNexus: re-checked 2026-07-17, still feed-less (same shapes
  as the 07-16 audit).

Newsletters channel: 15 → **21 live feeds**. Channel activation date unchanged (2026-07-16 —
clocks are per-channel, not per-feed). The digest never ranks; per-source chronological caps
bound the added volume.
