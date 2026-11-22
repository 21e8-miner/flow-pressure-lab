# Flow Pressure Lab

A reproducible, **research-only** prototype of the investment idea Michael Green described in his November 2026 Excess Returns interview. This is **not** Tier1 Alpha's algorithm, an affiliated product, a verified factor, or an order-management system.

## What is actually finished

| Component | Status | Verification |
|---|---|---|
| Independent analysis of Tier1's published framework | Complete | `docs/RESEARCH.md`, original interview, T1A site |
| Real, dated, selected ETF flow observations | Included | Thirteen securities from TickerInside's Nov. 3, 2026 issuer-derived disclosure; source credited |
| Interactive HTML diagnostics | Working | `output/observed_flow_dashboard.html` and `output/empirical_flow_dashboard.html` |
| Official ProShares NAV/share-count and holdings adapter | Live-verified | Verified Nov. 20, 2026 against 6 funds (`NOBL`, `UPRO`, `SSO`, `REGL`, `QLD`, `TQQQ`); fixed slash share-class normalization (`BRK/B` → `BRK-B`, `BF/B` → `BF-B`) |
| Official iShares IVV holdings snapshot adapter | Live-verified | Verified Nov. 20, 2026 (`asof = 2026-11-19`, 503 equity rows, 1.159B shares, `$719.74` NAV proxy) |
| Yahoo Finance v8 daily price/volume fallback adapter | Live-verified | Zero API key, stdlib `urllib`/`json`; fetched 68/68 NOBL tickers (9,656 bars) in ~2s |
| Twelve Data daily price/volume adapter | Implemented | Supported automatically when `TWELVEDATA_API_KEY` is set; header-only auth unit-tested |
| ETF share-creation baseline forecast | Empirically tested | **Fails kill criterion** across 25,034 real ProShares fund-days (2006–2026): MAE −18.6% worse, RMSE −6.0% worse than zero baseline |
| Stock-level creation-equivalent pressure | Live-verified | Full 68/68 NOBL constituent coverage (`asof = 2026-11-21`) with real IVV sectors & Yahoo 20d ADV |
| Fully invested, sector-neutral small tilts | Live-verified | Constraints verified on 68-stock universe (active share 2.43%, max tilt 35 bps, sector-neutral) |
| Annualized ex-ante tracking-error calculation | Live-verified | Measured **0.27%** annualized from 60 aligned Yahoo Finance daily closes (budget ≤ 1.00%) |
| Forward-return, cost-aware backtester | Empirically tested | 67-session constant-holdings pilot (`2026-08-17`→`2026-11-18`, 5 bps): **−5.4 bps** net excess, IR **−0.65** (gross +6.1 bps erased by turnover) |
| Forecast versus zero-baseline evaluator | Empirically tested | Reports MAE, RMSE, Pearson correlation, nonzero hit rate, and per-fund breakdown in `output/creation_forecast_evaluation.json` |
| Momentum/flow incremental-signal test | Empirically tested | 67 cross sections × 68 names (constant-holdings pilot): +3.37 bps/day per 1 SD, **HAC-5 t = +1.66** (not statistically significant at 5%) |
| Leveraged ETF reset scenario | Implemented | Formula unit-tested; **model exposure, not documented trades** |

## Live Empirical Findings (Verified Nov. 20–21, 2026)

Running the full pipeline on live-fetched ProShares official CSVs (`NOBL`, `UPRO`, `SSO`, `REGL`, `QLD`, `TQQQ`), iShares `IVV` sectors, and Yahoo Finance v8 daily closes/volumes produces a **clear falsification of the naive 5-day EWMA baseline**:

1. **Creation-flow forecast fails the kill criterion (strictly PIT, 25,034 ProShares fund-days, 2006-07-18 to 2026-11-20):**
   - Overall 5-day EWMA MAE is **\$25.76M** vs. **\$21.72M** for a zero-creation forecast (**−18.6% worse**); RMSE is **\$71.08M** vs. **\$67.06M** (**−6.0% worse**); Pearson correlation is **+0.142**; nonzero directional hit rate is **60.8%**.
   - Every individual fund fails MAE and RMSE against zero (`NOBL` −23.7% MAE / r = −0.301, `REGL` −37.6% MAE / r = −0.410, `QLD` −32.6%, `SSO` −30.6%, `UPRO` −24.9%, `TQQQ` −7.9%).
   - **Why:** 47.1% of fund-days have *zero* net share creations, and equity ETFs like `NOBL` and `REGL` exhibit quarter-end **ETF heartbeat trades** (e.g., `NOBL` `2020-07-31: +$998.2M` → `2020-08-04: −$1,002.9M`; `REGL` `2025-01-30: +$249.8M` → `2025-01-31: −$253.7M`). Naive EWMA extrapolates the creation spike directly into the next-day redemption reversal.
2. **Stock-level signal & portfolio (`asof = 2026-11-21`, 68/68 NOBL constituents, strictly PIT):**
   - Full benchmark coverage (100.0% weight) after fixing ProShares `/` share-class tickers (`BF/B` → `BF-B`, `BRK/B` → `BRK-B`).
   - Sector-neutral, long-only portfolio achieves **0.27%** measured annualized ex-ante tracking error (60 aligned sessions) with 2.43% active share.
3. **Walk-forward backtest & Fama–MacBeth test (67 sessions, `2026-08-17` to `2026-11-18`, constant-holdings pilot):**
   - *Point-in-time caveat:* Free issuer endpoints publish only the latest holdings snapshot, so constituent weights are held constant at `2026-11-20` while fund flows and stock prices/volumes are strictly point-in-time.
   - At an assumed 5 bps one-way cost, gross excess (+6.1 bps) is erased by 1.69% average daily one-way turnover, leaving **−5.4 bps cumulative net excess** (annualized **IR = −0.65**).
   - Cross-sectional Fama–MacBeth regression (controlling for 20-day momentum, log ADV20, and sector fixed effects) yields **+3.37 bps/day per 1 SD** with **HAC-5 t = +1.66** (raw: +2.76 bps/day, t = +1.28) — **not statistically significant** at the 5% level.

Open `output/empirical_flow_dashboard.html` (regenerated via `flowlab empirical-report`) for the full interactive breakdown.

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

Fetch dated equity prices and volumes (automatically uses Twelve Data when `TWELVEDATA_API_KEY` is set, or falls back to the zero-API-key Yahoo Finance v8 chart endpoint):

```bash
# Zero API key (Yahoo Finance v8 fallback):
flowlab prices --symbols AAPL,MSFT,NVDA,AMZN,AVGO --start 2026-08-01 --end 2026-11-20 --provider yahoo --data-dir data

# Or with an actual Twelve Data key:
export TWELVEDATA_API_KEY='your-own-key'
flowlab prices --symbols AAPL,MSFT,NVDA,AMZN,AVGO --start 2026-08-01 --end 2026-11-20 --provider twelvedata --data-dir data
```

The Twelve Data adapter limits each request batch to 50 names; both Twelve Data and Yahoo Finance default `close` bars are **split-adjusted but not total-return/dividend-adjusted** (pass `--use-adjclose` with `--provider yahoo` to use Yahoo's dividend+split-adjusted close, and verify corporate actions independently before fiduciary performance comparisons). Complete the *entire* benchmark universe, not just mega-caps, before expecting research portfolio weights.

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

The unit tests use **explicitly synthetic/mocked fixture inputs only to validate arithmetic, lag logic, split handling, long-only/sector neutrality, coverage failures, file parsers, and HTML rendering**. They make **zero claims about historical market behavior**. All 25 tests pass offline. Re-run tests after downloading vendor data; validate dates, daily fund totals and split histories independently.

All HTTP requests made by the local adapters set the User-Agent header to:

`OpenAI File Downloader, XaiImageApiFetch/1.0`

### Source and licensing notes

Primary references and uncertainty register: [docs/RESEARCH.md](docs/RESEARCH.md); data/provenance and archive rights: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md). Real historical issuer inputs and market data are intentionally not fabricated or bundled when unavailable.

**No brokerage connectivity, execution, order placement or live alerts exist in this package.**
