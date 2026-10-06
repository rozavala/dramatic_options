"""Data-feed resolution / validation / classification (the data-feed upgrade)."""

import pytest

import feeds


def test_validate_accepts_valid_block():
    feeds.validate({"equity_bars": "sip", "option_gate": "indicative", "option_monitor": "opra"})
    # an extra _comment key is ignored (only the three roles are checked)
    feeds.validate({"_comment": "x", "equity_bars": "iex", "option_gate": "opra",
                    "option_monitor": "indicative"})


@pytest.mark.parametrize("block", [
    {"equity_bars": "sipp", "option_gate": "indicative", "option_monitor": "indicative"},  # typo
    {"equity_bars": "sip", "option_gate": "opra"},                                          # missing role
    {"equity_bars": "opra", "option_gate": "indicative", "option_monitor": "indicative"},   # wrong domain
    {"equity_bars": "sip", "option_gate": "iex", "option_monitor": "indicative"},            # wrong domain
    {},                                                                                       # all missing
])
def test_validate_rejects_bad_block(block):
    with pytest.raises(feeds.FeedConfigError):
        feeds.validate(block)


def test_validate_rejects_non_dict():
    # the OLD flat string ("indicative") is no longer a valid data_feed value
    with pytest.raises(feeds.FeedConfigError):
        feeds.validate("indicative")


def test_to_equity_feed_maps_known():
    from alpaca.data.enums import DataFeed

    assert feeds.to_equity_feed("iex") is DataFeed.IEX
    assert feeds.to_equity_feed("sip") is DataFeed.SIP


def test_to_option_feed_maps_known():
    from alpaca.data.enums import OptionsFeed

    assert feeds.to_option_feed("indicative") is OptionsFeed.INDICATIVE
    assert feeds.to_option_feed("opra") is OptionsFeed.OPRA


def test_resolvers_reject_unknown():
    with pytest.raises(feeds.FeedConfigError):
        feeds.to_equity_feed("opra")   # an option value for an equity role
    with pytest.raises(feeds.FeedConfigError):
        feeds.to_option_feed("sip")    # an equity value for an option role


def test_classify_feed_error():
    ent = feeds.classify_feed_error(
        Exception("subscription does not permit querying recent SIP data"))
    assert ent == "entitlement"
    assert feeds.classify_feed_error(Exception("403 Forbidden")) == "entitlement"
    # anything not clearly a subscription/permission lapse → transient (never a false 'veto')
    assert feeds.classify_feed_error(Exception("Connection reset by peer")) == "transient"
    assert feeds.classify_feed_error(TimeoutError("read timed out")) == "transient"
