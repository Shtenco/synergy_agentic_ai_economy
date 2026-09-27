from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
import random
from typing import Mapping

from .capital import CapitalMarket
from .labor import LaborMarket
from .ledger import InsufficientFunds, Ledger
from .models import AgentState, Company


@dataclass(frozen=True)
class VerifiedWorkReceipt:
    receipt_id: str
    job_id: str
    buyer_id: str
    worker_id: str
    capability: str
    tick: int
    gross_value: Decimal
    quality: float
    useful_work_units: Decimal
    productive_capital_added: Decimal
    verified: bool = True


@dataclass
class ProductiveAsset:
    asset_id: str
    owner_id: str
    creator_id: str
    capability: str
    created_tick: int
    quality: float
    acquisition_cost: Decimal
    productive_value: Decimal


class EndogenousDemandEngine:
    """Closed-economy demand and useful-work accounting.

    All payments are ordinary internal Ledger transfers.  Internal GDP,
    productive capital and useful work are reporting dimensions only and never
    create cash, HardNAV or external income.
    """

    PROFESSION_NEEDS: Mapping[str, tuple[str, ...]] = {
        "researcher": ("data", "coding", "ops"),
        "builder": ("research", "data", "risk"),
        "lender": ("risk", "data", "economics"),
        "operator": ("coding", "research", "finance"),
        "analyst": ("data", "research", "coding"),
        "banker": ("risk", "finance", "data"),
    }

    PRODUCTIVITY_MULTIPLIER: Mapping[str, Decimal] = {
        "coding": Decimal("1.20"),
        "research": Decimal("1.15"),
        "data": Decimal("1.10"),
        "ops": Decimal("1.00"),
        "finance": Decimal("1.05"),
        "economics": Decimal("1.05"),
        "risk": Decimal("1.10"),
    }

    def __init__(
        self,
        ledger: Ledger,
        labor: LaborMarket,
        capital: CapitalMarket,
        agents: dict[str, AgentState],
        *,
        rng: random.Random,
        founder_account: str = "founder:treasury",
        productive_decay_per_tick: Decimal = Decimal("0.9998"),
        company_service_share: Decimal = Decimal("0.20"),
    ) -> None:
        self.ledger = ledger
        self.labor = labor
        self.capital = capital
        self.agents = agents
        self.rng = rng
        self.founder_account = founder_account
        self.productive_decay_per_tick = Decimal(productive_decay_per_tick)
        self.company_service_share = Decimal(company_service_share)
        self.receipts: list[VerifiedWorkReceipt] = []
        self.assets: dict[str, ProductiveAsset] = {}
        self.internal_gdp = Decimal("0")
        self.verified_useful_work = Decimal("0")
        self._next_receipt = 1
        self._next_asset = 1
        self._last_decay_tick = 0

    def _decay(self, tick: int) -> None:
        delta = max(0, int(tick) - self._last_decay_tick)
        if delta == 0 or not self.assets:
            self._last_decay_tick = int(tick)
            return
        factor = self.productive_decay_per_tick ** delta
        for asset in self.assets.values():
            asset.productive_value *= factor
        self._last_decay_tick = int(tick)

    @property
    def productive_capital(self) -> Decimal:
        return sum((asset.productive_value for asset in self.assets.values()), Decimal("0"))

    def _agent_budget(self, buyer: AgentState) -> Decimal:
        cash = self.ledger.balance(buyer.agent_id)
        if cash <= Decimal("0.50"):
            return Decimal("0")
        appetite = Decimal(str(buyer.strategy.hiring_appetite if buyer.strategy else buyer.genome.entrepreneurship))
        budget = cash * (Decimal("0.0125") + Decimal("0.0125") * appetite)
        return min(Decimal("3"), max(Decimal("0.35"), budget))

    def _company_budget(self, company: Company) -> Decimal:
        cash = self.ledger.balance(company.treasury_account)
        if cash <= Decimal("0.75"):
            return Decimal("0")
        return min(Decimal("4"), max(Decimal("0.50"), cash * Decimal("0.04")))

    def _need_for_agent(self, buyer: AgentState, tick: int) -> str:
        needs = self.PROFESSION_NEEDS.get(buyer.profession, ("research", "data", "coding"))
        return needs[(tick + int(buyer.agent_id.split(":")[-1])) % len(needs)]

    def _need_for_company(self, company: Company, tick: int) -> str:
        sequence = (company.specialty, "ops", "risk", "data", "research", "coding")
        return sequence[(tick + int(company.company_id.split(":")[-1])) % len(sequence)]

    def _eligible_workers(self, buyer_id: str, capability: str, min_skill: float) -> list[AgentState]:
        return [
            agent
            for agent in self.agents.values()
            if agent.active
            and agent.agent_id != buyer_id
            and agent.skill(capability) >= min_skill
        ]

    def _execute_internal_job(
        self,
        *,
        buyer_id: str,
        capability: str,
        budget: Decimal,
        tick: int,
        title: str,
        parent_job_id: str | None = None,
    ) -> VerifiedWorkReceipt | None:
        if budget <= 0:
            return None
        min_skill = 0.20
        workers = self._eligible_workers(buyer_id, capability, min_skill)
        if not workers:
            return None
        try:
            job = self.labor.post_internal_job(
                client_id=buyer_id,
                title=title,
                skill=capability,
                budget=budget,
                min_skill=min_skill,
                tick=tick,
                parent_job_id=parent_job_id,
            )
        except InsufficientFunds:
            return None

        for worker in workers:
            skill = worker.skill(capability)
            discount = Decimal(str(round(0.10 + 0.10 * skill, 6)))
            price = max(Decimal("0.10"), budget * (Decimal("1") - discount))
            try:
                self.labor.submit_bid(job.job_id, worker, price=price, tick=tick)
            except ValueError:
                continue

        if not job.bids:
            return None
        bid = self.labor.award(job.job_id, tick=tick)
        worker = self.agents[bid.bidder_id]
        quality = max(
            0.0,
            min(
                1.0,
                0.52
                + 0.34 * worker.skill(capability)
                + 0.10 * worker.reputation
                + self.rng.uniform(-0.02, 0.02),
            ),
        )
        completed = self.labor.complete(job.job_id, worker, quality=quality, tick=tick)

        # Root jobs are final output.  Subcontracts are intermediate production
        # and intentionally excluded from GDP to avoid double counting.
        if parent_job_id is None:
            self.internal_gdp += completed.awarded_price or Decimal("0")

        gross = completed.awarded_price or Decimal("0")
        useful_units = gross * Decimal(str(quality))
        productive = (
            gross
            * Decimal(str(quality))
            * self.PRODUCTIVITY_MULTIPLIER.get(capability, Decimal("1"))
        )

        receipt = VerifiedWorkReceipt(
            receipt_id=f"work:{self._next_receipt}",
            job_id=completed.job_id,
            buyer_id=buyer_id,
            worker_id=worker.agent_id,
            capability=capability,
            tick=tick,
            gross_value=gross,
            quality=quality,
            useful_work_units=useful_units,
            productive_capital_added=productive,
            verified=quality >= 0.50,
        )
        self._next_receipt += 1
        self.receipts.append(receipt)
        if receipt.verified:
            self.verified_useful_work += useful_units
            owner_id = buyer_id
            asset = ProductiveAsset(
                asset_id=f"productive:{self._next_asset}",
                owner_id=owner_id,
                creator_id=worker.agent_id,
                capability=capability,
                created_tick=tick,
                quality=quality,
                acquisition_cost=gross,
                productive_value=productive,
            )
            self._next_asset += 1
            self.assets[asset.asset_id] = asset

        # If the worker belongs to a company, a bounded share of the service
        # revenue is transferred to the company treasury.  This is internal
        # revenue, not new system wealth.
        if worker.employer_id and worker.employer_id in self.capital.companies:
            company = self.capital.companies[worker.employer_id]
            worker_cash = self.ledger.balance(worker.agent_id)
            service_share = min(worker_cash, gross * self.company_service_share)
            if service_share > 0:
                self.ledger.transfer(
                    worker.agent_id,
                    company.treasury_account,
                    service_share,
                    "company_internal_service_revenue",
                    completed.job_id,
                    metadata={"funding_source": "internal", "capability": capability},
                )
                company.retained_earnings += service_share
        return receipt

    def execute_agent_demand(self, tick: int) -> VerifiedWorkReceipt | None:
        self._decay(tick)
        active = [a for a in self.agents.values() if a.active]
        if not active:
            return None
        buyer = active[(tick - 1) % len(active)]
        budget = self._agent_budget(buyer)
        if budget <= 0:
            return None
        capability = self._need_for_agent(buyer, tick)
        return self._execute_internal_job(
            buyer_id=buyer.agent_id,
            capability=capability,
            budget=budget,
            tick=tick,
            title=f"Endogenous {capability} demand from {buyer.agent_id}",
        )

    def execute_company_demand(self, tick: int) -> VerifiedWorkReceipt | None:
        self._decay(tick)
        companies = [c for c in self.capital.companies.values() if c.active]
        if not companies:
            return None
        company = companies[(tick - 1) % len(companies)]
        budget = self._company_budget(company)
        if budget <= 0:
            return None
        capability = self._need_for_company(company, tick)
        return self._execute_internal_job(
            buyer_id=company.treasury_account,
            capability=capability,
            budget=budget,
            tick=tick,
            title=f"Internal company demand from {company.company_id}",
        )

    def execute_subcontract(
        self,
        receipt: VerifiedWorkReceipt,
        tick: int,
    ) -> VerifiedWorkReceipt | None:
        worker = self.agents.get(receipt.worker_id)
        if worker is None or not worker.active:
            return None
        budget = min(Decimal("1"), receipt.gross_value * Decimal("0.20"))
        if budget < Decimal("0.20") or self.ledger.balance(worker.agent_id) < budget:
            return None
        capability = "research" if receipt.capability != "research" else "coding"
        return self._execute_internal_job(
            buyer_id=worker.agent_id,
            capability=capability,
            budget=budget,
            tick=tick,
            title=f"Internal subcontract supporting {receipt.job_id}",
            parent_job_id=receipt.job_id,
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "internal_gdp": self.internal_gdp,
            "productive_capital": self.productive_capital,
            "verified_useful_work": self.verified_useful_work,
            "verified_work_receipts": len([r for r in self.receipts if r.verified]),
            "productive_assets": len(self.assets),
        }


def transaction_velocity(
    ledger: Ledger,
    *,
    opening_capital: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return gross internal transaction volume and SYNA/SYNR velocity indices.

    The current core uses one cash ledger.  Until native SYNA/SYNR balances are
    moved into this package, categories are mapped to the two settlement
    surfaces and divided by the common opening monetary base.  The indices do
    not change HardNAV or token supply.
    """

    syna_categories = {
        "job_escrow",
        "job_payment",
        "marketplace_fee",
        "company_internal_service_revenue",
        "research_market_fee",
        "platform_service_fee",
        "settlement_fee",
    }
    synr_categories = {
        "company_seed_capital",
        "loan_principal",
        "loan_repayment",
        "loan_default_cash_recovery",
        "loan_collateral_lock",
        "loan_collateral_release",
        "loan_collateral_liquidation",
        "deposit_principal",
        "deposit_withdrawal",
        "investment_principal",
        "investment_distribution",
        "investment_distribution_fee",
        "credit_origination_fee",
        "insurance_premium",
        "insurance_claim",
        "insurance_platform_fee",
    }
    internal = [e for e in ledger.entries if not e.external and not e.opening]
    gtv = sum((e.amount for e in internal), Decimal("0"))
    syna_volume = sum((e.amount for e in internal if e.category in syna_categories), Decimal("0"))
    synr_volume = sum((e.amount for e in internal if e.category in synr_categories), Decimal("0"))
    base = opening_capital if opening_capital > 0 else Decimal("1")
    return gtv, syna_volume / base, synr_volume / base


def gini(values: list[Decimal]) -> Decimal:
    vals = sorted(max(Decimal("0"), Decimal(v)) for v in values)
    if not vals:
        return Decimal("0")
    total = sum(vals, Decimal("0"))
    if total <= 0:
        return Decimal("0")
    n = Decimal(len(vals))
    weighted = sum((Decimal(i + 1) * value for i, value in enumerate(vals)), Decimal("0"))
    return (Decimal("2") * weighted) / (n * total) - (n + Decimal("1")) / n
