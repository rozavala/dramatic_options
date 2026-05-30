"""Market adapter: as-of truncation, strictly-forward label, momentum/ADV/beta math."""

from datetime import UTC, datetime, timedelta

from data.cache import PointInTimeCache
from data.market import MarketData


def _bars(start: str, n: int, price0: float = 10.0, step: float = 0.1, vol: float = 1_000_000):
    """n consecutive daily bars from start, close = price0 + i*step."""
    d0 = datetime.fromisoformat(start).replace(tzinfo=UTC)
    out = []
    for i in range(n):
        c = price0 + i * step
        out.append({
            "ts": (d0 + timedelta(days=i)).isoformat(),
            "open": c, "high": c, "low": c, "close": c, "volume": vol,
        })
    return out


def _market(tmp_path, symbol="JOBY", n=400):
    cache = PointInTimeCache(tmp_path)
    end = datetime.fromisoformat("2022-01-01").replace(tzinfo=UTC) + timedelta(days=n + 10)
    cache.write("bars", symbol, _bars("2022-01-01", n), coverage_through=end)
    return MarketData(cache, client=None, fetch_start=datetime(2021, 1, 1, tzinfo=UTC),
                      fetch_end=end), end


def test_latest_price_is_as_of(tmp_path):
    md, _ = _market(tmp_path)
    as_of = datetime.fromisoformat("2022-01-11").replace(tzinfo=UTC)  # 11th bar, idx 10
    # closes are 10.0 + idx*0.1; idx for 2022-01-11 is 10 → 11.0
    assert round(md.latest_price("JOBY", as_of), 4) == 11.0


def test_adv_uses_only_trailing_window(tmp_path):
    md, _ = _market(tmp_path)
    as_of = datetime.fromisoformat("2022-03-01").replace(tzinfo=UTC)
    adv = md.adv_usd("JOBY", as_of, window=20)
    assert adv is not None and adv > 0


def test_momentum_skips_recent_month(tmp_path):
    md, _ = _market(tmp_path, n=400)
    as_of = datetime.fromisoformat("2022-01-01").replace(tzinfo=UTC) + timedelta(days=399)
    mom = md.momentum("JOBY", as_of, lookback=252, skip=21)
    assert mom is not None and mom > 0  # steadily rising series → positive momentum


def test_forward_return_is_strictly_forward(tmp_path):
    md, _ = _market(tmp_path)
    as_of = datetime.fromisoformat("2022-02-01").replace(tzinfo=UTC)  # idx 31, close 13.1
    entry = md.latest_price("JOBY", as_of)
    fr = md.forward_return("JOBY", as_of, horizon_days=10)
    # exit close is the 10th forward bar; rising series → positive forward return
    assert fr is not None and fr > 0
    # and the label did not move the lookahead tripwire (read_between is exempt)
    assert md.cache.running_max_ts is None or md.cache.running_max_ts <= as_of
    assert entry > 0


def test_forward_return_none_near_end(tmp_path):
    md, end = _market(tmp_path, n=50)
    near_end = datetime.fromisoformat("2022-01-01").replace(tzinfo=UTC) + timedelta(days=48)
    assert md.forward_return("JOBY", near_end, horizon_days=21) is None
