# SYNERGY Global Stability Fund v8 — Release

This package is the current v8 release. It retains the verified v5 dual-contour economy and adds the v8 Global Stability Fund, Wealth Floor, dynamic external hedge, protected-wealth ratchet, Tier-0…Tier-4 banking risk metrics, endogenous haircuts, CCR/LCR controls and recursive collateral accounting.

**Primary research result:** the final 94% GREEN hedge configuration reduces reference max drawdown from 0.24538% to 0.00584% on seed 77, while the 20-seed mean max drawdown falls from 0.29396% to 0.00646%. This protection is not free; strong upward paths can produce negative alpha versus HODL.

---

# SYNERGY Dual Contour v5 — AI Market Maker + SYNERGY CHAIN

v5 extends the verified v4 agent capital markets into a two-contour monetary/market system.

The **real contour** remains the only source of HardNAV: real USDC, RUBX/RUBZ treasury assets, real Base inventory, companies, credit reserves and external trading PnL.

The new **SYNERGY CHAIN contour** mirrors all 13 system assets as non-redeemable synthetic assets:

`RUBX, RUBZ, USDC, WETH, cbBTC, VVV, VIRTUAL, AERO, cbETH, USDe, cbXRP, TOSHI, MORPHO`.

Internal synthetic assets may be minted and burned by the policy market maker. That can change internal supply, liquidity, TVL and price, but it does **not** increase HardNAV by accounting convention.

## The two controls

### 1. Counter-cyclical AI market maker

The internal MM uses exact CPMM math, not fixed trade sizes.

- external strength lowers the permitted internal spread and creates **mint → sell** pressure;
- external weakness raises internal support and creates **buyback → burn** pressure;
- volatility and bridge inventory skew widen/narrow the target spread;
- online reward feedback adjusts spread compensation;
- each trade is sized to the target internal price instead of overshooting it.

In the reference 500-block run the controller executed **4,317** policy actions: **2,146 mint/sell** and **2,171 buy/burn**. Mean absolute target error was only **0.256 bps**; maximum error was about **3.0 bps**.

### 2. Real external delta control

Synthetic market making cannot smooth real net assets by itself. v5 therefore separately manages the real inventory held by the bridge.

The controller sells part of real Base inventory into strength and restores inventory on weakness/drawdown. This is the only v5 mechanism that changes real exposure and can therefore change real HardNAV risk.

The default bridge takes custody of 50% of each protocol-owned Base AMM reserve pair. The transfer is proportional, so opening aggregate wealth is unchanged. The bridge starts at **$2,500 real NAV** and the controller defaults to an 18% base real-asset delta, adapting around that level.

## SYNERGY CHAIN Base-fork layer

`synergy_chain/chain.py` adds a deterministic internal blockchain model:

- chain name: `SYNERGY CHAIN`;
- chain id: `777777`;
- parent family: Base / OP Stack compatible simulation;
- block time used by this experiment: **12 seconds**;
- 13 mirrored assets;
- deterministic parent/hash linkage;
- ordered mint/burn/state-commitment transactions;
- **external redemption disabled**.

`synergy_chain/base_fork_manifest.json` is the machine-readable chain/bridge/accounting manifest.

This release is a Base-fork-style simulation and shadow infrastructure. It does **not** claim that an OP Stack production node or live bridge has been deployed.

## Inventory bridge

The bridge is a warehouse, not a teleport pipe. Real inventory is held on the external contour while the internal chain can issue shadow inventory against it. There is deliberately no `redeem_to_external()` path.

Synthetic leverage is bounded against marked real bridge inventory. In the reference run the maximum observed synthetic leverage was only **1.091×** versus the configured **4×** ceiling.

## Reference run: 500 × 12 seconds

`seed=77`, exactly **500 blocks = 6,000 seconds = 100 minutes**.

| Metric | v4 | v5 full |
|---|---:|---:|
| Opening real wealth | $8,700.00 | $8,700.00 |
| Capital-adjusted closing wealth | $8,734.94 | $8,729.29 |
| Alpha vs passive HODL | +$21.12 | **+$15.47** |
| Max adjusted drawdown | 0.3391% | **0.2454%** |
| Block-to-block NAV-change volatility | 1.594 | **1.163** |

The main result is risk smoothing, not free profit:

- max drawdown falls about **27.6%** on the matched reference path;
- block-to-block NAV-change volatility falls about **27.0%**;
- downside step volatility falls by roughly the same order;
- alpha remains positive, but is lower than v4 because the system deliberately carries less external market beta.

A matched v5 run with the shadow chain active but **external delta disabled** has drawdown **0.3409%**, essentially the same as v4. This isolates the result: internal minting does not magically smooth real HardNAV; the real smoothing comes from external delta management.

A second ablation disables only the internal shadow MM. On the same seed, mean internal spread error explodes from **0.256 bps** to about **1,242.8 bps**, while real drawdown is unchanged. This isolates the other direction: synthetic mint/burn controls the internal spread extremely strongly, but does not by itself create or smooth external HardNAV.

## Real vs synthetic economics

Reference v5:

- closing real wealth: **$8,765.0741**;
- net external capital flow: **+$35.7885**;
- capital-adjusted closing wealth: **$8,729.2855**;
- HODL benchmark: **$8,713.8193**;
- alpha: **+$15.4662**;
- bridge external volume: **$3,265.81**;
- bridge realized inventory PnL: **+$2.3960**;
- bridge external execution fees: **$1.3063**;
- ending bridge real asset share: **19.49%**.

Shadow contour:

- policy-minted synthetic value: **$1,076.93 sUSDC-equivalent**;
- policy-burned synthetic value: **$485.22 sUSDC-equivalent**;
- closing shadow supply value: **$2,731.70 synthetic USDC-equivalent**;
- internal synthetic fees: **$2.769 sUSDC-equivalent**.

The last four numbers are **not HardNAV or external profit**.

## 20-seed robustness

On deterministic seeds 1–20:

- v5 reduces max drawdown versus v4 in **20/20** paths;
- mean drawdown reduction: **27.06%**;
- median drawdown reduction: **27.05%**;
- observed range: **17.88% to 33.13%**;
- v5 alpha vs HODL remains positive in **20/20** paths;
- mean v5 alpha: **+$15.77**;
- alpha range: **+$3.01 to +$23.27**.

Bridge realized inventory PnL is positive only in **9/20** paths. That is intentional evidence that the risk smoothing is not based on a perfect predictor. The controller mainly reduces beta; trading alpha is path-dependent.

## 5× volatility stress

With the same seed and 5× reference volatility:

- v4 max drawdown: **1.8144%**;
- v5 max drawdown: **1.7166%**;
- v4 alpha vs HODL: **+$29.92**;
- v5 alpha vs HODL: **+$52.36** on this particular stress path;
- bridge realized inventory PnL: **+$53.60**.

This is a scenario result, not a guarantee or forecast.

## Chain result

The 500-block reference run seals exactly **500 SYNERGY CHAIN blocks** and **7,025 internal transactions/state commitments**. The final deterministic chain tip is stored in the JSON report.

## Run

```bash
python run_dual_contour.py --blocks 500 --seed 77 \
  --output reports/v5_seed77_final/v5_full.json

python scripts/render_dual_contour_report.py \
  reports/v5_seed77_final/v5_full.json \
  reports/v5_seed77_final/rendered
```

Ablation:

```bash
python run_dual_contour.py --blocks 500 --seed 77 --no-delta \
  --output reports/v5_seed77_final/v5_no_delta.json
```

## Package map

```text
agent_economy/                  v2 autonomous labor/credit/investment economy
macro_economy/                  v3/v4 triangle, Base markets and capital markets
  dual_contour_engine.py        v5 real + shadow orchestration
synergy_chain/
  ledger.py                     zero-HardNAV shadow mint/burn ledger
  bridge.py                     one-way real inventory warehouse
  ai_mm.py                      adaptive counter-cyclical AI MM + delta policy
  chain.py                      deterministic SYNERGY CHAIN block layer
  base_fork_manifest.json       machine-readable Base-fork rules
scripts/
  render_dual_contour_report.py 20-chart v5 report
legacy/
  2CHAN_PRINT_MONEY/            preserved user-supplied two-channel prototype
  RUBX_RUBZ_RELEASE/            preserved canonical RUBX/RUBZ release
reports/
  v5_seed77_final/
  v5_robustness_20_seeds_final.csv
tests/
```

## What was retained from 2CHAN_PRINT_MONEY

The original archive correctly emphasizes the **bridge-as-inventory** idea instead of physically bridging on every arbitrage. v5 retains that principle, but removes the experimental weaknesses from the economic model:

- no unimplemented arbitrage direction in the v5 Python engine;
- no claim that a lagged historical point is a TWAP;
- synthetic minting is explicitly excluded from HardNAV;
- bridge inventory is marked as real inventory and cannot be duplicated;
- internal spread capture and external realized PnL are separate metrics;
- fixed trade amounts are replaced by exact-target sizing;
- all 13 system assets are supported, not only WETH/USDC.

The original Solidity archive is preserved under `legacy/2CHAN_PRINT_MONEY/` for provenance.

## Verification

```bash
PYTHONPATH=. pytest -q tests
MODE=unit PYTHONPATH=. python experiments/dqn_cb_market/experiment_syna.py
```

The development tree currently passes **96/96 tests** and the legacy DQN invariant suite reports **UNIT PASS**. Final release verification is additionally run from a clean unpacked ZIP.

No live private keys, autonomous live-money permissions or production bridge deployment are enabled in this release.

# v8 — Global Stability Fund / Wealth Floor

v8 adds a global AI risk-management overlay above the v5 dual-contour system and the internal collateral/banking layer.

## Core design

- **50% of opening world wealth** is assigned as the Stability Fund's collateral/risk budget. This is existing wealth under a hedging mandate; it is not new NAV and is never double-counted.
- The fund dynamically targets **35–80%** of current system wealth depending on risk regime.
- A real external short-delta overlay hedges the ten Base assets. Hedge gains/losses, execution fees and funding costs are included in Economic Net Worth.
- `Protected Wealth` is a monotone profit-lock ratchet. It can rise when a new high-water mark is reached; it does not fall during normal rebalancing.
- `Wealth Floor = High-Water Mark × (1 − 0.15%)` is an internal control objective, not a guarantee.
- GREEN/YELLOW/ORANGE/RED regimes progressively increase hedge ratio and reduce credit/recursive growth.

Final policy hedge targets:

| Regime | Managed wealth target | Base hedge target | Credit multiplier | Recursive-growth multiplier |
|---|---:|---:|---:|---:|
| GREEN | 50% | 94% | 0.85× | 1.00× |
| YELLOW | 60% | 98% | 0.60× | 0.70× |
| ORANGE | 70% | 101% | 0.35× | 0.40× |
| RED | 80% | 105% | 0.10× | 0.15× |

The hedge can materially reduce drawdown, but it is not free. On strong upward paths the short hedge can lose money and underperform HODL. This protection drag is reported explicitly.

## Banking/collateral hierarchy retained in v8

v8 rebuilds the internal quality hierarchy used for risk control:

- **Tier-0:** USDC / real Base assets
- **Tier-1:** RUBX
- **Tier-2:** RUBZ
- **Tier-3:** agent/company bonds and equities
- **Tier-4:** recursive structured collateral

Haircuts increase endogenously with volatility, leverage, liquidity stress and tier depth. `CCR` and `LCR` are SYNERGY-internal control ratios, not claims of Basel regulatory compliance.

Three accounting layers remain separate:

- **Economic Net Worth / capital-adjusted wealth:** externally realizable wealth after external capital-flow adjustment, including real hedge PnL/costs.
- **Collateral NAV:** Economic/Hard asset base plus de-duplicated haircut-valued internal collateral claims.
- **Gross TVL:** every collateral lock including rehypothecation; intentionally a scale/activity metric, not profit.

Internal token issuance or recursive claims can increase Collateral NAV / Gross TVL but cannot increase Economic Net Worth by themselves.

## Reference run — seed 77, 500 × 12 seconds

| Metric | v5 unhedged | v8 Stability Fund |
|---|---:|---:|
| Opening world wealth | $8,700.00 | $8,700.00 |
| Capital-adjusted closing wealth | $8,729.2855 | **$8,715.7606** |
| Alpha vs HODL | +$15.4662 | **+$1.9413** |
| Max drawdown | 0.24538% | **0.00584%** |
| Stability Fund starting mandate | — | **$4,350.00 (50%)** |
| Stability Fund ending NAV | — | **$4,336.48** |
| Hedge PnL | — | **−$13.0000** |
| Hedge execution fees | — | **$0.5147** |
| Hedge funding cost | — | **$0.0103** |
| Floor breaches | — | **0** |
| Gross TVL end | — | **$15,735.92** |
| Collateral NAV end | — | **$13,534.77** |
| Internal claims end | — | **$6,553.65** |
| CCR end | — | **2.0626×** |
| LCR end | — | **1.6320×** |

The key result is not free profit; it is a drastic risk transfer. On the matched seed, v8 reduces max drawdown by roughly **97.6%** relative to v5 while giving up most of the upside.

## 20-seed robustness

Using deterministic seeds 1–20:

- drawdown improves vs v5 in **20/20** paths;
- mean max drawdown: **0.29396% → 0.00646%**;
- worst observed v8 drawdown: **0.00904%**;
- mean alpha vs HODL: **+$15.7654 v5 → +$16.0537 v8**;
- v8 alpha is positive in **16/20** paths;
- all 20 paths record **zero Wealth Floor breaches** under this modeled floor.

The mean alpha remains positive because hedge outcomes are path-dependent, but some strong trending paths suffer material protection drag. This is not a guaranteed-return system.

## 5× volatility stress — seed 77

| Metric | v5 | v8 |
|---|---:|---:|
| Max drawdown | 1.71658% | **0.04548%** |
| Alpha vs HODL | +$52.3637 | **−$49.6272** |
| Hedge PnL | — | **−$99.6232** |
| Hedge execution fees | — | **$2.3560** |
| Floor breaches | 355* | **0** |

`*` the v5 number is a hypothetical v8 floor applied to the unhedged path; v5 itself does not promise a floor.

The stress result is intentionally explicit: the hedge protects the NAV curve but can be expensive when the market path strongly rewards long beta.

## Run v8

```bash
PYTHONPATH=. python run_stability_v8.py \
  --blocks 500 --seed 77 \
  --output reports/v8_seed77/v8_full.json

PYTHONPATH=. python scripts/render_stability_v8_report.py \
  reports/v8_seed77/v8_full.json \
  reports/v8_seed77/rendered
```

A/B unhedged run:

```bash
PYTHONPATH=. python run_stability_v8.py \
  --blocks 500 --seed 77 --disable-stability-fund \
  --output reports/v8_seed77/v5_unhedged.json
```

Stress:

```bash
PYTHONPATH=. python run_stability_v8.py \
  --blocks 500 --seed 77 --reference-vol-multiplier 5 \
  --output reports/v8_seed77/v8_stress_vol5.json
```

## Verification

```bash
PYTHONPATH=. pytest -q tests
MODE=unit PYTHONPATH=. python experiments/dqn_cb_market/experiment_syna.py
```

No live private keys, real-money autonomous permissions, production bridge or guaranteed wealth floor are enabled in this release. The entire v8 is a deterministic research/simulation environment.

## v8.1 Gas-Aware Execution

The $1,000 / 1,000-block profile adds a cost-aware hedge executor instead of rebalancing every block.

Trained policy:

- minimum batch interval: 8 blocks;
- safety multiple: 1.50x gas + execution fee;
- risk-benefit multiplier: 3.0;
- batch gas model: 90,000 base gas + 33,000 per active hedge leg;
- all hedge legs are netted into one batch;
- execution is skipped unless estimated risk reduction clears transaction costs.

Training used seeds 1-3. Validation used unseen seeds 4-13. The selected policy produced positive capital-after-gas on all 10 validation seeds in this simulator. This is a simulation result, not a guarantee of real-world profit.

Reproduce the reference run:

    PYTHONPATH=. python run_stability_v8.py --blocks 1000 --seed 77 --initial-capital 1000 --gas-aware --gas-min-interval-blocks 8 --gas-safety-multiple 1.50 --gas-risk-benefit-multiplier 3.0 --output reports/gas_aware_1000/seed77.json

Train/re-evaluate:

    PYTHONPATH=. python scripts/train_gas_policy.py --capital 1000 --blocks 1000 --train-seeds 1,2,3 --holdout-seeds 4,5,6,7,8 --output reports/gas_aware_1000/training.json
