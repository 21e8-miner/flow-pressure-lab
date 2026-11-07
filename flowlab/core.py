"""Point-in-time flow reconstruction and constrained portfolio tilts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass(frozen=True)
class Config:
    forecast_days: int = 5
    min_flow_observations: int = 5
    min_adv_sessions: int = 20
    max_holdings_age_days: int = 5
    max_price_age_days: int = 5
    max_benchmark_age_days: int = 5
    max_weight_tilt: float = 0.0035
    target_tracking_error: float = 0.01
    minimum_risk_sessions: int = 60


def read_table(path: str | Path, required: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    for col in ("date", "asof"):
        if col in frame:
            frame[col] = pd.to_datetime(frame[col], errors="raise").dt.normalize()
    return frame


def load_inputs(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    base = Path(data_dir)
    definitions = {
        "fund_days": ("date", "fund", "nav", "shares_outstanding"),
        "holdings": ("asof", "fund", "ticker", "weight"),
        "prices": ("date", "ticker", "close", "volume"),
        "benchmark": ("asof", "ticker", "weight", "sector"),
    }
    return {name: read_table(base / f"{name}.csv", cols) for name, cols in definitions.items()}


def observed_fund_flows(fund_days: pd.DataFrame) -> pd.DataFrame:
    """Net primary-market creations/redemptions, not secondary ETF trading."""
    d = fund_days.sort_values(["fund", "date"]).copy()
    if d.duplicated(["fund", "date"]).any():
        raise ValueError("Duplicate fund-day rows")
    if (d[["nav", "shares_outstanding"]] <= 0).any().any():
        raise ValueError("NAV and shares outstanding must be positive")
    prev = d.groupby("fund")["shares_outstanding"].shift(1)
    prev_date = d.groupby("fund")["date"].shift(1)
    valid = (d["date"] - prev_date).dt.days.le(5)
    nav_prev = d.groupby("fund")["nav"].shift(1)
    share_ratio = d["shares_outstanding"] / prev
    nav_ratio = d["nav"] / nav_prev
    # Splits mechanically change outstanding shares without representing creations.
    split_like = pd.Series(False, index=d.index)
    for factor in (2, 3, 4, .5, 1 / 3, .25):
        split_like |= (share_ratio.sub(factor).abs().lt(.04 * factor)
                       & nav_ratio.sub(1 / factor).abs().lt(.04 / factor))
    valid &= ~split_like
    if "corporate_action" in d:
        valid &= ~d["corporate_action"].fillna(False).astype(bool)
    d["net_created_shares"] = (d["shares_outstanding"] - prev).where(valid)
    d["creation_usd"] = d["net_created_shares"] * d["nav"]
    d["creation_rate"] = (d["net_created_shares"] / prev).where(prev.gt(0))
    return d


def forecast_fund_flows(flows: pd.DataFrame, asof: pd.Timestamp, cfg: Config) -> pd.DataFrame:
    """Transparent trailing EWMA baseline, not Tier1's proprietary predictor."""
    rows = []
    for fund, part in flows[flows.date.le(asof)].groupby("fund"):
        part = part.sort_values("date")
        recent = part.dropna(subset=["creation_rate"]).tail(max(20, cfg.forecast_days))
        if len(recent) < cfg.min_flow_observations:
            continue
        last = part.iloc[-1]
        if asof - last.date > pd.Timedelta(days=cfg.max_holdings_age_days):
            continue
        rate = recent.creation_rate.ewm(span=cfg.forecast_days, adjust=False).mean().iloc[-1]
        rows.append({
            "fund": fund, "date": last.date, "nav": last.nav,
            "shares_outstanding": last.shares_outstanding,
            "actual_creation_usd": last.creation_usd,
            "forecast_creation_usd": rate * last.nav * last.shares_outstanding,
            "observations": len(recent),
        })
    return pd.DataFrame(rows, columns=["fund", "date", "nav", "shares_outstanding",
                                       "actual_creation_usd", "forecast_creation_usd", "observations"])


def asof_holdings(holdings: pd.DataFrame, asof: pd.Timestamp, cfg: Config) -> pd.DataFrame:
    h = holdings[holdings["asof"].le(asof)].copy()
    if h.empty:
        return h
    newest = h.groupby("fund")["asof"].transform("max")
    h = h[(h["asof"].eq(newest)) & ((asof - h["asof"]).dt.days.le(cfg.max_holdings_age_days))]
    if h.duplicated(["fund", "ticker"]).any():
        raise ValueError("Duplicate security in a fund snapshot")
    if h.weight.lt(0).any() or h.weight.gt(1).any():
        raise ValueError("Holdings weights must be decimal fractions")
    if h.groupby("fund").weight.sum().gt(1.02).any():
        raise ValueError("Fund holdings weights exceed 102%")
    return h


def asof_benchmark(benchmark: pd.DataFrame, asof: pd.Timestamp, cfg: Config = Config()) -> pd.DataFrame:
    b = benchmark[benchmark["asof"].le(asof)].copy()
    if b.empty:
        raise ValueError("No benchmark constituents on or before as-of date")
    date = b["asof"].max()
    if asof - date > pd.Timedelta(days=cfg.max_benchmark_age_days):
        raise ValueError("Benchmark constituents are stale")
    b = b[b["asof"].eq(date)].copy()
    if b.ticker.duplicated().any() or b.weight.lt(0).any():
        raise ValueError("Duplicate benchmark ticker or negative weight")
    if not 0.99 <= b.weight.sum() <= 1.01:
        raise ValueError("Benchmark must sum to approximately 1.0")
    b["weight"] = b.weight / b.weight.sum()
    return b


def asof_liquidity(prices: pd.DataFrame, asof: pd.Timestamp, cfg: Config) -> pd.DataFrame:
    p = prices[prices.date.le(asof)].sort_values(["ticker", "date"])
    if p.duplicated(["ticker", "date"]).any():
        raise ValueError("Duplicate stock price date")
    if (p[["close", "volume"]] <= 0).any().any():
        raise ValueError("Prices and volumes must be positive")
    rows = []
    for ticker, part in p.groupby("ticker"):
        latest = part.iloc[-1]
        if asof - latest.date > pd.Timedelta(days=cfg.max_price_age_days):
            continue
        recent = part.tail(cfg.min_adv_sessions)
        if len(recent) < cfg.min_adv_sessions:
            continue
        rows.append({"ticker": ticker, "price_date": latest.date,
                     "adv20_usd": float((recent.close * recent.volume).mean()),
                     "close": float(latest.close)})
    return pd.DataFrame(rows, columns=["ticker", "price_date", "adv20_usd", "close"])


def available_inputs(data: dict[str, pd.DataFrame], asof: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """Use actual release dates when known; otherwise conservatively lag fund disclosures."""
    result = {}
    for name, frame in data.items():
        if "available_on" in frame:
            released = pd.to_datetime(frame["available_on"])
            result[name] = frame[released.le(asof)].copy()
        elif name in {"fund_days", "holdings", "benchmark"}:
            col = "date" if name == "fund_days" else "asof"
            result[name] = frame[frame[col].lt(asof)].copy()
        else:
            result[name] = frame.copy()
    return result


def create_signal(data: dict[str, pd.DataFrame], asof: str | pd.Timestamp,
                  cfg: Config = Config()) -> tuple[pd.DataFrame, dict]:
    t = pd.Timestamp(asof).normalize()
    data = available_inputs(data, t)
    flows = forecast_fund_flows(observed_fund_flows(data["fund_days"]), t, cfg)
    h = asof_holdings(data["holdings"], t, cfg)
    b = asof_benchmark(data["benchmark"], t, cfg)
    adv = asof_liquidity(data["prices"], t, cfg)
    active_funds = set(flows.fund) & set(h.fund)
    if not active_funds:
        raise ValueError("No fund has both fresh holdings and enough historical creation observations")
    h = h[h.fund.isin(active_funds)]
    f = h.merge(flows[["fund", "actual_creation_usd", "forecast_creation_usd"]], on="fund")
    f["pred_demand"] = f.weight * f.forecast_creation_usd
    f["last_observed_demand"] = f.weight * f.actual_creation_usd
    agg = f.groupby("ticker", as_index=False).agg(
        forecast_demand_usd=("pred_demand", "sum"),
        observed_last_demand_usd=("last_observed_demand", "sum"),
        funds_measured=("fund", "nunique"),
    )
    merged = b.merge(agg, on="ticker", how="left").merge(adv, on="ticker", how="left")
    merged["covered_by_funds"] = merged.funds_measured.notna()
    merged["score"] = merged.forecast_demand_usd / merged.adv20_usd
    merged.loc[~merged.covered_by_funds, "score"] = np.nan
    usable = merged.score.notna()
    diagnostics = {
        "asof": t.strftime("%Y-%m-%d"), "funds_used": sorted(active_funds),
        "stocks_in_benchmark": len(merged), "stocks_with_scores": int(usable.sum()),
        "benchmark_weight_with_scores": round(float(merged.loc[usable, "weight"].sum()), 6),
        "not_modeled": ["unobserved funds", "retirement contributions", "CTA",
                         "vol-control", "risk parity", "dealer hedging", "borrow/issuance response"],
        "signal_type": "lag-aware creation-equivalent forecast; not executed underlying trades or validated alpha",
        "transmission_model": "unmeasured: an ETF creation can be in-kind and need not produce spot buying",
        "score_unit": "forecast dollars / trailing 20-session stock-dollar ADV",
    }
    return merged.sort_values("score", ascending=False, na_position="last"), diagnostics


def estimate_tracking_error(tilts: pd.Series, prices: pd.DataFrame,
                            asof: pd.Timestamp, cfg: Config) -> float | None:
    tickers = list(tilts.index)
    frame = prices[prices.date.le(asof)].pivot(index="date", columns="ticker", values="close")
    if not set(tickers).issubset(frame.columns):
        return None
    recent = frame[tickers].dropna().tail(cfg.minimum_risk_sessions + 1)
    if len(recent) < cfg.minimum_risk_sessions + 1:
        return None
    returns = recent.pct_change(fill_method=None).dropna()
    active_returns = returns @ tilts
    return float(active_returns.std(ddof=1) * np.sqrt(252))


def construct_portfolio(signal: pd.DataFrame, prices: pd.DataFrame,
                        asof: str | pd.Timestamp, cfg: Config = Config()) -> tuple[pd.DataFrame, dict]:
    """Constrained fully-invested long-only tilts; no alpha claims."""
    if signal.score.isna().any():
        raise ValueError("Refusing to optimize partial coverage: missing scores. Narrow benchmark or expand inputs.")
    s = signal.sort_values("ticker").reset_index(drop=True).copy()
    if len(s) < 2:
        raise ValueError("Need at least two benchmark securities")
    z = s.score.to_numpy(dtype=float)
    sd = np.std(z)
    z = np.clip((z - z.mean()) / sd, -3, 3) if sd > 0 else np.zeros_like(z)
    b = s.weight.to_numpy(dtype=float)
    bounds = [(max(-cfg.max_weight_tilt, -float(w)), min(cfg.max_weight_tilt, 1 - float(w)))
              for w in b]
    sectors = s.sector.fillna("UNKNOWN").to_numpy()
    groups = [np.flatnonzero(sectors == sector) for sector in np.unique(sectors)]
    constraints = [{"type": "eq", "fun": lambda x, idx=idx: float(x[idx].sum()),
                    "jac": lambda x, idx=idx: np.isin(np.arange(len(x)), idx).astype(float)}
                   for idx in groups]
    strength = 600.0
    result = minimize(lambda x: -float(z @ x) + (strength / 2) * float(x @ x),
                      np.zeros(len(s)), method="SLSQP",
                      jac=lambda x: -z + strength * x,
                      bounds=bounds, constraints=constraints,
                      options={"maxiter": 500, "ftol": 1e-12})
    if not result.success:
        raise RuntimeError(f"Portfolio optimizer: {result.message}")
    delta = pd.Series(result.x, index=s.ticker)
    te = estimate_tracking_error(delta, prices, pd.Timestamp(asof), cfg)
    if te is not None and te > cfg.target_tracking_error:
        delta *= cfg.target_tracking_error / te
        te = estimate_tracking_error(delta, prices, pd.Timestamp(asof), cfg)
    s["tilt"] = delta.to_numpy()
    s["target_weight"] = s.weight + s.tilt
    if abs(s.target_weight.sum() - 1) > 1e-8 or s.target_weight.lt(-1e-9).any():
        raise ValueError("Target portfolio violates funding or long-only constraints")
    info = {"asof": str(pd.Timestamp(asof).date()),
            "ex_ante_tracking_error": te,
            "tracking_error_status": "measured from historical closes" if te is not None else "unavailable: <60 matched price returns",
            "active_share": float(s.tilt.abs().sum() / 2),
            "maximum_absolute_tilt": float(s.tilt.abs().max()),
            "sector_neutral": all(abs(s.loc[s.sector.eq(sec), "tilt"].sum()) < 1e-7 for sec in np.unique(sectors)),
            "purpose": "research weights, not executable trade instructions"}
    return s.sort_values("tilt", ascending=False), info
