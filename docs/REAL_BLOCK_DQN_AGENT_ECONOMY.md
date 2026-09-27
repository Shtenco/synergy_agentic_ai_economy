# REAL-BLOCK DQN Agent Economic Replay

## Historical window

- Ethereum blocks: **18,251,965 -> 18,264,964**
- Count: **13,000 contiguous real block numbers**
- TRAIN: first **10,000**
- Freeze after TRAIN
- STRICT OOS: final **3,000**
- No environment reset

## Real market inputs

ETH/USD is sourced from real on-chain WETH/USDC pool price events keyed by Ethereum block number.

ETH/BTC is sourced from real on-chain WETH/WBTC reserve/price events keyed by Ethereum block number.

BTC/USD is reconstructed as ETH/USD divided by ETH/BTC.

WETH/USD follows ETH/USD.

Sparse on-chain price events are forward-filled between observed blocks.

## Agent economy

The Agent Economy remains a modeled behavioral layer using the repository's event cadence and accounting semantics. External jobs/company revenue are not historical marketplace logs yet.

## Gas limitation

The current run uses the historically reported **8.15 gwei median Ethereum gas price on 2023-10-01** as a calibration level.

It is **not** exact per-block baseFeePerGas.

Therefore this result must not be described as fully historical end-to-end replay yet.

## Results

- TRAIN end wealth: **61,161.72**
- OOS start wealth: **61,161.72**
- OOS end wealth: **76,853.25**
- OOS return: **+25.6558%**
- OOS max drawdown: **0.006242%**
- Full-path max drawdown: **0.039616%**
- Final market/Stability component: **8,698.72**
- Final modeled agent net external income: **68,154.53**
- Hedge PnL: **+18.24**
- Funding: **0.1148**

The majority of total wealth growth is driven by the modeled external agent economy, not trading alpha.

## Remaining work before FULL REAL-BLOCK status

1. exact per-block Ethereum baseFeePerGas / gasUsed;
2. historical marketplace/job-arrival logs for the external Agent Economy;
3. rerun the same 10k TRAIN -> frozen 3k OOS protocol with those inputs;
4. only then promote the benchmark to FULL HISTORICAL REAL-BLOCK MAINLINE.
