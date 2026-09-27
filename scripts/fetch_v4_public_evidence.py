from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

PUBLIC_REPO_COMMIT = "bdeaf4106909aefc9e2f982a515ff8c716cc4c2d"
EXPECTED_SHA256 = "6eb4ea7d3c6fadeebc2349e3a3f530bf1f4b50eb4c375127b41cd3e6ada8be0e"
URL = (
    "https://raw.githubusercontent.com/Shtenco/synergychain.github.io/"
    + PUBLIC_REPO_COMMIT
    + "/evidence/v4/ethereum_23544921_23557920_exact_gas_real_prices.csv"
)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "real_backtest_v4" / "ethereum_23544921_23557920_exact_gas_real_prices.csv"

def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = urllib.request.urlopen(URL, timeout=120).read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"V4 evidence checksum mismatch: {digest}")
    OUT.write_bytes(data)
    print(f"V4 evidence restored: {OUT} sha256={digest}")

if __name__ == "__main__":
    main()
