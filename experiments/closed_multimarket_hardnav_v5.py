from __future__ import annotations

import csv
import os
import json
import math
import statistics
from dataclasses import replace
from pathlib import Path

import numpy as np

from agent_economy.multimarket import BASE_ASSETS, D, MultiMarketConfig, MultiMarketHardNavEngine
from experiments.closed_multimarket_hardnav_v4 import (
    BLOCK_COUNT,
    TRAIN_BLOCKS,
    OOS_BLOCKS,
    SEED,
    max_drawdown_pct,
    rolling_volatility,
    price_ratios,
    select_train_anchor,
)

ROOT = Path(__file__).resolve().parents[1]
V4_CSV = Path(os.environ.get(
    "SYNERGY_V4_CSV",
    str(ROOT / "data" / "real_backtest_v4" / "ethereum_23544921_23557920_exact_gas_real_prices.csv"),
))
FLOW_CSV = ROOT / "data" / "real_external_flow_v5" / "observed_flow_by_eth_block.csv"
FLOW_MANIFEST = ROOT / "data" / "real_external_flow_v5" / "manifest.json"
REPORT_DIR = ROOT / "reports" / "closed_multimarket_hardnav_v5"


def load_v4_inputs():
    with V4_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != BLOCK_COUNT:
        raise RuntimeError(f"V4 row count mismatch: {len(rows)}")
    prices = {
        asset: [float(row[f"{asset}_usd"]) for row in rows]
        for asset in BASE_ASSETS
    }
    blocks = [
        {
            "block_number": int(r["block_number"]),
            "timestamp": int(r["timestamp"]),
            "gas_used": int(r["gas_used"]),
            "gas_limit": int(r["gas_limit"]),
            "base_fee_per_gas": int(r["base_fee_per_gas"]),
        }
        for r in rows
    ]
    return blocks, prices


def load_observed_flow(blocks):
    with FLOW_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_block = {int(r["block_number"]): r for r in rows}
    bridge = []
    dex = []
    unresolved = []
    for b in blocks:
        r = by_block.get(b["block_number"])
        if r is None:
            raise RuntimeError(f"missing observed-flow row for {b['block_number']}")
        bridge.append(float(r["observed_bridge_volume_usd"]))
        dex.append(float(r["observed_dex_swap_volume_usd"]))
        unresolved.append(int(r["unresolved_events"]))
    return bridge, dex, unresolved


def run_path_observed(blocks, prices, bridge_flow, dex_flow, *, anchor, count=None, enable_rebalance=True):
    n = count if count is not None else len(blocks)
    cfg = replace(MultiMarketConfig(), hedge_anchor=D(str(anchor)))
    engine = MultiMarketHardNavEngine(cfg)
    vols = rolling_volatility(prices)
    navs = [float(engine.capital_adjusted_hardnav())]

    for i in range(n):
        engine.apply_external_market_move(price_ratios(prices, i))
        # Counterfactual SYNERGY fee capture on observed historical demand:
        # bridge deposits pay only bridge fee; DEX swaps pay only swap fee.
        engine.record_external_bridge_flow(
            gross_volume=D(str(bridge_flow[i])),
            bridge_fee_bps=cfg.bridge_fee_bps,
            swap_fee_bps=D("0"),
        )
        engine.record_external_bridge_flow(
            gross_volume=D(str(dex_flow[i])),
            bridge_fee_bps=D("0"),
            swap_fee_bps=cfg.swap_fee_bps,
        )
        if enable_rebalance:
            engine.rebalance_external_risk(
                target_hedge_ratio=D(str(anchor)),
                target_bridge_share=cfg.bridge_asset_share,
                realized_volatility={asset: D(str(vols[i][asset])) for asset in BASE_ASSETS},
                eth_usd=D(str(prices["WETH"][i])),
                gas_gwei=D(str(blocks[i]["base_fee_per_gas"] / 1e9)),
                no_trade_band=D("0.002"),
            )
        navs.append(float(engine.capital_adjusted_hardnav()))
    return engine, navs, np.diff(np.asarray(navs, dtype=np.float64))


def select_anchor_observed(blocks, prices, bridge_flow, dex_flow):
    zero_engine, zero_nav, zero_steps = run_path_observed(
        blocks, prices, bridge_flow, dex_flow, anchor=0.0, count=TRAIN_BLOCKS, enable_rebalance=False
    )
    one_engine, one_nav, one_steps = run_path_observed(
        blocks, prices, bridge_flow, dex_flow, anchor=1.0, count=TRAIN_BLOCKS, enable_rebalance=False
    )
    a = zero_steps
    b = one_steps - zero_steps
    bc = b - b.mean()
    ac = a - a.mean()
    var_b = float(np.mean(bc * bc))
    if var_b <= 0:
        raise RuntimeError("TRAIN hedge coefficient not identifiable")
    raw = -float(np.mean(ac * bc)) / var_b
    selected = min(1.20, max(0.80, raw))
    return selected, raw


def main():
    blocks, prices = load_v4_inputs()
    bridge_flow, dex_flow, unresolved = load_observed_flow(blocks)
    flow_manifest = json.loads(FLOW_MANIFEST.read_text(encoding="utf-8"))
    scan_coverage = float(flow_manifest.get("aerodrome_scan_coverage_fraction", 1.0))
    failed_pool_scans = int(flow_manifest.get("aerodrome_failed_pool_scans", 0))
    anchor, raw_anchor = select_anchor_observed(blocks, prices, bridge_flow, dex_flow)
    engine, navs, steps = run_path_observed(
        blocks, prices, bridge_flow, dex_flow, anchor=anchor
    )

    train_end = navs[TRAIN_BLOCKS]
    oos_end = navs[-1]
    report = {
        "canonical_name": "CLOSED MULTI-MARKET HARDNAV V5",
        "classification": "REAL V4 MARKET PATH + OBSERVED EXTERNAL FLOW LOWER BOUND",
        "seed": SEED,
        "protocol": {
            "train_blocks": TRAIN_BLOCKS,
            "oos_blocks": OOS_BLOCKS,
            "continuous_no_reset": True,
            "hedge_anchor_selected_on_train_only": anchor,
            "hedge_anchor_selection": {
                "raw_anchor": raw_anchor,
                "selected_anchor": anchor,
                "oos_used_for_selection": False,
            },
        },
        "observed_external_flow": {
            "bridge_volume_usd": sum(bridge_flow),
            "dex_swap_volume_usd": sum(dex_flow),
            "total_usd": sum(bridge_flow) + sum(dex_flow),
            "nonzero_blocks": sum(
                (b + d) > 0 for b, d in zip(bridge_flow, dex_flow)
            ),
            "unresolved_events": sum(unresolved),
            "classification": "OBSERVED_EXTERNAL_FLOW_LOWER_BOUND",
            "aerodrome_scan_coverage_fraction": scan_coverage,
            "aerodrome_failed_pool_scans": failed_pool_scans,
            "coverage_claim": "LOWER_BOUND_ONLY; NOT FULL_MARKET_COVERAGE",
            "fee_capture_classification": "COUNTERFACTUAL_SYNERGY_FEE_CAPTURE_NOT_HISTORICALLY_EARNED",
            "fee_schedule_bps": {"bridge": 10, "dex_swap": 30},
        },
        "hardnav": {
            "start": navs[0],
            "train_end": train_end,
            "oos_end": oos_end,
            "train_return_pct": (train_end / navs[0] - 1) * 100,
            "oos_return_pct": (oos_end / train_end - 1) * 100,
            "full_return_pct": (oos_end / navs[0] - 1) * 100,
            "train_max_drawdown_pct": max_drawdown_pct(navs[: TRAIN_BLOCKS + 1]),
            "oos_max_drawdown_pct": max_drawdown_pct(navs[TRAIN_BLOCKS:]),
            "full_max_drawdown_pct": max_drawdown_pct(navs),
            "train_step_std": float(np.std(steps[:TRAIN_BLOCKS])),
            "oos_step_std": float(np.std(steps[TRAIN_BLOCKS:])),
            "negative_step_fraction": float(np.mean(steps < 0)),
        },
        "external_sources": {
            "bridge_and_swap_fee_revenue": float(engine.external_protocol_fee_revenue),
            "external_amm_fee_revenue": float(engine.external_amm_fee_revenue),
            "hedge_pnl": float(engine.hedge_pnl),
            "funding_cost": float(engine.funding_cost),
            "execution_cost": float(engine.execution_cost),
            "gas_cost": float(engine.gas_cost),
            "rebalance_batches": engine.rebalance_batches,
        },
        "status": "V5_PENDING_OBSERVED_FLOW_EVIDENCE_GATE",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "seed77_10000_train_3000_oos.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
