from __future__ import annotations

import bisect
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V4_CSV = ROOT / "data" / "real_backtest_v4" / "ethereum_23544921_23557920_exact_gas_real_prices.csv"
RAW_DIR = ROOT / "data" / "real_external_flow_v5" / "raw"
OUT_DIR = ROOT / "data" / "real_external_flow_v5"
OUT_CSV = OUT_DIR / "observed_flow_by_eth_block.csv"
MANIFEST = OUT_DIR / "manifest.json"

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913".lower()
WETH = "0x4200000000000000000000000000000000000006".lower()
AERO = "0x940181a94A35A4569E4529A3CDfB74e38FD98631".lower()
TOKEN_INFO = {
    USDC: ("USDC", 6),
    WETH: ("WETH", 18),
    AERO: ("AERO", 18),
}

DEPOSIT_EVENTS = {"FundsDeposited", "V3FundsDeposited"}


def load_v4():
    with V4_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 13_000:
        raise RuntimeError(f"expected 13,000 V4 rows, got {len(rows)}")
    ts = [int(r["timestamp"]) for r in rows]
    if any(b < a for a, b in zip(ts, ts[1:])):
        raise RuntimeError("V4 timestamps not monotonic")
    return rows, ts


def map_event_index(event_ts: int, v4_ts: list[int]) -> int | None:
    i = bisect.bisect_right(v4_ts, event_ts) - 1
    if i < 0 or i >= len(v4_ts):
        return None
    return i


def usd_price(symbol: str, v4_row: dict) -> float:
    if symbol == "USDC":
        return 1.0
    if symbol == "WETH":
        return float(v4_row["WETH_usd"])
    if symbol == "AERO":
        return float(v4_row["AERO_usd"])
    raise KeyError(symbol)


def normalize_address(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return value.lower()


def build():
    v4, v4_ts = load_v4()
    acc = [
        {
            "bridge_usd": 0.0,
            "dex_usd": 0.0,
            "bridge_events": 0,
            "dex_events": 0,
            "unresolved_events": 0,
        }
        for _ in v4
    ]

    across_path = RAW_DIR / "across_events.csv"
    aero_path = RAW_DIR / "aerodrome_swaps.csv"
    raw_manifest_path = RAW_DIR / "manifest.json"
    if not across_path.is_file() or not aero_path.is_file() or not raw_manifest_path.is_file():
        raise RuntimeError("raw V5 artifact is incomplete")

    raw_manifest = json.loads(raw_manifest_path.read_text(encoding="utf-8"))

    stats = defaultdict(int)
    bridge_usd = 0.0
    dex_usd = 0.0

    with across_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            stats["across_raw_rows"] += 1
            corridor = str(r.get("selected_eth_base_corridor", "")).strip().lower()
            if corridor not in {"true", "1", "yes"}:
                stats["across_non_eth_base_corridor_not_counted"] += 1
                continue
            if r["event"] not in DEPOSIT_EVENTS:
                stats["across_non_deposit_rows_not_counted"] += 1
                continue
            i = map_event_index(int(r["timestamp"]), v4_ts)
            if i is None:
                stats["out_of_window"] += 1
                continue
            token = normalize_address(r.get("input_token", ""))
            info = TOKEN_INFO.get(token)
            amount_raw = r.get("input_amount", "")
            if not info or not amount_raw:
                acc[i]["unresolved_events"] += 1
                stats["across_unresolved"] += 1
                continue
            symbol, decimals = info
            amount = int(amount_raw) / (10 ** decimals)
            value = amount * usd_price(symbol, v4[i])
            bridge_usd += value
            acc[i]["bridge_usd"] += value
            acc[i]["bridge_events"] += 1
            stats[f"across_priced_{symbol}"] += 1

    with aero_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            stats["aerodrome_raw_rows"] += 1
            i = map_event_index(int(r["timestamp"]), v4_ts)
            if i is None:
                stats["out_of_window"] += 1
                continue
            t0 = normalize_address(r["token0"])
            t1 = normalize_address(r["token1"])
            a0in = int(r["amount0_in"])
            a1in = int(r["amount1_in"])

            # Strict lower-bound rule: value the input side only.  If the input
            # token itself is not in the proven price set, do not infer value
            # from the output side.
            candidates = []
            if a0in > 0 and t0 in TOKEN_INFO:
                symbol, decimals = TOKEN_INFO[t0]
                candidates.append((symbol, a0in / (10 ** decimals)))
            if a1in > 0 and t1 in TOKEN_INFO:
                symbol, decimals = TOKEN_INFO[t1]
                candidates.append((symbol, a1in / (10 ** decimals)))

            if len(candidates) != 1:
                acc[i]["unresolved_events"] += 1
                stats["aerodrome_unresolved"] += 1
                continue

            symbol, amount = candidates[0]
            value = amount * usd_price(symbol, v4[i])
            dex_usd += value
            acc[i]["dex_usd"] += value
            acc[i]["dex_events"] += 1
            stats[f"aerodrome_priced_{symbol}"] += 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "block_number",
        "timestamp",
        "observed_bridge_volume_usd",
        "observed_dex_swap_volume_usd",
        "observed_external_volume_usd",
        "bridge_events",
        "dex_events",
        "unresolved_events",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r, a in zip(v4, acc):
            w.writerow({
                "block_number": r["block_number"],
                "timestamp": r["timestamp"],
                "observed_bridge_volume_usd": f"{a['bridge_usd']:.12f}",
                "observed_dex_swap_volume_usd": f"{a['dex_usd']:.12f}",
                "observed_external_volume_usd": f"{a['bridge_usd'] + a['dex_usd']:.12f}",
                "bridge_events": a["bridge_events"],
                "dex_events": a["dex_events"],
                "unresolved_events": a["unresolved_events"],
            })

    total = bridge_usd + dex_usd
    manifest = {
        "classification": "BASE_OBSERVED_EXTERNAL_FLOW_LOWER_BOUND",
        "raw_evidence": raw_manifest,
        "pricing": {
            "USDC": "1 USD reference",
            "WETH": "causal V4 WETH block-aligned price",
            "AERO": "causal V4 AERO block-aligned price",
            "unknown_tokens": "unresolved; never assigned synthetic price",
            "aerodrome_rule": "input side only; output side never substituted for an unpriced input",
            "across_rule": "deposit events only; relay fills preserved in raw evidence but excluded from volume to prevent double counting",
        },
        "observed_bridge_volume_usd": bridge_usd,
        "observed_dex_swap_volume_usd": dex_usd,
        "observed_external_volume_usd": total,
        "nonzero_eth_blocks": sum((a["bridge_usd"] + a["dex_usd"]) > 0 for a in acc),
        "stats": dict(stats),
        "rows": len(v4),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if len(v4) != 13_000:
        raise RuntimeError("bad aggregation row count")
    if total <= 0:
        raise RuntimeError("observed external volume is zero")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    build()
