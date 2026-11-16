"""Builds docs/data.json for the static dashboard (run by GitHub Actions).

The page shows the Overview only: price metrics, today's biggest movers, the SA gold and PGM
miners vs rand metal price charts, and the latest stories.

Uses the same fetching code as the Streamlit app (data.py, config.py, ai.py).
If a source fails, the last good copy from the previous data.json is kept and
flagged as stale, so the screen never goes blank.

Run locally:  python build_data.py
"""

from __future__ import annotations

import json
import logging
import re
import math
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Streamlit's cache decorators work outside a running app, but warn loudly about it
logging.getLogger("streamlit").setLevel(logging.ERROR)
for name in ("streamlit.runtime.caching.cache_data_api",
             "streamlit.runtime.scriptrunner_utils.script_run_context"):
    logging.getLogger(name).setLevel(logging.ERROR)

import pandas as pd  # noqa: E402

import config  # noqa: E402
import data  # noqa: E402

ROOT = Path(__file__).parent
OUT = ROOT / "docs" / "data.json"
SAST = timezone(timedelta(hours=2))

COMPANY_INFO = {c["ticker"]: {**c, "region": region}
                for region, companies in config.COMPANIES.items() for c in companies}
COMMODITY_INFO = {c["ticker"]: c for c in config.COMMODITIES}
FX_TICKERS = sorted({t for t, _ in config.FX_TO_USD.values()} | {config.FX_USDZAR})
ALL_TICKERS = tuple(list(COMPANY_INFO) + list(COMMODITY_INFO) + FX_TICKERS + list(config.INDICES))

# Price tiles across the top: (ticker, in rand?)
STRIP = [("GC=F", False), ("GC=F", True), ("PL=F", False), ("PL=F", True), ("PA=F", False),
         ("SI=F", False), ("HG=F", False), ("TIO=F", False), ("BZ=F", False), (config.FX_USDZAR, None)]
SPARK_DAYS = 90
CHART_YEARS = 3
# Miners on the Company Tracker chart (SA gold and PGM producers)
CHART_COMPANIES = ["ANG.JO", "GFI.JO", "HAR.JO", "IMP.JO", "VAL.JO", "NPH.JO", "SSW.JO"]


def num(v, nd=4):
    """JSON-safe rounded number (None for NaN)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else round(f, nd)


def pct(now, then):
    return None if then in (None, 0) or pd.isna(then) else (now / then - 1) * 100


def series_stats(s: pd.Series) -> dict:
    """Last value, % changes and a sparkline for one daily series."""
    s = s.dropna()
    if len(s) < 2:
        return {}
    last, last_date = s.iloc[-1], s.index[-1]

    def at(offset):
        prior = s[s.index <= last_date - offset]
        return prior.iloc[-1] if len(prior) else None

    ytd_base = s[s.index < pd.Timestamp(last_date.year, 1, 1)]
    spark = s[s.index > last_date - pd.Timedelta(days=SPARK_DAYS)]
    return {
        "price": num(last), "d1": num(pct(last, s.iloc[-2]), 2),
        "w1": num(pct(last, at(pd.Timedelta(days=7))), 2),
        "m1": num(pct(last, at(pd.DateOffset(months=1))), 2),
        "ytd": num(pct(last, ytd_base.iloc[-1] if len(ytd_base) else None), 2),
        "y1": num(pct(last, at(pd.DateOffset(years=1))), 2),
        "spark": [num(v, 2) for v in spark.values],
        "as_of": last_date.strftime("%Y-%m-%d"),
    }


def build_prices() -> dict:
    closes = data.get_closes(ALL_TICKERS, period="5y")   # Yahoo has no "3y"; trimmed below
    if closes.empty or closes.dropna(how="all").empty:
        raise RuntimeError("Yahoo Finance returned no prices")
    usdzar = closes[config.FX_USDZAR].dropna()

    def commodity(t):
        return closes[t].dropna() * COMMODITY_INFO[t]["factor"]

    def in_zar(t):
        s = commodity(t)
        return (s * usdzar.reindex(s.index, method="ffill")).dropna()

    tiles = []
    for t, zar in STRIP:
        if t == config.FX_USDZAR:
            tiles.append({"name": "USD/ZAR", "unit": "R per $", "inverse": True, **series_stats(usdzar)})
            continue
        info = COMMODITY_INFO[t]
        s = in_zar(t) if zar else commodity(t)
        unit = info["unit"].replace("USD", "ZAR") if zar else info["unit"]
        tiles.append({"name": info["name"], "unit": unit, "zar": bool(zar), **series_stats(s)})

    indices = [{"name": name, **series_stats(closes[t])}
               for t, name in config.INDICES.items() if t in closes]

    companies = {}
    for region, cs in config.COMPANIES.items():
        rows = []
        for c in cs:
            st_ = series_stats(closes[c["ticker"]]) if c["ticker"] in closes else {}
            st_.pop("spark", None)
            rows.append({"ticker": c["ticker"], "name": c["name"],
                         "short": c["name"].split(" (")[0], "commodity": c["commodity"],
                         "ccy": data.currency_for(c["ticker"])[0], **st_})
        companies[region] = rows

    # Weekly series for the tracker charts (3 years, aligned on one date axis, rebased in the page)
    chart = {
        "Gold (ZAR/oz)": in_zar("GC=F"), "Platinum (ZAR/oz)": in_zar("PL=F"),
        "Gold (USD/oz)": commodity("GC=F"), "Silver (USD/oz)": commodity("SI=F"),
        "Platinum (USD/oz)": commodity("PL=F"), "Palladium (USD/oz)": commodity("PA=F"),
        "Copper (USD/t)": commodity("HG=F"), "Iron ore 62% (USD/t)": commodity("TIO=F"),
    }
    for t in CHART_COMPANIES:
        if t in closes:
            chart[COMPANY_INFO[t]["name"]] = closes[t].dropna()
    for t, name in config.INDICES.items():
        if t in closes:
            chart[name] = closes[t].dropna()
    frame = pd.DataFrame(chart).sort_index()
    frame = frame[frame.index > frame.index.max() - pd.DateOffset(years=CHART_YEARS)].ffill()
    frame = frame.resample("W-FRI").last()   # weekly closes keep 3-year lines clean and the file small
    series = {"dates": [d.strftime("%Y-%m-%d") for d in frame.index],
              "values": {k: [num(v, 3) for v in frame[k].values] for k in frame.columns}}

    return {"as_of": closes.index.max().strftime("%Y-%m-%d"), "tiles": tiles,
            "indices": indices, "companies": companies, "series": series}


def build_news(limit: int = 40) -> list[dict]:
    df = data.get_news()
    if df.empty:
        raise RuntimeError("No news feeds returned stories")
    out = []
    for _, n in df.head(limit).iterrows():
        pub = n["published"]
        summary = n["summary"] or ""
        # Some feeds end the summary with their own name, e.g. "...20 million tonnes of annual  Australian Mining ."
        for name in {n["source"], n["feed"]}:
            summary = re.sub(rf"\s*{re.escape(name)}\s*\.?\s*$", "", summary).strip()
        if summary and summary[-1] not in ".!?\u2026":
            summary += "\u2026"
        out.append({
            "title": n["title"], "link": n["link"], "source": n["source"],
            "published": pub.isoformat() if pub is not None and not pd.isna(pub) else None,
            "summary": summary, "image": n.get("image") or "", "google": bool(n["google"]),
            "regions": list(n["regions"]), "commodities": list(n["commodities"]),
        })
    return out


# ---- Main ---------------------------------------------------------------
def main() -> int:
    try:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        prev = {}

    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "stale": {}, "errors": []}

    for key, fn in [("prices", build_prices), ("news", build_news)]:
        try:
            result[key] = fn()
            result["stale"][key] = False
        except Exception as ex:
            traceback.print_exc()
            result["errors"].append(f"{key}: {ex}")
            result[key] = prev.get(key)
            result["stale"][key] = True
            if prev.get(key) is not None:
                result.setdefault("last_good", {})[key] = (prev.get("last_good", {}).get(key)
                                                          or prev.get("generated_at"))

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB); errors: {result['errors'] or 'none'}")
    # Fail the run only if there is nothing at all to show
    return 0 if (result.get("prices") or result.get("news")) else 1


if __name__ == "__main__":
    sys.exit(main())
