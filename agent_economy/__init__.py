"""SYNERGY Autonomous Agent Economy v2.

The package is intentionally standard-library only so economic experiments remain
portable and auditable. Cash mutations are routed through :class:`Ledger`.
"""

from .engine import AgentEconomy, EconomyConfig, EconomyReport
from .closed_engine import ClosedAgentEconomy, ClosedEconomyConfig, ClosedEconomyReport
from .endogenous import EndogenousDemandEngine, ProductiveAsset, VerifiedWorkReceipt
from .evolution import EvolutionEngine
from .ledger import InsufficientFunds, Ledger, LedgerEntry
from .models import AdaptiveStrategy, AgentGenome, AgentState, Company, ExecutionMandate
from .multimarket import (
    ALL_INTERNAL_ASSETS,
    BASE_ASSETS,
    CORE_INTERNAL_POOLS,
    MIRRORED_ASSETS,
    P9_SETTLEMENT_POOLS,
    MultiMarketConfig,
    MultiMarketHardNavEngine,
)
from .protocols import (
    AgentIdentityCard,
    MachinePaymentRequest,
    PaymentMandateEnvelope,
    ProtocolRegistry,
    TaskEnvelope,
)
from .risk import BankruptcyEngine, InsuranceMarket

__all__ = [
    "AgentEconomy",
    "EconomyConfig",
    "EconomyReport",
    "ClosedAgentEconomy",
    "ClosedEconomyConfig",
    "ClosedEconomyReport",
    "EndogenousDemandEngine",
    "ProductiveAsset",
    "VerifiedWorkReceipt",
    "MultiMarketConfig",
    "MultiMarketHardNavEngine",
    "BASE_ASSETS",
    "MIRRORED_ASSETS",
    "ALL_INTERNAL_ASSETS",
    "CORE_INTERNAL_POOLS",
    "P9_SETTLEMENT_POOLS",
    "AdaptiveStrategy",
    "AgentGenome",
    "AgentState",
    "Company",
    "ExecutionMandate",
    "InsufficientFunds",
    "Ledger",
    "LedgerEntry",
    "InsuranceMarket",
    "BankruptcyEngine",
    "EvolutionEngine",
    "AgentIdentityCard",
    "TaskEnvelope",
    "PaymentMandateEnvelope",
    "MachinePaymentRequest",
    "ProtocolRegistry",
]
