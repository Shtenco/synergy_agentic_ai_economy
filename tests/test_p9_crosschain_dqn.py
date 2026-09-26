from experiments.p9_crosschain_dqn import Config, Economy, PAIR_NAMES, self_test

def test_p9_self_test():
    assert self_test()["status"] == "PASS"

def test_bidirectional_routes_require_backing():
    for ext in ("BTC","ETH","WETH"):
        for tok in ("SYNA","SYNR"):
            inbound = Economy(Config(seed=1))
            assert inbound.route(ext,tok,100.0) > 0
            empty = Economy(Config(seed=1))
            assert empty.route(tok,ext,50.0) == 0
            funded = Economy(Config(seed=1))
            funded.synthetic[ext] = 100.0
            assert funded.route(tok,ext,50.0) > 0

def test_cb_cannot_create_external_capital_flow():
    env = Economy(Config(seed=1))
    before = env.external_flow
    env.apply_cb(44)
    assert env.external_flow == before

def test_market_geometry_preserved():
    env = Economy(Config(seed=1))
    assert len(PAIR_NAMES) == 6
    assert len(env.market_state(PAIR_NAMES[0])) == 20
    assert len(env.cb_state()) == 12
