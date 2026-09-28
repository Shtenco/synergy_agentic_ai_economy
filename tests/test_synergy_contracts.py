from decimal import Decimal
from agent_economy.models import ExecutionMandate
from agent_economy.synergy_contracts import CONTRACT_ID, economy_simulation_payload

def test_agent_economy_payload_has_no_payment_authority():
    p=economy_simulation_payload(
        run_id="run-1",tick=10,active_agents=5,
        external_assets=Decimal("100"),internal_assets=Decimal("250"),
        external_revenue=Decimal("12"),
        mandate=ExecutionMandate(mode="simulation")
    )
    assert CONTRACT_ID=="synergy.agent.economy-simulation/v1"
    assert p["simulation_only"] is True
    assert p["payment_authority"] is False
    assert p["accounting_authority"] is False
