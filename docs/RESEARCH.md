# Research memo — Michael Green's passive-aware strategy

**Research cut:** 2026-11-06 (America/New_York). This memo separates what Green directly describes, public disclosures, mathematical reconstruction, empirical literature, and hypotheses not yet verified.

## 1. What Tier1 says publicly

In the supplied Excess Returns transcript (Chapter 5, approximately 21:28–23:06), Green says Tier1 synthetically models CTA, risk parity and similar strategies; tracks around 4,000 ETFs/funds as frequently as it can; translates inflows/outflows and endogenous fund liquidity into demand at individual stocks; and expresses modest over/underweights. At 39:18–41:08 he describes two initial implementations: U.S. large-cap benchmark-like equities with about 1% target tracking error, and equity exposure with custom negative-equity-correlation managed futures, targeting equity-like backtested returns at 60/40-like volatility. These are *his claims*, not live independently audited returns.

Tier1's public site explicitly describes:

1. **Flow Intelligence** — ETF/fund flows, retirement defaults, benchmark changes, model portfolios, CTA, volatility control, risk parity, leveraged resets, dealer hedging.
2. **Transmission** — signed stock-level demand, executable liquidity and scarcity.
3. **Portfolio Engineering** — costs, turnover, beta, liquidity and capacity.

Source: https://www.t1acapital.com/ (verified 2026-11-06). The same website states that Tier1 Alpha Asset Management, LLC **was not yet registered as an investment adviser** as of this research cut; do not interpret the firm as a currently tradable or verified ETF product. Source: https://www.t1acapital.com/about/ .

## 2. Observed data and why the two price-pressure questions differ

ETF issuance (change in ETF *shares outstanding*) is distinct from secondary market ETF share turnover. Pure secondary ETF trades are between shareholders and do not necessarily transfer underlying shares. An AP may create ETF shares in-kind from inventory; **even a positive creation need not require contemporaneous stock-market buying**. Thus `Δ ETF shares × NAV × underlying weight` is a **creation-equivalent exposure**, not verified stock order flow.

The Investment Company Institute estimated that 84% of overall ETF activity in 2023 was secondary market. The percentage is not a calibration for any single ETF or for the future. Source: https://www.ici.org/files/2024/2024-factbook.pdf .

Peer-reviewed evidence is nuanced: Comerton-Forde and Marta (2025) find primary-market ETF arbitrage can affect underlying stock liquidity while secondary-market liquidity can help market quality. https://www.sciencedirect.com/science/article/pii/S1386418125000230 . A paper on leveraged VIX products finds predictable rebalance price effects **without excess profit from front-running in its sample**: https://www.sciencedirect.com/science/article/pii/S0378426621002363 . Consequently, measure next-day predictive excess return after costs, rather than simply equating a mechanical flow with profit.

The Nov. 3, 2026 TickerInside source (https://tickerinside.com/api/v1/flows.json) publishes issuer-derived position changes for 460 counted funds with approximately $5.28T of reported assets from iShares, SPDR and Global X. The example selected 13 named stocks, including AAPL/MSFT/NVDA/AVGO, which report positive raw additions but negative reallocations beyond proportional fund growth. These are *issuer-derived third-party estimates*, not audited full-market primary creations. TickerInside's history rights apply; this repo deliberately does not systematically archive the service.

## 3. Nonconsensus research extension — model the seller

**The strongest alternative hypothesis is that the cross-sectional beneficiary of passive inflows is whichever stock has the least *responsive marginal supply*, not simply the largest ETF ownership or lowest ADV.**

Sammon and Shim (working paper, August 19, 2024) use stock-quarter ownership/issuance data and find that firms respond to 1 percentage point additional passive demand by supplying about 0.64 percentage points of shares on average. When index funds are buyers, they report a conditional response around 0.95 percentage points. Compensation/employee options and direct issuance are key mechanisms. That is a stock-quarter aggregate finding, **not** a daily price-impact calibration or a universal coefficient.

Paper: https://jhfinance.web.unc.edu/wp-content/uploads/sites/12369/2024/11/Who-Clears-the-Market-When-Passive-Investors-Trade.pdf .

A future model should estimate *net unexplained demand*:

```
Effective pressure ~ predicted marginal demand
                     - responsive issuance / hedge supply
                     - AP / dealer inventory absorption

then divide by effective executable liquidity (not just 20d ADV).
```

No issuance, AP inventory, auction imbalance or option dealer data is contained in this repository. The terms above are **research directions**, not filled with invented zeros or arbitrary confidence coefficients.

### A more promising identification strategy

Use broad ETF flows from securities economically unrelated to the focal stock as an instrument for mechanical ownership pressure. This is similar in spirit to Sammon & Shim's identification, and can reduce reverse causality in naive `flow ~ subsequent return` regressions. It requires detailed historical fund overlap, timestamps and clean benchmark membership. Not implemented; would require institutional-quality holdings and timestamps.

## 4. The math issue in Green's interview

At approximately 23:22–24:26, the transcript describes stock liquidity scaling as `market_cap ** 0.75` but then says that a $5.5 trillion company versus a $15 billion company has only ~10× liquidity. The stated power law implies:

```
(5,500 / 15) ** 0.75 = 83.79
```

A 10× ratio over that cap range implies an exponent around 0.390. The original remark may have compressed multiple kinds of liquidity or been mistranscribed; the numerical illustration **cannot simultaneously hold** under the specified power law. We therefore never hard-code a 0.75 elasticity or claim an 84× empirical ADV ratio. The prototype calculates dated observed ADV directly.

## 5. Tests that could overturn the strategy

**Forecast test (implemented):** Does out-of-sample prediction of the next ETF share-creation rate beat the trivial *zero creation* baseline in USD MAE? If not, do not treat a fitted EWMA of primary flows as an investor flow forecast. Compare at a per-fund and fund-category level, not only aggregate.

**Incremental stock-predictability test (implemented):** Condition on 20-session price momentum, log stock dollar volume, and sector fixed effects. Does the daily cross-sectional flow coefficient retain sign and economic size out of sample? The implementation demands 25+ valid days with 20+ matched securities, and returns `insufficient` rather than claiming significance for smaller samples. Add actual size, valuation, options positioning and earnings events in a larger institutional build.

**Clock test (partially implemented):** Only use disclosures available at the point a signal was formed. The package defaults to disallow same-day issuer data if actual release date is missing; signals trade no sooner than *the next trading day's close*. A continuous mechanical flow that is fully priced *before* an after-close issuer print is not necessarily monetizable using the disclosed figures.

**Stress / momentum-collision test (planned):** Does the factor help when trailing momentum turns negatively aligned with mechanical flow? Test 2008, 2020, 2022 and post-2026 eventually, using authentic *point-in-time* holdings. No historical backtest across these crises is currently present.

**Supply response test (planned):** Match high ETF flow-pressure names by stock issuance and compensation dilution. The plausible return effect should be stronger where marginal issue supply and dealer absorption are more constrained, controlling for momentum, earnings and size. Explicitly test asymmetry in inflow versus redemption regimes.

**Tradeability test (planned):** Measure realized closing auction impact, bid-ask and market depth (not just ADV), expected capacity, market impact under large orders and tax-lot turnover. A statistical price association that cannot survive realistic implementation is not portfolio alpha.

## 6. Interpreting forecast economics

Tier1 suggests approximately 1% incremental annual return at approximately 1% tracking error in a close-index portfolio. That corresponds to a target information ratio around one, **not verified public performance**. Even a high cross-sectional t-stat from our diagnostic does not prove that IR: one must construct a permitted portfolio, execute point-in-time, pay costs, include dividend-adjusted returns and funding/financing where appropriate, and test multiple regimes.

Consider the logical decomposition:

```
Actual capital flows (data) -> Expected next flow (prediction)
-> Underlying orders actually transmitted (microstructure)
-> Price movement net of all other counterparties (impact)
-> Gross portfolio excess return (security selection)
-> Net realized excess after turnover/taxes (investable alpha)
```

**Every arrow is a separate empirical claim.** The prototype implements the observable creation component, a conservative prediction baseline, an *un-calibrated* ADV normalization and a long-only tilt framework. It does **not** establish the microstructure transmission or the last three arrows.

## 7. Design priorities to reach institutional quality

1. **Daily, issuer-timestamped holdings and outstanding-share counts:** full SPY/IVV/VTI/QQQ/IWM plus the target-date fund and retirement recordkeeping channels. Sponsors differ in publication times, file formats and in-kind basket conventions; treat them separately.
2. **True stock and ETF execution liquidity:** TAQ/quote data, primary vs secondary ETF activity, creation baskets, closing auction imbalance, short borrow and options delta/gamma.
3. **Equity share supply:** quarterly and event-based share issuance, dilution/stock compensation, buybacks and float changes, aligned to availability dates.
4. **Systematic-hedging models:** leverage resets, CTA, volatility-targeting and risk parity, each with evidenced AUM, execution timing and real source sensitivity rather than invented $ estimates.
5. **Factor controls and causal design:** true market cap, industries, forecastable fund flows, index additions, lagged price and events; model selection frozen pre-test and walk-forward retraining.
6. **Institutional portfolio implementation:** dividend-and-split-adjusted point-in-time total returns, benchmark constituent history, beta/risk covariance, transaction-cost model, tax-aware lot choice and client IPS limits.

**Recommendation for a research program:** first establish whether issuer creation-rate forecasts beat zero, then whether broad passive pressure predicts anything after price momentum and liquidity. Only then spend on expensive quote feeds and 4,000-fund holdings ingestion. More data volume is not proof of alpha.
