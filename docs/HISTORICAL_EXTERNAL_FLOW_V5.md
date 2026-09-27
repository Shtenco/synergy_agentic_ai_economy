# V5 — historical external flow

V5 не меняет V4-экономику. Он заменяет последний synthetic input `84,911.06 MODELED_V5_CALIBRATED_REFERENCE` реальными on-chain bridge/swap events в том же окне:

- Ethereum 23,544,921 → 23,557,920
- timestamp 1760070203 → 1760227199
- 10,000 TRAIN → FREEZE → 3,000 STRICT OOS
- NO RESET

## Observed-flow lower bound

Первый V5 benchmark намеренно классифицируется как `OBSERVED_EXTERNAL_FLOW_LOWER_BOUND`, а не «весь рынок».

Источники:

1. Across SpokePool на Base/Ethereum: `FundsDeposited`, `FilledRelay` и legacy event forms. Historical/current addresses берутся из official deployment artifacts и legacy-addresses.
2. Aerodrome на Base: все pools из official PoolFactory `0x420DD381b31aEf6683db6B902084cB0FFECe40Da`, затем реальные `Swap` logs.

Base block boundaries определяются бинарным поиском по timestamp. Каждый event причинно маппится на последний Ethereum V4 block с timestamp <= event timestamp.

## Accounting

Разделять:
- `observed_bridge_volume_usd`
- `observed_dex_swap_volume_usd`
- `observed_external_volume_usd`
- `unresolved_volume_events`
- `counterfactual_synergy_fee_revenue`

Historical observed volume под текущей SYNERGY fee schedule — counterfactual demand replay, а не фактически заработанная историческая комиссия SYNERGY.

Неизвестным токенам нельзя придумывать USD price. Raw event сохраняется, USD volume остаётся unresolved.

## GREEN gate

Нужны raw logs, tx hash/block/timestamp/protocol provenance, on-chain pool discovery, causal price alignment, zero future-price use и фактическая замена V4 constant volume observed block-by-block series.
