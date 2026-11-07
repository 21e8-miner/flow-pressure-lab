"""Point-in-time forward-return diagnostic; coefficients are not tradeable alpha."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core import Config, create_signal


def make_forward_panel(data: dict[str, pd.DataFrame], start: str, end: str,
                       cfg: Config = Config()) -> tuple[pd.DataFrame, dict]:
    close = data["prices"].pivot(index="date", columns="ticker", values="close").sort_index()
    dates = close.index
    panels = []
    skipped = {}
    for i, t in enumerate(dates):
        if t < pd.Timestamp(start) or t > pd.Timestamp(end) or i < 20 or i + 2 >= len(dates):
            continue
        try:
            signal, info = create_signal(data, t, cfg)
        except ValueError as exc:
            skipped[str(exc)] = skipped.get(str(exc), 0) + 1
            continue
        # All constituent prices are required for benchmark excess returns.
        if signal.score.isna().any() or not set(signal.ticker).issubset(close.columns):
            skipped["incomplete cross-sectional signal"] = skipped.get("incomplete cross-sectional signal", 0) + 1
            continue
        names = signal.ticker.tolist()
        p0 = close.loc[dates[i - 20], names]
        p1 = close.loc[t, names]
        buy = close.loc[dates[i + 1], names]
        sell = close.loc[dates[i + 2], names]
        if pd.concat([p0, p1, buy, sell], axis=1).isna().any().any():
            skipped["incomplete price history"] = skipped.get("incomplete price history", 0) + 1
            continue
        forward = sell.to_numpy() / buy.to_numpy() - 1.0
        benchmark_forward = float(forward @ signal.weight.to_numpy())
        part = signal[["ticker", "sector", "weight", "score", "adv20_usd"]].copy()
        part["signal_asof"] = t.date().isoformat()
        part["trade_close"] = dates[i + 1].date().isoformat()
        part["realization_close"] = dates[i + 2].date().isoformat()
        part["momentum20"] = p1.to_numpy() / p0.to_numpy() - 1
        part["forward_excess"] = forward - benchmark_forward
        panels.append(part)
    result = pd.concat(panels, ignore_index=True) if panels else pd.DataFrame()
    return result, {"days": len(panels), "skipped": skipped,
                    "definition": "signal after close t; enter close t+1, exit close t+2; out-of-sample forward returns"}


def _standardize(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - x.mean()) / sd if sd > 0 else np.zeros(len(x))


def _nw_mean_tstat(series: np.ndarray, lag: int = 5) -> tuple[float, float | None]:
    n = len(series)
    if n <= lag + 1:
        return float(series.mean()), None
    x = series - series.mean()
    long_run_var = float(x @ x / n)
    for k in range(1, min(lag, n - 1) + 1):
        autocov = float(x[k:] @ x[:-k] / n)
        long_run_var += 2 * (1 - k / (lag + 1)) * autocov
    se = np.sqrt(max(long_run_var, 0) / n)
    return float(series.mean()), float(series.mean() / se) if se > 0 else None


def test_incremental_flow_premium(panel: pd.DataFrame,
                                  min_days: int = 25, min_names: int = 20) -> dict:
    """Fama–MacBeth-style daily cross-section with 5-lag HAC inference."""
    if panel.empty:
        return {"status": "no point-in-time signal and return panel"}
    b_flow, b_simple = [], []
    for _, g in panel.groupby("signal_asof", sort=True):
        g = g.dropna(subset=["score", "momentum20", "forward_excess", "adv20_usd", "sector"])
        if len(g) < min_names:
            continue
        flow = _standardize(g.score.to_numpy(dtype=float))
        mom = _standardize(g.momentum20.to_numpy(dtype=float))
        log_adv = _standardize(np.log(g.adv20_usd.to_numpy(dtype=float)))
        sector_dummies = pd.get_dummies(g.sector, drop_first=True).to_numpy(dtype=float)
        x = np.column_stack([np.ones(len(g)), flow, mom, log_adv, sector_dummies])
        raw = np.column_stack([np.ones(len(g)), flow])
        y = g.forward_excess.to_numpy(dtype=float)
        if np.linalg.matrix_rank(x) < x.shape[1] or np.linalg.matrix_rank(raw) < 2:
            continue
        b_flow.append(np.linalg.lstsq(x, y, rcond=None)[0][1])
        b_simple.append(np.linalg.lstsq(raw, y, rcond=None)[0][1])
    if len(b_flow) < min_days:
        return {"status": "insufficient test history", "valid_days": len(b_flow),
                "required_days": min_days, "min_names_per_day": min_names}
    adjusted, t_adjusted = _nw_mean_tstat(np.asarray(b_flow))
    simple, t_simple = _nw_mean_tstat(np.asarray(b_simple))
    return {"status": "observational cross-sectional regression", "valid_days": len(b_flow),
            "mean_daily_bps_per_one_sd_flow_raw": simple * 10000,
            "mean_daily_bps_per_one_sd_flow_adjusted": adjusted * 10000,
            "tstat_hac5_adjusted": t_adjusted,
            "tstat_hac5_raw": t_simple,
            "controls": "20-session momentum, log dollar ADV, sector fixed effects; not market cap",
            "warning": "Not causally identified; no multiple-testing correction, execution cost or exposure limits."}
