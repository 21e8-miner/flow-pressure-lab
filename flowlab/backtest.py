"""Walk-forward, delayed execution. Rejects unavailable point-in-time inputs."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core import Config, construct_portfolio, create_signal


def walk_forward(data: dict[str, pd.DataFrame], start: str, end: str,
                 cost_bps: float = 5.0,
                 cfg: Config = Config()) -> tuple[pd.DataFrame, dict]:
    prices = data["prices"].pivot(index="date", columns="ticker", values="close").sort_index()
    dates = prices.index
    rows = []
    skipped: dict[str, int] = {}
    old_weights: pd.Series | None = None
    candidates = [(i, day) for i, day in enumerate(dates)
                  if pd.Timestamp(start) <= day <= pd.Timestamp(end) and i + 2 < len(dates)]
    for idx, day in candidates:
        try:
            signal, diag = create_signal(data, day, cfg)
            weights, info = construct_portfolio(signal, data["prices"], day, cfg)
        except (ValueError, RuntimeError) as error:
            msg = str(error)
            skipped[msg] = skipped.get(msg, 0) + 1
            continue
        trade_date, exit_date = dates[idx + 1], dates[idx + 2]
        tickers = weights.ticker.tolist()
        if not set(tickers).issubset(prices.columns):
            skipped["missing price column"] = skipped.get("missing price column", 0) + 1
            continue
        start_p = prices.loc[trade_date, tickers]
        end_p = prices.loc[exit_date, tickers]
        if start_p.isna().any() or end_p.isna().any() or start_p.le(0).any():
            skipped["missing next-close execution or return prices"] = skipped.get("missing next-close execution or return prices", 0) + 1
            continue
        ret = end_p.to_numpy() / start_p.to_numpy() - 1
        w = pd.Series(weights.target_weight.to_numpy(), index=tickers)
        b = pd.Series(weights.weight.to_numpy(), index=tickers)
        if old_weights is not None:
            all_names = w.index.union(old_weights.index)
            traded = float((w.reindex(all_names, fill_value=0) -
                            old_weights.reindex(all_names, fill_value=0)).abs().sum())
        else:
            traded = float((w - b).abs().sum())
        cost = traded * cost_bps / 10000.0
        rows.append({"signal_asof": day.date().isoformat(),
                     "execution_close": trade_date.date().isoformat(),
                     "return_close": exit_date.date().isoformat(),
                     "gross_return": float(w.to_numpy() @ ret),
                     "net_return": float(w.to_numpy() @ ret - cost),
                     "benchmark_return": float(b.to_numpy() @ ret),
                     "cost_fraction": cost,
                     "net_excess_return": float((w - b).to_numpy() @ ret - cost),
                     "turnover_one_way": traded / 2,
                     "names": len(tickers)})
        old_weights = w
    result = pd.DataFrame(rows)
    summary = {"status": "completed" if len(result) else "no valid backtest rows",
               "trades": len(result), "skipped_reasons": skipped,
               "execution": "signal after close t, execute close t+1, realize close t+1 to t+2",
               "cost_assumption_bps": cost_bps,
               "warning": "No live performance or alpha claim; EWMA is a baseline forecast, not T1A's model."}
    if not result.empty:
        result["cumulative_net_portfolio"] = (1 + result.net_return).cumprod() - 1
        result["cumulative_benchmark"] = (1 + result.benchmark_return).cumprod() - 1
        result["cumulative_net_excess"] = result.cumulative_net_portfolio - result.cumulative_benchmark
        summary["cumulative_net_excess"] = float(result.cumulative_net_excess.iloc[-1])
        summary["annualized_information_ratio"] = (
            float(result.net_excess_return.mean() / result.net_excess_return.std(ddof=1) * np.sqrt(252))
            if len(result) > 30 and result.net_excess_return.std(ddof=1) > 0 else None)
    return result, summary
