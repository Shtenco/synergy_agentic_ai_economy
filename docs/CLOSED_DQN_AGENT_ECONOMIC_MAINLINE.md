# CLOSED DQN AGENT ECONOMIC MAINLINE

This document defines the new canonical **closed** SYNERGY agent-economy research line.

The legacy open-economy scenarios remain reproducible, but they are no longer the preferred benchmark for autonomous machine-to-machine economic activity.

## Core invariant

The closed mode disables all artificial external operating flows:

```text
external job inflow        = 0
external company revenue   = 0
external business loss     = 0
```

The external BTC/ETH/WETH layer remains a reserve/market-pricing environment only. It does not inject job revenue into agents.

Internal activity is therefore:

```text
agent need
→ internal Task/Job demand
→ bidding
→ escrow
→ agent execution
→ verified useful work
→ internal settlement
→ protocol fee
→ reputation / credit / capital effects
```

## Accounting separation

The mainline explicitly separates:

```text
HardNAV
Internal GDP
Productive Capital
Gross Transaction Volume
Financial Claims / Credit
Token Velocity
```

Internal payments do **not** increase HardNAV.

Likewise:

```text
loan principal     != profit
deposit principal  != profit
investment         != profit
token mint         != HardNAV
internal GDP       != HardNAV
productive capital != cash
transaction volume != profit
```

## Closed-mode implementation

New modules:

- `agent_economy/endogenous.py`
  - endogenous agent demand;
  - company service demand;
  - internal escrow jobs;
  - verified-work receipts;
  - productive assets;
  - internal GDP;
  - productive-capital decay;
  - gross transaction volume;
  - SYNA/SYNR settlement-velocity indices.

- `agent_economy/closed_engine.py`
  - reuses the existing verified labor/credit/deposit/company/investment/insurance/bankruptcy state machines;
  - replaces the legacy external orchestration;
  - never invokes external job funding, external company revenue or random external business loss in the closed run loop.

The legacy `AgentEconomy` is preserved for historical reproducibility.

## Canonical DQN protocol

```text
Seed 77

HardNAV start:
8,700

Blocks 1–10,000:
TRAIN

Block 10,000:
freeze DQN weights

Blocks 10,001–13,000:
STRICT OOS

No environment reset.
No artificial external job income.
No artificial external company income.
```

The market overlay uses the historical block-number / on-chain price path assembled in the preceding real-block work. Gas remains historically calibrated rather than exact per-block gas in this integration reconstruction.

## Monetary governor

The first closed-economy run exposed +13.5% internal token-supply inflation.

That run was rejected as the canonical monetary policy.

V2 adds a fail-safe supply corridor around approximately ±2%:

- positive issuance is disabled when the supply corridor is reached;
- excessive positive inflation triggers bounded burn;
- positive issuance is disabled under sufficiently high settlement velocity;
- RED regime cannot use positive emission.

The DQN still selects mint / neutral / burn intent inside this guard.

## Canonical V2 result

### HardNAV

```text
Start                    8,700.000000
TRAIN end                8,710.318523
STRICT OOS end           8,710.407763

OOS return               +0.001025%
Full-path max DD          0.006236%
Strict-OOS max DD         0.000144%
```

This is intentionally almost flat: internal agent commerce is not reclassified as external wealth.

### Internal economy

```text
Internal GDP              1,147.539441
Productive Capital          306.299335
Gross Transaction Volume 14,585.404681
Verified Useful Work      1,024.486781
Verified Work Receipts        3,289
Internal Jobs                 3,289
Active Agents                    24
```

### Credit

Final active credit happened to be zero at the final block because loans are short-maturity.

The full path is therefore reported as:

```text
Mean Credit Outstanding   0.251860
Peak Credit Outstanding   4.904812
Final Credit Outstanding  0
```

### Wealth distribution

```text
Gini                      0.676083
Minimum agent wealth      0.230881
Median agent wealth      12.974312
Maximum agent wealth    161.772427
```

This concentration is not hidden: it is a current hardening target.

### Protocol Treasury

```text
Protocol Treasury         73.974361
```

All of this is internally funded fee income. It is not external system profit.

### SYNA / SYNR velocity

The current `agent_economy` core still uses a common cash ledger. Until native token balances are migrated into that package, transaction categories are mapped onto the two settlement surfaces.

```text
SYNA velocity index       0.140516
SYNR velocity index       1.347802
```

These are accounting indices, not claims that the legacy ledger already has native on-chain SYNA/SYNR balances.

### Defaults

```text
Loan defaults             0
Deposit defaults          55
Total defaults            55
```

Deposit defaults and wealth concentration are explicit remaining weaknesses.

### Inflation

```text
Final token inflation    -2.000728%
Observed max              +0.005999%
Observed min              -2.000728%
```

The result sits at the lower edge of the safety corridor. A future target should center supply closer to neutral rather than riding a boundary.

### Conservation

```text
Opening internal claim cash  720.000000000000
Closing internal claim cash  719.999999999997
Gap                         -3.41e-12
```

This is the most important accounting result of the closed run:

> thousands of jobs, loans, deposits, investments, fees and insurance actions occurred without creating artificial system cash.

## Interpretation

The old open benchmark could grow top-line system wealth because modeled external buyers and enterprise clients injected cash.

The closed mainline cannot do that.

Its success criteria are instead:

1. preserve HardNAV;
2. create useful machine-to-machine production;
3. circulate internal money efficiently;
4. produce measurable productive capital;
5. maintain solvency;
6. avoid inflationary financing;
7. avoid excessive concentration/default cascades.

## Current weaknesses

The V2 run exposes three areas for the next hardening pass:

1. **wealth concentration:** Gini ≈ 0.676;
2. **deposit defaults:** 55 over the run;
3. **monetary centering:** inflation ended at the lower supply corridor rather than near zero.

These should be treated as optimization targets for DQN-CB V3.

## Canonical status

```text
Artificial external job inflow        OFF
Artificial company external revenue   OFF
Random external business loss         OFF
Internal job market                    ON
Agent-to-agent escrow settlement       ON
P2P credit / deposits                  ON
Companies / investments               ON
Insurance / bankruptcy                ON
Productive capital accounting          ON
Verified useful work                   ON
HardNAV separation                     ON
10,000 TRAIN                           PASS
3,000 STRICT OOS                       PASS
No reset                               YES
Closed cash conservation               PASS

Status:
CLOSED DQN AGENT ECONOMIC MAINLINE V2
```
