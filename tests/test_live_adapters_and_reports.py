"""Offline/mocked unit tests for hardened vendor parsers, Yahoo Finance fallback,
extended evaluation metrics, and empirical HTML dashboard rendering."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from flowlab.evaluate import evaluate_creation_forecast
from flowlab.report import empirical_report
from flowlab.vendors import (
    fetch_prices,
    fetch_yahoo_prices,
    parse_proshares_holdings,
    parse_proshares_nav,
    parse_yahoo_chart,
)


def test_proshares_holdings_normalizes_slash_share_classes():
    """Live ProShares CSVs encode BRK/B and BF/B with slashes; normalize to '-'."""
    raw = (
        b"PORTFOLIO HOLDINGS INFORMATION,,,,\nAS OF 11/20/2026,,,,\n,,,,\n"
        b"Fund Ticker, Fund Name, Security Ticker, Security Sedol, Security Description, "
        b"Coupon, Maturity Date, Shares/Contracts, Exposure Value (Notional + G/L), Market Value\n"
        b'"UPRO","ProShares UltraPro S&P500","BRK/B","2073390","BERKSHIRE HATHAWAY",,,100,,600,\n'
        b'"UPRO","ProShares UltraPro S&P500","BF/B","2146838","BROWN-FORMAN",,,200,,400,\n'
        b'"UPRO","ProShares UltraPro S&P500","","","S&P 500 Index SWAP",,,0,5000,,\n'
    )
    parsed = parse_proshares_holdings(raw, "UPRO")
    assert set(parsed["ticker"]) == {"BRK-B", "BF-B"}
    assert parsed["weight"].sum() == pytest.approx(1.0)
    assert parsed.loc[parsed["ticker"] == "BRK-B", "weight"].iloc[0] == pytest.approx(0.6)


def test_proshares_nav_drops_nonpositive_and_deduplicates():
    raw = (
        b"Date,ProShares Name,Ticker,NAV,Prior NAV,Shares Outstanding (000),Assets Under Management\n"
        b"11/20/2026,Test,NOBL,$58.75,$59.02,202000,11866591117\n"
        b"11/20/2026,Test,NOBL,$58.76,$59.02,202000,11866591117\n"
        b"11/19/2026,Test,NOBL,0,59.02,202050,0\n"
        b"11/18/2026,Test,NOBL,--,59.02,202050,0\n"
    )
    parsed = parse_proshares_nav(raw, "NOBL")
    assert len(parsed) == 1
    assert parsed["date"].iloc[0] == "2026-11-20"
    assert parsed["nav"].iloc[0] == pytest.approx(58.76)
    assert parsed["shares_outstanding"].iloc[0] == pytest.approx(202_000_000.0)


def _yahoo_payload(dates: list[str], closes: list[float | None],
                   volumes: list[int | None], adjcloses: list[float | None] | None = None) -> bytes:
    ts = [int(datetime.fromisoformat(d).replace(hour=14, minute=30, tzinfo=timezone.utc).timestamp())
          for d in dates]
    indicators = {"quote": [{"close": closes, "volume": volumes}]}
    if adjcloses is not None:
        indicators["adjclose"] = [{"adjclose": adjcloses}]
    return json.dumps({"chart": {"result": [{"timestamp": ts, "indicators": indicators}], "error": None}}).encode()


def test_parse_yahoo_chart_filters_nulls_range_and_supports_adjclose():
    payload = _yahoo_payload(
        dates=["2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"],
        closes=[100.0, None, 102.0, 104.0],
        volumes=[1_000_000, 500_000, 0, 2_000_000],
        adjcloses=[99.5, None, 101.5, 104.0],
    )
    df = parse_yahoo_chart(payload, "AAPL", start="2026-11-18", end="2026-11-20")
    assert list(df["date"]) == ["2026-11-20"]
    assert df["close"].iloc[0] == pytest.approx(104.0)

    df_adj = parse_yahoo_chart(payload, "AAPL", use_adjclose=True)
    assert list(df_adj["date"]) == ["2026-11-17", "2026-11-20"]
    assert df_adj["close"].iloc[0] == pytest.approx(99.5)


def test_parse_yahoo_chart_raises_on_api_error():
    payload = json.dumps({"chart": {"result": None, "error": {"code": "Not Found"}}}).encode()
    with pytest.raises(RuntimeError, match="Yahoo Finance rejected"):
        parse_yahoo_chart(payload, "BADSYM")


def test_fetch_yahoo_prices_and_auto_provider_selection(monkeypatch, tmp_path):
    called_urls = []

    def fake_fetch(url, headers=None):
        called_urls.append(url)
        return _yahoo_payload(["2026-11-19", "2026-11-20"], [50.0, 51.0], [100_000, 120_000])

    monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)
    monkeypatch.setattr("flowlab.vendors.fetch", fake_fetch)
    res = fetch_prices(["BF/B"], tmp_path, "2026-11-18", "2026-11-20", provider="auto")
    assert res["provider"] == "yahoo"
    assert res["symbols_fetched"] == 1
    assert res["rows_fetched"] == 2
    assert any("BF-B" in u for u in called_urls)
    saved = pd.read_csv(tmp_path / "prices.csv")
    assert list(saved["ticker"].unique()) == ["BF-B"]


def test_fetch_yahoo_prices_skip_errors_records_failures(monkeypatch, tmp_path):
    def fake_fetch(url, headers=None):
        if "FAIL" in url:
            raise RuntimeError("HTTP 404")
        return _yahoo_payload(["2026-11-20"], [100.0], [50_000])

    monkeypatch.setattr("flowlab.vendors.fetch", fake_fetch)
    res = fetch_yahoo_prices(["AAPL", "FAIL"], tmp_path, "2026-11-19", "2026-11-20",
                             max_workers=1, skip_errors=True)
    assert res["symbols_fetched"] == 1
    assert "FAIL" in res["failed_symbols"]


def test_evaluate_creation_forecast_reports_rmse_corr_and_per_fund():
    dates = pd.bdate_range("2026-07-01", periods=60)
    f1 = pd.DataFrame({
        "date": dates, "fund": "F1", "nav": 100.0,
        "shares_outstanding": [100_000 + i * 500 for i in range(len(dates))],
    })
    f2 = pd.DataFrame({
        "date": dates, "fund": "F2", "nav": 50.0,
        "shares_outstanding": [200_000 + (1000 if i % 2 == 0 else -1000) for i in range(len(dates))],
    })
    rows, report = evaluate_creation_forecast(pd.concat([f1, f2], ignore_index=True))
    assert not rows.empty
    for key in (
        "rmse_model_usd", "rmse_zero_baseline_usd", "rmse_improvement_vs_zero_pct",
        "pearson_correlation", "nonzero_outcome_rate_pct", "per_fund",
    ):
        assert key in report
    assert set(report["per_fund"].keys()) == {"F1", "F2"}
    assert report["rmse_model_usd"] >= 0
    assert report["rmse_zero_baseline_usd"] >= 0


def test_empirical_report_renders_self_contained_html(tmp_path):
    eval_summary = {
        "observation_count": 100,
        "nonzero_outcome_count": 55,
        "nonzero_outcome_rate_pct": 55.0,
        "mae_model_usd": 12e6,
        "mae_zero_baseline_usd": 10e6,
        "mae_improvement_vs_zero_pct": -20.0,
        "rmse_model_usd": 25e6,
        "rmse_zero_baseline_usd": 22e6,
        "rmse_improvement_vs_zero_pct": -13.6,
        "pearson_correlation": -0.15,
        "nonzero_direction_hit_rate_pct": 62.0,
        "date_start": "2026-01-02",
        "date_end": "2026-11-20",
        "funds": ["NOBL"],
        "per_fund": {
            "NOBL": {
                "observation_count": 100,
                "nonzero_outcome_rate_pct": 55.0,
                "mae_model_usd": 12e6,
                "mae_zero_baseline_usd": 10e6,
                "mae_improvement_vs_zero_pct": -20.0,
                "rmse_model_usd": 25e6,
                "rmse_zero_baseline_usd": 22e6,
                "rmse_improvement_vs_zero_pct": -13.6,
                "pearson_correlation": -0.15,
                "nonzero_direction_hit_rate_pct": 62.0,
                "date_start": "2026-01-02",
                "date_end": "2026-11-20",
            }
        },
    }
    bt = pd.DataFrame({
        "return_close": ["2026-11-18", "2026-11-19", "2026-11-20"],
        "gross_return": [0.001, -0.0005, 0.0002],
        "net_return": [0.0009, -0.0006, 0.0001],
        "benchmark_return": [0.001, -0.0004, 0.0002],
        "turnover_one_way": [0.015, 0.018, 0.012],
        "cumulative_net_excess": [-0.0001, -0.0003, -0.0004],
    })
    sig = pd.DataFrame({
        "ticker": ["WMT", "BF-B"],
        "sector": ["Consumer Staples", "Consumer Staples"],
        "weight": [0.5, 0.5],
        "forecast_demand_usd": [1e6, -5e5],
        "adv20_usd": [1e9, 1e8],
        "score": [0.001, -0.005],
    })
    out_html = tmp_path / "empirical_flow_dashboard.html"
    empirical_report(
        creation_eval=eval_summary,
        path=out_html,
        signal=sig,
        signal_diag={"asof": "2026-11-21"},
        portfolio=pd.DataFrame({"ticker": ["WMT", "BF-B"], "tilt": [0.001, -0.001], "target_weight": [0.501, 0.499]}),
        portfolio_info={"ex_ante_tracking_error": 0.0027, "active_share": 0.024, "sector_neutral": True},
        backtest=bt,
        backtest_summary={"trades": 3, "cumulative_net_excess": -0.0004, "annualized_information_ratio": -0.5},
        incremental={"valid_days": 30, "mean_daily_bps_per_one_sd_flow_adjusted": 1.2, "tstat_hac5_adjusted": 0.8},
    )
    rendered = out_html.read_text(encoding="utf-8")
    assert "KILL CRITERION TRIGGERED" in rendered
    assert "<svg " in rendered
    assert "BF-B" in rendered
    assert "NOBL" in rendered
