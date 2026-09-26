# P9 — Cross-Chain DQN Economy

## Goal

P9 connects the bidirectional BTC / ETH / WETH asset layer to the block-by-block DQN economy.

The production intent is:

```text
BTC / ETH / WETH
        ↕
bridge-backed synthetic inventory
        ↕
SYNA / SYNR
        ↕
DQN Market + DQN Central Bank
```

This repository implementation is still a deterministic research/simulation environment. It does not claim live custody, live bridge execution or guaranteed profitability.

## Preserved DQN baseline geometry

The implementation preserves the established DQN geometry:

- 6 market agents;
- one agent per SYNA/SYNR × BTC/ETH/WETH pair;
- market state: 20 features;
- market actions: 32;
- central-bank state: 12 features;
- central-bank actions: 90;
- MLP: 64 → 64 → action head;
- gamma: 0.99;
- replay buffer: 20,000;
- batch: 48;
- target sync: 500;
- update every 4 environment steps.

## Bidirectional router

Supported user-level routes:

- BTC → SYNA
- BTC → SYNR
- ETH → SYNA
- ETH → SYNR
- WETH → SYNA
- WETH → SYNR
- SYNA → BTC
- SYNR → BTC
- SYNA → ETH
- SYNR → ETH
- SYNA → WETH
- SYNR → WETH

Outbound routes fail closed if the bridge has insufficient backed synthetic inventory. The simulator does not create BTC/ETH/WETH from internal token issuance.

## Accounting invariant

External principal is tracked separately from economic performance.

```text
CapitalAdjustedHardNAV = HardNAV - NetExternalCapitalFlow
```

Inbound bridge deposits therefore do not count as profit.

Central-bank actions can alter internal emission, reserve targets, fees and risk limits, but may not create external capital flow.

## DQN Central Bank

The CB action space controls combinations of:

- bridge fee;
- reserve target;
- internal emission/burn bias;
- risk multiplier.

A deterministic risk guard activates during material drawdown and restricts risk, increases reserve target and prevents positive emission bias.

## Training protocol

Safe-policy experiment:

```text
TRAIN:
  seeds = 1, 2, 3
  400 blocks per seed

Freeze DQN weights

OOS:
  seeds = 77, 101, 2026, 42, 31415
  300 blocks per seed
```

The same frozen policy is used on all holdout paths.

## Safe-policy OOS result

| Seed | DQN return | Passive return | Alpha | DQN max DD | Passive max DD |
|---:|---:|---:|---:|---:|---:|
| 77 | +15.6128% | +15.5808% | +0.0277% | 6.0235% | 6.4132% |
| 101 | +4.6873% | +4.5917% | +0.0915% | 10.0529% | 10.2660% |
| 2026 | -6.3247% | -5.9597% | -0.3882% | 14.4698% | 14.5973% |
| 42 | +11.2011% | +11.2185% | -0.0157% | 4.7066% | 4.9174% |
| 31415 | +2.8140% | +2.9236% | -0.1064% | 6.9855% | 7.0180% |

Aggregate:

- drawdown better than matched passive: **5/5**;
- mean drawdown improvement: **0.1947 percentage points**;
- positive alpha: **2/5**;
- mean alpha: **-0.0782%**;
- median alpha: **-0.0157%**;
- worst alpha: **-0.3882%**;
- worst DQN max drawdown: **14.4698%**.

Interpretation: current safe policy acts as a risk controller. It is not yet a demonstrated alpha engine.

## Negative control: longer/aggressive training

A larger run with 5 training seeds × 800 blocks increased mean alpha to +0.3389%, but drawdown became worse than passive on 5/5 holdout paths and worst DQN drawdown reached 22.2717%.

Therefore the longer-trained policy is explicitly retained as a negative control and is not the default.

## Tests

Local exact-source test:

```text
pytest
4 passed
```

Covered invariants:

1. P9 self-test passes.
2. All 12 bidirectional routes are recognized.
3. Outbound external asset delivery requires backed bridge inventory.
4. DQN Central Bank cannot create external capital flow.
5. Market/CB state geometry remains 20 / 12 and six market pairs.

## Current status

```text
P9.1 bidirectional BTC/ETH/WETH router       ✅ simulation
P9.2 SYNA/SYNR cross-chain routes            ✅ simulation
P9.3 DQN Market                              ✅ trained
P9.4 DQN Central Bank                        ✅ trained
P9.5 block-by-block learning                  ✅
P9.6 frozen OOS                              ✅ 5 seeds
P9.7 accounting invariants                    ✅
P9.8 risk-controller result                   ✅
P9.9 stable positive OOS alpha                ❌ not yet proven
P9.10 live bridge execution                   ❌ separate production layer
P9.11 DQN Treasury                            🧪 keep experimental until safer
```

The safe default remains DQN Market + DQN Central Bank. Treasury autonomy must remain an explicit experimental toggle until it passes the same frozen multi-seed OOS risk criteria.
