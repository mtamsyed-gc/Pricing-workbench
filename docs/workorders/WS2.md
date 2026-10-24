# Work order WS2 — A: market benchmark

Branch: `ws2-benchmark` · Read: SPEC §0–§4, §6, §7, §13 · Depends on: WS0 merged; WS1 `BenefitFactors` for richness
Attach read-only: the owner's product benchmarking tool (separate repo) when the session starts.

## Goal
Place the expiring catalogue and each proposal against the market on price and richness, and list what is missing.

## Deliverables
1. Market catalogue intake through catalogue specs (kind `MARKET`); no new parser code per market source.
2. Tier matching across catalogues with different plan counts via `tier_map.csv` (SPEC §3.3; many-to-one / one-to-many with weights).
3. Value map: price (standard cell set and exposure mix) vs richness index per plan/tier; Parquet + Excel view.
4. Gap register: benefit lines present / absent / weaker vs market, by plan tier (SPEC §4.1 comparison rules).
5. Benefit taxonomy reconciliation with the owner's benchmarking tool (mapping table, not code).
6. CLI `benchmark`; end-to-end check added to `tools/laptop_check.py`.

## Files
- May create: `pw/benchmark.py`, `pw/tiers.py`, tests `tests/test_ws2_*.py`, market fixture specs under `fixtures/` (fictional).
- May edit: `tools/pw.py`, `tools/laptop_check.py`, `registry/benefit_factors.json` (entries only).
- Must not edit: registries' structure, contracts, `pw/model.py`, evaluator semantics (CR only).

## Fixtures
CAT_ALPHA vs CAT_GAMMA vs CAT_IPMI (different products, plan counts and currencies; FX from run config).

## Acceptance criteria
- Comparisons CAT_ALPHA vs CAT_GAMMA vs CAT_IPMI run end to end with FX; tier weights sum to 1 per source plan.
- Gap register hand-checked on two benefit lines per comparison rule type.
- Market-facing outputs never name the incumbent reinsurer.
- Full suite green; `LAPTOP CHECK PASS` on the owner's laptop (SPEC §13).

## Out of scope
Market data collection; scorecard weights (WS3).
