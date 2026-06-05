from macd_searcher.classify import classify_asset


def test_core_perps_are_crypto():
    assert classify_asset("BTC") == "crypto"
    assert classify_asset("HYPE") == "crypto"
    assert classify_asset("kPEPE") == "crypto"
    # A crypto token that happens to share a name with an index ticker stays crypto
    # because it has no DEX prefix.
    assert classify_asset("SPX") == "crypto"


def test_hip3_subclassification():
    assert classify_asset("xyz:TSLA") == "equity"
    assert classify_asset("xyz:NVDA") == "equity"
    assert classify_asset("xyz:GOLD") == "commodity"
    assert classify_asset("xyz:BRENTOIL") == "commodity"
    assert classify_asset("xyz:CL") == "commodity"
    assert classify_asset("xyz:EUR") == "fx"
    assert classify_asset("xyz:DXY") == "fx"
    assert classify_asset("xyz:SP500") == "index"


def test_unknown_prefixed_defaults_to_equity():
    assert classify_asset("xyz:SOMENEWTICKER") == "equity"


def test_case_insensitive_base():
    assert classify_asset("xyz:gold") == "commodity"
