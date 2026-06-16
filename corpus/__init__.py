"""Stage-0 structural corpus for the theme-generation layer (``PREREG_THEME_GENERATION_STUB`` Stage 0).

Deterministic, point-in-time pulls of pinned STRUCTURAL sources (capital-raise filings,
customer-concentration disclosures, federal awards, energy/labor series, interconnection queues,
reactor dockets, ETF constituents). NO LLM, no fitted parameters — pure plumbing.

The §2 prohibition is enforced HERE, at the INPUT layer (auditable, not in a prompt): corpus modules
carry NO prices, IV, momentum, or news-sentiment, and import no market/price source. The guard is
``tests/test_corpus_stage0.py::test_corpus_forbids_price_imports`` (a static import audit over this
package) — the "enforced at the input layer (auditable), not in the prompt (hopeful)" design line.
"""
