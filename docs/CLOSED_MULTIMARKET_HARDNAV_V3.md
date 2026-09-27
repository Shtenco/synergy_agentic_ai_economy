# CLOSED MULTI-MARKET HARDNAV V3

## Goal

V3 restores the repository's v3 → v8.1 market/bridge/pool geometry on top of the preferred closed agent economy.

The objective is **very smooth positive HardNAV drift after costs**, without classifying internal token issuance, recursive collateral, internal AMM fees or agent-to-agent transfers as system profit.

## Restored market geometry

Opening HardNAV remains exactly **8,700**:

- **3,700** protected / treasury reserve;
- **2,500** protocol-owned external AMM liquidity;
- **2,500** Inventory Bridge custody.

External Base-style risk assets:

```text
WETH
cbBTC
VVV
VIRTUAL
AERO
cbETH
USDe
cbXRP
TOSHI
MORPHO
```

Internal mirrored assets:

```text
RUBX
RUBZ
USDC
WETH
cbBTC
VVV
VIRTUAL
AERO
cbETH
USDe
cbXRP
TOSHI
MORPHO
```

P9 settlement layer additionally carries:

```text
SYNA
SYNR
```

with the six bidirectional market surfaces:

```text
SYNA/BTC
SYNA/ETH
SYNA/WETH
SYNR/BTC
SYNR/ETH
SYNR/WETH
```

## Internal pools

The original monetary core is retained conceptually:

```text
RUBX ↔ USDC
RUBZ ↔ USDC
RUBX ↔ RUBZ
```

All mirrored Base assets may also participate in internal shadow liquidity.

These pools can generate internal volume, internal fees, mint/burn activity, collateral depth and GrossTVL, but none of those are booked directly into HardNAV.

## External HardNAV sources

Only externally realizable items can move HardNAV upward:

1. external bridge / swap fees;
2. external protocol-owned AMM fees;
3. realized external inventory / market PnL;
4. external hedge PnL;

minus:

1. funding;
2. gas;
3. execution costs.

External bridge principal is explicitly capital-adjusted and is not profit.

## Smoothness controller

The first 10,000 TRAIN blocks estimate the variance-minimizing hedge anchor using only TRAIN data.

Selected anchor:

```text
0.9954415206
≈ 99.54% external delta hedge
```

The anchor is then frozen for the final 3,000 STRICT OOS blocks.

The design intentionally separates:

- DQN economic decisions;
- a deterministic safety envelope for real external delta.

DQN is not permitted to turn synthetic issuance into HardNAV.

## Canonical 10,000 TRAIN + 3,000 OOS result

Start:

```text
HardNAV = 8,700
```

TRAIN:

```text
8,700 → 8,962.680901
return = +3.0193%
max DD = 0.000333%
```

STRICT OOS:

```text
8,962.680901 → 9,041.154578
return = +0.87556%
max DD = 0.000534%
```

Full 13,000 blocks:

```text
return = +3.92132%
max DD = 0.000534%
negative block-to-block steps ≈ 2.31%
```

## Where the HardNAV growth came from

Cumulative externally realizable modeled sources:

```text
bridge + swap fee revenue = 339.644240
external AMM fee revenue  =   1.747330
hedge PnL                 =  -1.002767
funding                    =  -0.170147
```

The closed agent economy remains separate:

```text
Internal GDP               = 1,147.539441
Productive Capital         =   306.299335
Gross Transaction Volume   = 14,585.404681
Verified Useful Work       = 1,024.486781
Protocol internal treasury =    73.974361
```

None of these internal metrics is automatically added to HardNAV.

## Data classification

This benchmark is still an **integration reconstruction**, not a fully historical replay of all ten Base assets.

Current inputs:

- ETH / WETH path: real historical on-chain path already used by the real-block replay;
- BTC / cbBTC path: real historical on-chain path already used by the real-block replay;
- the remaining Base assets: factor-mapped to the historical ETH/BTC path with deterministic idiosyncratic residuals;
- external bridge volume: modeled P9-style flow calibrated to the recorded v5 reference average;
- gas-aware code path exists in the engine, but this particular smooth anchor path required no discretionary rebalance batches.

Therefore this result demonstrates accounting and control behavior, not guaranteed live profitability.

## Hard invariants

```text
internal mint/burn        != HardNAV profit
internal CPMM fees        != HardNAV profit
recursive collateral      != HardNAV profit
GrossTVL                  != HardNAV
external capital inflow   != operating profit

external protocol fees    → HardNAV
external AMM fees         → HardNAV
external hedge PnL        → HardNAV
gas/funding/execution     → deducted from HardNAV
```

## Next hardening

The next evidence gate is to replace every factor-mapped Base asset with real per-block historical price data and replace the calibrated gas path with exact per-block gas/base-fee data, while keeping the same frozen 10k/3k protocol.
