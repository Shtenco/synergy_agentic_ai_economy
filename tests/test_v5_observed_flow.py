import pytest

from experiments.build_observed_external_flow_v5 import (
    BASE_AERO,
    BASE_USDC,
    BASE_WETH,
    ETH_USDC,
    ETH_WETH,
    map_event_index,
    usd_price,
)


def test_event_mapping_is_causal_and_never_uses_future_block() -> None:
    v4_ts = [100, 110, 120, 130]
    assert map_event_index(99, v4_ts) is None
    assert map_event_index(100, v4_ts) == 0
    assert map_event_index(109, v4_ts) == 0
    assert map_event_index(110, v4_ts) == 1
    assert map_event_index(129, v4_ts) == 2
    assert map_event_index(130, v4_ts) == 3


def test_only_proven_token_prices_are_accepted() -> None:
    row = {"WETH_usd": "4000.0", "AERO_usd": "1.25"}
    assert usd_price("USDC", row) == 1.0
    assert usd_price("WETH", row) == 4000.0
    assert usd_price("AERO", row) == 1.25
    with pytest.raises(KeyError):
        usd_price("UNPROVEN", row)


def test_supported_chain_token_addresses_resolve_to_proven_symbols() -> None:
    # The builder must explicitly recognize both Ethereum and Base wrappers,
    # rather than inventing a cross-chain token price.
    from experiments.build_observed_external_flow_v5 import TOKEN_INFO

    assert TOKEN_INFO[BASE_USDC] == ("USDC", 6)
    assert TOKEN_INFO[ETH_USDC] == ("USDC", 6)
    assert TOKEN_INFO[BASE_WETH] == ("WETH", 18)
    assert TOKEN_INFO[ETH_WETH] == ("WETH", 18)
    assert TOKEN_INFO[BASE_AERO] == ("AERO", 18)
