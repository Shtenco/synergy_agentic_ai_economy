from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from math import sqrt
from typing import Mapping

getcontext().prec = 28

BASE_ASSETS = (
    "WETH",
    "cbBTC",
    "VVV",
    "VIRTUAL",
    "AERO",
    "cbETH",
    "USDe",
    "cbXRP",
    "TOSHI",
    "MORPHO",
)

MIRRORED_ASSETS = (
    "RUBX",
    "RUBZ",
    "USDC",
    *BASE_ASSETS,
)

SETTLEMENT_TOKENS = ("SYNA", "SYNR")

ALL_INTERNAL_ASSETS = (*MIRRORED_ASSETS, *SETTLEMENT_TOKENS)

CORE_INTERNAL_POOLS = (
    ("RUBX", "USDC"),
    ("RUBZ", "USDC"),
    ("RUBX", "RUBZ"),
)

SHADOW_BASE_POOLS = tuple((asset, "USDC") for asset in BASE_ASSETS)

P9_SETTLEMENT_POOLS = (
    ("SYNA", "BTC"),
    ("SYNA", "ETH"),
    ("SYNA", "WETH"),
    ("SYNR", "BTC"),
    ("SYNR", "ETH"),
    ("SYNR", "WETH"),
)

D = Decimal


@dataclass(frozen=True)
class MultiMarketConfig:
    opening_hardnav: Decimal = D("8700")
    protected_reserve: Decimal = D("3700")
    external_pool_nav: Decimal = D("2500")
    bridge_nav: Decimal = D("2500")
    external_pool_fee_bps: Decimal = D("30")
    bridge_fee_bps: Decimal = D("10")
    swap_fee_bps: Decimal = D("30")
    external_execution_fee_bps: Decimal = D("4")
    bridge_asset_share: Decimal = D("0.18")
    hedge_anchor: Decimal = D("0.9955")
    wealth_floor_gap: Decimal = D("0.0015")
    funding_apr: Decimal = D("0.02")
    block_seconds: Decimal = D("12")
    gas_base_units: int = 90_000
    gas_per_active_leg_units: int = 33_000
    min_batch_interval_blocks: int = 8
    gas_safety_multiple: Decimal = D("1.50")
    risk_benefit_multiplier: Decimal = D("3.0")

    def __post_init__(self) -> None:
        components = self.protected_reserve + self.external_pool_nav + self.bridge_nav
        if components != self.opening_hardnav:
            raise ValueError("opening components must sum exactly to opening_hardnav")
        if not D("0") < self.bridge_asset_share < D("1"):
            raise ValueError("bridge_asset_share must be in (0, 1)")
        if self.min_batch_interval_blocks <= 0:
            raise ValueError("min_batch_interval_blocks must be positive")


@dataclass
class ExternalPool:
    asset: str
    nav: Decimal
    cumulative_external_fee: Decimal = D("0")

    def mark_to_external_price(
        self,
        price_ratio: Decimal | float | str,
        *,
        fee_bps: Decimal,
    ) -> Decimal:
        q = D(str(price_ratio))
        if q <= 0:
            raise ValueError("price_ratio must be positive")
        root = q.sqrt()
        old = self.nav
        # A 50/50 CPMM reprices by sqrt(q).  The absolute USDC reserve
        # adjustment is a conservative proxy for arbitrage notional.
        arbitrage_notional = old * abs(root - D("1")) / D("2")
        fee = arbitrage_notional * fee_bps / D("10000")
        self.cumulative_external_fee += fee
        self.nav = old * root + fee
        return fee


@dataclass
class BridgeInventory:
    asset: str
    asset_value: Decimal
    usdc_value: Decimal

    @property
    def nav(self) -> Decimal:
        return self.asset_value + self.usdc_value

    @property
    def asset_share(self) -> Decimal:
        if self.nav <= 0:
            return D("0")
        return self.asset_value / self.nav

    def mark_asset(self, price_ratio: Decimal | float | str) -> None:
        q = D(str(price_ratio))
        if q <= 0:
            raise ValueError("price_ratio must be positive")
        self.asset_value *= q


@dataclass
class ShadowAccounting:
    supplies: dict[str, Decimal] = field(default_factory=dict)
    internal_fees: Decimal = D("0")
    internal_volume: Decimal = D("0")
    mint_value: Decimal = D("0")
    burn_value: Decimal = D("0")

    def __post_init__(self) -> None:
        if not self.supplies:
            self.supplies = {asset: D("1000") for asset in ALL_INTERNAL_ASSETS}

    def mint(self, asset: str, amount: Decimal | str | float) -> None:
        if asset not in self.supplies:
            raise KeyError(asset)
        value = D(str(amount))
        if value <= 0:
            raise ValueError("mint amount must be positive")
        self.supplies[asset] += value
        self.mint_value += value

    def burn(self, asset: str, amount: Decimal | str | float) -> None:
        if asset not in self.supplies:
            raise KeyError(asset)
        value = D(str(amount))
        if value <= 0 or value > self.supplies[asset]:
            raise ValueError("invalid burn amount")
        self.supplies[asset] -= value
        self.burn_value += value

    def internal_trade(
        self,
        notional: Decimal | str | float,
        *,
        fee_bps: Decimal | str | float = D("30"),
    ) -> Decimal:
        value = D(str(notional))
        fee_rate = D(str(fee_bps)) / D("10000")
        if value < 0:
            raise ValueError("notional must be non-negative")
        fee = value * fee_rate
        self.internal_volume += value
        self.internal_fees += fee
        return fee


class MultiMarketHardNavEngine:
    """Strict HardNAV layer for the closed agent economy.

    The engine restores the repository's v3-v8.1 market geometry while keeping
    the closed agent economy's accounting invariant:

    * internal mint/burn, internal CPMM fees, credit and collateral claims do
      not increase HardNAV;
    * only externally realizable assets/PnL/fees enter HardNAV;
    * external principal is removed again in capital-adjusted HardNAV;
    * gas, funding and execution costs are always deducted.
    """

    def __init__(self, config: MultiMarketConfig | None = None) -> None:
        self.config = config or MultiMarketConfig()
        pool_each = self.config.external_pool_nav / D(len(BASE_ASSETS))
        bridge_each = self.config.bridge_nav / D(len(BASE_ASSETS))
        self.protected_usdc = self.config.protected_reserve
        self.pools = {
            asset: ExternalPool(asset=asset, nav=pool_each)
            for asset in BASE_ASSETS
        }
        self.bridge = {
            asset: BridgeInventory(
                asset=asset,
                asset_value=bridge_each * self.config.bridge_asset_share,
                usdc_value=bridge_each * (D("1") - self.config.bridge_asset_share),
            )
            for asset in BASE_ASSETS
        }
        self.shadow = ShadowAccounting()

        self.net_external_capital_flow = D("0")
        self.external_protocol_fee_revenue = D("0")
        self.external_amm_fee_revenue = D("0")
        self.hedge_pnl = D("0")
        self.funding_cost = D("0")
        self.execution_cost = D("0")
        self.gas_cost = D("0")
        self.block = 0
        self.last_rebalance_block = -10**9
        self.rebalance_batches = 0

        # Short-dollar notionals are initialized to the training-selected
        # near-delta-neutral anchor.  They are real risk positions: gains and
        # losses enter HardNAV and funding is charged.
        self.short_notional = {
            asset: self.config.hedge_anchor
            * (self.pools[asset].nav / D("2") + self.bridge[asset].asset_value)
            for asset in BASE_ASSETS
        }

        self.high_water_mark = self.capital_adjusted_hardnav()
        self.wealth_floor = self.high_water_mark * (
            D("1") - self.config.wealth_floor_gap
        )

    def raw_hardnav(self) -> Decimal:
        external_assets = (
            self.protected_usdc
            + sum((pool.nav for pool in self.pools.values()), D("0"))
            + sum((inventory.nav for inventory in self.bridge.values()), D("0"))
        )
        return (
            external_assets
            + self.hedge_pnl
            - self.funding_cost
            - self.execution_cost
            - self.gas_cost
        )

    def capital_adjusted_hardnav(self) -> Decimal:
        return self.raw_hardnav() - self.net_external_capital_flow

    def _update_floor(self) -> None:
        nav = self.capital_adjusted_hardnav()
        if nav > self.high_water_mark:
            self.high_water_mark = nav
            self.wealth_floor = self.high_water_mark * (
                D("1") - self.config.wealth_floor_gap
            )

    def record_external_bridge_flow(
        self,
        *,
        gross_volume: Decimal | str | float,
        net_principal_flow: Decimal | str | float = D("0"),
        bridge_fee_bps: Decimal | None = None,
        swap_fee_bps: Decimal | None = None,
    ) -> Decimal:
        """Book external user flow without misclassifying principal as profit."""

        volume = D(str(gross_volume))
        principal = D(str(net_principal_flow))
        if volume < 0:
            raise ValueError("gross_volume must be non-negative")
        bridge_bps = bridge_fee_bps or self.config.bridge_fee_bps
        swap_bps = swap_fee_bps or self.config.swap_fee_bps
        fee = volume * (bridge_bps + swap_bps) / D("10000")

        # Principal changes raw cash but is backed out from capital-adjusted
        # HardNAV.  Protocol fees are swept immediately to protected USDC.
        self.protected_usdc += principal + fee
        self.net_external_capital_flow += principal
        self.external_protocol_fee_revenue += fee
        self._update_floor()
        return fee

    def apply_external_market_move(
        self,
        price_ratios: Mapping[str, Decimal | str | float],
    ) -> Decimal:
        if set(price_ratios) != set(BASE_ASSETS):
            missing = set(BASE_ASSETS) - set(price_ratios)
            extra = set(price_ratios) - set(BASE_ASSETS)
            raise ValueError(f"price ratios must cover BASE_ASSETS; missing={missing}, extra={extra}")

        before = self.capital_adjusted_hardnav()
        year_seconds = D(365 * 24 * 3600)
        block_year_fraction = self.config.block_seconds / year_seconds

        for asset in BASE_ASSETS:
            q = D(str(price_ratios[asset]))
            if q <= 0:
                raise ValueError("price ratio must be positive")

            old_short = self.short_notional[asset]
            self.hedge_pnl -= old_short * (q - D("1"))
            self.short_notional[asset] *= q
            self.funding_cost += (
                abs(old_short)
                * self.config.funding_apr
                * block_year_fraction
            )

            fee = self.pools[asset].mark_to_external_price(
                q,
                fee_bps=self.config.external_pool_fee_bps,
            )
            self.external_amm_fee_revenue += fee
            self.bridge[asset].mark_asset(q)

        self.block += 1
        self._update_floor()
        return self.capital_adjusted_hardnav() - before

    def target_external_delta(self, asset: str) -> Decimal:
        return self.pools[asset].nav / D("2") + self.bridge[asset].asset_value

    def rebalance_external_risk(
        self,
        *,
        target_hedge_ratio: Decimal | str | float,
        target_bridge_share: Decimal | str | float,
        realized_volatility: Mapping[str, Decimal | str | float],
        eth_usd: Decimal | str | float,
        gas_gwei: Decimal | str | float,
        no_trade_band: Decimal | str | float = D("0.002"),
    ) -> bool:
        """v8.1-style netted batch rebalance with an economic execution gate."""

        if self.block - self.last_rebalance_block < self.config.min_batch_interval_blocks:
            return False

        hedge_ratio = D(str(target_hedge_ratio))
        bridge_share = D(str(target_bridge_share))
        band = D(str(no_trade_band))
        if hedge_ratio <= 0:
            raise ValueError("target_hedge_ratio must be positive")
        if not D("0") < bridge_share < D("1"):
            raise ValueError("target_bridge_share must be in (0, 1)")

        target_bridge_asset: dict[str, Decimal] = {}
        target_short: dict[str, Decimal] = {}
        total_notional = D("0")
        expected_benefit = D("0")
        active_legs = 0

        for asset in BASE_ASSETS:
            inv = self.bridge[asset]
            bridge_target = inv.nav * bridge_share
            target_bridge_asset[asset] = bridge_target
            delta = self.pools[asset].nav / D("2") + bridge_target
            target_short[asset] = delta * hedge_ratio

            bridge_trade = abs(bridge_target - inv.asset_value)
            hedge_trade = abs(target_short[asset] - self.short_notional[asset])
            total_notional += bridge_trade + hedge_trade
            if bridge_trade > 0:
                active_legs += 1
            if hedge_trade > 0:
                active_legs += 1

            vol = D(str(realized_volatility[asset]))
            expected_benefit += (
                hedge_trade
                * vol
                * D(str(sqrt(float(self.config.min_batch_interval_blocks))))
                * self.config.risk_benefit_multiplier
            )

        nav = self.capital_adjusted_hardnav()
        if total_notional <= nav * band:
            return False

        gas_units = self.config.gas_base_units + (
            self.config.gas_per_active_leg_units * active_legs
        )
        gas = (
            D(gas_units)
            * D(str(gas_gwei))
            * D("1e-9")
            * D(str(eth_usd))
        )
        execution = (
            total_notional
            * self.config.external_execution_fee_bps
            / D("10000")
        )

        if expected_benefit <= (
            gas + execution
        ) * self.config.gas_safety_multiple:
            return False

        for asset in BASE_ASSETS:
            inv = self.bridge[asset]
            target = target_bridge_asset[asset]
            if target > inv.asset_value:
                buy = min(target - inv.asset_value, inv.usdc_value)
                inv.asset_value += buy
                inv.usdc_value -= buy
            else:
                sell = min(inv.asset_value - target, inv.asset_value)
                inv.asset_value -= sell
                inv.usdc_value += sell
            self.short_notional[asset] = target_short[asset]

        self.gas_cost += gas
        self.execution_cost += execution
        self.rebalance_batches += 1
        self.last_rebalance_block = self.block
        self._update_floor()
        return True

    def mint_shadow(self, asset: str, amount: Decimal | str | float) -> None:
        before = self.capital_adjusted_hardnav()
        self.shadow.mint(asset, amount)
        if self.capital_adjusted_hardnav() != before:
            raise AssertionError("shadow mint changed HardNAV")

    def burn_shadow(self, asset: str, amount: Decimal | str | float) -> None:
        before = self.capital_adjusted_hardnav()
        self.shadow.burn(asset, amount)
        if self.capital_adjusted_hardnav() != before:
            raise AssertionError("shadow burn changed HardNAV")

    def record_internal_pool_trade(
        self,
        notional: Decimal | str | float,
        *,
        fee_bps: Decimal | str | float = D("30"),
    ) -> Decimal:
        before = self.capital_adjusted_hardnav()
        fee = self.shadow.internal_trade(notional, fee_bps=fee_bps)
        if self.capital_adjusted_hardnav() != before:
            raise AssertionError("internal pool fee changed HardNAV")
        return fee

    def snapshot(self) -> dict[str, object]:
        nav = self.capital_adjusted_hardnav()
        drawdown = D("0")
        if self.high_water_mark > 0 and nav < self.high_water_mark:
            drawdown = D("1") - nav / self.high_water_mark
        return {
            "hardnav": nav,
            "raw_hardnav": self.raw_hardnav(),
            "net_external_capital_flow": self.net_external_capital_flow,
            "high_water_mark": self.high_water_mark,
            "wealth_floor": self.wealth_floor,
            "drawdown": drawdown,
            "protected_usdc": self.protected_usdc,
            "external_protocol_fee_revenue": self.external_protocol_fee_revenue,
            "external_amm_fee_revenue": self.external_amm_fee_revenue,
            "hedge_pnl": self.hedge_pnl,
            "funding_cost": self.funding_cost,
            "execution_cost": self.execution_cost,
            "gas_cost": self.gas_cost,
            "rebalance_batches": self.rebalance_batches,
            "bridge_asset_share": {
                asset: inventory.asset_share
                for asset, inventory in self.bridge.items()
            },
            "shadow_internal_fees": self.shadow.internal_fees,
            "shadow_internal_volume": self.shadow.internal_volume,
            "shadow_mint_value": self.shadow.mint_value,
            "shadow_burn_value": self.shadow.burn_value,
        }
