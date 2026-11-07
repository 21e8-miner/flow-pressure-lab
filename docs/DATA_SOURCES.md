# Data provenance, access, rights and failure conditions

Prepared 2026-11-06. Actual sample date **2026-11-03**. All live vendor adapters use User-Agent `OpenAI File Downloader, XaiImageApiFetch/1.0`.

| Data | URL | Authority and cadence | Use in lab | Caveat |
|---|---|---|---|---|
| Tier1 research framework | https://www.t1acapital.com/ | Issuer's public site; seen Nov. 6, 2026 | Strategy reconstruction | No complete executable formula, parameters or verified results |
| Tier1 registration disclosure | https://www.t1acapital.com/about/ | Firm's website; seen Nov. 6 | Context | States Tier1 Alpha Asset Management not yet registered as adviser |
| ProShares daily holdings / NAVs | https://prod.proshares.com/resources/data-downloads and `https://accounts.profunds.com/etfdata/ByFund/NOBL-historical_nav.csv` | Official vendor CSVs | Fund NAV and actual shares outstanding; single latest equity holdings file | Raw feeds not fetched in this build environment; verify header changes/splits |
| iShares IVV current holdings | https://www.ishares.com/us/products/239726/ | Sponsor site with downloadable CSV | Large-cap holdings, weights, sector, shares outstanding | Only latest snapshot; NAV proxy opt-in; no historical returns from this file |
| Twelve Data historical daily | https://support.twelvedata.com/en/articles/5214728-getting-historical-data | Commercial market data vendor | Dated split-adjusted close/volume via user's credentials | Dividends not adjusted in the simple price time series; plan/limit restrictions |
| TickerInside selected stock flows | https://tickerinside.com/api/v1/flows.json | Independent aggregator, issuer-derived holdings | 13-row selected Nov. 3 **observational** sample | The snapshot is a *small extract*; archive/history rights apply |
| TickerInside per-security flow | https://tickerinside.com/api/v1/flows/nvda.json | Aggregator, attributed per request | Inspect one requested ticker in interactive CLI | Not suitable for unattended bulk archive |
| SEC Form N-PORT datasets | https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets | SEC quarterly bulk public datasets | Future historical monthly/quarterly holdings research | Filings/release availability dates matter; do not use report period as trade availability |
| SEC N-PORT transparency amendment | https://www.sec.gov/newsroom/press-releases/2024-110 | SEC release | Research on publication lags | Confirm actual 2026 form implementation and fund-size rules when ingesting |
| ETF primary/secondary activity | https://www.ici.org/files/2024/2024-factbook.pdf | Industry association (2024 report) | Primary/secondary transmission caveat | Industry aggregates do not measure an individual fund |
| Empirical seller response | https://jhfinance.web.unc.edu/wp-content/uploads/sites/12369/2024/11/Who-Clears-the-Market-When-Passive-Investors-Trade.pdf | Academic working paper (2024) | Forming stock issuance counterparty hypothesis | Quarterly estimates, not a daily price coefficient |
| ETF market effects | https://www.sciencedirect.com/science/article/pii/S1386418125000230 | Peer-reviewed paper (2025) | Primary/secondary separation | Market/context may differ |
| Leveraged rebalance market impact | https://www.sciencedirect.com/science/article/pii/S0378426621002363 | Peer-reviewed paper (2021) | Prevent assuming predictable equals tradable | Focuses on leveraged VIX ETPs |

## TickerInside archival restrictions

https://tickerinside.com/legal/#history allows individual per-request use with attribution, including in commercial products, but not systematic extraction of the archive or repeated scheduled downloads of the bulk flows and many securities' histories. The lab includes a **small, manually selected, attributed extract** from the Nov. 3 reported figures. It offers *one-security user-directed lookups only*; it does not schedule TickerInside downloads, save its history, or copy its bulk database.

## The three different clocks

- **Economic date:** date of underlying holdings or market close.
- **Publication date:** when a sponsor's ETF fund counts or portfolio snapshots were actually available.
- **Execution date:** the earliest practical trade after publication and signal calculation.

`available_on` can be supplied in normalized tables to enforce publication timing. When it is absent, this prototype conservatively excludes *same-day* fund, holdings and benchmark rows. Historical SEC N-PORT publication lag must be modeled from actual EDGAR acceptance timestamps, not just the report's period end.

## Scope of data NOT in package

There is no observed live stock-dollar ADV series, no 20-year fund-holdings archive, no daily 4,000-fund flow predictions, no paid tick quotes, no borrow or corporate supply history, no actual execution orders, and no audited performance. Missing fields must remain missing. A unit test's synthetic data is not evidence of a market fact.
