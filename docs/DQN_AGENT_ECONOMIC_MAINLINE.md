# DQN AGENT ECONOMIC MAINLINE

This document defines the canonical research line for the integrated SYNERGY DQN agent economy.

## What is integrated

The mainline is not only a trading DQN.

It combines:

- the full agent-economy semantics from `agent_economy/`:
  - 24 heterogeneous agents;
  - external jobs;
  - agent-to-agent subcontracting;
  - P2P loans;
  - deposits;
  - companies;
  - investments;
  - insurance;
  - bankruptcy/default accounting;
  - strategy evolution;
  - policy research;
  - Founder/Protocol fees;
- the P9 cross-chain market surface:
  - BTC;
  - ETH;
  - WETH;
  - SYNA;
  - SYNR;
- DQN Market;
- DQN Central Bank;
- v8 Global Stability Fund;
- v8.1 gas-aware execution.

Internal finance remains conservation-respecting:

```text
loan principal != profit
deposit principal != profit
investment principal != profit
subcontract payment != profit
internal fee != new system wealth
```

Only genuine external income and external expense change the agent-economy contribution to Economic Net Worth.

## Canonical walk-forward protocol

```text
Seed: 77

Blocks 1-10,000
TRAIN
DQN updates enabled

Block 10,000
freeze policy weights

Blocks 10,001-13,000
STRICT OOS
no DQN learning
no environment reset
same continuous market/economy path
```

This is intentionally stronger than resetting the OOS environment.

## v8 / v8.1 protection layer

The mainline preserves the documented protection framework:

| Regime | Hedge target | Credit multiplier |
|---|---:|---:|
| GREEN | 94% | 0.85x |
| YELLOW | 98% | 0.60x |
| ORANGE | 101% | 0.35x |
| RED | 105% | 0.10x |

Wealth floor:

```text
WealthFloor = HighWaterMark * (1 - 0.15%)
```

Gas-aware execution:

```text
minimum batch interval = 8 blocks
safety multiple = 1.50x
risk-benefit multiplier = 3.0
batch gas = 90,000 + 33,000 * active hedge legs
netting + batching + economic execution gate
```

## Canonical seed-77 result

Opening world wealth:

```text
8,700.00
```

After 10,000 TRAIN blocks:

```text
60,836.5364
```

After the following 3,000 STRICT OOS blocks:

```text
76,723.0879
```

OOS return from the freeze boundary:

```text
+26.1135%
```

Risk:

```text
full-path max drawdown = 0.042523%
strict-OOS max drawdown = 0.006219%
```

Execution cost over all 13,000 blocks:

```text
gas             = 27.24624
execution fees  = 1.55191
funding         = 0.46320
hedge batches   = 901
hedge PnL       = +137.54363
```

## Full agent-economy activity

At block 13,000:

```text
external jobs       = 4,333
P2P loans           = 1,857
loan default rate   = 2.6387%
deposits            = 1,181
investments         = 1,000
insurance actions   = 4,331
net external income = 68,060
```

The large rise in total wealth must not be misreported as DQN trading alpha.

Most of the increase comes from genuine modeled external economic activity: external jobs and company revenue, net of explicit external business losses.

The DQN/Stability layer's primary role in this benchmark is risk control, reserve allocation and execution efficiency.

## Canonical wealth line

The canonical top-level metric is:

```text
TOTAL ECONOMIC WEALTH AFTER GAS
=
opening world wealth
+ real market PnL
+ hedge PnL
- gas
- execution fees
- funding
+ agent external income
- agent external expense
```

Internal issuance/claims and internal principal transfers are excluded from profit.

## Calibration

The external-market volatility is calibrated so the reconstruction reproduces the repository's documented v5 seed-77 / 500-block unhedged maximum drawdown:

```text
target   = 0.245383602289%
achieved = 0.245383602288%
```

## Evidence classification

This benchmark is a **canonical integration reconstruction** built from:

- current `agent_economy/` source semantics;
- current P9 DQN architecture;
- repository-documented v8/v8.1 Stability Fund and gas-aware parameters.

It is not claimed to be byte-for-byte execution of the archived v8.1 source tree. That distinction must remain in future reports.

## Canonical status

```text
Full agent economy semantics      YES
Cross-chain market state          YES
DQN Market                        YES
DQN Central Bank                  YES
Global Stability Fund             YES
Gas-aware execution               YES
10,000-block TRAIN                PASS
3,000-block strict OOS            PASS
No reset at OOS boundary          YES
Frozen OOS weights                YES
Internal mint counted as profit   NO
Internal finance counted profit   NO

Status:
DQN AGENT ECONOMIC MAINLINE
```
