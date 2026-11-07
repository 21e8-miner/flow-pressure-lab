"""Evaluate a genuine observed ETF share-creation forecast, before any alpha claims."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core import Config, observed_fund_flows


def evaluate_creation_forecast(fund_days: pd.DataFrame,
                               cfg: Config = Config(),
                               min_history: int = 20) -> tuple[pd.DataFrame, dict]:
    """Walk-forward EWM rate against next observed creations, per fund."""
    full = observed_fund_flows(fund_days)
    rows = []
    for fund, g in full.groupby("fund"):
        g = g.sort_values("date").reset_index(drop=True)
        for i in range(min_history, len(g)):
            prev = g.iloc[i - 1]
            actual = g.iloc[i]
            if pd.isna(actual.creation_usd) or actual.date - prev.date > pd.Timedelta(days=5):
                continue
            history = g.iloc[:i].dropna(subset=["creation_rate"])
            if len(history) < min_history - 1:
                continue
            forecast_rate = history.creation_rate.tail(max(20, cfg.forecast_days)).ewm(
                span=cfg.forecast_days, adjust=False).mean().iloc[-1]
            # Scale using information available before the next observation.
            forecast_usd = float(forecast_rate * prev.nav * prev.shares_outstanding)
            true_usd = float(actual.creation_usd)
            rows.append({"fund": fund, "signal_after_close": prev.date.date().isoformat(),
                         "evaluation_close": actual.date.date().isoformat(),
                         "forecast_usd": forecast_usd, "actual_usd": true_usd,
                         "error_usd": true_usd - forecast_usd,
                         "absolute_error_usd": abs(true_usd - forecast_usd),
                         "zero_forecast_absolute_error_usd": abs(true_usd),
                         "direction_correct": bool(np.sign(forecast_usd) == np.sign(true_usd))})
    out = pd.DataFrame(rows)
    report = {"observation_count": len(out),
              "benchmark": "predict no net primary creations/redemptions",
              "method": "trailing five-span EWMA of historical share creation rates",
              "limitation": "The realized NAV is used to value realized share changes, but forecasts use only prior NAV and shares.",
              "sample": "Fund days with one-step changes and at least 20 past observations; no prices or stock returns involved."}
    if not out.empty:
        report.update({"mae_model_usd": float(out.absolute_error_usd.mean()),
                       "mae_zero_baseline_usd": float(out.zero_forecast_absolute_error_usd.mean()),
                       "mae_improvement_vs_zero_pct": float(100 * (1 - out.absolute_error_usd.mean() /
                                                                   out.zero_forecast_absolute_error_usd.mean()))
                       if out.zero_forecast_absolute_error_usd.mean() > 0 else None,
                       "nonzero_direction_hit_rate_pct": float(100 * out.loc[out.actual_usd.ne(0), "direction_correct"].mean())
                       if out.actual_usd.ne(0).any() else None,
                       "funds": sorted(out.fund.unique().tolist())})
    return out, report


def leveraged_reset_estimate(fund_nav: float, shares: float,
                             leverage: float, underlying_day_return: float) -> dict:
    """Textbook levered ETF theoretical end-of-day rebalance, index-equivalent only."""
    if fund_nav <= 0 or shares <= 0 or leverage == 0 or underlying_day_return <= -1:
        raise ValueError("Positive NAV and shares, nonzero leverage, and a valid return are needed")
    aum = fund_nav * shares
    notionals = leverage * (leverage - 1) * aum * underlying_day_return
    return {"leverage": leverage, "fund_aum_usd": aum,
            "underlying_daily_return": underlying_day_return,
            "theoretical_index_rebalance_usd": notionals,
            "method": "L*(L-1)*prior AUM * index daily return",
            "warning": "Theoretical delta exposure, not observed ETF/futures/stock trades; counterparties may internalize."}
