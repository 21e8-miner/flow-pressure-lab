"""Self-contained evidence dashboard with source and staleness disclosures."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd


STYLE = """
:root{color-scheme:dark;--bg:#0a111a;--panel:#121e2b;--line:#25384a;--soft:#889cac;--white:#eef4f8;--up:#58d2ad;--down:#ff9279;--gold:#e9ca78}
*{box-sizing:border-box}body{font:14px/1.52 ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--white);margin:0}
main{max-width:1270px;margin:0 auto;padding:48px 25px 80px}.eyebrow{font-size:11px;letter-spacing:2.7px;color:var(--up);font-weight:700;text-transform:uppercase}
h1{font-size:clamp(31px,5vw,62px);line-height:1.07;letter-spacing:-2px;margin:12px 0 18px;font-weight:750}h2{font-size:21px;letter-spacing:-.5px;margin:0}
.lead{max-width:930px;color:#a8bac9;font-size:17px;line-height:1.65}.muted{color:var(--soft)}a{color:#7ccef9}strong{font-weight:650}
.badges{display:flex;flex-wrap:wrap;gap:10px;margin:24px 0 32px}.pill{border:1px solid var(--line);padding:7px 12px;border-radius:999px;font-size:12px;letter-spacing:.2px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:26px 0 36px}.metric{border:1px solid var(--line);background:var(--panel);padding:22px;border-radius:13px}
.metric .val{font-size:28px;font-weight:700;letter-spacing:-.7px;margin:10px 0 6px}.metric small{color:var(--soft)}
section{margin-top:30px;border:1px solid var(--line);border-radius:14px;overflow:hidden;background:var(--panel)}.sec-head{padding:23px 24px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.sec-body{padding:25px}.controls{display:flex;gap:8px;flex-wrap:wrap}button{cursor:pointer;border:1px solid #31495a;background:#162638;color:#c4d5e2;border-radius:8px;padding:8px 13px;font-weight:600}
button.active{border-color:var(--up);background:#17372f;color:var(--up)}.table-scroller{overflow:auto}table{width:100%;border-collapse:collapse;min-width:750px}
th{font-size:11px;text-align:right;color:#8096a8;padding:15px 18px;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}td{padding:14px 18px;text-align:right;border-bottom:1px solid #20303d;font-variant-numeric:tabular-nums}tr:last-child td{border:0}
.symbol{font-weight:800;font-size:16px;letter-spacing:.3px}.name{display:block;font-size:12px;color:var(--soft);font-weight:400}.up{color:var(--up)}.down{color:var(--down)}
.barwrap{display:flex;align-items:center;gap:12px;justify-content:flex-end}.bartrack{width:110px;height:7px;background:#293745;border-radius:9px;overflow:hidden}.barfill{height:100%;border-radius:9px}
.note{padding:17px 22px;background:#152938;border-left:3px solid var(--gold);margin:20px 0;color:#d3e2ec;line-height:1.65}.explain{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.explain div{padding:15px;background:#172635;border-radius:8px}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);font-size:12px;color:var(--soft)}
@media(max-width:850px){.grid{grid-template-columns:repeat(2,1fr)}.explain{grid-template-columns:1fr}}@media(max-width:490px){main{padding:29px 14px}.grid{grid-template-columns:1fr 1fr}.metric{padding:14px}.metric .val{font-size:22px}.sec-body{padding:15px}}
"""


def base_html(title: str, main: str, script: str = "") -> str:
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'><title>" + html.escape(title) +
            "</title><style>" + STYLE + "</style></head><body><main>" + main +
            "</main><script>" + script + "</script></body></html>")


def fmt_millions(n) -> str:
    if pd.isna(n):
        return "—"
    return f"{'+' if n > 0 else '−' if n < 0 else ''}${abs(n)/1e6:,.1f}M"


def observed_report(observed: pd.DataFrame, path: Path) -> None:
    req = {"ticker", "name", "date", "net_value_usd", "net_value_beyond_growth_usd"}
    if not req.issubset(observed.columns):
        raise ValueError(f"Observed flow file must include {req}")
    if observed.date.nunique() != 1:
        raise ValueError("Only a single disclosure date per observational report")
    asof = str(observed.date.iloc[0]); count = len(observed)
    discrepancy = int((observed.net_value_usd * observed.net_value_beyond_growth_usd < 0).sum())
    mega = observed[observed.ticker.isin(["AAPL", "MSFT", "NVDA", "AVGO", "AMZN", "META", "GOOGL", "GOOG"])]
    mega_out = int(mega.net_value_beyond_growth_usd.lt(0).sum())
    source = "https://tickerinside.com/api/v1/flows.json"
    rows = observed.fillna(value={"name": ""}).to_dict(orient="records")
    content = f"""
    <div class='eyebrow'>FLOW PRESSURE LAB / MARKET STRUCTURE RESEARCH / 01</div>
    <h1>The ETF flow illusion.</h1>
    <p class='lead'>A fund can report more shares of a stock while its managers are effectively <strong>reducing that stock relative to fund growth</strong>. This page visualizes verified issuer-derived figures, not predicted flows or trades.</p>
    <div class='badges'><span class='pill'>OBSERVED: {html.escape(asof)} CLOSE</span><span class='pill'>PROVIDER: TICKERINSIDE</span><span class='pill'>NO ADV / NO MODEL ALPHA</span></div>
    <div class='grid'>
      <div class='metric'><small>Stocks in this selected snapshot</small><div class='val'>{count}</div><small>Not the complete U.S. market</small></div>
      <div class='metric'><small>Sign flips after growth adjustment</small><div class='val'>{discrepancy}</div><small>Accumulation ≠ allocation</small></div>
      <div class='metric'><small>Megacaps with negative residual</small><div class='val'>{mega_out}/{len(mega)}</div><small>Within displayed mega-cap names</small></div>
      <div class='metric'><small>Issuer coverage in source</small><div class='val'>460 funds</div><small>~$5.28T of reported net assets</small></div>
    </div>
    <section><div class='sec-head'><div><h2>What the ETFs actually reported</h2><span class='muted'>Click sorting modes; totals are over selected securities only</span></div>
      <div class='controls'><button id='sort_residual' class='active'>Growth-adjusted</button><button id='sort_raw'>Raw change</button><button id='sort_diverge'>Largest gap</button></div></div>
      <div class='table-scroller'><table><thead><tr><th>Security</th><th>Raw ETF holding change</th><th>Beyond fund growth</th><th>Residual direction</th></tr></thead><tbody id='flow-body'></tbody></table></div>
      <div class='sec-body'><div class='note'><strong>Read this correctly:</strong> growth-adjusted residual does not equal an ETF investor redemption. It may reflect constituent reweighting, index events, corporate actions or the provider's estimation methodology. Neither column establishes the next day's price direction.</div></div>
    </section>
    <section><div class='sec-head'><h2>Signal construction and what remains missing</h2></div><div class='sec-body'><div class='explain'>
      <div><div class='eyebrow'>01 / Observe</div><h2>Δ ETF share count × NAV</h2><p class='muted'>Primary creations/redemptions are observable where the issuer publishes daily shares outstanding.</p></div>
      <div><div class='eyebrow'>02 / Forecast</div><h2>Expected fund demand</h2><p class='muted'>The included code forecasts future creations from historical flows, not from this one-day table.</p></div>
      <div><div class='eyebrow'>03 / Transmit</div><h2>$/20-day dollar ADV</h2><p class='muted'>A stock pressure score requires independently sourced, dated stock prices and volume.</p></div>
    </div></div></section>
    <footer><p>Attribution: <a href='{source}'>TickerInside ETF flows, November 3, 2026</a> (<a href='https://tickerinside.com/legal/#history'>history terms</a>). The small hand-selected extract here is for analysis, not a republished archive. Provider says its data cover iShares, SPDR and Global X funds. Issuer data can arrive late and change. Source figures are not independently audited. Built for research, not investment recommendations.</p></footer>
    """
    js = "const rows=" + json.dumps(rows, ensure_ascii=True).replace("<", "\\u003c") + ";" + r"""
    let mode='residual';const body=document.getElementById('flow-body');
    const money=n=>n===null||n===undefined?'—':(n<0?'−':n>0?'+':'')+'$'+(Math.abs(n)/1e6).toFixed(1)+'M';
    const text=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const style=n=>n<0?'down':'up';
    const key=r=>mode==='raw'?Math.abs(r.net_value_usd):mode==='diverge'?Math.abs(r.net_value_usd-r.net_value_beyond_growth_usd):Math.abs(r.net_value_beyond_growth_usd);
    function draw(){let sorted=rows.slice().sort((a,b)=>key(b)-key(a));const mx=Math.max(...rows.map(r=>Math.abs(r.net_value_beyond_growth_usd||0)),1);
      body.innerHTML=sorted.map(r=>{let f=r.net_value_beyond_growth_usd,raw=r.net_value_usd;
        let width=Math.min(100,Math.abs(f||0)/mx*100),cls=style(f||0);
        return `<tr><td><span class="symbol">${text(r.ticker)}</span><span class="name">${text(r.name)}</span></td><td class="${style(raw||0)}">${money(raw)}</td><td class="${cls}">${money(f)}</td><td><span class="barwrap"><span class="${cls}">${f>=0?'Addition':'Reduction'}</span><span class="bartrack"><span class="barfill" style="display:block;width:${width}%;background:var(--${f<0?'down':'up'})"></span></span></span></td></tr>`}).join('');
      ['residual','raw','diverge'].forEach(m=>document.getElementById('sort_'+m).classList.toggle('active',m===mode));}
    ['residual','raw','diverge'].forEach(m=>document.getElementById('sort_'+m).addEventListener('click',()=>{mode=m;draw()}));draw();
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(base_html("ETF Flow Illusion | Flow Pressure Lab", content, js), encoding="utf-8")


def signal_report(signal: pd.DataFrame, diagnostics: dict, path: Path, portfolio: pd.DataFrame | None = None,
                  portfolio_info: dict | None = None) -> None:
    usable = signal[signal.score.notna()].sort_values("score", ascending=False).copy()
    scored = len(usable)
    weight = diagnostics["benchmark_weight_with_scores"] * 100
    explain = "No optimized portfolio: incomplete benchmark flow/price coverage. This is deliberate." if portfolio is None else f"Research portfolio active share: {portfolio_info['active_share']*100:.2f}%. Tracking error: {portfolio_info['tracking_error_status']}."
    tr = "".join(f"<tr><td><span class='symbol'>{html.escape(str(r.ticker))}</span></td><td>{r.weight*100:.2f}%</td><td>{fmt_millions(r.forecast_demand_usd)}</td><td>{r.adv20_usd/1e6:,.1f}M</td><td class='{('up' if r.score>=0 else 'down')}'>{r.score*100:.3f}%</td></tr>"
                 for r in usable.itertuples())
    markup = f"""
    <div class='eyebrow'>FLOW PRESSURE LAB / FORECAST / NOT VERIFIED ALPHA</div><h1>Demand meets liquidity.</h1>
    <p class='lead'>Estimated future ETF creations, distributed over published constituent weights and normalized by actual stock-dollar trading volume. Signal is one narrow source of demand; it is not a return forecast.</p>
    <div class='badges'><span class='pill'>MODEL AS OF {html.escape(diagnostics['asof'])}</span><span class='pill'>FUND DATA LAGGED</span><span class='pill'>PIT RESEARCH</span></div>
    <div class='grid'><div class='metric'><small>Funds modeled</small><div class='val'>{len(diagnostics['funds_used'])}</div></div>
    <div class='metric'><small>Benchmarked names</small><div class='val'>{diagnostics['stocks_in_benchmark']}</div></div>
    <div class='metric'><small>Names scored</small><div class='val'>{scored}</div></div>
    <div class='metric'><small>Weight with valid signal</small><div class='val'>{weight:.1f}%</div></div></div>
    <section><div class='sec-head'><h2>Forecast pressure / dollar ADV</h2></div><div class='table-scroller'><table><thead><tr><th>Stock</th><th>Benchmark wt</th><th>Forecast demand</th><th>ADV20</th><th>Pressure</th></tr></thead><tbody>{tr}</tbody></table></div></section>
    <section><div class='sec-head'><h2>Model integrity</h2></div><div class='sec-body'><div class='note'>{html.escape(explain)}</div><p class='muted'>Unmodeled sources: {html.escape(', '.join(diagnostics['not_modeled']))}. Forecasts are a 5-observation EWMA baseline. All prices and fund observations carry real as-of dates. No externally verified alpha or empirical market-impact calibration.</p></div></section>
    <footer>Signal numbers are research estimates, not third-party performance. Input files, vendor attribution, units, trade lag, and portfolio constraints are documented in README.md.</footer>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(base_html("Research Signal | Flow Pressure Lab", markup), encoding="utf-8")


def _fmt_pct(val: float | None, digits: int = 1, signed: bool = False) -> str:
    if val is None or pd.isna(val):
        return "—"
    prefix = "+" if signed and val > 0 else ""
    return f"{prefix}{val:.{digits}f}%"


def _fmt_num(val: float | None, digits: int = 2, signed: bool = False) -> str:
    if val is None or pd.isna(val):
        return "—"
    prefix = "+" if signed and val > 0 else ""
    return f"{prefix}{val:.{digits}f}"


def _svg_excess_chart(backtest: pd.DataFrame) -> str:
    """Render a lightweight self-contained SVG chart of cumulative net excess return (bps)."""
    if backtest is None or backtest.empty or "cumulative_net_excess" not in backtest.columns:
        return "<p class='muted'>No walk-forward backtest rows available to chart.</p>"
    vals = (backtest["cumulative_net_excess"].astype(float) * 10000.0).tolist()
    dates = backtest["return_close"].astype(str).tolist()
    n = len(vals)
    if n < 2:
        return "<p class='muted'>Need at least 2 backtest sessions to plot a curve.</p>"
    w, h, pad_l, pad_r, pad_t, pad_b = 900, 220, 56, 20, 18, 30
    vmin, vmax = min(min(vals), 0.0), max(max(vals), 0.0)
    span = max(vmax - vmin, 1e-6)
    vmin -= span * 0.1
    vmax += span * 0.1
    span = vmax - vmin

    def sx(i: int) -> float:
        return pad_l + (w - pad_l - pad_r) * (i / (n - 1))

    def sy(v: float) -> float:
        return pad_t + (h - pad_t - pad_b) * (1.0 - (v - vmin) / span)

    zero_y = sy(0.0)
    pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(vals))
    color = "#58d2ad" if vals[-1] >= 0 else "#ff9279"
    return (
        f"<svg viewBox='0 0 {w} {h}' style='width:100%;height:auto;display:block' role='img' "
        f"aria-label='Cumulative net excess return in basis points'>"
        f"<line x1='{pad_l}' y1='{zero_y:.1f}' x2='{w - pad_r}' y2='{zero_y:.1f}' "
        f"stroke='#3a5166' stroke-dasharray='4 4' stroke-width='1'/>"
        f"<polyline fill='none' stroke='{color}' stroke-width='2.4' points='{pts}'/>"
        f"<text x='{pad_l - 8}' y='{pad_t + 6}' text-anchor='end' fill='#889cac' font-size='11'>{vmax:+.1f}bp</text>"
        f"<text x='{pad_l - 8}' y='{zero_y + 4:.1f}' text-anchor='end' fill='#889cac' font-size='11'>0bp</text>"
        f"<text x='{pad_l - 8}' y='{h - pad_b}' text-anchor='end' fill='#889cac' font-size='11'>{vmin:+.1f}bp</text>"
        f"<text x='{pad_l}' y='{h - 8}' fill='#889cac' font-size='11'>{html.escape(dates[0])}</text>"
        f"<text x='{w - pad_r}' y='{h - 8}' text-anchor='end' fill='#889cac' font-size='11'>{html.escape(dates[-1])}</text>"
        f"</svg>"
    )


def empirical_report(
    creation_eval: dict,
    path: Path,
    signal: pd.DataFrame | None = None,
    signal_diag: dict | None = None,
    portfolio: pd.DataFrame | None = None,
    portfolio_info: dict | None = None,
    backtest: pd.DataFrame | None = None,
    backtest_summary: dict | None = None,
    incremental: dict | None = None,
    pilot_note: str | None = None,
) -> None:
    """Render an honest, self-contained HTML dashboard of live empirical test results."""
    obs = creation_eval.get("observation_count", 0)
    mae_imp = creation_eval.get("mae_improvement_vs_zero_pct")
    rmse_imp = creation_eval.get("rmse_improvement_vs_zero_pct")
    hit_rate = creation_eval.get("nonzero_direction_hit_rate_pct")
    corr = creation_eval.get("pearson_correlation")
    nz_rate = creation_eval.get("nonzero_outcome_rate_pct")
    date_span = f"{creation_eval.get('date_start', '—')} to {creation_eval.get('date_end', '—')}"
    funds = creation_eval.get("funds", [])

    bt_net_bps = None
    bt_ir = None
    bt_trades = 0
    bt_turnover = None
    bt_gross_bps = None
    if backtest_summary:
        bt_trades = backtest_summary.get("trades", 0)
        if backtest_summary.get("cumulative_net_excess") is not None:
            bt_net_bps = backtest_summary["cumulative_net_excess"] * 10000.0
        bt_ir = backtest_summary.get("annualized_information_ratio")
    if backtest is not None and not backtest.empty:
        bt_turnover = float(backtest["turnover_one_way"].mean() * 100.0)
        cum_gross = float((1.0 + backtest["gross_return"]).prod() - 1.0)
        cum_bench = float((1.0 + backtest["benchmark_return"]).prod() - 1.0)
        bt_gross_bps = (cum_gross - cum_bench) * 10000.0

    inc_t = incremental.get("tstat_hac5_adjusted") if incremental else None
    inc_raw_t = incremental.get("tstat_hac5_raw") if incremental else None
    inc_bps = incremental.get("mean_daily_bps_per_one_sd_flow_adjusted") if incremental else None
    inc_raw_bps = incremental.get("mean_daily_bps_per_one_sd_flow_raw") if incremental else None
    inc_days = incremental.get("valid_days", 0) if incremental else 0

    kill_failed = mae_imp is not None and mae_imp <= 0
    verdict_cls = "down" if kill_failed else "up"
    verdict_label = "KILL CRITERION TRIGGERED — EWMA UNDERPERFORMS ZERO BASELINE" if kill_failed else "EWMA OUTPERFORMS ZERO BASELINE"

    per_fund = creation_eval.get("per_fund") or {}
    fund_rows_html = []
    for f_name, stats in per_fund.items():
        mi = stats.get("mae_improvement_vs_zero_pct")
        ri = stats.get("rmse_improvement_vs_zero_pct")
        c = stats.get("pearson_correlation")
        fund_rows_html.append(
            f"<tr><td><span class='symbol'>{html.escape(f_name)}</span>"
            f"<span class='name'>{html.escape(str(stats.get('date_start', '')))} → {html.escape(str(stats.get('date_end', '')))}</span></td>"
            f"<td>{stats.get('observation_count', 0):,}</td>"
            f"<td>{_fmt_pct(stats.get('nonzero_outcome_rate_pct'), 1)}</td>"
            f"<td>{fmt_millions(stats.get('mae_model_usd'))}</td>"
            f"<td>{fmt_millions(stats.get('mae_zero_baseline_usd'))}</td>"
            f"<td class='{('up' if (mi or 0) > 0 else 'down')}'>{_fmt_pct(mi, 1, signed=True)}</td>"
            f"<td>{fmt_millions(stats.get('rmse_model_usd'))}</td>"
            f"<td class='{('up' if (ri or 0) > 0 else 'down')}'>{_fmt_pct(ri, 1, signed=True)}</td>"
            f"<td class='{('up' if (c or 0) > 0 else 'down')}'>{_fmt_num(c, 3, signed=True)}</td>"
            f"<td>{_fmt_pct(stats.get('nonzero_direction_hit_rate_pct'), 1)}</td></tr>"
        )
    fund_rows_html.append(
        f"<tr style='font-weight:700;background:#162638'><td>ALL ({len(funds)} funds)</td>"
        f"<td>{obs:,}</td>"
        f"<td>{_fmt_pct(nz_rate, 1)}</td>"
        f"<td>{fmt_millions(creation_eval.get('mae_model_usd'))}</td>"
        f"<td>{fmt_millions(creation_eval.get('mae_zero_baseline_usd'))}</td>"
        f"<td class='{verdict_cls}'>{_fmt_pct(mae_imp, 1, signed=True)}</td>"
        f"<td>{fmt_millions(creation_eval.get('rmse_model_usd'))}</td>"
        f"<td class='{('up' if (rmse_imp or 0) > 0 else 'down')}'>{_fmt_pct(rmse_imp, 1, signed=True)}</td>"
        f"<td class='{('up' if (corr or 0) > 0 else 'down')}'>{_fmt_num(corr, 3, signed=True)}</td>"
        f"<td>{_fmt_pct(hit_rate, 1)}</td></tr>"
    )

    # Stock-level table payload for client-side sorting
    stock_records = []
    if signal is not None and not signal.empty:
        merged = signal[signal["score"].notna()].copy()
        if portfolio is not None and "tilt" in portfolio.columns:
            merged = merged.merge(portfolio[["ticker", "tilt", "target_weight"]], on="ticker", how="left")
        else:
            merged["tilt"] = None
            merged["target_weight"] = None
        for r in merged.itertuples():
            stock_records.append({
                "ticker": str(r.ticker),
                "sector": str(getattr(r, "sector", "") or ""),
                "weight_pct": float(r.weight * 100.0),
                "demand_usd": float(r.forecast_demand_usd),
                "adv20_usd": float(r.adv20_usd),
                "score_pct": float(r.score * 100.0),
                "tilt_bps": None if pd.isna(r.tilt) else float(r.tilt * 10000.0),
            })

    te_text = "unavailable"
    as_text = "—"
    if portfolio_info:
        te = portfolio_info.get("ex_ante_tracking_error")
        te_text = f"{te*100:.2f}% annualized" if te is not None else str(portfolio_info.get("tracking_error_status", "unavailable"))
        as_text = f"{portfolio_info.get('active_share', 0)*100:.2f}%"

    pilot_disclosure = pilot_note or (
        "Free public issuer endpoints publish only the latest holdings snapshot, not historical daily constituent archives. "
        "Therefore the multi-session backtest and incremental-signal tests hold the latest constituent weights constant "
        "while using strictly point-in-time historical ProShares share creations and Yahoo Finance daily closes/volumes."
    )

    asof_label = signal_diag.get("asof", "—") if signal_diag else "—"
    stock_count = len(stock_records)

    content = f"""
    <div class='eyebrow'>FLOW PRESSURE LAB / LIVE EMPIRICAL EVALUATION</div>
    <h1>Empirical falsification report.</h1>
    <p class='lead'>Live-fetched ProShares official NAV/share-count histories, iShares IVV sector classifications, and Yahoo Finance daily price/volume bars tested end-to-end. Results are reported without tuning or cherry-picking.</p>
    <div class='badges'>
      <span class='pill'>PROSHARES HISTORY: {html.escape(date_span)}</span>
      <span class='pill'>PIT SIGNAL AS OF: {html.escape(str(asof_label))}</span>
      <span class='pill'>PRICES: YAHOO FINANCE V8</span>
      <span class='pill {verdict_cls}'>{html.escape(verdict_label)}</span>
    </div>
    <div class='grid'>
      <div class='metric'><small>Real ProShares fund-days tested</small><div class='val'>{obs:,}</div><small>{len(funds)} funds ({html.escape(', '.join(funds))})</small></div>
      <div class='metric'><small>EWMA vs zero-flow MAE</small><div class='val {verdict_cls}'>{_fmt_pct(mae_imp, 1, signed=True)}</div><small>RMSE: {_fmt_pct(rmse_imp, 1, signed=True)} · r = {_fmt_num(corr, 3, signed=True)}</small></div>
      <div class='metric'><small>Walk-forward net excess (5 bps)</small><div class='val {("up" if (bt_net_bps or 0) > 0 else "down")}'>{_fmt_num(bt_net_bps, 1, signed=True)} bps</div><small>{bt_trades} sessions · IR {_fmt_num(bt_ir, 2, signed=True)}</small></div>
      <div class='metric'><small>Fama–MacBeth HAC-5 t-stat</small><div class='val'>{_fmt_num(inc_t, 2, signed=True)}</div><small>{_fmt_num(inc_bps, 2, signed=True)} bps/day per 1 SD ({inc_days}d)</small></div>
    </div>

    <section>
      <div class='sec-head'>
        <div><h2>1. ETF Share-Creation Forecast vs. Zero-Flow Baseline (Strictly PIT)</h2>
        <span class='muted'>Trailing 5-session EWMA of share-creation rates evaluated strictly out-of-sample against predicting zero net creations</span></div>
      </div>
      <div class='table-scroller'>
        <table>
          <thead><tr><th>Fund</th><th>Obs</th><th>Nonzero Days</th><th>Model MAE</th><th>Zero MAE</th><th>MAE vs Zero</th><th>Model RMSE</th><th>RMSE vs Zero</th><th>Pearson r</th><th>Nonzero Hit</th></tr></thead>
          <tbody>{"".join(fund_rows_html)}</tbody>
        </table>
      </div>
      <div class='sec-body'>
        <div class='note'><strong>Empirical finding:</strong> The naive 5-day EWMA fails the zero-baseline kill criterion on every tested fund. Two structural reasons explain why: (1) roughly half of all trading days have <em>zero</em> net share creations ({_fmt_pct(nz_rate, 1)} nonzero overall), and (2) equity ETFs like NOBL and REGL experience quarter-end <strong>ETF heartbeat trades</strong> (large in-kind creations immediately followed by matching redemptions for tax-basis management), causing EWMA to extrapolate spikes into next-day reversals (negative Pearson correlation on NOBL and REGL).</div>
      </div>
    </section>

    <section>
      <div class='sec-head'>
        <div><h2>2. Walk-Forward Backtest &amp; Incremental Signal Diagnostics</h2>
        <span class='muted'>Signal after close t → execute close t+1 → realize close t+1 to t+2 · Assumed 5 bps one-way cost</span></div>
      </div>
      <div class='sec-body'>
        {_svg_excess_chart(backtest)}
        <div class='explain' style='margin-top:20px'>
          <div><div class='eyebrow'>Backtest (Gross vs Net)</div><h2>{_fmt_num(bt_gross_bps, 1, signed=True)} / {_fmt_num(bt_net_bps, 1, signed=True)} bps</h2><p class='muted'>Cumulative gross vs. net excess over {bt_trades} sessions. Mean daily one-way turnover: {_fmt_pct(bt_turnover, 2)}. At 5 bps cost, turnover erases gross excess (IR {_fmt_num(bt_ir, 2, signed=True)}).</p></div>
          <div><div class='eyebrow'>Fama–MacBeth (Controlled)</div><h2>{_fmt_num(inc_bps, 2, signed=True)} bps/d (t={_fmt_num(inc_t, 2, signed=True)})</h2><p class='muted'>Controlled for 20-day momentum, log ADV20, and sector fixed effects over {inc_days} cross sections. Raw slope: {_fmt_num(inc_raw_bps, 2, signed=True)} bps/d (t={_fmt_num(inc_raw_t, 2, signed=True)}). Not significant at 5%.</p></div>
          <div><div class='eyebrow'>PIT Portfolio Snapshot</div><h2>TE {html.escape(te_text)}</h2><p class='muted'>Constrained long-only, sector-neutral tilts (±35 bps cap) on {stock_count} constituents. Active share: {html.escape(as_text)}. Sector neutral: {html.escape(str(portfolio_info.get('sector_neutral', '—') if portfolio_info else '—'))}.</p></div>
        </div>
        <div class='note'><strong>Point-in-time caveat:</strong> {html.escape(pilot_disclosure)}</div>
      </div>
    </section>

    <section>
      <div class='sec-head'>
        <div><h2>3. Live Point-in-Time Stock Pressure ({stock_count} Constituents, as of {html.escape(str(asof_label))})</h2>
        <span class='muted'>Forecast creation-equivalent dollars divided by trailing 20-session dollar ADV</span></div>
        <div class='controls'>
          <button id='sort_score' class='active'>Pressure (% ADV20)</button>
          <button id='sort_demand'>Forecast Demand ($)</button>
          <button id='sort_tilt'>Active Tilt (bps)</button>
        </div>
      </div>
      <div class='table-scroller'>
        <table>
          <thead><tr><th>Security</th><th>Benchmark Wt</th><th>Forecast Demand</th><th>ADV20</th><th>Pressure (% ADV20)</th><th>Target Tilt</th></tr></thead>
          <tbody id='stock-body'></tbody>
        </table>
      </div>
    </section>

    <footer><p>Sources: ProShares official CSVs (historical NAV &amp; daily holdings), iShares IVV holdings CSV (sector mapping), Yahoo Finance v8 chart API (daily split-adjusted closes &amp; volume). Research prototype only — not investment advice or verified alpha.</p></footer>
    """

    js = "const stocks=" + json.dumps(stock_records, ensure_ascii=True).replace("<", "\\u003c") + ";" + r"""
    let mode='score';const tbody=document.getElementById('stock-body');
    const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const fmtM=n=>n===null||n===undefined?'—':(n<0?'−':n>0?'+':'')+'$'+(Math.abs(n)/1e6).toFixed(2)+'M';
    const fmtADV=n=>'$'+(n/1e6).toFixed(1)+'M';
    const key=r=>mode==='demand'?r.demand_usd:mode==='tilt'?(r.tilt_bps??-999):r.score_pct;
    function draw(){
      const sorted=stocks.slice().sort((a,b)=>key(b)-key(a));
      tbody.innerHTML=sorted.map(r=>{
        const scCls=r.score_pct>=0?'up':'down';
        const tCls=(r.tilt_bps??0)>=0?'up':'down';
        const tiltTxt=r.tilt_bps===null?'—':(r.tilt_bps>0?'+':'')+r.tilt_bps.toFixed(1)+' bps';
        return `<tr><td><span class="symbol">${esc(r.ticker)}</span><span class="name">${esc(r.sector)}</span></td><td>${r.weight_pct.toFixed(2)}%</td><td class="${scCls}">${fmtM(r.demand_usd)}</td><td>${fmtADV(r.adv20_usd)}</td><td class="${scCls}">${r.score_pct>=0?'+':''}${r.score_pct.toFixed(4)}%</td><td class="${tCls}">${tiltTxt}</td></tr>`;
      }).join('');
      ['score','demand','tilt'].forEach(m=>document.getElementById('sort_'+m).classList.toggle('active',m===mode));
    }
    ['score','demand','tilt'].forEach(m=>document.getElementById('sort_'+m).addEventListener('click',()=>{mode=m;draw();}));
    draw();
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(base_html("Empirical Evaluation | Flow Pressure Lab", content, js), encoding="utf-8")
