from decimal import Decimal

from agent_economy.multimarket import (
    D,
    ALL_INTERNAL_ASSETS,
    BASE_ASSETS,
    CORE_INTERNAL_POOLS,
    MultiMarketHardNavEngine,
    P9_SETTLEMENT_POOLS,
)


def test_opening_geometry_matches_repository_v3_v8_stack():
    e = MultiMarketHardNavEngine()
    assert e.capital_adjusted_hardnav() == Decimal("8700")
    assert len(BASE_ASSETS) == 10
    assert len(CORE_INTERNAL_POOLS) == 3
    assert len(P9_SETTLEMENT_POOLS) == 6
    assert set(("RUBX", "RUBZ", "USDC", "SYNA", "SYNR")).issubset(
        set(ALL_INTERNAL_ASSETS)
    )


def test_shadow_mint_burn_and_internal_pool_fees_do_not_change_hardnav():
    e = MultiMarketHardNavEngine()
    before = e.capital_adjusted_hardnav()
    e.mint_shadow("RUBX", Decimal("100"))
    e.record_internal_pool_trade(Decimal("250"))
    e.burn_shadow("RUBX", Decimal("50"))
    assert e.capital_adjusted_hardnav() == before
    assert e.shadow.internal_fees > 0


def test_external_principal_is_not_profit_but_external_fee_is():
    e = MultiMarketHardNavEngine()
    before = e.capital_adjusted_hardnav()
    fee = e.record_external_bridge_flow(
        gross_volume=Decimal("1000"),
        net_principal_flow=Decimal("250"),
    )
    assert fee == Decimal("4")
    assert e.raw_hardnav() == before + Decimal("254")
    assert e.capital_adjusted_hardnav() == before + Decimal("4")


def test_external_amm_fee_is_hardnav_revenue():
    e = MultiMarketHardNavEngine()
    before = e.capital_adjusted_hardnav()
    ratios = {asset: Decimal("1.001") for asset in BASE_ASSETS}
    e.apply_external_market_move(ratios)
    assert e.external_amm_fee_revenue > 0
    assert e.capital_adjusted_hardnav() != before


def test_near_delta_neutral_opening_short_covers_all_base_assets():
    e = MultiMarketHardNavEngine()
    for asset in BASE_ASSETS:
        delta = e.target_external_delta(asset)
        ratio = e.short_notional[asset] / delta
        assert Decimal("0.99") < ratio < Decimal("1.01")


def test_gas_aware_rebalance_is_bounded_and_fail_closed():
    e = MultiMarketHardNavEngine()
    vols = {asset: Decimal("0.001") for asset in BASE_ASSETS}
    # Too early: minimum batch interval not satisfied.
    assert not e.rebalance_external_risk(
        target_hedge_ratio=Decimal("1"),
        target_bridge_share=Decimal("0.18"),
        realized_volatility=vols,
        eth_usd=Decimal("1700"),
        gas_gwei=Decimal("8"),
    )
    # Advance enough blocks using flat prices.
    for _ in range(8):
        e.apply_external_market_move({asset: Decimal("1") for asset in BASE_ASSETS})
    result = e.rebalance_external_risk(
        target_hedge_ratio=Decimal("1.01"),
        target_bridge_share=Decimal("0.20"),
        realized_volatility=vols,
        eth_usd=Decimal("1700"),
        gas_gwei=Decimal("8"),
        no_trade_band=Decimal("0.0001"),
    )
    assert isinstance(result, bool)
    assert e.gas_cost >= 0
    assert e.execution_cost >= 0


def test_explicit_zero_fee_legs_are_respected() -> None:
    engine = MultiMarketHardNavEngine()
    start = engine.capital_adjusted_hardnav()

    bridge_fee = engine.record_external_bridge_flow(
        gross_volume=D("1000"),
        bridge_fee_bps=D("10"),
        swap_fee_bps=D("0"),
    )
    swap_fee = engine.record_external_bridge_flow(
        gross_volume=D("1000"),
        bridge_fee_bps=D("0"),
        swap_fee_bps=D("30"),
    )

    assert bridge_fee == D("1")
    assert swap_fee == D("3")
    assert engine.external_protocol_fee_revenue == D("4")
    assert engine.capital_adjusted_hardnav() == start + D("4")
