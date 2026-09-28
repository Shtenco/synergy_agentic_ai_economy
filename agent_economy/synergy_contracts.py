from __future__ import annotations
from decimal import Decimal
from typing import Any

from .models import ExecutionMandate

CONTRACT_ID = "synergy.agent.economy-simulation/v1"
AUTHORITY = "agent_economy_simulation"


def economy_simulation_payload(
    *,
    run_id: str,
    tick: int,
    active_agents: int,
    external_assets: Decimal | str,
    internal_assets: Decimal | str,
    external_revenue: Decimal | str,
    mandate: ExecutionMandate,
) -> dict[str, Any]:
    if not run_id.strip() or tick < 0 or active_agents < 0:
        raise ValueError("invalid simulation identity")
    values = [Decimal(str(external_assets)), Decimal(str(internal_assets)), Decimal(str(external_revenue))]
    if any(v < 0 for v in values):
        raise ValueError("simulation values cannot be negative")
    return {
        "run_id": run_id,
        "tick": int(tick),
        "active_agents": int(active_agents),
        "external_assets": str(values[0]),
        "internal_assets": str(values[1]),
        "external_revenue": str(values[2]),
        "mandate_mode": mandate.mode,
        "per_transaction_limit": str(mandate.per_transaction_limit),
        "daily_limit": str(mandate.daily_limit),
        "allowed_actions": sorted(mandate.allowed_actions),
        "simulation_only": mandate.mode != "live",
        "payment_authority": False,
        "accounting_authority": False,
    }
