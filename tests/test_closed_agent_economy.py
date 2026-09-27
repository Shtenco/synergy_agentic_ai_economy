from decimal import Decimal

from agent_economy.closed_engine import ClosedAgentEconomy, ClosedEconomyConfig


def make_env(steps: int = 300, seed: int = 77) -> ClosedAgentEconomy:
    return ClosedAgentEconomy(
        ClosedEconomyConfig(
            agent_count=24,
            steps=steps,
            seed=seed,
            initial_cash=Decimal("30"),
        )
    )


def test_closed_economy_has_zero_external_money_flows():
    env = make_env(steps=500)
    report = env.run_closed()
    assert report.external_income == 0
    assert report.external_expense == 0
    assert report.conservation_gap == 0
    assert report.closing_system_cash == report.opening_capital


def test_closed_economy_creates_real_internal_jobs_and_useful_work():
    env = make_env(steps=300)
    report = env.run_closed()
    assert report.internal_jobs_completed > 0
    assert report.internal_gdp > 0
    assert report.verified_useful_work > 0
    assert report.productive_capital > 0
    assert report.verified_work_receipts > 0
    assert report.productive_assets > 0


def test_internal_finance_does_not_create_system_cash():
    env = make_env(steps=500)
    opening = env.ledger.system_cash()
    report = env.run_closed()
    assert report.loans_originated > 0
    assert report.deposits_opened > 0
    assert report.investments_opened > 0
    assert env.ledger.system_cash() == opening


def test_protocol_earns_internal_fees_without_creating_hardnav():
    env = make_env(steps=300)
    opening = env.ledger.system_cash()
    report = env.run_closed()
    assert report.protocol_treasury > 0
    assert report.founder_external_attributed_revenue == 0 if hasattr(report, "founder_external_attributed_revenue") else True
    assert report.closing_system_cash == opening


def test_transaction_metrics_are_nonzero_but_not_profit():
    env = make_env(steps=400)
    report = env.run_closed()
    assert report.gross_transaction_volume > 0
    assert report.syna_velocity > 0
    assert report.synr_velocity > 0
    assert report.hardnav == report.opening_capital
    assert report.inflation_rate == 0


def test_agent_wealth_distribution_is_reported():
    env = make_env(steps=300)
    report = env.run_closed()
    assert Decimal("0") <= report.agent_wealth_gini <= Decimal("1")
    assert report.min_agent_wealth <= report.median_agent_wealth <= report.max_agent_wealth
