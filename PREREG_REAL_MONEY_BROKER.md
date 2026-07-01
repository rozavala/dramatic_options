# PREREG — the real-money broker path (the last T4 build)

**Status: FROZEN 2026-07-01 (design signed off by the operator before any code).** This pins the
design so the build cannot retro-fit it (anti-HARK, the project's freeze-before-build discipline).
T4 = enabling the real-money broker path LAST, behind the triple-gate; this is that path.

## 0. The gap
The only order broker, `AlpacaPaperBroker` (`broker.py:78`), hardwires
`TradingClient(api_key, secret_key, paper=True)` (`broker.py:84`); the orchestrator constructs it
unconditionally. The submit/reconcile logic — `submit_paper`, `order_status`, `cancel_order`, the
idempotent `make_client_order_id`, the `order_status` enum-value reconcile fix (PR #44) — is solid
and paper-exercised end-to-end, but **there is no `paper=False` path**. Everything else T4 needs
already exists: the triple-gate (`config_loader.live_allowed(config, cli_live)` = `paper is False ∧
live_trading_enabled ∧ --live`), DRY_RUN gating, the kill switch, the book/cluster caps.

## 1. Structure — an explicit `AlpacaLiveBroker` over a shared base (SIGNED OFF)
Extract the submit/reconcile logic into `_AlpacaBrokerBase(paper: bool)` (own `TradingClient`,
parameterized `paper`); `AlpacaPaperBroker(paper=True)` and `AlpacaLiveBroker(paper=False)` become
thin subclasses. Rationale: the submit code is **identical** (same `LimitOrderRequest`) → share ONE
tested path; but a class named `PaperBroker` must never be able to transmit real money, so the
real-money path is a **distinct, auditable type** with its own home for the safeguard in §3. The
base preserves all existing behavior; `AlpacaPaperBroker`'s public surface is byte-unchanged.

## 2. Selection — only under the existing triple-gate (SIGNED OFF)
The orchestrator selects `AlpacaLiveBroker` **iff** `live_allowed(config, cli_live)` is True;
otherwise `AlpacaPaperBroker` (the default, unchanged). DRY_RUN is honored in BOTH — even
live-and-armed, `DRY_RUN=true` logs-and-simulates and transmits nothing. There is intentionally no
other path to a `paper=False` client. The live log line must read `[LIVE — REAL MONEY]`, distinct
from the paper `[paper]`.

## 3. Real-money safeguard — a hard per-order notional ceiling (the SOLE broker-level guard, SIGNED OFF)
`AlpacaLiveBroker` rejects **fail-closed** (`Fill(False, …)`, nothing transmitted) any order whose
premium notional (`qty × limit × 100`) exceeds a configured `safety.live_max_order_notional`
(no default → absent config fails closed to reject; the operator sets it at arm time). This bounds a
sizing/pricing bug from placing a large real order, independent of the book/cluster caps upstream.
- **On the record (offered + DESELECTED by the operator, so the decision is explicit, not an
  oversight):** per-order Pushover paging on every live submit; a first-N-orders manual arm; a
  per-cycle live-spend cap. Not built. Live orders remain **journal-logged** (the existing log +
  the run record), and the existing `notify.py` pager still covers OnFailure + the soft trips
  (kill / fail-closed council / cost cap). Any of the three can be added later without a redesign.

## 4. Order-safety parity — inherited from the base (no new risk surface)
Reconciliation (`reconcile_pending` / `_reconcile_closing`), the idempotent per-(action,contract,date)
`client_order_id`, missed-order persistence, and the `order_status` enum-value fix are all in the
shared base → the live path gets them unchanged. No paper-only safety is left behind.

## 5. Validation — mechanics + one tiny operator-authorized smoke (SIGNED OFF)
The council produces no trades (the empty book / accepted ceiling), so the live path cannot be
exercised through the normal loop. Validation is therefore:
- **Offline unit tests:** the shared base (paper path stays green); `AlpacaLiveBroker` constructs
  `paper=False`; the broker-selection wiring keys on `live_allowed`; the notional ceiling
  rejects-fail-closed at the boundary; DRY_RUN simulates in the live class too.
- **One tiny real-money smoke (OUT OF BAND, separately operator-authorized):** a single 1-contract
  far-OTM BUY_TO_OPEN under a hard `< $X` cap (the operator sets X + gives the go AT execution
  time), submitted via a small script (NOT the council), to prove endpoint → reconcile
  (`order_status`) → `SELL_TO_CLOSE` on the real account. This is the only honest end-to-end proof
  without waiting on a market include. It is a REAL order → it does not happen without the operator's
  explicit, contemporaneous authorization; it is not implied by this freeze.

## 6. Guardrails alignment
Paper-first (live only under the triple-gate; default is paper). Fail-closed (any submit error OR a
ceiling breach → `Fill(False)`; absent ceiling config → reject). DRY_RUN honored. Kill switch checked
upstream (the cycle halts before the council/entries). No "maximize leverage" path; sizing is
unchanged; the ceiling is a cap, never a target.

## 7. What this does NOT do (scope honesty)
- It does **not** unblock the empty book — the council still includes 0/16 and the gate/caps still
  admit ~nothing, so a live-armed loop would submit nothing (hence the §5 smoke). Building this makes
  the apparatus **T4-ready**; it does not graduate T4.
- It does **not** graduate T4 — conds (2)/(3)/(4) still require resolved real trades, which remain
  market-gated (the deferred strategic fork: apparatus-ready vs. yield-block diagnostic vs.
  criteria-reconsideration, IMPLEMENTATION_PLAN §T4).
- The smoke order (§5) is the ONLY real order this workstream contemplates, and it is
  operator-authorized at execution time.
