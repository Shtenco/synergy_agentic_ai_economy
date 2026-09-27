# V4 GREEN — executed historical evidence

Status: **GREEN for V4 evidence scope**.

This status means the promised V4 gate has actually executed with real historical inputs. It does **not** claim that the remaining modeled bridge volume is historical; that is the next evidence milestone.

## Executed protocol

- Ethereum blocks: `23,544,921 → 23,557,920`
- Count: **13,000 contiguous**
- TRAIN: **10,000**
- STRICT OOS: **3,000**
- Reset between TRAIN/OOS: **none**
- Hedge anchor selected from TRAIN only: **1.1120974216643325**
- OOS used for anchor selection: **false**
- Factor-mapped market legs: **0 / 10**
- Future-candle violations: **0 for every asset**

## Historical market provenance

| Asset | Historical source | Maximum causal staleness |
|---|---|---:|
| WETH | Coinbase ETH-USD | 60 s |
| cbBTC | Coinbase BTC-USD underlying | 60 s |
| VVV | Coinbase VVV-USD | 1500 s |
| VIRTUAL | Binance Vision VIRTUALUSDT | 0 s |
| AERO | Coinbase AERO-USD | 180 s |
| cbETH | Coinbase CBETH-USD | 660 s |
| USDe | Binance Vision USDEUSDT | 0 s |
| cbXRP | Coinbase XRP-USD underlying | 60 s |
| TOSHI | Coinbase TOSHI-USD | 120 s |
| MORPHO | Coinbase MORPHO-USD | 360 s |

All alignments use the last fully completed one-minute candle only.

## Ethereum block environment

Xatu provides exact historical `block_date_time`, `gas_used`, and `base_fee_per_gas`.

The real Xatu schema does not expose `gas_limit` in `canonical_execution_block`, so V4 now obtains exact `gasLimit` from archive Ethereum JSON-RPC `eth_getBlockByNumber`. Each RPC block is cross-checked against Xatu on timestamp, gasUsed, and baseFeePerGas. Any mismatch is a hard failure.

Strategy gas **units** remain modeled by the strategy configuration. Strategy gas **price environment** uses exact historical base fee and no invented priority tip.

## V4 executed results

| Metric | V3 factor-mapped | V4 historical |
|---|---:|---:|
| HardNAV start | 8700.0000 | 8700.0000 |
| TRAIN end | 8962.6809 | **8982.3377** |
| OOS end | 9041.1546 | **9066.3138** |
| Full return | 3.921317% | **4.210503%** |
| OOS return | 0.875560% | **0.934902%** |
| Full max DD | 0.000534% | **0.173472%** |
| TRAIN step std | 0.020955 | **0.171632** |
| OOS step std | 0.020657 | **0.093686** |
| Negative-step fraction | 2.3079% | **7.3231%** |

The historical replay therefore increased full return by **+0.289186 percentage points** and OOS return by **+0.059342 points**, but it disproved the extreme smoothness of the factor-mapped V3 reconstruction:

- full max drawdown is ~**324.75×** V3,
- TRAIN step volatility is ~**8.19×** V3,
- OOS step volatility is ~**4.54×** V3,
- negative-step frequency is ~**3.17×** V3.

That is an important evidence result: V3's extremely smooth curve was not robust to replacing all market legs with real historical paths.

## External-source decomposition

- modeled bridge volume: **84,911.06**
- bridge + swap fees: **339.64424**
- external AMM fees: **7.8085535**
- hedge PnL: **+321.6180938**
- funding cost: **0.1716442**
- execution cost: **0.0879961**
- strategy gas cost: **1.4360058**
- executed rebalance batches: **1**

The modeled bridge volume is intentionally still classified as:

`MODELED_V5_CALIBRATED_REFERENCE_UNCHANGED_FROM_V3`

It is the next synthetic layer to remove.

## Evidence chain

Public-only raw-data collector run:
- repository: `Shtenco/synergychain.github.io`
- workflow run: `36316047443`
- artifact: `10931131509`
- artifact digest: `sha256:980eb7fd4c0f02ed106629f578ea25fe28865f23e58aa7af07cb090043cce911`

Final local evidence hashes:
- 13k CSV SHA-256: `6eb4ea7d3c6fadeebc2349e3a3f530bf1f4b50eb4c375127b41cd3e6ada8be0e`
- manifest SHA-256: `20ab0a7e355968283ca0437bab77f15d8b73ef7755b07d24a7f9e4813d10b29a`
- report SHA-256: `b76ce762678f88a60a530c794aa6d67ac71b758b85952d75f3a7dda2ad4ec11e`

The private computation was executed twice deterministically and returned the same gate result.

## M1–M12

```
M1  runnable environment             GREEN
M2  exact 13k Ethereum blocks       GREEN
M3  exact timestamps + gas env      GREEN
M4  real prices 10 assets           GREEN
M5  no-lookahead proof              GREEN
M6  10k TRAIN                       GREEN
M7  TRAIN-only hedge anchor         GREEN
M8  FREEZE                          GREEN
M9  3k STRICT OOS                   GREEN
M10 CSV + manifest + JSON report    GREEN
M11 V3 vs V4 comparison             GREEN
M12 executable evidence status      GREEN
```

## Next evidence milestone

Replace the final synthetic revenue input:

`84,911.06 MODELED_V5_CALIBRATED_REFERENCE`

with block-by-block historical bridge/swap/DEX activity, preserving the exact V4 market path and TRAIN/FREEZE/OOS protocol.