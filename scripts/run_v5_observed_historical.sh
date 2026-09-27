#!/usr/bin/env bash
set -euo pipefail

: "${SYNERGY_V4_CSV:=data/real_backtest_v4/ethereum_23544921_23557920_exact_gas_real_prices.csv}"
export SYNERGY_V4_CSV

python3 experiments/build_observed_external_flow_v5.py
python3 experiments/closed_multimarket_hardnav_v5.py

python3 - <<'PY'
import csv, json
from pathlib import Path

root=Path(".")
flow_csv=root/"data/real_external_flow_v5/observed_flow_by_eth_block.csv"
flow_manifest=root/"data/real_external_flow_v5/manifest.json"
report_path=root/"reports/closed_multimarket_hardnav_v5/seed77_10000_train_3000_oos.json"

for p in (flow_csv,flow_manifest,report_path):
    if not p.is_file():
        raise SystemExit(f"MISSING V5 ARTIFACT: {p}")

with flow_csv.open(newline="",encoding="utf-8") as f:
    rows=list(csv.DictReader(f))
if len(rows)!=13000:
    raise SystemExit(f"BAD V5 FLOW ROW COUNT: {len(rows)}")
nums=[int(r["block_number"]) for r in rows]
if nums[0]!=23544921 or nums[-1]!=23557920:
    raise SystemExit("BAD V5 BLOCK ENDPOINTS")
if any(b!=a+1 for a,b in zip(nums,nums[1:])):
    raise SystemExit("NON-CONTIGUOUS V5 BLOCKS")

m=json.loads(flow_manifest.read_text(encoding="utf-8"))
if m.get("classification")!="BASE_OBSERVED_EXTERNAL_FLOW_LOWER_BOUND":
    raise SystemExit("BAD V5 CLASSIFICATION")
if m.get("rows")!=13000:
    raise SystemExit("BAD V5 MANIFEST ROW COUNT")
if m.get("observed_external_volume_usd",0)<=0:
    raise SystemExit("ZERO OBSERVED V5 FLOW")
if m.get("coverage_claim")!="LOWER_BOUND_ONLY; NOT FULL_MARKET_COVERAGE":
    raise SystemExit("MISSING LOWER-BOUND COVERAGE CLAIM")
coverage=float(m.get("aerodrome_scan_coverage_fraction",0))
if not (0 < coverage <= 1):
    raise SystemExit(f"INVALID AERODROME COVERAGE: {coverage}")
raw=m.get("raw_evidence",{})
if raw.get("provenance",{}).get("no_synthetic_prices") is not True:
    raise SystemExit("RAW V5 EVIDENCE DOES NOT PROVE NO SYNTHETIC PRICES")

r=json.loads(report_path.read_text(encoding="utf-8"))
p=r["protocol"]
if p["train_blocks"]!=10000 or p["oos_blocks"]!=3000:
    raise SystemExit("BAD V5 TRAIN/OOS COUNTS")
if p["continuous_no_reset"] is not True:
    raise SystemExit("V5 RESET DETECTED")
if p["hedge_anchor_selection"]["oos_used_for_selection"] is not False:
    raise SystemExit("V5 OOS LEAKAGE")
obs=r["observed_external_flow"]
if obs["classification"]!="OBSERVED_EXTERNAL_FLOW_LOWER_BOUND":
    raise SystemExit("V5 REPORT OVERCLAIMS COVERAGE")
if obs["fee_capture_classification"]!="COUNTERFACTUAL_SYNERGY_FEE_CAPTURE_NOT_HISTORICALLY_EARNED":
    raise SystemExit("V5 FEE CAPTURE MISCLASSIFIED")
if abs(float(obs["aerodrome_scan_coverage_fraction"])-coverage)>1e-12:
    raise SystemExit("V5 COVERAGE MISMATCH")

print("V5 OBSERVED LOWER-BOUND EVIDENCE GATES: PASS")
print(json.dumps({
    "anchor":p["hedge_anchor_selected_on_train_only"],
    "bridge_volume_usd":obs["bridge_volume_usd"],
    "dex_swap_volume_usd":obs["dex_swap_volume_usd"],
    "observed_total_usd":obs["total_usd"],
    "aerodrome_scan_coverage_fraction":coverage,
    "aerodrome_failed_pool_scans":obs["aerodrome_failed_pool_scans"],
    "full_return_pct":r["hardnav"]["full_return_pct"],
    "oos_return_pct":r["hardnav"]["oos_return_pct"],
    "full_max_drawdown_pct":r["hardnav"]["full_max_drawdown_pct"],
    "negative_step_fraction":r["hardnav"]["negative_step_fraction"],
    "counterfactual_fee_revenue":r["external_sources"]["bridge_and_swap_fee_revenue"],
},indent=2))
PY
