"""Synthetic fixtures test mechanics only. They are NOT research results."""

import numpy as np
import pandas as pd
import pytest

from flowlab.backtest import walk_forward
from flowlab.core import (Config, asof_benchmark, asof_holdings, construct_portfolio,
                          create_signal, observed_fund_flows)
from flowlab.vendors import parse_proshares_nav, parse_proshares_holdings, parse_ishares_csv


def fixture_data():
    dates = pd.bdate_range("2026-07-01", periods=90)
    funds = pd.DataFrame({"date": dates, "fund": "FUND", "nav": 100.0,
                          "shares_outstanding": [100000 + i * (100 if i % 2 else 200) for i in range(len(dates))]})
    holdings = pd.DataFrame({"asof": dates[-4], "fund": ["FUND"] * 4,
                             "ticker": ["AAA", "BBB", "CCC", "DDD"],
                             "weight": [.25] * 4})
    benchmark = pd.DataFrame({"asof": dates[-4],
                              "ticker": ["AAA", "BBB", "CCC", "DDD"],
                              "weight": [.25] * 4,
                              "sector": ["Tech", "Tech", "Energy", "Energy"]})
    prices = pd.DataFrame([{"date": d, "ticker": ticker,
                            "close": 100 + i * m + np.sin(i * m),
                            "volume": 100000 + (n * 50000)}
                           for i, d in enumerate(dates)
                           for n, (ticker, m) in enumerate([("AAA", .2), ("BBB", .3),
                                                             ("CCC", .13), ("DDD", .17)])])
    return {"fund_days": funds, "holdings": holdings,
            "benchmark": benchmark, "prices": prices}, dates


def test_creations_are_share_changes_not_aum_changes():
    d = pd.DataFrame({"fund": ["F", "F"], "date": pd.to_datetime(["2026-11-02", "2026-11-03"]),
                      "nav": [100, 110], "shares_outstanding": [1000, 1000]})
    flows = observed_fund_flows(d)
    assert flows.creation_usd.iloc[1] == 0


def test_flow_estimate_uses_nav_at_current_date():
    d = pd.DataFrame({"fund": ["F", "F"], "date": pd.to_datetime(["2026-11-02", "2026-11-03"]),
                      "nav": [100, 110], "shares_outstanding": [1000, 1200]})
    assert observed_fund_flows(d).creation_usd.iloc[-1] == 22000


def test_gap_invalidates_creation():
    d = pd.DataFrame({"fund": ["F", "F"], "date": pd.to_datetime(["2026-11-01", "2026-11-10"]),
                      "nav": [100, 110], "shares_outstanding": [1000, 1200]})
    assert pd.isna(observed_fund_flows(d).creation_usd.iloc[-1])


def test_asof_disclosure_excludes_same_day():
    data, dates = fixture_data()
    signal, diag = create_signal(data, dates[-3])
    assert diag["stocks_with_scores"] == 4
    assert abs(diag["benchmark_weight_with_scores"] - 1) < 1e-8
    assert len(signal) == 4
    # Same-day fund rows are unavailable absent a release timestamp.
    d2 = {**data, "fund_days": pd.concat([data["fund_days"], pd.DataFrame([{
        "date": dates[-3], "fund": "FUND", "nav": 100.0, "shares_outstanding": 9999999}])],
        ignore_index=True).drop_duplicates(["fund", "date"], keep="last")}
    sig2, _ = create_signal(d2, dates[-3])
    pd.testing.assert_series_equal(signal.set_index("ticker").score,
                                   sig2.set_index("ticker").score)


def test_target_long_only_neutral_and_has_measured_te():
    data, dates = fixture_data()
    signal, _ = create_signal(data, dates[-3])
    weights, diag = construct_portfolio(signal, data["prices"], dates[-3])
    assert (weights.target_weight >= 0).all()
    assert np.isclose(weights.target_weight.sum(), 1)
    assert diag["sector_neutral"]
    assert diag["ex_ante_tracking_error"] is not None
    assert diag["ex_ante_tracking_error"] <= .0100001
    assert weights.tilt.abs().max() <= .00350001


def test_missing_price_blocks_optimization():
    data, dates = fixture_data()
    data["prices"] = data["prices"][data["prices"].ticker != "AAA"]
    signal, diag = create_signal(data, dates[-3])
    assert diag["stocks_with_scores"] == 3
    assert diag["benchmark_weight_with_scores"] == .75
    with pytest.raises(ValueError, match="partial coverage"):
        construct_portfolio(signal, data["prices"], dates[-3])


def test_backtest_never_enters_at_signal_close():
    data, dates = fixture_data()
    # Daily holdings/benchmark snapshots are needed to span multiple historical periods.
    result, report = walk_forward(data, dates[-3].date().isoformat(),
                                  dates[-3].date().isoformat())
    assert len(result) == 1
    row = result.iloc[0]
    assert pd.Timestamp(row.execution_close) > pd.Timestamp(row.signal_asof)
    assert pd.Timestamp(row.return_close) > pd.Timestamp(row.execution_close)
    assert report["cost_assumption_bps"] == 5.0


def test_proshares_parsers():
    nav = (b"Date,ProShares Name,Ticker,NAV,Prior NAV,Shares Outstanding (000),Assets Under Management\n"
           b"11/03/2026,Test,NOBL,100,99,200,20000000\n")
    assert parse_proshares_nav(nav, "NOBL").shares_outstanding.iloc[0] == 200000
    holdings = (b"PORTFOLIO HOLDINGS INFORMATION\nAS OF 11/03/2026\n\n"
                b"Fund Ticker,Fund Name,Security Ticker,Security Sedol,Security Description,Market Value\n"
                b"NOBL,Test,AAA,1234567,A,700\nNOBL,Test,BBB,3456789,B,300\n")
    parsed = parse_proshares_holdings(holdings, "NOBL")
    assert parsed.weight.sum() == pytest.approx(1)
    assert parsed["asof"].iloc[0] == "2026-11-03"


def test_ishares_parser_is_snapshot_only():
    raw = (b"iShares Core S&P 500 ETF\nFund Holdings as of,Nov 03 2026\nShares Outstanding,1000\n"
           b"Ticker,Name,Sector,Asset Class,Market Value,Weight (%)\n"
           b"AAA,AAA,Technology,Equity,60000,60\nBBB,BBB,Technology,Equity,40000,40\n")
    parsed, meta = parse_ishares_csv(raw)
    assert parsed.weight.sum() == pytest.approx(1)
    assert meta["shares_outstanding"] == 1000
    assert len(parsed) == 2


def test_split_does_not_count_as_creation():
    d = pd.DataFrame({"fund": ["F", "F"],
                      "date": pd.to_datetime(["2026-11-02", "2026-11-03"]),
                      "nav": [100, 50], "shares_outstanding": [1000, 2000]})
    assert pd.isna(observed_fund_flows(d).creation_usd.iloc[1])


def test_ewma_report_is_measured_against_zero():
    from flowlab.evaluate import evaluate_creation_forecast
    data, _ = fixture_data()
    rows, info = evaluate_creation_forecast(data["fund_days"])
    assert len(rows) > 30
    assert rows.eval("absolute_error_usd >= 0").all()
    assert info["mae_zero_baseline_usd"] >= 0
    assert info["observation_count"] == len(rows)


def test_theoretical_leverage_rebalance_direction():
    from flowlab.evaluate import leveraged_reset_estimate
    long3 = leveraged_reset_estimate(100, 1000, 3, .01)
    short3 = leveraged_reset_estimate(100, 1000, -3, .01)
    assert long3["theoretical_index_rebalance_usd"] == pytest.approx(6000)
    assert short3["theoretical_index_rebalance_usd"] == pytest.approx(12000)


def test_hac_output_never_guesses_without_history():
    from flowlab.factor_eval import test_incremental_flow_premium
    assert test_incremental_flow_premium(pd.DataFrame())["status"].startswith("no point")


def test_quoted_ishares_header_is_accepted():
    raw = (b'Fund Holdings as of,Nov 03 2026\nShares Outstanding,1000\n'
           b'"Ticker","Name","Sector","Asset Class","Market Value","Weight (%)"\n'
           b'"AAA","AAA","Technology","Equity","60000","60"\n'
           b'"BBB","BBB","Energy","Equity","40000","40"\n')
    rows, meta = parse_ishares_csv(raw)
    assert len(rows) == 2
    assert meta["asof"] == "2026-11-03"


def test_twelvedata_key_is_never_put_into_query_url(monkeypatch, tmp_path):
    import json
    from urllib.parse import urlsplit, parse_qs
    from flowlab.vendors import fetch_twelvedata_prices

    def fake_fetch(url, headers=None):
        assert "test-private-key" not in url
        assert "apikey" not in parse_qs(urlsplit(url).query)
        assert headers == {"Authorization": "apikey test-private-key"}
        return json.dumps({"values": [{"datetime": "2026-11-03",
                                       "close": "100", "volume": "2000"}]}).encode()

    monkeypatch.setenv("TWELVEDATA_API_KEY", "test-private-key")
    monkeypatch.setattr("flowlab.vendors.fetch", fake_fetch)
    result = fetch_twelvedata_prices(["AAA"], tmp_path, "2026-11-02", "2026-11-03")
    assert result["rows_fetched"] == 1
    assert (tmp_path / "prices.csv").exists()


def test_proshares_holdings_leading_spaces_and_trailing_comma():
    holdings = (
        b"PORTFOLIO HOLDINGS INFORMATION,,,,\nAS OF 11/5/2026,,,,\n,,,,\n"
        b"Fund Ticker, Fund Name, Security Ticker, Security Sedol, Security Description, Coupon, Maturity Date, Shares/Contracts, Exposure Value (Notional + G/L), Market Value\n"
        b'"NOBL","ProShares ETF","PNR","BLS09M3","PENTAIR PLC",,,3232880,,700,\n'
        b'"NOBL","ProShares ETF","ROP","2749602","ROPER TECH",,,429844,,300,\n'
    )
    parsed = parse_proshares_holdings(holdings, "NOBL")
    assert list(parsed["ticker"]) == ["PNR", "ROP"]
    assert parsed["weight"].sum() == pytest.approx(1.0)
    assert parsed["asof"].iloc[0] == "2026-11-05"


def test_ishares_market_weight_column_is_accepted():
    raw = (
        b'iShares Core S&P 500 ETF\nFund Holdings as of,"Nov 05, 2026"\nShares Outstanding,"1,000.00"\n'
        b"Ticker,Name,Type,Sector,Asset Class,Market Value,Market Weight\n"
        b'"AAPL","APPLE","EQUITY","Information Technology","Equity","60,000.00","60.00"\n'
        b'"NVDA","NVIDIA","EQUITY","Information Technology","Equity","40,000.00","40.00"\n'
    )
    rows, meta = parse_ishares_csv(raw)
    assert len(rows) == 2
    assert rows["weight"].sum() == pytest.approx(1.0)
    assert meta["asof"] == "2026-11-05"
