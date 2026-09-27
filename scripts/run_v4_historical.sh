#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade pip
python3 -m pip install numpy pyarrow requests

python3 experiments/closed_multimarket_hardnav_v4.py

python3 - <<'PY'
import csv
import json
from pathlib import Path

root = Path(".")
csv_path = root / "data/real_backtest_v4/ethereum_23544921_23557920_exact_gas_real_prices.csv"
manifest_path = root / "data/real_backtest_v4/manifest.json"
report_path = root / "reports/closed_multimarket_hardnav_v4/seed77_10000_train_3000_oos.json"

for path in (csv_path, manifest_path, report_path):
    if not path.is_file():
        raise SystemExit(f"MISSING ARTIFACT: {path}")

with csv_path.open(newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

if len(rows) != 13000:
    raise SystemExit(f"BAD BLOCK COUNT: {len(rows)}")
nums = [int(r["block_number"]) for r in rows]
if nums[0] != 23544921 or nums[-1] != 23557920:
    raise SystemExit("BAD BLOCK ENDPOINTS")
if any(b != a + 1 for a, b in zip(nums, nums[1:])):
    raise SystemExit("NON-CONTIGUOUS BLOCKS")

report = json.loads(report_path.read_text(encoding="utf-8"))
if report["protocol"]["train_blocks"] != 10000:
    raise SystemExit("BAD TRAIN COUNT")
if report["protocol"]["oos_blocks"] != 3000:
    raise SystemExit("BAD OOS COUNT")
if report["protocol"]["continuous_no_reset"] is not True:
    raise SystemExit("RESET DETECTED")
if report["protocol"]["hedge_anchor_selection"]["oos_used_for_selection"] is not False:
    raise SystemExit("OOS LEAKAGE INTO HEDGE SELECTION")
if report["market_inputs"]["factor_mapped_assets"] != []:
    raise SystemExit("FACTOR-MAPPED ASSETS REMAIN")

provenance = report["market_inputs"]["provenance"]
if len(provenance) != 10:
    raise SystemExit(f"BAD PROVENANCE COUNT: {len(provenance)}")
for asset, src in provenance.items():
    if src.get("future_candle_violations") != 0:
        raise SystemExit(f"LOOKAHEAD DETECTED: {asset}")
    if src.get("min_alignment_age_seconds", -1) < 0:
        raise SystemExit(f"NEGATIVE ALIGNMENT AGE: {asset}")

print("V4 EVIDENCE GATES: PASS")
print(json.dumps({
    "status": report["status"],
    "anchor": report["protocol"]["hedge_anchor_selected_on_train_only"],
    "full_return_pct": report["hardnav"]["full_return_pct"],
    "oos_return_pct": report["hardnav"]["oos_return_pct"],
    "full_max_drawdown_pct": report["hardnav"]["full_max_drawdown_pct"],
    "negative_step_fraction": report["hardnav"]["negative_step_fraction"],
    "gas_cost": report["external_sources"]["gas_cost"],
    "rebalance_batches": report["external_sources"]["rebalance_batches"],
}, indent=2))
PY
