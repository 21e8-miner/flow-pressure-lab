"""Command line workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .backtest import walk_forward
from .core import Config, construct_portfolio, create_signal, load_inputs, read_table
from .evaluate import evaluate_creation_forecast, leveraged_reset_estimate
from .factor_eval import make_forward_panel, test_incremental_flow_premium
from .report import observed_report, signal_report
from .vendors import fetch_twelvedata_prices, import_ishares_ivv, import_proshares, inspect_stock_flow


def store_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(prog="flowlab", description="Issuer-based flow research; no broker orders")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("capture-proshares", help="Download official ProShares NAV and latest holdings")
    p.add_argument("fund"); p.add_argument("--data-dir", default="data")
    p = sub.add_parser("capture-ivv", help="Download official iShares IVV snapshot (not historical NAV)")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--estimate-nav", action="store_true", help="Explicitly use holdings market value / shares as a NAV proxy")
    p = sub.add_parser("inspect-stock", help="One user-requested TickerInside stock flow lookup; never archives")
    p.add_argument("ticker")
    p = sub.add_parser("prices", help="Fetch dated genuine Twelve Data daily closes and volumes")
    p.add_argument("--symbols", required=True, help="comma-separated tickers")
    p.add_argument("--start", required=True); p.add_argument("--end", required=True)
    p.add_argument("--data-dir", default="data")
    p = sub.add_parser("benchmark-from-holdings", help="Create benchmark from issuer holdings")
    p.add_argument("fund"); p.add_argument("--data-dir", default="data")
    p.add_argument("--sector-map", help="CSV containing ticker,sector if issuer omits sector")
    p = sub.add_parser("signal", help="Calculate flow scores; portfolio only if all weights covered")
    p.add_argument("--asof", required=True); p.add_argument("--data-dir", default="data")
    p.add_argument("--output-dir", default="output")
    p = sub.add_parser("backtest", help="Run PIT-delayed daily closes only when history available")
    p.add_argument("--start", required=True); p.add_argument("--end", required=True)
    p.add_argument("--cost-bps", type=float, default=5.0)
    p.add_argument("--data-dir", default="data"); p.add_argument("--output-dir", default="output")
    p = sub.add_parser("evaluate-creations", help="Test forecast against zero-flow baseline on real historical NAVs")
    p.add_argument("--data-dir", default="data"); p.add_argument("--output-dir", default="output")
    p = sub.add_parser("test-incremental", help="Test flow signal conditional on momentum, liquidity and sector")
    p.add_argument("--start", required=True); p.add_argument("--end", required=True)
    p.add_argument("--data-dir", default="data"); p.add_argument("--output-dir", default="output")
    p = sub.add_parser("leveraged-reset", help="Theoretical index-equivalent rebalancing, not stock trades")
    p.add_argument("--nav", type=float, required=True); p.add_argument("--shares", type=float, required=True)
    p.add_argument("--leverage", type=float, required=True); p.add_argument("--index-return", type=float, required=True)
    p = sub.add_parser("observed-report", help="Chart small attributed source snapshot, no scores")
    p.add_argument("--input", default="examples/observed_flows_2026-11-03.csv")
    p.add_argument("--output", default="output/observed_flow_dashboard.html")
    args = parser.parse_args()
    if args.command == "capture-proshares":
        print(json.dumps(import_proshares(args.fund, Path(args.data_dir)), indent=2))
    elif args.command == "capture-ivv":
        print(json.dumps(import_ishares_ivv(Path(args.data_dir), estimate_nav=args.estimate_nav), indent=2))
    elif args.command == "inspect-stock":
        print(json.dumps(inspect_stock_flow(args.ticker), indent=2))
    elif args.command == "prices":
        tickers = [t.strip().upper() for t in args.symbols.split(",") if t.strip()]
        print(json.dumps(fetch_twelvedata_prices(tickers, Path(args.data_dir), args.start, args.end), indent=2))
    elif args.command == "benchmark-from-holdings":
        data = Path(args.data_dir)
        h = pd.read_csv(data / "holdings.csv")
        h = h[h.fund.eq(args.fund.upper())]
        if h.empty:
            raise ValueError("No holdings loaded for that fund")
        h = h[h["asof"].eq(h["asof"].max())]
        if args.sector_map:
            sectors = pd.read_csv(args.sector_map)[["ticker", "sector"]]
            h = h.drop(columns="sector", errors="ignore").merge(sectors, on="ticker", how="left")
        if "sector" not in h or h.sector.isna().any():
            raise ValueError("Real sector classifications are required; provide --sector-map ticker,sector")
        b = h[["asof", "ticker", "weight", "sector"]].copy()
        b.weight = b.weight / b.weight.sum()
        b.to_csv(data / "benchmark.csv", index=False)
        print(f"Wrote {len(b)} issuer-derived benchmark constituents, as of {b['asof'].iloc[0]}")
    elif args.command == "signal":
        out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
        data = load_inputs(args.data_dir)
        signal, diag = create_signal(data, args.asof)
        signal.to_csv(out / "signal.csv", index=False)
        weights, info = None, None
        if signal.score.notna().all():
            weights, info = construct_portfolio(signal, data["prices"], args.asof)
            weights.to_csv(out / "research_weights.csv", index=False)
            store_json(out / "portfolio_diagnostics.json", info)
        else:
            diag["portfolio_blocked"] = "Partial coverage. No missing score treated as zero."
        store_json(out / "signal_diagnostics.json", diag)
        signal_report(signal, diag, out / "signal_dashboard.html", weights, info)
        print(json.dumps({**diag, "portfolio": info}, indent=2))
    elif args.command == "backtest":
        out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
        result, summary = walk_forward(load_inputs(args.data_dir), args.start, args.end, args.cost_bps)
        result.to_csv(out / "backtest.csv", index=False)
        store_json(out / "backtest_diagnostics.json", summary)
        print(json.dumps(summary, indent=2))
    elif args.command == "evaluate-creations":
        out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
        fund_days = read_table(Path(args.data_dir) / "fund_days.csv",
                               ("date", "fund", "nav", "shares_outstanding"))
        rows, report = evaluate_creation_forecast(fund_days)
        rows.to_csv(out / "creation_forecast_evaluation.csv", index=False)
        store_json(out / "creation_forecast_evaluation.json", report)
        print(json.dumps(report, indent=2))
    elif args.command == "test-incremental":
        out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
        panel, coverage = make_forward_panel(load_inputs(args.data_dir), args.start, args.end)
        result = test_incremental_flow_premium(panel)
        panel.to_csv(out / "forward_signal_panel.csv", index=False)
        store_json(out / "incremental_factor_test.json", {**coverage, **result})
        print(json.dumps({**coverage, **result}, indent=2))
    elif args.command == "leveraged-reset":
        print(json.dumps(leveraged_reset_estimate(args.nav, args.shares, args.leverage, args.index_return), indent=2))
    elif args.command == "observed-report":
        observed_report(pd.read_csv(args.input), Path(args.output))
        print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
