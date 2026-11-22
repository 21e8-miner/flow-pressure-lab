"""Issuer and market-data adapters. All HTTP requests use the configured User-Agent."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from io import StringIO
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd

USER_AGENT = "OpenAI File Downloader, XaiImageApiFetch/1.0"
PROSHARES_ROOT = "https://accounts.profunds.com/etfdata/ByFund"
ISHARES_IVV = "https://www.ishares.com/us/products/239726/ishares-core-s-p-500-etf/latest-holdings.csv"
YAHOO_CHART_ROOT = "https://query1.finance.yahoo.com/v8/finance/chart"


def fetch(url: str, headers: dict[str, str] | None = None) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "text/csv,application/json,*/*"}
    if headers:
        request_headers.update(headers)
    req = Request(url, headers=request_headers)
    with urlopen(req, timeout=35) as response:
        return response.read()


def append_unique(existing: Path, addition: pd.DataFrame, keys: list[str]) -> None:
    existing.parent.mkdir(parents=True, exist_ok=True)
    if existing.exists():
        old = pd.read_csv(existing)
        addition = pd.concat([old, addition], ignore_index=True)
    addition = addition.drop_duplicates(keys, keep="last").sort_values(keys)
    addition.to_csv(existing, index=False)


def parse_proshares_nav(payload: bytes, fund: str) -> pd.DataFrame:
    d = pd.read_csv(StringIO(payload.decode("utf-8-sig")), index_col=False)
    d.columns = [str(c).strip() for c in d.columns]
    needed = {"Date", "NAV", "Shares Outstanding (000)"}
    if not needed.issubset(d.columns):
        raise ValueError(f"{fund}: ProShares NAV format changed: {list(d.columns)}")
    out = pd.DataFrame({
        "date": pd.to_datetime(d["Date"], errors="coerce").dt.strftime("%Y-%m-%d"),
        "fund": fund,
        "nav": pd.to_numeric(d["NAV"].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce"),
        "shares_outstanding": pd.to_numeric(
            d["Shares Outstanding (000)"].astype(str).str.replace(r"[$,]", "", regex=True),
            errors="coerce",
        ) * 1000,
    })
    out = out.dropna()
    out = out[out["nav"].gt(0) & out["shares_outstanding"].gt(0)]
    return out.drop_duplicates(["fund", "date"], keep="last").sort_values("date").reset_index(drop=True)


def parse_proshares_holdings(payload: bytes, fund: str) -> pd.DataFrame:
    content = payload.decode("utf-8-sig")
    lines = content.splitlines()
    header = next((i for i, line in enumerate(lines) if line.startswith("Fund Ticker,")), None)
    if header is None:
        raise ValueError("ProShares holdings CSV header not found")
    preamble = " ".join(lines[:header])
    match = re.search(r"AS OF\s+([A-Za-z]+\s+\d+,?\s*\d{4}|\d{1,2}/\d{1,2}/\d{4})", preamble, re.I)
    if not match:
        raise ValueError("ProShares holdings as-of date missing")
    asof = pd.to_datetime(match.group(1)).strftime("%Y-%m-%d")
    d = pd.read_csv(StringIO("\n".join(lines[header:])), index_col=False)
    d.columns = [str(c).strip() for c in d.columns]
    needed = {"Security Ticker", "Market Value"}
    if not needed.issubset(d.columns):
        raise ValueError(f"ProShares holdings format changed: {list(d.columns)}")
    d["market_value"] = pd.to_numeric(d["Market Value"].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")
    # ProShares encodes share-class tickers with '/' (e.g., BRK/B, BF/B); normalize to '-' to match iShares & Yahoo.
    d["ticker"] = (
        d["Security Ticker"]
        .astype(str)
        .str.strip()
        .str.replace("/", "-", regex=False)
        .str.replace(" ", "-", regex=False)
    )
    d = d[d.ticker.str.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}") & d.market_value.gt(0)].copy()
    if len(d) < 2:
        raise ValueError("No equity holdings in file; reject derivative-only fund")
    if "Exposure Value (Notional + G/L)" in d:
        # Exclude derivative/swap notional lines; do not treat contracts as stock ownership.
        notional = pd.to_numeric(d["Exposure Value (Notional + G/L)"].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")
        d = d[notional.fillna(0).eq(0)]
    if d.ticker.duplicated().any():
        d = d.groupby("ticker", as_index=False).market_value.sum()
    total = d.market_value.sum()
    out = pd.DataFrame({"asof": asof, "fund": fund, "ticker": d.ticker,
                        "weight": d.market_value / total})
    return out


def import_proshares(fund: str, out_dir: Path) -> dict:
    fund = fund.upper()
    if not re.fullmatch(r"[A-Z]{2,6}", fund):
        raise ValueError("Invalid ProShares fund symbol")
    base = out_dir / "raw" / "proshares"
    base.mkdir(parents=True, exist_ok=True)
    urls = {"nav": f"{PROSHARES_ROOT}/{fund}-historical_nav.csv",
            "holdings": f"{PROSHARES_ROOT}/{fund}-psdlyhld.csv"}
    payloads = {key: fetch(url) for key, url in urls.items()}
    nav = parse_proshares_nav(payloads["nav"], fund)
    holdings = parse_proshares_holdings(payloads["holdings"], fund)
    if nav.empty or holdings.empty:
        raise ValueError(f"{fund}: vendor files contained no usable data")
    for key, payload in payloads.items():
        (base / f"{fund}-{key}.csv").write_bytes(payload)
    append_unique(out_dir / "fund_days.csv", nav, ["fund", "date"])
    append_unique(out_dir / "holdings.csv", holdings, ["fund", "asof", "ticker"])
    provenance = {"fund": fund, "source": "ProShares official downloadable files",
                  "urls": urls, "latest_nav_date": max(nav.date),
                  "holdings_asof": holdings["asof"].iloc[0],
                  "note": "Shares outstanding from vendor measured in thousands, converted to shares. "
                          "Holdings weights normalized over identifiable positive-value equities; "
                          "do not use for derivatives or international security keys."}
    (base / f"{fund}-provenance.json").write_text(json.dumps(provenance, indent=2))
    return provenance


def parse_ishares_csv(payload: bytes, fund: str = "IVV") -> tuple[pd.DataFrame, dict]:
    content = payload.decode("utf-8-sig")
    lines = content.splitlines()
    import csv
    header = next((i for i, row in enumerate(csv.reader(lines))
                   if row and row[0].strip() == "Ticker"
                   and ({"Weight (%)", "Market Weight"} & {c.strip() for c in row})), None)
    if header is None:
        raise ValueError("iShares holdings table header not found")
    metadata = {}
    for row in csv.reader(lines[:header]):
        if len(row) >= 2 and row[0].strip() in {"Fund Holdings as of", "Shares Outstanding"}:
            metadata[row[0].strip()] = row[1].strip()
    if "Fund Holdings as of" not in metadata or "Shares Outstanding" not in metadata:
        raise ValueError("iShares required snapshot metadata absent")
    asof = pd.to_datetime(metadata["Fund Holdings as of"]).strftime("%Y-%m-%d")
    shares_outstanding = float(metadata["Shares Outstanding"].replace(",", ""))
    d = pd.read_csv(StringIO("\n".join(lines[header:])), on_bad_lines="skip", index_col=False)
    d.columns = [str(c).strip() for c in d.columns]
    weight_col = "Weight (%)" if "Weight (%)" in d.columns else "Market Weight"
    req = {"Ticker", weight_col, "Asset Class", "Market Value"}
    if not req.issubset(d.columns):
        raise ValueError("iShares holdings fields absent")
    market_values = pd.to_numeric(
        d["Market Value"].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")
    total_published_market_value = float(market_values[market_values.gt(0)].sum())
    d = d[d["Asset Class"].eq("Equity")].copy()
    d["weight"] = pd.to_numeric(d[weight_col], errors="coerce") / 100.0
    d["ticker"] = d["Ticker"].astype(str).str.strip().str.replace(" ", "-", regex=False)
    d = d[d.ticker.str.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}") & d.weight.gt(0)]
    out = pd.DataFrame({"asof": asof, "fund": fund, "ticker": d.ticker, "weight": d.weight, "sector": d["Sector"] if "Sector" in d else None})
    if out.ticker.duplicated().any():
        out = out.groupby(["asof", "fund", "ticker"], as_index=False).agg({"weight": "sum", "sector": "first"})
    return out, {"asof": asof, "shares_outstanding": shares_outstanding,
                 "holdings_market_value_sum_usd": total_published_market_value,
                 "nav_proxy_usd": total_published_market_value / shares_outstanding,
                 "equity_weight_sum": float(out.weight.sum()),
                 "note": "A single holdings snapshot is NOT a NAV history and cannot establish creations."}


def import_ishares_ivv(out_dir: Path, estimate_nav: bool = False) -> dict:
    payload = fetch(ISHARES_IVV)
    holdings, meta = parse_ishares_csv(payload)
    raw = out_dir / "raw" / "ishares"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / f"IVV-{meta['asof']}.csv").write_bytes(payload)
    append_unique(out_dir / "holdings.csv", holdings, ["fund", "asof", "ticker"])
    if estimate_nav:
        nav = pd.DataFrame([{"date": meta["asof"], "fund": "IVV",
                             "nav": meta["nav_proxy_usd"],
                             "shares_outstanding": meta["shares_outstanding"],
                             "nav_source": "estimated: sum of holdings market values / outstanding shares"}])
        append_unique(out_dir / "fund_days.csv", nav, ["fund", "date"])
    meta["nav_proxy_included_in_fund_days"] = estimate_nav
    meta["url"] = ISHARES_IVV
    (raw / f"IVV-{meta['asof']}.json").write_text(json.dumps(meta, indent=2))
    return meta


def fetch_twelvedata_prices(tickers: list[str], out_dir: Path,
                            start: str, end: str) -> dict:
    key = os.environ.get("TWELVEDATA_API_KEY")
    if not key:
        raise ValueError("Set TWELVEDATA_API_KEY locally (not in source code)")
    if pd.Timestamp(end).date() > date.today():
        raise ValueError("End date cannot be in the future")
    if len(tickers) > 50:
        raise ValueError("Limit each price sync to 50 names to manage provider quotas")
    records = []
    for ticker in tickers:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9.\-]{0,11}", ticker):
            raise ValueError(f"Invalid stock symbol {ticker!r}")
        url = "https://api.twelvedata.com/time_series?" + urlencode({
            "symbol": ticker, "interval": "1day", "start_date": start,
            "end_date": end})
        data = json.loads(fetch(url, {"Authorization": f"apikey {key}"}))
        if data.get("status") == "error" or "values" not in data:
            raise RuntimeError(f"Twelve Data rejected {ticker}: {data.get('message', data)}")
        for item in data["values"]:
            records.append({"date": item["datetime"], "ticker": ticker.upper(),
                            "close": float(item["close"]), "volume": float(item["volume"])})
    if not records:
        raise ValueError("Provider returned no price observations")
    append_unique(out_dir / "prices.csv", pd.DataFrame(records), ["ticker", "date"])
    return {"symbols": tickers, "rows_fetched": len(records),
            "start": start, "end": end,
            "source": "Twelve Data daily time_series: split-adjusted closes, dividend-unadjusted; verify volume treatment",
            "url": "https://api.twelvedata.com/time_series"}


def parse_yahoo_chart(payload: bytes, ticker: str,
                      start: str | None = None, end: str | None = None,
                      use_adjclose: bool = False) -> pd.DataFrame:
    """Parse Yahoo Finance v8 chart JSON into normalized daily OHLCV rows."""
    data = json.loads(payload)
    chart = data.get("chart") or {}
    if chart.get("error"):
        raise RuntimeError(f"Yahoo Finance rejected {ticker}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"Yahoo Finance returned empty result for {ticker}")
    res = results[0]
    timestamps = res.get("timestamp") or []
    indicators = res.get("indicators") or {}
    quotes = (indicators.get("quote") or [{}])[0]
    closes = quotes.get("close") or []
    volumes = quotes.get("volume") or []
    if use_adjclose:
        adj = (indicators.get("adjclose") or [{}])[0].get("adjclose")
        if adj and len(adj) == len(timestamps):
            closes = adj
    records = []
    for ts, close, volume in zip(timestamps, closes, volumes):
        if ts is None or close is None or volume is None:
            continue
        close_f, vol_f = float(close), float(volume)
        if close_f <= 0 or vol_f <= 0:
            continue
        day = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        if start and day < start:
            continue
        if end and day > end:
            continue
        records.append({"date": day, "ticker": ticker.upper(), "close": close_f, "volume": vol_f})
    if not records:
        return pd.DataFrame(columns=["date", "ticker", "close", "volume"])
    df = pd.DataFrame(records)
    return df.drop_duplicates(["ticker", "date"], keep="last").sort_values("date").reset_index(drop=True)


def fetch_yahoo_prices(tickers: list[str], out_dir: Path,
                       start: str, end: str,
                       use_adjclose: bool = False,
                       max_workers: int = 6,
                       skip_errors: bool = False) -> dict:
    """Zero-API-key daily close/volume adapter using Yahoo Finance v8 chart API."""
    end_d = pd.Timestamp(end).date()
    start_d = pd.Timestamp(start).date()
    if end_d > date.today():
        raise ValueError("End date cannot be in the future")
    if start_d > end_d:
        raise ValueError("Start date cannot be after end date")
    cleaned = []
    for raw in tickers:
        sym = raw.strip().upper().replace("/", "-").replace(" ", "-")
        if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", sym):
            raise ValueError(f"Invalid stock symbol {raw!r}")
        if sym not in cleaned:
            cleaned.append(sym)
    p1 = int(datetime(start_d.year, start_d.month, start_d.day, tzinfo=timezone.utc).timestamp())
    p2_dt = datetime(end_d.year, end_d.month, end_d.day, tzinfo=timezone.utc) + timedelta(days=1)
    p2 = int(p2_dt.timestamp())

    def _fetch_one(sym: str) -> pd.DataFrame:
        url = f"{YAHOO_CHART_ROOT}/{quote(sym)}?" + urlencode({
            "period1": p1, "period2": p2, "interval": "1d",
        })
        payload = fetch(url, {"Accept": "application/json"})
        return parse_yahoo_chart(payload, sym, start=start_d.isoformat(),
                                 end=end_d.isoformat(), use_adjclose=use_adjclose)

    frames: list[pd.DataFrame] = []
    failed: dict[str, str] = {}
    workers = max(1, min(max_workers, len(cleaned)))
    if workers == 1:
        for sym in cleaned:
            try:
                df = _fetch_one(sym)
                if not df.empty:
                    frames.append(df)
                else:
                    failed[sym] = "no valid daily bars in range"
            except Exception as exc:
                if not skip_errors:
                    raise
                failed[sym] = str(exc)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(_fetch_one, sym): sym for sym in cleaned}
            for fut in as_completed(futs):
                sym = futs[fut]
                try:
                    df = fut.result()
                    if not df.empty:
                        frames.append(df)
                    else:
                        failed[sym] = "no valid daily bars in range"
                except Exception as exc:
                    if not skip_errors:
                        raise
                    failed[sym] = str(exc)

    if not frames:
        raise ValueError(f"Yahoo Finance returned no price observations (failed: {failed})")
    combined = pd.concat(frames, ignore_index=True)
    append_unique(out_dir / "prices.csv", combined, ["ticker", "date"])
    return {
        "provider": "yahoo",
        "symbols_requested": len(cleaned),
        "symbols_fetched": int(combined["ticker"].nunique()),
        "failed_symbols": failed,
        "rows_fetched": len(combined),
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "price_basis": "adjclose (split+dividend adjusted)" if use_adjclose else "close (split-adjusted, dividend-unadjusted)",
        "source": "Yahoo Finance v8 chart API (public unofficial endpoint; verify corporate-action and volume treatment)",
        "url": YAHOO_CHART_ROOT,
    }


def fetch_prices(tickers: list[str], out_dir: Path, start: str, end: str,
                 provider: str = "auto", use_adjclose: bool = False,
                 skip_errors: bool = False) -> dict:
    """Fetch daily prices via Twelve Data when configured, otherwise Yahoo Finance v8."""
    choice = provider.lower()
    if choice == "auto":
        choice = "twelvedata" if os.environ.get("TWELVEDATA_API_KEY") else "yahoo"
    if choice == "twelvedata":
        return fetch_twelvedata_prices(tickers, out_dir, start, end)
    if choice == "yahoo":
        return fetch_yahoo_prices(tickers, out_dir, start, end,
                                  use_adjclose=use_adjclose, skip_errors=skip_errors)
    raise ValueError(f"Unknown price provider {provider!r}; expected auto, yahoo, or twelvedata")


def inspect_stock_flow(ticker: str) -> dict:
    """User-directed per-security lookup; never fetch bulk history or store responses."""
    ticker = ticker.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,10}", ticker):
        raise ValueError("Invalid ticker")
    url = f"https://tickerinside.com/api/v1/flows/{ticker.lower()}.json"
    data = json.loads(fetch(url))
    latest = data.get("latest") or {}
    return {"ticker": data.get("ticker"), "asof_close": data.get("date"),
            "funds_counted": data.get("funds_counted"),
            "net_value_usd": latest.get("net_value_usd"),
            "net_value_beyond_growth_usd": latest.get("net_value_beyond_growth_usd"),
            "missing_reason": latest.get("withheld"),
            "source": url, "method": data.get("method"),
            "terms": "https://tickerinside.com/legal/#history",
            "warning": "Issuer-derived holdings changes, not a next-day prediction; selected-user-request lookup only."}
