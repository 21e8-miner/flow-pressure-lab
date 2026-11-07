# Flow Pressure Lab

A reproducible, **research-only** prototype of the investment idea Michael Green described in his November 2026 Excess Returns interview. This is **not** Tier1 Alpha's algorithm, an affiliated product, a verified factor, or an order-management system.

## What is actually finished

| Component | Status | Verification |
|---|---|---|
| Independent analysis of Tier1's published framework | Complete | `docs/RESEARCH.md`, original interview, T1A site |
| Real, dated, selected ETF flow observations | Included | Thirteen securities from TickerInside's Nov. 3, 2026 issuer-derived disclosure; source credited |
| Interactive HTML diagnostic | Working | `output/observed_flow_dashboard.html` |
| Official ProShares NAV/share-count and holdings adapter | Implemented | Schema unit-tested; **not live fetched in this execution environment** |
| Official iShares IVV holdings snapshot adapter | Implemented | Schema unit-tested; **not live fetched in this execution environment** |
| Twelve Data daily price/volume adapter | Implemented | Requires user's existing API key; **not live fetched here** |
| ETF share-creation baseline forecast | Implemented | Unit-tested on explicitly synthetic fixtures; empirical accuracy **not measured** |
| Stock-level creation-equivalent pressure | Implemented | Requires real issuer data plus 20 trading sessions of prices/volume |
| Fully invested, sector-neutral small tilts | Implemented | Constraints unit-tested; **not an investment recommendation** |
| Annualized ex-ante tracking-error calculation | Implemented | Needs 60 aligned stock return observations; no number claimed when missing |
| Forward-return, cost-aware backtester | Implemented | Point-in-time lag and next-close execution tested; **no genuine historical performance computed here** |
| Forecast versus zero-baseline evaluator | Implemented | Use actual ProShares history locally to test if predictability exists |
| Momentum/flow incremental-signal test | Implemented | Needs ≥25 valid cross sections and ≥20 names per day; no p-value invented |
| Leveraged ETF reset scenario | Implemented | Formula unit-tested; **model exposure, not documented trades** |

**Environment limitation:** outgoing internet requests from the artifact-building container failed. The sample HTML uses the publicly accessible November 3 figures explicitly recorded from a source inspected in this research; no claim is made to have downloaded and validated current raw issuer CSVs here. The vendor adapters must be run on a host with internet and verified against the current official files.

## Immediate use, no API key

```bash
python -m pip install -e .
flowlab observed-report
# Open output/observed_flow_dashboard.html
```

The included figures are measured changes in *issuer-reported ETF holdings* from a **small hand-selected subset**, not backtested signals, and they lack stock-dollar ADV. The observed date is Nov. 3, 2026, not the date you run the tool. Full-source coverage was 460 counted funds (~$5.28T, issuer names iShares/SPDR/Global X); those totals do **not** describe the thirteen-row subset. Original source: https://tickerinside.com/api/v1/flows.json . Terms: https://tickerinside.com/legal/#history .

To look up **one requested stock** directly from the third party without archiving its historical database:

```bash
flowlab inspect-stock NVDA
flowlab inspect-stock AVGO
```

`inspect-stock` requests only the named stock, prints its as-of date, latest issuer holdings change and beyond-growth residual, and preserves null values. It never downloads whole historical flow shards or runs a scheduled bulk archive. Cite TickerInside when using the output.

## Workflow A: Is the creation-flow baseline predictive at all?

This is the fastest useful falsification test. It does not require any historical constituent list or price vendor.

```bash
flowlab capture-proshares NOBL --data-dir data
flowlab capture-proshares UPRO --data-dir data
flowlab evaluate-creations --data-dir data --output-dir output
```

Results, if the real issuer download succeeds:

- `output/creation_forecast_evaluation.csv`: date-by-date historical EWM forecasts versus realized changes in ETF shares outstanding multiplied by that day's NAV.
- `output/creation_forecast_evaluation.json`: actual MAE, MAE of a **zero-flow forecast**, relative improvement and directional accuracy on nonzero outcomes.

The baseline is deliberately simple: a 5-session-span EWMA of historical share-creation *rates*, multiplied by previous-day NAV and shares. It is evaluated strictly using information from earlier dates. ProShares includes historical NAV, AUM and shares outstanding, all issuer publications. A rising AUM caused by appreciation is **not** treated as an inflow.

**Kill criterion:** if the prediction does not outperform the zero-creation baseline, do not infer an alpha-producing repeatable flow signal. Try better out-of-sample forecasting before taking any stock-level tilt seriously.

## Workflow B: Run a broad-cap creation-pressure prototype

Capture current official IVV constituent holdings, shares outstanding and sectors:

```bash
flowlab capture-ivv --data-dir data --estimate-nav
flowlab benchmark-from-holdings IVV --data-dir data
```

`--estimate-nav` is **explicit opt-in**. It uses `sum(issuer-reported holdings market values) / issuer-reported fund shares outstanding` as an *approximate* NAV per share; it is not a published official NAV. Verify/replace this estimate with direct daily NAV from your licensed vendor for production research. Collect fresh IVV snapshots on separate trading days; one file is insufficient to calculate share creations, and at least six prior valid creation observations are needed for the forecast. iShares publishes latest holdings and shares outstanding, but the single CSV is not a historical fund-flow series.

Fetch dated equity prices and volumes with an **actual** Twelve Data key on the user's host:

```bash
export TWELVEDATA_API_KEY='your-own-key'
flowlab prices --symbols AAPL,MSFT,NVDA,AMZN,AVGO --start 2026-08-01 --end 2026-11-06 --data-dir data
```

The CLI limits each request batch to 50 names. Complete the *entire* benchmark universe, not just mega-caps, before expecting research portfolio weights. Twelve Data has quotas and plan-specific history access; test them locally. Its daily prices are **split-adjusted but not total-return/dividend-adjusted**; raw price-only backtests will omit dividends. Obtain a proper total-return series before fiduciary performance comparisons.

For any named evaluation date (use a historical trade day, not a future date):

```bash
flowlab signal --asof 2026-11-06 --data-dir data --output-dir output
```

Outputs include:

- `signal.csv`: benchmark weights, estimated future *creation-equivalent* dollar exposure by stock, last observed exposure, twenty-day dollar ADV, `score = forecast_creation_equivalent_usd / ADV20`; `NaN` when the stock or disclosure is not covered.
- `signal_diagnostics.json`: source coverage, date, modeled funds, omitted components and meaning of the proxy.
- `signal_dashboard.html`: sortable scientific report of **only valid estimates**.
- `research_weights.csv` and `portfolio_diagnostics.json`: **only if every benchmark stock has a valid score**; no unknown treated as zero.

The baseline predictor does not model ETF creation baskets, AP inventories, in-kind transfers, dealer hedging, discretionary share redistribution, open/close auctions, or retirement default contributions. Even a correctly forecast creation-equivalent is **not the same as a purchase order in underlying stock**.

### If using ProShares rather than IVV

ProShares latest holdings may not publish a sector field, and may include derivatives or non-U.S. lines; derivatives are explicitly excluded. To use an equities-only ProShares fund as a small pilot benchmark, supply a **real** `ticker,sector` CSV:

```bash
flowlab benchmark-from-holdings NOBL --data-dir data --sector-map data/verified_sector_map.csv
```

Do not fabricate sectors, and do not assume a ProShares equity pilot represents the S&P 500. A fund-of-funds or derivative-only product is not suitable for the equity look-through engine.

## Backtests and factor tests

**No historical 2026 return or alpha number is shipped.** To establish one, you need point-in-time constituent snapshots, share-count changes, stock prices, and benchmark weights on each test date. A single latest issuer snapshot cannot be backfilled into old dates.

```bash
flowlab backtest --start 2026-09-01 --end 2026-11-01 --cost-bps 5 --data-dir data
flowlab test-incremental --start 2026-09-01 --end 2026-11-01 --data-dir data
```

Both commands require the four normalized tables listed below. Dates absent from the permitted data window are reported as skipped, not silently filled. A signal formed *after close t* trades at **close t+1**, and return is close t+1→close t+2. The cost input is an **assumed** basis-points charge (default 5bps per dollar traded), not an empirically sourced transaction-cost estimate. Portfolio turnover cost is an approximation and excludes market impact, bid/ask and benchmark rebalance costs. Returns are price-only unless you supply a proper total-return close series and adapt the methodology.

The incremental-signal test measures whether stock-level flow pressure has any next-close-to-next-close cross-sectional association left **after 20-session momentum, log dollar trading volume, and sector fixed effects**. Its inference uses daily cross-sectional flow coefficients and a five-lag heteroskedasticity/autocorrelation-consistent mean t-statistic. This is **not** causal identification, not adjusted for searching many hypotheses, and not equivalent to live strategy performance.

## Normalized input schema

Write these to `data/` using the exact columns. Weights are **fractions**, not percentages; price/flow USD; raw shares, not thousands. Optional `available_on` is the known **publication date**; if omitted, the framework conservatively treats holdings, benchmark and ETF fund-days as available no earlier than the following calendar day. Prices may be used only on or before the signal close.

| File | Required columns | Notes |
|---|---|---|
| `fund_days.csv` | `date,fund,nav,shares_outstanding` | Official NAV preferred; no forward-filling share counts |
| `holdings.csv` | `asof,fund,ticker,weight` | One position per fund/ticker/date; full equity-only holdings, not top-10 |
| `prices.csv` | `date,ticker,close,volume` | ≥20 true sessions for ADV, ≥61 aligned sessions for tracking error |
| `benchmark.csv` | `asof,ticker,weight,sector` | Must total ~100%, fresh ≤5 calendar days |

Optional `corporate_action=true` in `fund_days.csv` invalidates a creation event. Naive split-like jumps in share count and reciprocal NAV are also excluded. Do not use a ticker alone for international/global holdings when symbols collide across markets; this adapter is designed for clean U.S.-equity universes and institutional data can instead use FIGI/CUSIP.

## Portfolio construction

This prototype uses a **research design**, not settings attributed to Tier1 Alpha:

1. Estimate each fund's next creation-equivalent dollars: `latest published shares × NAV × trailing EWM creation rate`.
2. Map those dollars into current dated U.S. equity holdings and sum across modeled funds.
3. Divide per-stock estimate by trailing twenty-day **observed stock-dollar ADV**; no causal price-impact coefficient is assumed.
4. Cross-sectionally standardize the pressure proxy and maximize a penalized linear score subject to long-only weights, **zero active sector weights**, and ±35-bp per-security tilt caps. Full benchmark coverage is mandatory.
5. Scale tilts down if a **measured**, aligned trailing historical covariance estimate would exceed an annualized 1% tracking-error *budget*. If fewer than 60 common daily returns exist, tracking error is explicitly `unavailable`, not asserted to be 1%.

There is no calibration establishing a price response per dollar of flow, or an efficient portfolio's future alpha. Tax-lot management, beta neutrality, borrow and issuer capital-supply response are not in this prototype.

## Leveraged ETF formula (separate from stock scores)

For a leveraged ETF with prior AUM `A`, constant daily target leverage `L`, and today's index return `r`, the textbook **theoretical** rebalance exposure is:

`Delta_index_notional = L * (L - 1) * A * r`.

```bash
flowlab leveraged-reset --nav 100 --shares 1000000 --leverage 3 --index-return 0.01
```

The `nav`, `shares`, leverage and index return must be **actual sourced inputs** for a real-world run. This command does not assert that the fund bought equities, that its swaps dealers executed public trades, or that the flow is a tradable anomaly.

## Tests and reproducibility

```bash
python -m pip install -e '.[test]'
pytest -q
```

The unit tests use **explicitly synthetic fixture inputs only to validate arithmetic, lag logic, split handling, long-only/sector neutrality, coverage failures and file parsers**. They make **zero claims about historical market behavior**. At preparation time, all 13 tests pass. Re-run tests after downloading vendor data; validate dates, daily fund totals and split histories independently.

All HTTP requests made by the local adapters set the User-Agent header to:

`OpenAI File Downloader, XaiImageApiFetch/1.0`

### Source and licensing notes

Primary references and uncertainty register: [docs/RESEARCH.md](docs/RESEARCH.md); data/provenance and archive rights: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md). Real historical issuer inputs and market data are intentionally not fabricated or bundled when unavailable.

**No brokerage connectivity, execution, order placement or live alerts exist in this package.**
