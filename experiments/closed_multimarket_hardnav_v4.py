from __future__ import annotations

import bisect
import csv
import io
import json
import math
import statistics
import time
import zipfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pyarrow.parquet as pq
import requests

from agent_economy.multimarket import BASE_ASSETS, D, MultiMarketConfig, MultiMarketHardNavEngine


START_BLOCK = 23_544_921
END_BLOCK = 23_557_920
BLOCK_COUNT = 13_000
TRAIN_BLOCKS = 10_000
OOS_BLOCKS = 3_000
SEED = 77
XATU_ROOT = (
    "https://data.ethpandaops.io/xatu/mainnet/databases/default/"
    "canonical_execution_block/1000"
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "real_backtest_v4"
REPORT_DIR = ROOT / "reports" / "closed_multimarket_hardnav_v4"
V3_REPORT = (
    ROOT
    / "reports"
    / "closed_multimarket_hardnav_v3"
    / "seed77_10000_train_3000_oos.json"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "SYNERGY-Historical-V4/1.0"})


def _get(url: str, *, params: dict | None = None, attempts: int = 6, timeout: int = 60) -> requests.Response:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            response = SESSION.get(url, params=params, timeout=timeout)
            if response.status_code == 429:
                time.sleep(min(2 ** attempt, 15))
                continue
            response.raise_for_status()
            return response
        except Exception as exc:
            last = exc
            time.sleep(min(2 ** attempt, 15))
    raise RuntimeError(f"GET failed after {attempts} attempts: {url}: {last!r}")


def _epoch_seconds(value) -> int:
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    if isinstance(value, np.datetime64):
        return int(value.astype("datetime64[s]").astype(np.int64))
    text = str(value)
    if text.isdigit():
        raw = int(text)
        if raw > 10**15:
            return raw // 1_000_000
        if raw > 10**12:
            return raw // 1_000
        return raw
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def fetch_xatu_blocks() -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    urls: list[str] = []
    first_chunk = (START_BLOCK // 1000) * 1000
    last_chunk = (END_BLOCK // 1000) * 1000

    for chunk in range(first_chunk, last_chunk + 1, 1000):
        url = f"{XATU_ROOT}/{chunk}.parquet"
        urls.append(url)
        response = _get(url)
        table = pq.read_table(
            io.BytesIO(response.content),
            columns=[
                "block_date_time",
                "block_number",
                "gas_used",
                "gas_limit",
                "base_fee_per_gas",
            ],
        )
        data = table.to_pydict()
        for i, number in enumerate(data["block_number"]):
            n = int(number)
            if START_BLOCK <= n <= END_BLOCK:
                rows.append(
                    {
                        "block_number": n,
                        "timestamp": _epoch_seconds(data["block_date_time"][i]),
                        "gas_used": int(data["gas_used"][i]),
                        "gas_limit": int(data["gas_limit"][i]),
                        "base_fee_per_gas": int(data["base_fee_per_gas"][i]),
                    }
                )

    rows.sort(key=lambda row: row["block_number"])
    numbers = [row["block_number"] for row in rows]
    if len(rows) != BLOCK_COUNT:
        raise RuntimeError(f"Xatu block count mismatch: {len(rows)} != {BLOCK_COUNT}")
    if numbers[0] != START_BLOCK or numbers[-1] != END_BLOCK:
        raise RuntimeError("Xatu block endpoints mismatch")
    if any(b != a + 1 for a, b in zip(numbers, numbers[1:])):
        raise RuntimeError("Xatu blocks are not contiguous")
    if any(row["gas_limit"] <= 0 or row["gas_used"] < 0 or row["base_fee_per_gas"] <= 0 for row in rows):
        raise RuntimeError("Invalid exact gas fields in Xatu rows")
    return rows, urls


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def coinbase_candles(product: str, t0: int, t1: int) -> dict[int, float]:
    out: dict[int, float] = {}
    cursor = t0
    while cursor <= t1:
        chunk_end = min(t1, cursor + 299 * 60)
        url = f"https://api.exchange.coinbase.com/products/{product}/candles"
        response = _get(
            url,
            params={
                "granularity": 60,
                "start": _iso(cursor),
                "end": _iso(chunk_end),
            },
            timeout=40,
        )
        batch = response.json()
        if isinstance(batch, dict):
            raise RuntimeError(f"Coinbase {product} error: {batch}")
        for item in batch:
            if len(item) >= 5:
                out[int(item[0])] = float(item[4])
        cursor = chunk_end + 60
        time.sleep(0.12)
    if len(out) < 30:
        raise RuntimeError(f"Insufficient Coinbase candles for {product}: {len(out)}")
    return out


def _date_range(t0: int, t1: int) -> list[str]:
    start = datetime.fromtimestamp(t0, timezone.utc).date()
    end = datetime.fromtimestamp(t1, timezone.utc).date()
    days = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _parse_binance_open_time(raw: str) -> int:
    value = int(raw)
    if value > 10**15:
        return value // 1_000_000
    if value > 10**12:
        return value // 1_000
    return value


def binance_vision_candles(symbol: str, t0: int, t1: int) -> tuple[dict[int, float], str]:
    dates = _date_range(t0, t1)
    roots = [
        ("spot", "https://data.binance.vision/data/spot/daily/klines"),
        ("futures_um", "https://data.binance.vision/data/futures/um/daily/klines"),
    ]
    last_error: Exception | None = None
    for venue, root in roots:
        out: dict[int, float] = {}
        try:
            for day in dates:
                filename = f"{symbol}-1m-{day}.zip"
                url = f"{root}/{symbol}/1m/{filename}"
                response = _get(url, attempts=3, timeout=45)
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    names = archive.namelist()
                    if not names:
                        raise RuntimeError(f"Empty Binance zip {url}")
                    text = archive.read(names[0]).decode("utf-8")
                reader = csv.reader(io.StringIO(text))
                for row in reader:
                    if not row or not row[0].lstrip("-").isdigit():
                        continue
                    ts = _parse_binance_open_time(row[0])
                    if t0 - 120 <= ts <= t1 + 120:
                        out[(ts // 60) * 60] = float(row[4])
            if len(out) >= 30:
                return out, f"Binance Vision {venue} {symbol}"
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"No Binance Vision series for {symbol}: {last_error!r}")


def bybit_candles(symbol: str, t0: int, t1: int) -> dict[int, float]:
    out: dict[int, float] = {}
    cursor = t0
    url = "https://api.bybit.com/v5/market/kline"
    while cursor <= t1:
        chunk_end = min(t1, cursor + 900 * 60)
        response = _get(
            url,
            params={
                "category": "spot",
                "symbol": symbol,
                "interval": "1",
                "start": cursor * 1000,
                "end": chunk_end * 1000,
                "limit": 1000,
            },
            timeout=45,
        )
        payload = response.json()
        if payload.get("retCode") != 0:
            raise RuntimeError(f"Bybit {symbol} error: {payload}")
        for item in payload.get("result", {}).get("list", []):
            ts = int(item[0]) // 1000
            out[(ts // 60) * 60] = float(item[4])
        cursor = chunk_end + 60
        time.sleep(0.12)
    if len(out) < 30:
        raise RuntimeError(f"Insufficient Bybit candles for {symbol}: {len(out)}")
    return out


def fetch_with_fallbacks(
    asset: str,
    candidates: list[tuple[str, Callable[[], tuple[dict[int, float], str] | dict[int, float]]]],
) -> tuple[dict[int, float], dict]:
    errors = []
    for label, loader in candidates:
        try:
            value = loader()
            if isinstance(value, tuple):
                series, actual_label = value
            else:
                series, actual_label = value, label
            if len(series) < 30:
                raise RuntimeError(f"only {len(series)} candles")
            return series, {
                "asset": asset,
                "source": actual_label,
                "attempted": [x[0] for x in candidates],
            }
        except Exception as exc:
            errors.append(f"{label}: {exc!r}")
    raise RuntimeError(f"No real historical feed for {asset}: {' | '.join(errors)}")


def fetch_price_series(blocks: list[dict]) -> tuple[dict[str, list[float]], dict]:
    t0 = blocks[0]["timestamp"] - 600
    t1 = blocks[-1]["timestamp"] + 120

    def cb(product: str):
        return lambda: (coinbase_candles(product, t0, t1), f"Coinbase Exchange {product}")

    def bv(symbol: str):
        return lambda: binance_vision_candles(symbol, t0, t1)

    def by(symbol: str):
        return lambda: (bybit_candles(symbol, t0, t1), f"Bybit spot {symbol}")

    plan = {
        "WETH": [
            ("Coinbase ETH-USD", cb("ETH-USD")),
            ("Binance ETHUSDT", bv("ETHUSDT")),
        ],
        "cbBTC": [
            ("Coinbase BTC-USD", cb("BTC-USD")),
            ("Binance BTCUSDT", bv("BTCUSDT")),
        ],
        "VVV": [
            ("Coinbase VVV-USD", cb("VVV-USD")),
            ("Binance VVVUSDT", bv("VVVUSDT")),
        ],
        "VIRTUAL": [
            ("Coinbase VIRTUAL-USD", cb("VIRTUAL-USD")),
            ("Binance VIRTUALUSDT", bv("VIRTUALUSDT")),
        ],
        "AERO": [
            ("Coinbase AERO-USD", cb("AERO-USD")),
            ("Binance AEROUSDT", bv("AEROUSDT")),
        ],
        "cbETH": [
            ("Coinbase CBETH-USD", cb("CBETH-USD")),
            ("Coinbase CBETH-USDC", cb("CBETH-USDC")),
        ],
        "USDe": [
            ("Coinbase USDE-USD", cb("USDE-USD")),
            ("Coinbase USDE-USDC", cb("USDE-USDC")),
            ("Bybit USDEUSDT", by("USDEUSDT")),
            ("Binance USDEUSDT", bv("USDEUSDT")),
        ],
        "cbXRP": [
            ("Coinbase XRP-USD 1:1 underlying", cb("XRP-USD")),
            ("Binance XRPUSDT 1:1 underlying", bv("XRPUSDT")),
        ],
        "TOSHI": [
            ("Coinbase TOSHI-USD", cb("TOSHI-USD")),
            ("Coinbase TOSHI-USDC", cb("TOSHI-USDC")),
            ("Binance TOSHIUSDT", bv("TOSHIUSDT")),
        ],
        "MORPHO": [
            ("Coinbase MORPHO-USD", cb("MORPHO-USD")),
            ("Coinbase MORPHO-USDC", cb("MORPHO-USDC")),
            ("Binance MORPHOUSDT", bv("MORPHOUSDT")),
        ],
    }

    raw: dict[str, dict[int, float]] = {}
    provenance: dict[str, dict] = {}
    for asset in BASE_ASSETS:
        raw[asset], provenance[asset] = fetch_with_fallbacks(asset, plan[asset])

    aligned: dict[str, list[float]] = {}
    for asset in BASE_ASSETS:
        series = raw[asset]
        times = sorted(series)
        values: list[float] = []
        ages: list[int] = []
        for block in blocks:
            target = (block["timestamp"] // 60) * 60 - 60
            idx = bisect.bisect_right(times, target) - 1
            if idx < 0:
                raise RuntimeError(f"No causal price for {asset} before block {block['block_number']}")
            candle_ts = times[idx]
            age = target - candle_ts
            values.append(series[candle_ts])
            ages.append(age)
        if any(value <= 0 or not math.isfinite(value) for value in values):
            raise RuntimeError(f"Invalid aligned price for {asset}")
        max_age = max(ages)
        if max_age > 3600:
            raise RuntimeError(f"{asset} candle staleness too large: {max_age}s")
        aligned[asset] = values
        provenance[asset]["candle_rows"] = len(series)
        provenance[asset]["max_forward_fill_staleness_seconds"] = max_age
        provenance[asset]["alignment"] = "last fully completed 1-minute candle; causal forward-fill"
        provenance[asset]["price_role"] = (
            "redeemable_1_to_1_underlying"
            if asset in {"WETH", "cbBTC", "cbXRP"}
            else "direct_market_price"
        )
    return aligned, provenance


def rolling_volatility(prices: dict[str, list[float]], window: int = 8) -> list[dict[str, float]]:
    returns: dict[str, list[float]] = {asset: [] for asset in BASE_ASSETS}
    out: list[dict[str, float]] = []
    length = len(next(iter(prices.values())))
    for i in range(length):
        row: dict[str, float] = {}
        for asset in BASE_ASSETS:
            if i == 0:
                r = 0.0
            else:
                r = math.log(prices[asset][i] / prices[asset][i - 1])
            returns[asset].append(r)
            sample = returns[asset][-window:]
            row[asset] = statistics.pstdev(sample) if len(sample) >= 2 else 0.0
        out.append(row)
    return out


def price_ratios(prices: dict[str, list[float]], i: int) -> dict[str, D]:
    if i == 0:
        return {asset: D("1") for asset in BASE_ASSETS}
    return {
        asset: D(str(prices[asset][i] / prices[asset][i - 1]))
        for asset in BASE_ASSETS
    }


def run_path(
    blocks: list[dict],
    prices: dict[str, list[float]],
    *,
    anchor: float,
    bridge_volume_per_block: float,
    count: int | None = None,
    enable_rebalance: bool,
) -> dict:
    n = count if count is not None else len(blocks)
    cfg = replace(MultiMarketConfig(), hedge_anchor=D(str(anchor)))
    engine = MultiMarketHardNavEngine(cfg)
    vols = rolling_volatility(prices)
    navs = [float(engine.capital_adjusted_hardnav())]

    for i in range(n):
        engine.apply_external_market_move(price_ratios(prices, i))
        engine.record_external_bridge_flow(gross_volume=D(str(bridge_volume_per_block)))

        if enable_rebalance:
            base_fee_gwei = blocks[i]["base_fee_per_gas"] / 1e9
            engine.rebalance_external_risk(
                target_hedge_ratio=D(str(anchor)),
                target_bridge_share=cfg.bridge_asset_share,
                realized_volatility={
                    asset: D(str(vols[i][asset]))
                    for asset in BASE_ASSETS
                },
                eth_usd=D(str(prices["WETH"][i])),
                gas_gwei=D(str(base_fee_gwei)),
                no_trade_band=D("0.002"),
            )
        navs.append(float(engine.capital_adjusted_hardnav()))

    steps = np.diff(np.asarray(navs, dtype=np.float64))
    return {
        "navs": navs,
        "steps": steps,
        "snapshot": engine.snapshot(),
        "engine": engine,
    }


def select_train_anchor(
    blocks: list[dict],
    prices: dict[str, list[float]],
    bridge_volume_per_block: float,
) -> tuple[float, dict]:
    zero = run_path(
        blocks,
        prices,
        anchor=0.0,
        bridge_volume_per_block=bridge_volume_per_block,
        count=TRAIN_BLOCKS,
        enable_rebalance=False,
    )
    one = run_path(
        blocks,
        prices,
        anchor=1.0,
        bridge_volume_per_block=bridge_volume_per_block,
        count=TRAIN_BLOCKS,
        enable_rebalance=False,
    )
    a = zero["steps"]
    b = one["steps"] - zero["steps"]
    b_centered = b - b.mean()
    a_centered = a - a.mean()
    variance_b = float(np.mean(b_centered * b_centered))
    if variance_b <= 0:
        raise RuntimeError("TRAIN hedge coefficient is not identifiable")
    covariance = float(np.mean(a_centered * b_centered))
    raw = -covariance / variance_b
    selected = min(1.20, max(0.80, raw))
    return selected, {
        "method": "TRAIN-only analytic variance minimizer for affine HardNAV step process",
        "raw_anchor": raw,
        "clipped_range": [0.80, 1.20],
        "selected_anchor": selected,
        "oos_used_for_selection": False,
    }


def max_drawdown_pct(values: list[float]) -> float:
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, 1.0 - value / peak)
    return worst * 100.0


def json_snapshot(snapshot: dict) -> dict:
    def convert(value):
        if hasattr(value, "as_tuple"):
            return float(value)
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        return value

    return convert(snapshot)


def write_block_csv(blocks: list[dict], prices: dict[str, list[float]]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"ethereum_{START_BLOCK}_{END_BLOCK}_exact_gas_real_prices.csv"
    fields = [
        "block_number",
        "timestamp",
        "gas_used",
        "gas_limit",
        "base_fee_per_gas",
        "base_fee_gwei",
        *[f"{asset}_usd" for asset in BASE_ASSETS],
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i, block in enumerate(blocks):
            row = dict(block)
            row["base_fee_gwei"] = block["base_fee_per_gas"] / 1e9
            for asset in BASE_ASSETS:
                row[f"{asset}_usd"] = prices[asset][i]
            writer.writerow(row)
    return path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with V3_REPORT.open(encoding="utf-8") as handle:
        v3 = json.load(handle)
    modeled_bridge_volume = float(v3["external_sources"]["bridge_volume"])
    bridge_volume_per_block = modeled_bridge_volume / BLOCK_COUNT

    blocks, xatu_urls = fetch_xatu_blocks()
    prices, price_provenance = fetch_price_series(blocks)
    csv_path = write_block_csv(blocks, prices)

    anchor, anchor_evidence = select_train_anchor(
        blocks,
        prices,
        bridge_volume_per_block,
    )
    run = run_path(
        blocks,
        prices,
        anchor=anchor,
        bridge_volume_per_block=bridge_volume_per_block,
        enable_rebalance=True,
    )
    navs = run["navs"]
    steps = run["steps"]
    engine = run["engine"]

    train_end = navs[TRAIN_BLOCKS]
    oos_start = train_end
    oos_end = navs[-1]
    train_navs = navs[: TRAIN_BLOCKS + 1]
    oos_navs = navs[TRAIN_BLOCKS:]
    train_steps = steps[:TRAIN_BLOCKS]
    oos_steps = steps[TRAIN_BLOCKS:]

    base_fees = [row["base_fee_per_gas"] / 1e9 for row in blocks]
    gas_util = [row["gas_used"] / row["gas_limit"] for row in blocks]

    report = {
        "canonical_name": "CLOSED MULTI-MARKET HARDNAV V4",
        "classification": (
            "REAL HISTORICAL BLOCK-ALIGNED PRICES FOR ALL 10 MARKET LEGS + "
            "EXACT ETHEREUM PER-BLOCK BASE FEE/GAS USED; MODELED V5-CALIBRATED BRIDGE FLOW"
        ),
        "seed": SEED,
        "ethereum_blocks": {
            "start": START_BLOCK,
            "end": END_BLOCK,
            "count": len(blocks),
            "contiguous": True,
            "timestamp_start": blocks[0]["timestamp"],
            "timestamp_end": blocks[-1]["timestamp"],
            "datetime_start_utc": _iso(blocks[0]["timestamp"]),
            "datetime_end_utc": _iso(blocks[-1]["timestamp"]),
            "xatu_partitions": xatu_urls,
        },
        "protocol": {
            "start_hardnav": float(MultiMarketConfig().opening_hardnav),
            "train_blocks": TRAIN_BLOCKS,
            "oos_blocks": OOS_BLOCKS,
            "continuous_no_reset": True,
            "hedge_anchor_selected_on_train_only": anchor,
            "hedge_anchor_selection": anchor_evidence,
            "weights_frozen_after_train": True,
            "artificial_agent_external_income": 0.0,
        },
        "market_inputs": {
            "assets": list(BASE_ASSETS),
            "factor_mapped_assets": [],
            "price_granularity_seconds": 60,
            "block_alignment": "last fully completed candle only; causal forward-fill",
            "provenance": price_provenance,
            "csv": str(csv_path.relative_to(ROOT)),
        },
        "gas_input": {
            "source": "EthPandaOps Xatu canonical_execution_block public Parquet",
            "exact_fields": ["block_date_time", "gas_used", "gas_limit", "base_fee_per_gas"],
            "base_fee_gwei_min": min(base_fees),
            "base_fee_gwei_median": statistics.median(base_fees),
            "base_fee_gwei_max": max(base_fees),
            "gas_utilization_mean": statistics.fmean(gas_util),
            "gas_utilization_max": max(gas_util),
            "transaction_priority_tip": "not invented; hypothetical rebalance uses exact historical base fee only",\n            "strategy_gas_units": "MODELED_FROM_MULTIMARKET_CONFIG_PER_ACTIVE_LEG",\n            "strategy_gas_price": "EXACT_HISTORICAL_BASE_FEE_ONLY_NO_PRIORITY_TIP",\n            "strategy_gas_cost_classification": "HYBRID_EXACT_BASE_FEE_MODELED_GAS_UNITS",
        },
        "hardnav": {
            "start": navs[0],
            "train_end": train_end,
            "oos_start": oos_start,
            "oos_end": oos_end,
            "train_return_pct": (train_end / navs[0] - 1.0) * 100.0,
            "oos_return_pct": (oos_end / oos_start - 1.0) * 100.0,
            "full_return_pct": (oos_end / navs[0] - 1.0) * 100.0,
            "train_max_drawdown_pct": max_drawdown_pct(train_navs),
            "oos_max_drawdown_pct": max_drawdown_pct(oos_navs),
            "full_max_drawdown_pct": max_drawdown_pct(navs),
            "train_step_std": float(np.std(train_steps)),
            "oos_step_std": float(np.std(oos_steps)),
            "negative_step_fraction": float(np.mean(steps < 0)),
        },
        "external_sources": {
            "bridge_volume": modeled_bridge_volume,
            "bridge_volume_classification": "MODELED_V5_CALIBRATED_REFERENCE_UNCHANGED_FROM_V3",
            "bridge_and_swap_fee_revenue": float(engine.external_protocol_fee_revenue),
            "external_amm_fee_revenue": float(engine.external_amm_fee_revenue),
            "hedge_pnl": float(engine.hedge_pnl),
            "funding_cost": float(engine.funding_cost),
            "execution_cost": float(engine.execution_cost),
            "gas_cost": float(engine.gas_cost),
            "rebalance_batches": engine.rebalance_batches,
        },
        "closed_agent_economy": {
            **v3["closed_agent_economy"],
            "classification": "UNCHANGED_DETERMINISTIC_V3_INTERNAL_LAYER_NOT_ADDED_TO_HARDNAV",
        },
        "accounting": v3["accounting"],
        "final_snapshot": json_snapshot(run["snapshot"]),
        "comparison_to_v3": {
            "v3_full_return_pct": v3["hardnav"]["full_return_pct"],
            "v3_oos_return_pct": v3["hardnav"]["oos_return_pct"],
            "v3_full_max_drawdown_pct": v3["hardnav"]["full_max_drawdown_pct"],
            "v4_minus_v3_full_return_pct_points": (
                (oos_end / navs[0] - 1.0) * 100.0
                - v3["hardnav"]["full_return_pct"]
            ),
        },
        "status": "V4_REAL_MARKET_EXACT_BLOCK_FEE_ENVIRONMENT_GREEN_MODELED_BRIDGE_FLOW_REMAINS",
    }

    report_path = REPORT_DIR / "seed77_10000_train_3000_oos.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "classification": report["classification"],
                "ethereum_blocks": report["ethereum_blocks"],
                "market_inputs": report["market_inputs"],
                "gas_input": report["gas_input"],
                "protocol": report["protocol"],
                "report": str(report_path.relative_to(ROOT)),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    assert len(blocks) == BLOCK_COUNT
    assert len(steps) == BLOCK_COUNT
    assert len(prices) == len(BASE_ASSETS) == 10
    assert not report["market_inputs"]["factor_mapped_assets"]
    assert report["protocol"]["hedge_anchor_selection"]["oos_used_for_selection"] is False
    expected_fee = modeled_bridge_volume * float(
        MultiMarketConfig().bridge_fee_bps + MultiMarketConfig().swap_fee_bps
    ) / 10_000
    assert math.isclose(
        float(engine.external_protocol_fee_revenue),
        expected_fee,
        rel_tol=1e-10,
        abs_tol=1e-8,
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
