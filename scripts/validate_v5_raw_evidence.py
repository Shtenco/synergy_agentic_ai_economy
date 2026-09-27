from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

START_TS = 1760070203
END_TS = 1760227199
TX_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "raw_dir",
        nargs="?",
        default="data/real_external_flow_v5/raw",
    )
    args = ap.parse_args()
    root = Path(args.raw_dir)

    required = {
        "across": root / "across_events.csv",
        "swaps": root / "aerodrome_swaps.csv",
        "pools": root / "aerodrome_pools.csv",
        "manifest": root / "manifest.json",
    }
    for name, path in required.items():
        if not path.is_file():
            raise SystemExit(f"MISSING V5 RAW FILE [{name}]: {path}")

    manifest = json.loads(required["manifest"].read_text(encoding="utf-8"))
    across = read_rows(required["across"])
    swaps = read_rows(required["swaps"])
    pools = read_rows(required["pools"])

    if not across:
        raise SystemExit("V5 RAW FAIL: zero Across rows")
    if not swaps:
        raise SystemExit("V5 RAW FAIL: zero Aerodrome swap rows")
    if not pools:
        raise SystemExit("V5 RAW FAIL: zero Aerodrome pools")

    pool_addresses = {r["pool"].lower() for r in pools}
    selected_corridor = 0
    across_tx = set()
    for r in across:
        tx = r["tx_hash"]
        if not TX_RE.match(tx):
            raise SystemExit(f"V5 RAW FAIL: invalid Across tx hash {tx!r}")
        across_tx.add(tx.lower())

        ts = int(r["timestamp"])
        if not START_TS <= ts <= END_TS:
            raise SystemExit(f"V5 RAW FAIL: Across timestamp outside replay window: {ts}")

        if str(r.get("selected_eth_base_corridor", "")).strip().lower() in {"true", "1", "yes"}:
            selected_corridor += 1

        if int(r["input_amount"]) < 0 or int(r["output_amount"]) < 0:
            raise SystemExit("V5 RAW FAIL: negative Across amount")

    if selected_corridor <= 0:
        raise SystemExit("V5 RAW FAIL: zero Ethereum<->Base Across deposits")

    seen_swap_keys = set()
    for r in swaps:
        tx = r["tx_hash"]
        if not TX_RE.match(tx):
            raise SystemExit(f"V5 RAW FAIL: invalid Aerodrome tx hash {tx!r}")
        key = (tx.lower(), int(r["log_index"]))
        if key in seen_swap_keys:
            raise SystemExit(f"V5 RAW FAIL: duplicate Aerodrome log {key}")
        seen_swap_keys.add(key)

        ts = int(r["timestamp"])
        if not START_TS <= ts <= END_TS:
            raise SystemExit(f"V5 RAW FAIL: swap timestamp outside replay window: {ts}")

        if r["pool"].lower() not in pool_addresses:
            raise SystemExit(f"V5 RAW FAIL: swap references unknown pool {r['pool']}")

        for field in ("amount0_in", "amount1_in", "amount0_out", "amount1_out"):
            if int(r[field]) < 0:
                raise SystemExit(f"V5 RAW FAIL: negative {field}")

    if manifest.get("provenance", {}).get("no_synthetic_prices") is not True:
        raise SystemExit("V5 RAW FAIL: collector does not attest no_synthetic_prices=true")

    print("V5 RAW EVIDENCE GATES: PASS")
    print(json.dumps({
        "across_rows": len(across),
        "eth_base_corridor_deposits": selected_corridor,
        "unique_across_transactions": len(across_tx),
        "aerodrome_pools": len(pools),
        "aerodrome_swaps": len(swaps),
        "unique_aerodrome_logs": len(seen_swap_keys),
        "window": [START_TS, END_TS],
    }, indent=2))


if __name__ == "__main__":
    main()
