"""Mining Tracker - Streamlit dashboard.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import ai
import config
import data

st.set_page_config(page_title="Mining Tracker", page_icon="⛏️", layout="wide")

# Smaller commodity price tiles (Streamlit's metric default is very large)
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.5rem; }
[data-testid="stMetricLabel"] p { font-size: 0.8rem; }
[data-testid="stMetricDelta"] { font-size: 0.75rem; }
</style>
""", unsafe_allow_html=True)

# Categorical palette, fixed order (colour follows the entity, never its rank)
SERIES_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                  "#e87ba4", "#008300", "#6250d6", "#e34948"]
MAX_SERIES = len(SERIES_COLOURS)

# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------
COMPANY_INFO = {
    c["ticker"]: {**c, "region": region}
    for region, companies in config.COMPANIES.items()
    for c in companies
}
COMMODITY_INFO = {c["ticker"]: c for c in config.COMMODITIES}
FX_TICKERS = sorted({t for t, _ in config.FX_TO_USD.values()} | {config.FX_USDZAR})
ALL_TICKERS = tuple(list(COMPANY_INFO) + list(COMMODITY_INFO) + FX_TICKERS
                    + list(config.INDICES))

PERIODS = {"1M": pd.DateOffset(months=1), "3M": pd.DateOffset(months=3),
           "6M": pd.DateOffset(months=6), "YTD": None, "1Y": pd.DateOffset(years=1),
           "2Y": pd.DateOffset(years=2)}


def period_start(label: str, last: pd.Timestamp) -> pd.Timestamp:
    if label == "YTD":
        return pd.Timestamp(last.year, 1, 1)
    return last - PERIODS[label]


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.title("⛏️ Mining Tracker")
    st.caption("South Africa · Rest of Africa · Global")
    if st.button("Refresh data", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    chart_period = st.segmented_control("Chart period", list(PERIODS), default="6M")
    chart_period = chart_period or "6M"
    st.divider()
    if ai.is_configured():
        st.caption(f"✅ AI summaries on ({config.AI_MODEL})")
    st.caption(
        "Prices: Yahoo Finance, delayed ~15 min, end-of-day for history. "
        "JSE prices shown in rand, LSE in pounds. SENS: Sharenet (15 min delay). "
        "Not for trading decisions."
    )

# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
closes = data.get_closes(ALL_TICKERS)
perf = data.performance(closes)
usdzar = closes[config.FX_USDZAR].dropna()


def commodity_series(ticker: str) -> pd.Series:
    return closes[ticker].dropna() * COMMODITY_INFO[ticker]["factor"]


def zar_series(ticker: str) -> pd.Series:
    s = commodity_series(ticker)
    fx = usdzar.reindex(s.index, method="ffill")
    return (s * fx).dropna()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def fmt_price(v: float) -> str:
    if pd.isna(v):
        return "–"
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}"


def fmt_delta(v) -> str | None:
    return None if v is None or pd.isna(v) else f"{v:+.2f}%"


def colour_pct(v):
    if v is None or pd.isna(v):
        return ""
    return "color: #0ca30c" if v > 0 else ("color: #d03b3b" if v < 0 else "")


PCT_COLS = ["1D %", "1W %", "1M %", "YTD %", "1Y %"]


def styled_table(df: pd.DataFrame):
    fmt = {c: "{:+.2f}%" for c in PCT_COLS}
    fmt.update({"Price": "{:,.2f}", "52W high": "{:,.2f}", "52W low": "{:,.2f}"})
    fmt = {k: v for k, v in fmt.items() if k in df.columns}
    df = df.copy()
    for c in fmt:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return (df.style.format(fmt, na_rep="–")
            .map(colour_pct, subset=[c for c in PCT_COLS if c in df.columns]))


def company_table(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for t in tickers:
        info = COMPANY_INFO[t]
        p = perf.loc[t] if t in perf.index else pd.Series(dtype=float)
        rows.append({
            "Company": info["name"], "Ticker": t, "Focus": info["commodity"],
            "Ccy": data.currency_for(t)[0], "Price": p.get("last"),
            **{c: p.get(c) for c in PCT_COLS},
            "52W high": p.get("52W high"), "52W low": p.get("52W low"),
        })
    return pd.DataFrame(rows)


def indexed_chart(series: dict[str, pd.Series], title: str, height: int = 420):
    """Line chart of several series rebased to 100 at the start of the period."""
    if not series:
        st.info("Select at least one series.")
        return
    frame = pd.DataFrame(series).sort_index()
    start = period_start(chart_period, frame.index.max())
    rebased = data.rebase(frame, start)
    fig = go.Figure()
    for i, name in enumerate(rebased.columns):
        fig.add_trace(go.Scatter(
            x=rebased.index, y=rebased[name], name=name, mode="lines",
            line={"width": 2, "color": SERIES_COLOURS[i % MAX_SERIES]},
            hovertemplate="%{y:.1f}<extra>" + name + "</extra>",
        ))
    fig.add_hline(y=100, line_width=1, line_dash="dot", line_color="#898781")
    fig.update_layout(
        title={"text": title, "font": {"size": 15}}, height=height,
        hovermode="x unified", margin={"l": 10, "r": 10, "t": 50, "b": 10},
        legend={"orientation": "h", "y": -0.12},
        yaxis={"title": f"Indexed (start of {chart_period} = 100)"},
    )
    st.plotly_chart(fig, width="stretch")


def price_chart(s: pd.Series, title: str, unit: str, colour: str = SERIES_COLOURS[0]):
    start = period_start(chart_period, s.index.max())
    s = s[s.index >= start]
    fig = go.Figure(go.Scatter(
        x=s.index, y=s.values, mode="lines", line={"width": 2, "color": colour},
        hovertemplate="%{y:,.2f} " + unit + "<extra></extra>",
    ))
    fig.update_layout(title={"text": title, "font": {"size": 15}}, height=340,
                      hovermode="x unified", margin={"l": 10, "r": 10, "t": 50, "b": 10},
                      yaxis={"title": unit}, showlegend=False)
    st.plotly_chart(fig, width="stretch")


def news_list(df: pd.DataFrame, limit: int = 30, key: str = "news",
              summaries: bool = True, images: bool = True):
    """Headlines with source, age, tags and (where available) a short summary."""
    if df.empty:
        st.info("No matching news.")
        return
    now = datetime.now(timezone.utc)
    for i, (_, n) in enumerate(df.head(limit).iterrows()):
        when = ""
        if n["published"] is not None and not pd.isna(n["published"]):
            hours = (now - n["published"]).total_seconds() / 3600
            when = f"{hours:.0f}h ago" if hours < 48 else n["published"].strftime("%d %b")
        tags = " · ".join(n["regions"] + list(n["commodities"]))
        headline_only = " · headline only" if n.get("google", False) else ""

        image = n.get("image") if images else ""
        if image:
            img_col, body = st.columns([1, 3], vertical_alignment="top")
            # URLs come from outside sources, so escape them before putting them in HTML
            img_col.markdown(
                f'<a href="{html.escape(n["link"], quote=True)}" target="_blank">'
                f'<img src="{html.escape(image, quote=True)}" loading="lazy" '
                'style="width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:6px;"></a>',
                unsafe_allow_html=True)
        else:
            body = st.container()

        with body:
            st.markdown(f"**[{n['title']}]({n['link']})**  \n"
                        f"<small>{n['source']} · {when} · {tags}{headline_only}</small>",
                        unsafe_allow_html=True)
            if summaries:
                preview_key = f"preview_{n['link']}"
                if n["summary"]:
                    st.caption(n["summary"])
                elif preview_key in st.session_state:
                    st.caption(st.session_state[preview_key]
                               or "_No preview available for this article._")
                elif not n.get("google", False):
                    if st.button("Preview", key=f"{key}_pv_{i}", type="tertiary", icon="📄"):
                        with st.spinner("Loading article…"):
                            st.session_state[preview_key] = data.article_preview(n["link"])
                        st.rerun()
        st.write("")


def sens_list(df: pd.DataFrame, limit: int = 30):
    if df.empty:
        st.info("No matching SENS announcements yet. History builds up each time the "
                "dashboard refreshes.")
        return
    for _, s in df.head(limit).iterrows():
        company = f"**{s['company']}** · " if s["company"] else ""
        st.markdown(f"{company}[{s['headline']}]({s['link']})  \n"
                    f"<small>{s['published']:%d %b %H:%M} · SENS</small>",
                    unsafe_allow_html=True)


# ---- Material for AI summaries -------------------------------------------
def _pct_txt(v) -> str:
    return "n/a" if v is None or pd.isna(v) else f"{v:+.1f}%"


def price_material() -> str:
    lines = [f"Data as of {closes.index.max():%d %b %Y}.", "", "COMMODITIES (1D / 1M / YTD):"]
    for c in config.COMMODITIES:
        p = perf.loc[c["ticker"]]
        s = commodity_series(c["ticker"])
        extra = ""
        if c["name"] in config.SHOW_IN_ZAR:
            z = zar_series(c["ticker"])
            extra = f"; ZAR {z.iloc[-1]:,.0f}/oz ({_pct_txt((z.iloc[-1] / z.iloc[-2] - 1) * 100)} 1D)"
        lines.append(f"- {c['name']}: {s.iloc[-1]:,.2f} {c['unit']} "
                     f"({_pct_txt(p['1D %'])} / {_pct_txt(p['1M %'])} / {_pct_txt(p['YTD %'])}){extra}")
    p = perf.loc[config.FX_USDZAR]
    lines.append(f"- USD/ZAR: {usdzar.iloc[-1]:.2f} ({_pct_txt(p['1D %'])} 1D; higher = weaker rand)")
    for region, companies in config.COMPANIES.items():
        lines += ["", f"{region.upper()} MINERS (1D / 1M / YTD):"]
        for c in companies:
            p = perf.loc[c["ticker"]] if c["ticker"] in perf.index else {}
            lines.append(f"- {c['name']} ({c['commodity']}): {_pct_txt(p.get('1D %'))} / "
                         f"{_pct_txt(p.get('1M %'))} / {_pct_txt(p.get('YTD %'))}")
    return "\n".join(lines)


def news_material(df: pd.DataFrame, limit: int = 60) -> str:
    lines = []
    for i, (_, n) in enumerate(df.head(limit).iterrows(), 1):
        when = n["published"].strftime("%d %b") if n["published"] is not None and not pd.isna(n["published"]) else ""
        summary = f" - {n['summary'][:250]}" if n["summary"] else ""
        lines.append(f"[{i}] ({when}, {n['source']}; {', '.join(n['regions'])}) {n['title']}{summary}")
    return "\n".join(lines)


def sens_material(df: pd.DataFrame, limit: int = 40) -> str:
    return "\n".join(f"[S{i}] ({s['published']:%d %b %H:%M}) {s['headline']}"
                     for i, (_, s) in enumerate(df.head(limit).iterrows(), 1))


def ai_box(label: str, material_fn, mode: str, key: str):
    """Button that generates an AI summary and keeps it on screen."""
    if not ai.is_configured():
        return  # stays hidden until an API key is added
    if st.button(label, key=f"btn_{key}", type="primary"):
        with st.spinner("Claude is reading the latest prices and news…"):
            try:
                st.session_state[key] = (ai.summarise(material_fn(), mode),
                                         datetime.now().strftime("%H:%M"))
            except RuntimeError as e:
                st.error(str(e))
    if key in st.session_state:
        text, at = st.session_state[key]
        with st.container(border=True):
            st.markdown(text)
            st.caption(f"Generated {at} by {config.AI_MODEL} from the prices, headlines and "
                       "SENS shown on this dashboard. Check the sources before relying on it.")


# --------------------------------------------------------------------------
# Commodity strip
# --------------------------------------------------------------------------
top_left, top_right = st.columns([3, 2], gap="large")

# ---- Today's biggest movers (top right) ----------------------------------
with top_right:
    st.subheader("Today's biggest movers")
    all_tbl = company_table(list(COMPANY_INFO))
    valid = all_tbl.dropna(subset=["1D %"]).copy()
    # Short names so the compact tables don't need to scroll sideways
    valid["Company"] = valid["Company"].str.replace(r"\s*\(.*\)", "", regex=True)
    movers_cols = ["Company", "1D %"]
    g, l = st.columns(2)
    g.markdown("**Top gainers**")
    g.dataframe(styled_table(valid.nlargest(5, "1D %")[movers_cols]),
                hide_index=True, width="stretch")
    l.markdown("**Top losers**")
    l.dataframe(styled_table(valid.nsmallest(5, "1D %")[movers_cols]),
                hide_index=True, width="stretch")

# ---- Commodity prices (top left) ------------------------------------------
with top_left:
    st.header("Mining markets")
    last_date = closes.index.max()
    st.caption(f"Latest data: {last_date:%d %b %Y}")

strip = [("GC=F", False), ("GC=F", True), ("PL=F", False), ("PL=F", True),
         ("PA=F", False), ("HG=F", False), ("TIO=F", False), (config.FX_USDZAR, None)]
cols = top_left.columns(4) + top_left.columns(4)
for col, (t, in_zar) in zip(cols, strip):
    if t == config.FX_USDZAR:
        s = usdzar
        label = "USD/ZAR"
    else:
        info = COMMODITY_INFO[t]
        s = zar_series(t) if in_zar else commodity_series(t)
        unit = info["unit"].replace("USD", "ZAR") if in_zar else info["unit"]
        label = f"{info['name']} ({unit})"
    change = (s.iloc[-1] / s.iloc[-2] - 1) * 100 if len(s) > 1 else None
    # A stronger rand (lower USD/ZAR) is shown as the good direction
    col.metric(label, fmt_price(s.iloc[-1]), fmt_delta(change),
               delta_color="inverse" if t == config.FX_USDZAR else "normal")

# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------
news = data.get_news()
sens, sens_errors = data.get_sens()
sens_mining = sens[sens["mining"]]
sens_tracked = sens[sens["company"] != ""]
tab_names = ["Overview", "Markets", "Company", "Calendar", "South Africa", "Rest of Africa",
             "Global", "Commodities", "News", "JSE SENS"]
tabs = st.tabs(tab_names)

# ---- Overview -------------------------------------------------------------
with tabs[0]:
    if ai.is_configured():
        st.subheader("AI market briefing")
    ai_box("Generate today's briefing",
           lambda: (price_material() + "\n\nNEWS HEADLINES:\n" + news_material(news)
                    + "\n\nJSE SENS ANNOUNCEMENTS (mining-related):\n" + sens_material(sens_mining)),
           "briefing", "ai_briefing")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("SA gold miners vs the gold price (in rand)")
        series = {"Gold (ZAR/oz)": zar_series("GC=F")}
        for t in ["ANG.JO", "GFI.JO", "HAR.JO", "DRD.JO"]:
            series[COMPANY_INFO[t]["name"]] = closes[t].dropna()
        indexed_chart(series, "")

        st.subheader("SA PGM miners vs the platinum price (in rand)")
        series = {"Platinum (ZAR/oz)": zar_series("PL=F")}
        for t in ["IMP.JO", "VAL.JO", "NPH.JO", "SSW.JO"]:
            series[COMPANY_INFO[t]["name"]] = closes[t].dropna()
        indexed_chart(series, "")
    with right:
        st.subheader("Latest stories")
        st.caption("Stories with summaries. All headlines are in the News tab.")
        news_list(news[news["summary"].str.len() > 0], limit=12, key="overview")

# ---- Markets --------------------------------------------------------------
with tabs[1]:
    fundamentals = data.get_fundamentals(tuple(COMPANY_INFO))

    # Company table with USD market value (used by heatmap and valuation table)
    mkt_rows = []
    for t, info in COMPANY_INFO.items():
        p = perf.loc[t] if t in perf.index else pd.Series(dtype=float)
        f = fundamentals.loc[t] if t in fundamentals.index else pd.Series(dtype=float)
        ccy = data.currency_for(t)[0]
        rate = data.usd_rate(ccy, closes)
        mcap = f.get("market_cap")
        last, high = p.get("last"), p.get("52W high")
        mkt_rows.append({
            "Company": info["name"].split(" (")[0], "Region": info["region"],
            "Focus": info["commodity"], "Ticker": t,
            "mcap_usd_bn": (mcap * rate / 1e9) if mcap and rate else None,
            **{c: p.get(c) for c in PCT_COLS},
            "off_high": (last / high - 1) * 100 if last and high else None,
            "trailing_pe": f.get("trailing_pe"), "forward_pe": f.get("forward_pe"),
            "dividend_yield": f.get("dividend_yield"), "price_to_book": f.get("price_to_book"),
            "ev_ebitda": f.get("ev_ebitda"),
        })
    mkt = pd.DataFrame(mkt_rows)

    # ---- Sector heatmap ---------------------------------------------------
    st.subheader("Sector heatmap")
    h1, h2 = st.columns([2, 3])
    heat_period = h1.segmented_control("Performance over", ["1D %", "1W %", "1M %", "YTD %"],
                                       default="1D %", key="heat_period") or "1D %"
    h2.caption("Box size = market value (USD). Blue = up, red = down; the % is printed in "
               "each box. Click a region to zoom in, click the top bar to zoom out.")
    hm = mkt.dropna(subset=["mcap_usd_bn", heat_period]).copy()
    if hm.empty:
        st.info("Market values aren't available right now.")
    else:
        lim = max(1.0, float(hm[heat_period].abs().quantile(0.9)))

        def wavg(df):  # market-value-weighted average change
            return float((df[heat_period] * df["mcap_usd_bn"]).sum() / df["mcap_usd_bn"].sum())

        ids, labels, parents, values, changes = ["All"], ["All miners"], [""], \
            [hm["mcap_usd_bn"].sum()], [wavg(hm)]
        for region, grp in hm.groupby("Region"):
            ids.append(region); labels.append(region); parents.append("All")
            values.append(grp["mcap_usd_bn"].sum()); changes.append(wavg(grp))
            for _, r in grp.iterrows():
                ids.append(r["Ticker"]); labels.append(r["Company"]); parents.append(region)
                values.append(r["mcap_usd_bn"]); changes.append(r[heat_period])

        fig = go.Figure(go.Treemap(
            ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
            customdata=changes,
            marker={"colors": changes, "cmin": -lim, "cmax": lim, "cmid": 0,
                    "colorscale": [[0, "#e34948"], [0.5, "#6b6a66"], [1, "#2a78d6"]],
                    "line": {"width": 2}, "showscale": True,
                    "colorbar": {"title": heat_period, "ticksuffix": "%"}},
            texttemplate="<b>%{label}</b><br>%{customdata:+.1f}%",
            hovertemplate="<b>%{label}</b><br>Change: %{customdata:+.2f}%<br>"
                          "Market value: US$%{value:,.1f}bn<extra></extra>",
            root_color="rgba(0,0,0,0)",
        ))
        fig.update_layout(height=520, margin={"l": 0, "r": 0, "t": 10, "b": 0})
        st.plotly_chart(fig, width="stretch")

    # ---- JSE indices ------------------------------------------------------
    st.subheader("JSE: resources vs the market")
    icols = st.columns(len(config.INDICES))
    for col, (t, name) in zip(icols, config.INDICES.items()):
        s = closes[t].dropna()
        if len(s) > 1:
            p = perf.loc[t]
            col.metric(name, f"{s.iloc[-1]:,.0f}", fmt_delta(p["1D %"]))
            col.caption(f"YTD {_pct_txt(p['YTD %'])} · 1Y {_pct_txt(p['1Y %'])}")
    idx_series = {name: closes[t].dropna() for t, name in config.INDICES.items()}
    idx_series["Gold (ZAR/oz)"] = zar_series("GC=F")
    indexed_chart(idx_series, "JSE indices vs the rand gold price")

    # ---- Commodity ratios -------------------------------------------------
    st.subheader("Commodity ratios")
    ratios = {
        "Gold / silver": ("GC=F", "SI=F",
                          "Ounces of silver one ounce of gold buys. High = silver cheap vs gold."),
        "Gold / platinum": ("GC=F", "PL=F",
                            "Ounces of platinum one ounce of gold buys. High = platinum cheap vs gold."),
        "Platinum / palladium": ("PL=F", "PA=F",
                                 "Above 1 = platinum dearer than palladium. Matters for SA PGM revenue mix."),
    }
    ratio_series = {}
    rcols = st.columns(len(ratios))
    for col, (name, (a, b, help_txt)) in zip(rcols, ratios.items()):
        s = (closes[a] / closes[b]).dropna()
        ratio_series[name] = s
        year = s[s.index > s.index.max() - pd.DateOffset(years=1)]
        col.metric(name, f"{s.iloc[-1]:.2f}",
                   f"{(s.iloc[-1] / year.mean() - 1) * 100:+.1f}% vs 1Y avg",
                   delta_color="off", help=help_txt)
    pick_ratio = st.segmented_control("Ratio chart", list(ratios), default="Gold / silver",
                                      key="ratio_pick") or "Gold / silver"
    rs = ratio_series[pick_ratio]
    rs = rs[rs.index >= period_start(chart_period, rs.index.max())]
    rfig = go.Figure(go.Scatter(x=rs.index, y=rs.values, mode="lines", name=pick_ratio,
                                line={"width": 2, "color": SERIES_COLOURS[0]},
                                hovertemplate="%{y:.2f}<extra></extra>"))
    avg = ratio_series[pick_ratio]
    avg = avg[avg.index > avg.index.max() - pd.DateOffset(years=1)].mean()
    rfig.add_hline(y=avg, line_width=1, line_dash="dot", line_color="#898781",
                   annotation_text="1Y average", annotation_position="top left")
    rfig.update_layout(height=320, hovermode="x unified", showlegend=False,
                       margin={"l": 10, "r": 10, "t": 20, "b": 10},
                       yaxis={"title": pick_ratio})
    st.plotly_chart(rfig, width="stretch")
    st.caption("A PGM 'basket price' would also need rhodium, which has no free data source.")

    # ---- Valuation table --------------------------------------------------
    st.subheader("Valuations")
    v_regions = st.multiselect("Regions", ["South Africa", "Rest of Africa", "Global"],
                               default=["South Africa", "Rest of Africa", "Global"],
                               key="val_regions")
    vt = mkt[mkt["Region"].isin(v_regions)].sort_values("mcap_usd_bn", ascending=False)
    st.dataframe(
        vt[["Company", "Region", "Focus", "mcap_usd_bn", "trailing_pe", "forward_pe",
            "dividend_yield", "price_to_book", "ev_ebitda", "off_high", "YTD %"]],
        hide_index=True, width="stretch", height=38 + 35 * len(vt),
        column_config={
            "mcap_usd_bn": st.column_config.NumberColumn("Market value (US$bn)", format="%.1f"),
            "trailing_pe": st.column_config.NumberColumn("P/E", format="%.1f",
                                                         help="Price / last 12 months' earnings"),
            "forward_pe": st.column_config.NumberColumn("Forward P/E", format="%.1f",
                                                        help="Price / forecast earnings"),
            "dividend_yield": st.column_config.NumberColumn("Div. yield", format="%.1f%%"),
            "price_to_book": st.column_config.NumberColumn("P/B", format="%.2f"),
            "ev_ebitda": st.column_config.NumberColumn("EV/EBITDA", format="%.1f"),
            "off_high": st.column_config.NumberColumn("From 52W high", format="%.1f%%",
                                                      help="How far below its 52-week high"),
            "YTD %": st.column_config.NumberColumn("YTD", format="%+.1f%%"),
        },
    )
    st.caption("Valuation figures from Yahoo Finance, refreshed twice a day. Some ratios can be "
               "stale or distorted by one-off items, so check company reports before relying "
               "on them. Click a column header to sort.")

# ---- Company detail -------------------------------------------------------
# Which commodity price each company is compared with (by its "commodity" focus)
FOCUS_COMMODITY = {"Gold": "GC=F", "PGMs": "PL=F", "Copper": "HG=F", "Iron ore": "TIO=F",
                   "Uranium": "SRUUF"}


def _fmt_big(v: float | None, prefix: str = "") -> str:
    if v is None or pd.isna(v):
        return "–"
    for div, suffix in [(1e12, "tn"), (1e9, "bn"), (1e6, "m")]:
        if abs(v) >= div:
            return f"{prefix}{v / div:,.1f}{suffix}"
    return f"{prefix}{v:,.0f}"


def _fmt_date(d) -> str:
    return pd.Timestamp(d).strftime("%d %b %Y") if d else "–"


with tabs[2]:
    options = {f"{i['name'].split(' (')[0]} · {t} ({i['region']})": t
               for t, i in COMPANY_INFO.items()}
    pick = st.selectbox("Company", list(options), key="company_pick")
    t = options[pick]
    info = COMPANY_INFO[t]
    base_name = info["name"].split(" (")[0]
    det = data.get_company_details(t)
    fund = data.get_fundamentals(tuple(COMPANY_INFO))
    f = fund.loc[t] if t in fund.index else pd.Series(dtype=float)
    ccy = data.currency_for(t)[0]
    rate = data.usd_rate(ccy, closes)
    s = closes[t].dropna()
    p = perf.loc[t]
    sym = {"ZAR": "R", "USD": "US$", "GBP": "£", "CAD": "C$", "AUD": "A$", "HKD": "HK$"}.get(ccy, "")

    # ---- Header and key figures ------------------------------------------
    st.subheader(det["name"])
    bits = [b for b in [det["industry"], det["country"], f"{t} · prices in {ccy}"] if b]
    site = f" · [{det['website'].split('//')[-1]}]({det['website']})" if det["website"] else ""
    st.caption(" · ".join(bits) + site)

    k = st.columns(6)
    k[0].metric("Price", f"{sym}{fmt_price(p['last'])}", fmt_delta(p["1D %"]))
    k[1].metric("YTD", _pct_txt(p["YTD %"]))
    k[2].metric("1 year", _pct_txt(p["1Y %"]))
    mcap = f.get("market_cap")
    k[3].metric("Market value", _fmt_big(mcap, sym),
                f"≈ {_fmt_big(mcap * rate, 'US$')}" if mcap and rate and ccy != "USD" else None,
                delta_color="off")
    dy = f.get("dividend_yield")
    k[4].metric("Dividend yield", f"{dy:.1f}%" if dy is not None and not pd.isna(dy) else "–")
    pe = f.get("forward_pe")
    k[5].metric("Forward P/E", f"{pe:.1f}" if pe is not None and not pd.isna(pe) else "–")

    # 52-week range bar and analyst view
    year = s[s.index > s.index.max() - pd.DateOffset(years=1)]
    lo, hi, last = year.min(), year.max(), s.iloc[-1]
    pos = (last - lo) / (hi - lo) * 100 if hi > lo else 50
    r1, r2 = st.columns(2)
    with r1:
        st.markdown(f"**52-week range** &nbsp; <small>{sym}{fmt_price(lo)} – {sym}{fmt_price(hi)}"
                    f" · now {pos:.0f}% of the way up</small>", unsafe_allow_html=True)
        st.markdown(
            f'<div style="position:relative;height:8px;border-radius:4px;'
            f'background:linear-gradient(90deg,#e34948,#6b6a66,#2a78d6);margin:6px 0 4px">'
            f'<div style="position:absolute;left:calc({pos:.1f}% - 6px);top:-4px;width:12px;'
            f'height:16px;border-radius:3px;background:#f0efec;border:2px solid #0b0b0b"></div></div>',
            unsafe_allow_html=True)
    with r2:
        if det["target"]:
            upside = (det["target"] / last - 1) * 100
            rec = f" · consensus: **{det['recommendation']}**" if det["recommendation"] not in ("", "none") else ""
            st.markdown(f"**Analyst target** {sym}{fmt_price(det['target'])} "
                        f"({upside:+.0f}% vs now) · {det['analysts'] or '?'} analysts{rec}")
            if det["target_low"] and det["target_high"]:
                st.caption(f"Range of targets: {sym}{fmt_price(det['target_low'])} – "
                           f"{sym}{fmt_price(det['target_high'])}")
        else:
            st.markdown("**Analyst target** – not available")

    # ---- Price chart ------------------------------------------------------
    focus = next((c for c in FOCUS_COMMODITY if info["commodity"].startswith(c)), None)
    compare = False
    if focus:
        comm_t = FOCUS_COMMODITY[focus]
        comm_name = COMMODITY_INFO[comm_t]["name"]
        in_zar = ccy == "ZAR" and comm_t in ("GC=F", "PL=F")
        compare = st.toggle(f"Compare with the {comm_name.lower()} price"
                            + (" (in rand)" if in_zar else ""), value=False, key="co_compare")
    if compare:
        comm = zar_series(comm_t) if in_zar else commodity_series(comm_t)
        indexed_chart({base_name: s, comm_name: comm}, f"{base_name} vs {comm_name}")
    else:
        price_chart(s, f"{base_name} share price ({ccy})", ccy)

    # ---- Dividends, dates and profile -------------------------------------
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**Dividends paid** (per share, by ex-dividend date)")
        divs = det["dividends"]
        divs = divs[divs.index > divs.index.max() - pd.DateOffset(years=5)] if len(divs) else divs
        if len(divs):
            dfig = go.Figure(go.Bar(x=divs.index, y=divs.values, marker_color=SERIES_COLOURS[0],
                                    hovertemplate=f"%{{x|%d %b %Y}}: {sym}%{{y:,.2f}}<extra></extra>"))
            dfig.update_layout(height=260, margin={"l": 10, "r": 10, "t": 10, "b": 10},
                               yaxis={"title": ccy}, bargap=0.5)
            st.plotly_chart(dfig, width="stretch")
            yearly = divs.groupby(divs.index.year).sum()
            st.caption("Total per year: " + " · ".join(f"{y}: {sym}{v:,.2f}"
                                                      for y, v in yearly.items()))
        else:
            st.caption("No dividends in the last five years.")
    with c2:
        st.markdown("**Key dates**")
        today = datetime.now().date()
        rd = det["results_date"]
        st.markdown(
            f"- {'Next' if rd and rd >= today else 'Last'} results: **{_fmt_date(rd)}**\n"
            f"- Last ex-dividend date: **{_fmt_date(det['ex_dividend_date'])}**\n"
            + (f"- Dividend paid: **{_fmt_date(det['dividend_pay_date'])}**\n"
               if det["dividend_pay_date"] else ""))
        if det["summary"]:
            with st.expander("About the company", expanded=True):
                st.write(det["summary"])
        if det["employees"]:
            st.caption(f"Employees: {det['employees']:,}")

    # ---- Company news and SENS -------------------------------------------
    patterns = config.SENS_COMPANIES.get(base_name, []) + [base_name.lower()]
    name_re = "|".join(rf"\b{re.escape(pt)}\b" for pt in patterns)
    n1, n2 = st.columns(2)
    with n1:
        st.markdown(f"**News mentioning {base_name}**")
        co_news = news[news["title"].str.contains(name_re, case=False, regex=True, na=False)
                       | news["summary"].str.contains(name_re, case=False, regex=True, na=False)]
        news_list(co_news, limit=10, key=f"co_{t}")
    with n2:
        st.markdown("**SENS announcements**")
        co_sens = sens[sens["headline"].str.contains(name_re, case=False, regex=True, na=False)]
        if ccy != "ZAR" and co_sens.empty:
            st.caption("Not listed on the JSE, so no SENS announcements.")
        else:
            sens_list(co_sens, limit=15)
    st.caption("Company data from Yahoo Finance (profile, analyst targets and dates can lag). "
               "News is matched on the company name.")

# ---- Calendar -------------------------------------------------------------
EVENT_STYLE = {  # event -> (colour slot, marker symbol)
    "Results": (SERIES_COLOURS[0], "diamond"),
    "Ex-dividend": (SERIES_COLOURS[1], "circle"),
    "Dividend paid": (SERIES_COLOURS[2], "square"),
}
SENS_RESULTS_RE = (r"results|trading statement|trading update|dividend|production|"
                   r"operating update|operational update|interim|annual financial|guidance")

with tabs[3]:
    cal = data.get_calendar(tuple(COMPANY_INFO))
    cal["Company"] = cal["ticker"].map(lambda x: COMPANY_INFO[x]["name"].split(" (")[0])
    cal["Region"] = cal["ticker"].map(lambda x: COMPANY_INFO[x]["region"])
    today = pd.Timestamp(datetime.now().date())

    f1, f2, f3 = st.columns([2, 2, 1])
    cal_regions = f1.multiselect("Regions", ["South Africa", "Rest of Africa", "Global"],
                                 default=["South Africa", "Rest of Africa", "Global"],
                                 key="cal_regions")
    cal_events = f2.multiselect("Events", list(EVENT_STYLE), default=list(EVENT_STYLE),
                                key="cal_events")
    horizon = f3.selectbox("Look ahead", ["30 days", "90 days", "6 months"], index=1,
                           key="cal_horizon")
    days = {"30 days": 30, "90 days": 90, "6 months": 183}[horizon]
    view = cal[cal["Region"].isin(cal_regions) & cal["event"].isin(cal_events)]

    # ---- Coming up --------------------------------------------------------
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Coming up")
        upcoming = view[(view["date"] >= today) & (view["date"] <= today + pd.Timedelta(days=days))]
        if upcoming.empty:
            st.info("Nothing scheduled in this window.")
        for month, grp in upcoming.groupby(upcoming["date"].dt.to_period("M"), sort=True):
            st.markdown(f"**{month.strftime('%B %Y')}**")
            lines = []
            for _, e in grp.iterrows():
                tag = "confirmed" if e["status"] == "Confirmed" else "*estimated*"
                in_days = (e["date"] - today).days
                when = "today" if in_days == 0 else f"in {in_days} days"
                lines.append(f"- **{e['date']:%a %d %b}** · {e['Company']} · {e['event']} "
                             f"<small>({tag}, {when})</small>")
            st.markdown("\n".join(lines), unsafe_allow_html=True)
        st.caption("*Confirmed* dates come from Yahoo Finance. *Estimated* dates are projected "
                   "from each company's usual rhythm (half-yearly for JSE, London, ASX and "
                   "Hong Kong listings, quarterly for US and Canada; dividends from the usual "
                   "gap between payments). Check SENS or the company's site for the final date.")

    # ---- Recent results-related SENS --------------------------------------
    with right:
        st.subheader("Recent results & dividend SENS")
        res_sens = sens_tracked[sens_tracked["headline"].str.contains(
            SENS_RESULTS_RE, case=False, regex=True, na=False)]
        sens_list(res_sens, limit=12)

    # ---- Timeline -----------------------------------------------------------
    st.subheader("Timeline")
    window = view[(view["date"] >= today - pd.DateOffset(months=6))
                  & (view["date"] <= today + pd.DateOffset(months=6))]
    if not window.empty:
        order = (window[["Company", "Region"]].drop_duplicates()
                 .sort_values(["Region", "Company"], ascending=[False, False]))
        tfig = go.Figure()
        for event, (colour, symbol) in EVENT_STYLE.items():
            for status in ["Past", "Confirmed", "Estimated"]:
                pts = window[(window["event"] == event) & (window["status"] == status)]
                if pts.empty:
                    continue
                open_marker = status == "Estimated"
                tfig.add_trace(go.Scatter(
                    x=pts["date"], y=pts["Company"], mode="markers",
                    name=f"{event} ({status.lower()})",
                    marker={"symbol": symbol + ("-open" if open_marker else ""), "size": 11,
                            "color": colour, "opacity": 0.45 if status == "Past" else 1,
                            "line": {"width": 2, "color": colour}},
                    hovertemplate="%{y}<br>" + event + f" ({status.lower()})"
                                  "<br>%{x|%d %b %Y}<extra></extra>",
                ))
        tfig.add_vline(x=today, line_width=1, line_dash="dot", line_color="#898781")
        tfig.add_annotation(x=today, y=1, yref="paper", text="Today", showarrow=False,
                            yanchor="bottom", font={"size": 11, "color": "#898781"})
        tfig.update_layout(
            height=max(320, 24 * len(order) + 120), hovermode="closest",
            margin={"l": 10, "r": 10, "t": 30, "b": 10},
            yaxis={"categoryorder": "array", "categoryarray": order["Company"].tolist(),
                   "title": None},
            legend={"orientation": "h", "y": -0.08},
        )
        st.plotly_chart(tfig, width="stretch")
        st.caption("Faded = past, solid = confirmed, hollow = estimated.")

    # ---- Per-company summary table -----------------------------------------
    st.subheader("By company")
    rows = []
    for t, info in COMPANY_INFO.items():
        if info["region"] not in cal_regions:
            continue
        ev = cal[cal["ticker"] == t]

        def pick(event, past):
            sel = ev[(ev["event"] == event) & ((ev["status"] == "Past") == past)]
            if sel.empty:
                return "–"
            row = sel.iloc[-1] if past else sel.iloc[0]
            return f"{row['date']:%d %b %Y}" + ("" if past or row["status"] == "Confirmed"
                                                 else " (est.)")

        divs = data.get_company_details(t)["dividends"]
        last12 = divs[divs.index > today - pd.DateOffset(years=1)].sum() if len(divs) else 0
        ccy = data.currency_for(t)[0]
        rows.append({"Company": info["name"].split(" (")[0], "Region": info["region"],
                     "Last results": pick("Results", True), "Next results": pick("Results", False),
                     "Last ex-dividend": pick("Ex-dividend", True),
                     "Next ex-dividend": pick("Ex-dividend", False),
                     "Dividends, last 12m": f"{ccy} {last12:,.2f}" if last12 else "none"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 height=38 + 35 * len(rows))

# ---- Region tabs ----------------------------------------------------------
for tab, region in zip(tabs[4:7], ["South Africa", "Rest of Africa", "Global"]):
    with tab:
        tickers = [c["ticker"] for c in config.COMPANIES[region]]
        tbl = company_table(tickers)
        st.dataframe(styled_table(tbl), hide_index=True, width="stretch",
                     height=38 + 35 * len(tbl))

        names = {COMPANY_INFO[t]["name"]: t for t in tickers}
        chosen = st.multiselect(
            f"Compare (max {MAX_SERIES})", list(names), default=list(names)[:5],
            max_selections=MAX_SERIES, key=f"cmp_{region}")
        indexed_chart({n: closes[names[n]].dropna() for n in chosen},
                      f"{region}: relative performance")

        if region == "South Africa":
            st.subheader("Latest SENS from tracked companies")
            sens_list(sens_tracked, limit=10)

        st.subheader(f"{region} news")
        news_list(news[news["regions"].apply(lambda r: region in r)], limit=20,
                  key=f"region_{region}")

# ---- Commodities ----------------------------------------------------------
with tabs[7]:
    rows = []
    for c in config.COMMODITIES:
        p = perf.loc[c["ticker"]] if c["ticker"] in perf.index else pd.Series(dtype=float)
        last = commodity_series(c["ticker"])
        rows.append({
            "Commodity": c["name"], "Group": c["group"], "Unit": c["unit"],
            "Price": last.iloc[-1] if len(last) else None,
            "ZAR price": (f"{zar_series(c['ticker']).iloc[-1]:,.0f}"
                          if c["name"] in config.SHOW_IN_ZAR else "–"),
            **{k: p.get(k) for k in PCT_COLS},
        })
    ctbl = pd.DataFrame(rows)
    st.dataframe(styled_table(ctbl), hide_index=True, width="stretch")
    st.caption("Uranium and lithium use listed funds as price proxies. "
               "Coal, manganese, chrome and rhodium need a paid data source.")

    c1, c2 = st.columns(2)
    with c1:
        pick = st.selectbox("Price chart", [c["name"] for c in config.COMMODITIES])
        t = next(c["ticker"] for c in config.COMMODITIES if c["name"] == pick)
        currency = "USD"
        if pick in config.SHOW_IN_ZAR:
            currency = st.radio("Currency", ["USD", "ZAR"], horizontal=True)
        unit = COMMODITY_INFO[t]["unit"].replace("USD", currency)
        s = zar_series(t) if currency == "ZAR" else commodity_series(t)
        price_chart(s, f"{pick} ({unit})", unit)
    with c2:
        names = [c["name"] for c in config.COMMODITIES]
        chosen = st.multiselect("Compare commodities", names,
                                default=["Gold", "Platinum", "Copper", "Iron ore 62%"],
                                max_selections=MAX_SERIES)
        indexed_chart({n: commodity_series(next(c["ticker"] for c in config.COMMODITIES
                                                if c["name"] == n)) for n in chosen},
                      "Relative performance (USD)", height=440)

# ---- News -----------------------------------------------------------------
with tabs[8]:
    f1, f2, f3 = st.columns([1, 1, 2])
    region_f = f1.multiselect("Region", ["South Africa", "Rest of Africa", "Global"])
    comm_f = f2.multiselect("Commodity", list(config.COMMODITY_KEYWORDS))
    text_f = f3.text_input("Search headlines and summaries",
                           placeholder="e.g. Sibanye, strike, royalty")
    g1, g2, g3 = st.columns(3)
    summaries_only = g1.toggle("Only stories with a summary", value=False)
    show_summaries = g2.toggle("Show summaries", value=True)
    show_images = g3.toggle("Show images", value=True)
    view = news
    if region_f:
        view = view[view["regions"].apply(lambda r: any(x in r for x in region_f))]
    if comm_f:
        view = view[view["commodities"].apply(lambda c: any(x in c for x in comm_f))]
    if text_f:
        view = view[view["title"].str.contains(text_f, case=False, na=False)
                    | view["summary"].str.contains(text_f, case=False, na=False)]
    if summaries_only:
        view = view[view["summary"].str.len() > 0]
    st.caption(f"{len(view)} stories from {news['feed'].nunique() if len(news) else 0} feeds")
    ai_box(f"Summarise these {min(len(view), 60)} stories",
           lambda: "NEWS STORIES:\n" + news_material(view), "focus",
           "ai_news_" + "_".join(region_f + comm_f + [text_f]))
    news_list(view, limit=100, key="newstab", summaries=show_summaries, images=show_images)

# ---- JSE SENS -------------------------------------------------------------
with tabs[9]:
    s1, s2 = st.columns([1, 2])
    scope = s1.radio("Show", ["Tracked companies", "All mining-related", "All SENS"],
                     horizontal=False)
    sens_text = s2.text_input("Search SENS headlines",
                              placeholder="e.g. trading statement, production, dividend")
    sview = {"Tracked companies": sens_tracked, "All mining-related": sens_mining,
             "All SENS": sens}[scope]
    if sens_text:
        sview = sview[sview["headline"].str.contains(sens_text, case=False, na=False)]
    if len(sens):
        st.caption(f"{len(sview)} announcements · history since "
                   f"{sens['published'].min():%d %b %Y} · edit SENS_COMPANIES in config.py "
                   "to track more companies")
    for err in sens_errors:
        st.warning(f"SENS source problem: {err}")
    ai_box("Summarise these announcements",
           lambda: "JSE SENS ANNOUNCEMENTS (headlines only):\n" + sens_material(sview),
           "focus", f"ai_sens_{scope}_{sens_text}")
    sens_list(sview, limit=150)
