"""Evaluate a genuine observed ETF share-creation forecast, before any alpha claims."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core import Config, observed_fund_flows


def _summarize_slice(df: pd.DataFrame) -> dict:
    mae_model = float(df.absolute_error_usd.mean())
    mae_zero = float(df.zero_forecast_absolute_error_usd.mean())
    rmse_model = float(np.sqrt(np.mean(np.square(df.error_usd.to_numpy(dtype=float)))))
    rmse_zero = float(np.sqrt(np.mean(np.square(df.actual_usd.to_numpy(dtype=float)))))
    nz = df[df.actual_usd.ne(0)]
    corr = None
    if len(df) >= 3 and df.forecast_usd.std(ddof=1) > 0 and df.actual_usd.std(ddof=1) > 0:
        corr = float(np.corrcoef(df.forecast_usd.to_numpy(dtype=float),
                                 df.actual_usd.to_numpy(dtype=float))[0, 1])
    return {
        "observation_count": int(len(df)),
        "nonzero_outcome_count": int(len(nz)),
        "nonzero_outcome_rate_pct": float(100.0 * len(nz) / len(df)) if len(df) else None,
        "mae_model_usd": mae_model,
        "mae_zero_baseline_usd": mae_zero,
        "mae_improvement_vs_zero_pct": float(100 * (1 - mae_model / mae_zero)) if mae_zero > 0 else None,
        "rmse_model_usd": rmse_model,
        "rmse_zero_baseline_usd": rmse_zero,
        "rmse_improvement_vs_zero_pct": float(100 * (1 - rmse_model / rmse_zero)) if rmse_zero > 0 else None,
        "pearson_correlation": corr,
        "nonzero_direction_hit_rate_pct": float(100 * nz["direction_correct"].mean()) if len(nz) else None,
        "date_start": str(df.evaluation_close.min()),
        "date_end": str(df.evaluation_close.max()),
    }


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
        report.update(_summarize_slice(out))
        report["funds"] = sorted(out.fund.unique().tolist())
        report["per_fund"] = {
            fund: _summarize_slice(part)
            for fund, part in out.groupby("fund", sort=True)
        }
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
