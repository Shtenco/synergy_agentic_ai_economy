from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from .endogenous import EndogenousDemandEngine, gini, transaction_velocity
from .engine import AgentEconomy, EconomyConfig
from .ledger import InsufficientFunds


@dataclass(frozen=True)
class ClosedEconomyReport:
    steps: int
    agent_count: int
    opening_capital: Decimal
    closing_system_cash: Decimal
    hardnav: Decimal
    external_income: Decimal
    external_expense: Decimal
    conservation_gap: Decimal
    internal_gdp: Decimal
    productive_capital: Decimal
    gross_transaction_volume: Decimal
    credit_outstanding: Decimal
    protocol_treasury: Decimal
    syna_velocity: Decimal
    synr_velocity: Decimal
    loan_defaults: int
    deposit_defaults: int
    insurer_defaults: int
    bankruptcies: int
    verified_useful_work: Decimal
    verified_work_receipts: int
    productive_assets: int
    agent_wealth_gini: Decimal
    min_agent_wealth: Decimal
    median_agent_wealth: Decimal
    max_agent_wealth: Decimal
    internal_jobs_completed: int
    companies_formed: int
    loans_originated: int
    deposits_opened: int
    investments_opened: int
    insurance_policies: int
    inflation_rate: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        def cv(value: Any) -> Any:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, dict):
                return {k: cv(v) for k, v in value.items()}
            if isinstance(value, (tuple, list)):
                return [cv(v) for v in value]
            return value
        return cv(asdict(self))


@dataclass(frozen=True)
class ClosedEconomyConfig(EconomyConfig):
    economic_mode: str = "closed"
    endogenous_job_every: int = 2
    company_demand_every: int = 5

    def __post_init__(self) -> None:
        # Preserve validation from the legacy config while keeping the legacy
        # cadence fields present for serialization/backward compatibility.
        super().__post_init__()
        if self.economic_mode != "closed":
            raise ValueError("ClosedEconomyConfig requires economic_mode='closed'")
        if self.endogenous_job_every <= 0 or self.company_demand_every <= 0:
            raise ValueError("endogenous demand intervals must be positive")


class ClosedAgentEconomy(AgentEconomy):
    """Autonomous closed agent economy.

    No method in the run loop calls Ledger.external_inflow/outflow.  External
    market assets may be integrated by a higher layer for HardNAV pricing, but
    jobs, company service revenue, credit losses and all settlements remain
    inside the system ledger.
    """

    def __init__(self, config: ClosedEconomyConfig | None = None) -> None:
        cfg = config or ClosedEconomyConfig()
        super().__init__(cfg)
        self.config = cfg
        self.endogenous = EndogenousDemandEngine(
            self.ledger,
            self.labor,
            self.capital,
            self.agents,
            rng=self.rng,
            founder_account="founder:treasury",
        )

    def _originate_closed_credit(self, tick: int) -> None:
        ranked = sorted(self.agents.values(), key=lambda a: self.ledger.balance(a.agent_id))
        borrower = next((a for a in ranked if a.active), None)
        lender = next((a for a in reversed(ranked) if a.active and a is not borrower), None)
        if borrower is None or lender is None:
            return
        lender_cash = self.ledger.balance(lender.agent_id)
        principal = min(Decimal("5"), lender_cash * Decimal("0.10"))
        if principal < Decimal("0.75"):
            return
        try:
            self.credit.originate_loan(
                lender,
                borrower,
                principal=principal,
                term_ticks=5,
                collateral_ratio=Decimal("0.20"),
                tick=tick,
            )
        except InsufficientFunds:
            return
        # Crucially: no external_business_loss.  Any future loss must arise
        # from internal insolvency/default or a separately accounted HardNAV
        # market layer.

    def _assign_company_employees(self) -> None:
        for company in self.capital.companies.values():
            if len(company.employee_ids) >= 3:
                continue
            candidates = sorted(
                (
                    agent
                    for agent in self.agents.values()
                    if agent.active and agent.agent_id != company.founder_agent_id
                ),
                key=lambda a: (a.skill(company.specialty), a.reputation),
                reverse=True,
            )
            for agent in candidates:
                if len(company.employee_ids) >= 3:
                    break
                company.employee_ids.add(agent.agent_id)
                if agent.employer_id is None:
                    agent.employer_id = company.company_id

    def step_closed(self, tick: int) -> dict[str, object]:
        self.ledger.set_tick(tick)
        self._settle_maturities(tick)
        self._settle_insurance(tick)

        receipt = None
        if tick % self.config.endogenous_job_every == 0:
            receipt = self.endogenous.execute_agent_demand(tick)
            if receipt and tick % self.config.subcontract_every == 0:
                self.endogenous.execute_subcontract(receipt, tick)

        if tick % self.config.company_demand_every == 0:
            self.endogenous.execute_company_demand(tick)

        if tick % self.config.credit_every == 0:
            self._originate_closed_credit(tick)
        if tick % self.config.insurance_every == 0:
            self._buy_credit_insurance(tick)
        if tick % self.config.deposit_every == 0:
            self._open_deposit(tick)
        if tick % self.config.investment_every == 0:
            self._open_investment(tick)
        if tick % self.config.policy_research_every == 0:
            self._run_policy_research(tick)
        self._distribute_company_returns(tick)
        self._assign_company_employees()
        if tick % self.config.evolution_every == 0:
            self._adapt_and_check_bankruptcy(tick)

        return self.snapshot_closed()

    def _credit_outstanding(self) -> Decimal:
        return sum(
            (loan.amount_due() for loan in self.credit.active_loans()),
            Decimal("0"),
        )

    def snapshot_closed(self) -> dict[str, object]:
        opening = self.ledger.opening_capital()
        gtv, syna_velocity, synr_velocity = transaction_velocity(
            self.ledger,
            opening_capital=opening,
        )
        net_worth = self._agent_net_worth()
        wealths = sorted(net_worth.values())
        if wealths:
            mid = len(wealths) // 2
            if len(wealths) % 2:
                median = wealths[mid]
            else:
                median = (wealths[mid - 1] + wealths[mid]) / Decimal("2")
            min_wealth = wealths[0]
            max_wealth = wealths[-1]
        else:
            median = min_wealth = max_wealth = Decimal("0")
        endo = self.endogenous.snapshot()
        return {
            "hardnav": self.ledger.system_cash(),
            "internal_gdp": endo["internal_gdp"],
            "productive_capital": endo["productive_capital"],
            "gross_transaction_volume": gtv,
            "credit_outstanding": self._credit_outstanding(),
            "protocol_treasury": self.ledger.balance("founder:treasury"),
            "syna_velocity": syna_velocity,
            "synr_velocity": synr_velocity,
            "loan_defaults": sum(1 for l in self.credit.loans.values() if l.status == "defaulted"),
            "deposit_defaults": sum(1 for d in self.credit.deposits.values() if d.status == "defaulted"),
            "insurer_defaults": sum(1 for p in self.insurance.policies.values() if p.status == "insurer_default"),
            "bankruptcies": len(self.bankruptcy.cases),
            "verified_useful_work": endo["verified_useful_work"],
            "verified_work_receipts": endo["verified_work_receipts"],
            "productive_assets": endo["productive_assets"],
            "agent_wealth_gini": gini(list(net_worth.values())),
            "min_agent_wealth": min_wealth,
            "median_agent_wealth": median,
            "max_agent_wealth": max_wealth,
            "external_income": self.ledger.external_income(),
            "external_expense": self.ledger.external_expense(),
            "conservation_gap": self.ledger.conservation_gap(),
            "system_cash": self.ledger.system_cash(),
        }

    def run_closed(self) -> ClosedEconomyReport:
        for tick in range(1, self.config.steps + 1):
            self.step_closed(tick)

        snap = self.snapshot_closed()
        return ClosedEconomyReport(
            steps=self.config.steps,
            agent_count=self.config.agent_count,
            opening_capital=self.ledger.opening_capital(),
            closing_system_cash=snap["system_cash"],
            hardnav=snap["hardnav"],
            external_income=snap["external_income"],
            external_expense=snap["external_expense"],
            conservation_gap=snap["conservation_gap"],
            internal_gdp=snap["internal_gdp"],
            productive_capital=snap["productive_capital"],
            gross_transaction_volume=snap["gross_transaction_volume"],
            credit_outstanding=snap["credit_outstanding"],
            protocol_treasury=snap["protocol_treasury"],
            syna_velocity=snap["syna_velocity"],
            synr_velocity=snap["synr_velocity"],
            loan_defaults=snap["loan_defaults"],
            deposit_defaults=snap["deposit_defaults"],
            insurer_defaults=snap["insurer_defaults"],
            bankruptcies=snap["bankruptcies"],
            verified_useful_work=snap["verified_useful_work"],
            verified_work_receipts=snap["verified_work_receipts"],
            productive_assets=snap["productive_assets"],
            agent_wealth_gini=snap["agent_wealth_gini"],
            min_agent_wealth=snap["min_agent_wealth"],
            median_agent_wealth=snap["median_agent_wealth"],
            max_agent_wealth=snap["max_agent_wealth"],
            internal_jobs_completed=sum(
                1
                for job in self.labor.jobs.values()
                if job.funding_source == "internal" and job.status == "completed"
            ),
            companies_formed=len(self.capital.companies),
            loans_originated=len(self.credit.loans),
            deposits_opened=len(self.credit.deposits),
            investments_opened=len(self.capital.investments),
            insurance_policies=len(self.insurance.policies),
            inflation_rate=Decimal("0"),
        )
