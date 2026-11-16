"""Data fetching: prices (Yahoo Finance) and news (RSS)."""

from __future__ import annotations

import html
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser
import pandas as pd
import streamlit as st
import yfinance as yf

import config

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

# --------------------------------------------------------------------------
# Prices
# --------------------------------------------------------------------------
# Yahoo quotes some exchanges in minor units (cents / pence).
_SUFFIX_CCY = {
    ".JO": ("ZAR", 100),   # JSE quoted in ZA cents
    ".L": ("GBP", 100),    # LSE quoted in pence
    ".TO": ("CAD", 1),
    ".AX": ("AUD", 1),
    ".HK": ("HKD", 1),
}


def currency_for(ticker: str) -> tuple[str, float]:
    if ticker.startswith("^"):          # indices are points, not cents
        return ("pts", 1)
    for suffix, info in _SUFFIX_CCY.items():
        if ticker.endswith(suffix):
            return info
    return ("USD", 1)


@st.cache_data(ttl=15 * 60, show_spinner="Fetching prices…")
def get_closes(tickers: tuple[str, ...], period: str = "2y") -> pd.DataFrame:
    """Daily closes, one column per ticker, in major currency units."""
    raw = yf.download(list(tickers), period=period, interval="1d",
                      auto_adjust=True, progress=False, threads=True)
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if not isinstance(raw.columns, pd.MultiIndex):
        closes.columns = list(tickers)
    closes = closes.copy()
    closes.index = pd.to_datetime(closes.index).tz_localize(None)
    for t in closes.columns:
        _, divisor = currency_for(t)
        if divisor != 1:
            closes[t] = closes[t] / divisor
    return closes.sort_index()


def _company_fundamentals(ticker: str) -> dict:
    try:
        i = yf.Ticker(ticker).info
    except Exception:
        return {"ticker": ticker}
    return {
        "ticker": ticker,
        "market_cap": i.get("marketCap"),          # in the listing's major currency
        "trailing_pe": i.get("trailingPE"),
        "forward_pe": i.get("forwardPE"),
        "dividend_yield": i.get("dividendYield"),  # already a percentage
        "price_to_book": i.get("priceToBook"),
        "ev_ebitda": i.get("enterpriseToEbitda"),
    }


@st.cache_data(ttl=12 * 60 * 60, show_spinner="Fetching company valuations…")
def get_fundamentals(tickers: tuple[str, ...]) -> pd.DataFrame:
    """Market value and valuation ratios per company (Yahoo Finance, refreshed twice a day)."""
    with ThreadPoolExecutor(max_workers=12) as pool:
        rows = list(pool.map(_company_fundamentals, tickers))
    return pd.DataFrame(rows).set_index("ticker")


@st.cache_data(ttl=6 * 60 * 60, show_spinner="Loading company details…")
def get_company_details(ticker: str) -> dict:
    """Profile, analyst view, dividends and key dates for one company (Yahoo Finance).

    Prices (target, dividends) are converted to major units (rand, pounds).
    """
    _, divisor = currency_for(ticker)
    tk = yf.Ticker(ticker)
    try:
        info = tk.info
    except Exception:
        info = {}
    try:
        dividends = tk.dividends / divisor
        dividends.index = pd.to_datetime(dividends.index).tz_localize(None)
    except Exception:
        dividends = pd.Series(dtype=float)
    try:
        calendar = tk.calendar or {}
    except Exception:
        calendar = {}

    target = info.get("targetMeanPrice")
    earnings = calendar.get("Earnings Date") or []
    return {
        "name": info.get("longName") or info.get("shortName") or ticker,
        "industry": info.get("industry"),
        "country": info.get("country"),
        "website": info.get("website"),
        "employees": info.get("fullTimeEmployees"),
        "summary": info.get("longBusinessSummary") or "",
        "target": target / divisor if target else None,
        "target_high": (info.get("targetHighPrice") or 0) / divisor or None,
        "target_low": (info.get("targetLowPrice") or 0) / divisor or None,
        "analysts": info.get("numberOfAnalystOpinions"),
        "recommendation": (info.get("recommendationKey") or "").replace("_", " "),
        "beta": info.get("beta"),
        "dividends": dividends,
        "results_date": earnings[0] if earnings else None,
        "ex_dividend_date": calendar.get("Ex-Dividend Date"),
        "dividend_pay_date": calendar.get("Dividend Date"),
    }


# --------------------------------------------------------------------------
# Results and dividend calendar
# --------------------------------------------------------------------------
# Listings that usually report half-yearly; others (US, Canada) report quarterly
_HALF_YEARLY_SUFFIXES = (".JO", ".L", ".AX", ".HK")
# US-listed companies that still report half-yearly
_HALF_YEARLY_TICKERS = {"BHP", "RIO"}


def _roll_forward(last: pd.Timestamp, step: pd.DateOffset, today: pd.Timestamp) -> pd.Timestamp:
    nxt = last + step
    while nxt <= today:
        nxt += step
    return nxt


def _company_events(ticker: str) -> list[dict]:
    """Past and upcoming results / dividend dates for one company.

    Dates Yahoo gives for the future are 'Confirmed'; dates projected from the company's
    usual reporting or dividend rhythm are 'Estimated'.
    """
    det = get_company_details(ticker)
    today = pd.Timestamp(datetime.now().date())
    events = []

    def add(date, kind, status, amount=None):
        if date is None or pd.isna(date):
            return
        date = pd.Timestamp(date).normalize()
        events.append({"ticker": ticker, "date": date, "event": kind,
                       "status": "Past" if date < today else status, "amount": amount})

    # Results
    rd = det["results_date"]
    if rd:
        rd = pd.Timestamp(rd)
        add(rd, "Results", "Confirmed")
        if rd < today:
            half_yearly = ticker.endswith(_HALF_YEARLY_SUFFIXES) or ticker in _HALF_YEARLY_TICKERS
            months = 6 if half_yearly else 3
            add(_roll_forward(rd, pd.DateOffset(months=months), today), "Results", "Estimated")

    # Dividends: history, Yahoo's announced dates, then a projection from the usual gap
    divs = det["dividends"]
    for d, amt in divs[divs.index > today - pd.DateOffset(years=2)].items():
        add(d, "Ex-dividend", "Confirmed", amt)
    ex = det["ex_dividend_date"]
    if ex and pd.Timestamp(ex) >= today:
        add(ex, "Ex-dividend", "Confirmed")
    elif len(divs) >= 3 and divs.index.max() > today - pd.DateOffset(years=1):
        gaps = divs.index.to_series().diff().dropna().tail(4).dt.days
        gap_days = int(gaps.median())
        if 60 <= gap_days <= 400:  # ignore irregular payers
            add(_roll_forward(divs.index.max(), pd.DateOffset(days=gap_days), today),
                "Ex-dividend", "Estimated")
    if det["dividend_pay_date"]:
        add(det["dividend_pay_date"], "Dividend paid", "Confirmed")

    # Keep one entry per date and event (history and calendar can repeat a date)
    seen, unique = set(), []
    for e in events:
        key = (e["date"], e["event"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


@st.cache_data(ttl=6 * 60 * 60, show_spinner="Building the results and dividend calendar…")
def get_calendar(tickers: tuple[str, ...]) -> pd.DataFrame:
    with ThreadPoolExecutor(max_workers=12) as pool:
        batches = list(pool.map(_company_events, tickers))
    rows = [e for batch in batches for e in batch]
    cols = ["ticker", "date", "event", "status", "amount"]
    return pd.DataFrame(rows, columns=cols).sort_values("date").reset_index(drop=True)


def usd_rate(currency: str, closes: pd.DataFrame) -> float | None:
    """How many USD one unit of `currency` buys, from the latest close."""
    if currency == "USD":
        return 1.0
    if currency not in config.FX_TO_USD:
        return None
    ticker, invert = config.FX_TO_USD[currency]
    s = closes[ticker].dropna() if ticker in closes else pd.Series(dtype=float)
    if s.empty:
        return None
    return 1 / s.iloc[-1] if invert else s.iloc[-1]


def _pct(now: float, then: float | None) -> float | None:
    if then is None or pd.isna(then) or then == 0:
        return None
    return (now / then - 1) * 100


def performance(closes: pd.DataFrame) -> pd.DataFrame:
    """Last price and % changes (1D, 1W, 1M, YTD, 1Y) per ticker."""
    rows = []
    year_start = pd.Timestamp(datetime.now().year, 1, 1)
    for t in closes.columns:
        s = closes[t].dropna()
        if len(s) < 2:
            rows.append({"ticker": t})
            continue
        last, last_date = s.iloc[-1], s.index[-1]

        def at(offset):
            prior = s[s.index <= last_date - offset]
            return prior.iloc[-1] if len(prior) else None

        ytd_base = s[s.index < year_start]
        rows.append({
            "ticker": t,
            "last": last,
            "as_of": last_date.date(),
            "1D %": _pct(last, s.iloc[-2]),
            "1W %": _pct(last, at(pd.Timedelta(days=7))),
            "1M %": _pct(last, at(pd.DateOffset(months=1))),
            "YTD %": _pct(last, ytd_base.iloc[-1] if len(ytd_base) else None),
            "1Y %": _pct(last, at(pd.DateOffset(years=1))),
            "52W high": s[s.index > last_date - pd.DateOffset(years=1)].max(),
            "52W low": s[s.index > last_date - pd.DateOffset(years=1)].min(),
        })
    return pd.DataFrame(rows).set_index("ticker")


def rebase(closes: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    """Index each series to 100 at the first available value after start."""
    df = closes[closes.index >= start].ffill()
    return df.div(df.bfill().iloc[0]).mul(100)


# --------------------------------------------------------------------------
# News
# --------------------------------------------------------------------------
def _compile(words):
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)


_REGION_RE = {r: _compile(w) for r, w in config.REGION_KEYWORDS.items()}
_COMMODITY_RE = {c: _compile(w) for c, w in config.COMMODITY_KEYWORDS.items()}
_TAG_RE = re.compile(r"<[^>]+>")
# Google News searches are broad; keep only headlines that look mining-related
_RELEVANT_RE = _compile(
    ["mine", "mines", "miner", "miners", "mining", "mineral", "minerals", "metal", "metals",
     "ore", "smelter", "refinery", "royalty", "exploration", "bullion", "commodity", "commodities"]
    + [w for words in config.COMMODITY_KEYWORDS.values() for w in words]
    + [c["name"].split(" (")[0] for cs in config.COMPANIES.values() for c in cs]
)


GOOGLE_MAX_PER_SEARCH = 15

_BOILERPLATE_RE = re.compile(
    r"(The post .*? appeared first on .*$|Continue reading.*$|Read more.*$|\[(?:…|\.\.\.)\]|…$)",
    re.IGNORECASE)


# Photo captions and credits some feeds put before the article text
_FIGURE_RE = re.compile(
    r"<figure\b.*?</figure>|<figcaption\b.*?</figcaption>|"
    r"<(p|div|span)[^>]*class=[\"'][^\"']*caption[^\"']*[\"'][^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL)
_CREDIT_RE = re.compile(r"^(?P<before>.{0,300}?)\b(?:Image|Photo|Picture|Credit)s?\s*:\s*",
                        re.IGNORECASE)
_CREDIT_TOKEN_RE = re.compile(r"^\S*(?:/|\.com|\.au|\.co\.za)\S*\s+", re.IGNORECASE)
_AGENCY_RE = re.compile(r"^(?:Supplied|Shutterstock|Adobe Stock|Getty Images|iStock|AdobeStock|AAP|Reuters|"
                        r"Bloomberg|AFP)\b[.,]?\s*", re.IGNORECASE)
_REPEAT_RE = re.compile(r"^((?:\S+\s+){0,4}?\S+)\s+\1\b")


def strip_photo_credit(text: str) -> str:
    """Remove a leading photo caption and credit, e.g. 'Image: Timon/stock.adobe.com Rio Tinto has...'."""
    m = _CREDIT_RE.match(text)
    if not m:
        return text
    rest = text[m.end():]                       # drop the caption before "Image:" as well
    rest = _CREDIT_TOKEN_RE.sub("", rest, count=1)
    rest = _AGENCY_RE.sub("", rest, count=1)
    rest = _REPEAT_RE.sub(r"\1", rest, count=1)  # 'Austral Resources Austral Resources has' -> once
    return rest.strip() or text


def clean_summary(raw: str, max_chars: int = 420) -> str:
    """Strip HTML, photo captions and feed boilerplate, then trim to whole sentences."""
    text = _FIGURE_RE.sub(" ", raw or "")
    text = html.unescape(_TAG_RE.sub(" ", text))
    text = re.sub(r"\s+", " ", text).strip()
    text = strip_photo_credit(text)
    text = _BOILERPLATE_RE.sub("", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > 120 else cut.rsplit(" ", 1)[0] + "…"


_IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)", re.I)
_OG_IMAGE_RES = [
    re.compile(r"<meta[^>]+property=[\"']og:image(?::url)?[\"'][^>]+content=[\"']([^\"']+)", re.I),
    re.compile(r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+property=[\"']og:image(?::url)?[\"']", re.I),
    re.compile(r"<meta[^>]+name=[\"']twitter:image[\"'][^>]+content=[\"']([^\"']+)", re.I),
]


def _feed_image(entry) -> str:
    """Image URL carried in the feed itself, if any."""
    for field in ("media_thumbnail", "media_content"):
        for m in entry.get(field) or []:
            if m.get("url"):
                return m["url"]
    for link in entry.get("links", []):
        if link.get("type", "").startswith("image") and link.get("href"):
            return link["href"]
    htm = entry.get("summary", "") + "".join(c.get("value", "") for c in entry.get("content", []))
    m = _IMG_RE.search(htm)
    return m.group(1) if m else ""


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def og_image(url: str) -> str:
    """The article's social-preview image (og:image), read from the page header."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        head = urllib.request.urlopen(req, timeout=10).read(200_000).decode("utf-8", "replace")
    except Exception:
        return ""
    for rx in _OG_IMAGE_RES:
        m = rx.search(head)
        if m:
            return html.unescape(m.group(1))
    return ""


def _fetch_feed(feed: dict) -> list[dict]:
    try:
        req = urllib.request.Request(feed["url"], headers={"User-Agent": USER_AGENT})
        parsed = feedparser.parse(urllib.request.urlopen(req, timeout=15).read())
    except Exception:
        return []
    is_google = "news.google.com" in feed["url"]
    items = []
    for e in parsed.entries:
        title = html.unescape(e.get("title", "")).strip()
        source = feed["name"]
        # Google News puts the publisher in <source> and appends it to the title
        if is_google:
            pub = e.get("source", {}).get("title")
            if pub:
                source = pub
                title = re.sub(rf"\s+-\s+{re.escape(pub)}$", "", title)
        if (is_google or feed.get("filter")) and not _RELEVANT_RE.search(title):
            continue
        summary = "" if is_google else clean_summary(e.get("summary", ""))
        try:
            published = parsedate_to_datetime(e.get("published", ""))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except Exception:
            published = None
        items.append({
            "title": title,
            "link": e.get("link", ""),
            "source": source,
            "feed": feed["name"],
            "published": published,
            "summary": summary,
            "google": is_google,
            "image": "" if is_google else _feed_image(e),
        })
    if is_google:
        # Headline-only, so keep each search to its most recent stories
        items.sort(key=lambda i: i["published"] or datetime.min.replace(tzinfo=timezone.utc),
                   reverse=True)
        items = items[:GOOGLE_MAX_PER_SEARCH]
    return items


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def article_preview(url: str, max_chars: int = 900) -> str:
    """Opening paragraphs of an article, for stories whose feed has no summary."""
    import trafilatura
    try:
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False) or ""
    except Exception:
        text = ""
    text = re.sub(r"\s+", " ", text).strip()
    return clean_summary(text, max_chars) if text else ""


def _tag(item: dict) -> dict:
    text = f"{item['title']} {item['summary']}"
    regions = [r for r, rx in _REGION_RE.items() if rx.search(text)]
    item["regions"] = regions or ["Global"]
    item["commodities"] = [c for c, rx in _COMMODITY_RE.items() if rx.search(text)]
    return item


@st.cache_data(ttl=30 * 60, show_spinner="Fetching news…")
def get_news() -> pd.DataFrame:
    with ThreadPoolExecutor(max_workers=8) as pool:
        batches = list(pool.map(_fetch_feed, config.NEWS_FEEDS))
    items = [_tag(i) for batch in batches for i in batch]
    if not items:
        return pd.DataFrame(columns=["title", "link", "source", "feed", "published",
                                     "summary", "google", "image", "regions", "commodities"])
    df = pd.DataFrame(items)
    # De-duplicate the same story appearing in several feeds, keeping the copy with a summary
    df["key"] = df["title"].str.lower().str.replace(r"[^a-z0-9 ]", "", regex=True).str[:80]
    df["has_summary"] = df["summary"].str.len() > 0
    df = df.sort_values("has_summary", ascending=False).drop_duplicates("key")
    df = df.sort_values("published", ascending=False, na_position="last")
    df = df.drop(columns=["key", "has_summary"]).reset_index(drop=True)

    # Fill in missing images from the article pages (direct feeds only; cached per article)
    need = df.index[(df["image"] == "") & (~df["google"])]
    with ThreadPoolExecutor(max_workers=16) as pool:
        found = list(pool.map(og_image, df.loc[need, "link"]))
    df.loc[need, "image"] = found
    return df


# --------------------------------------------------------------------------
# JSE SENS announcements
# --------------------------------------------------------------------------
SAST = timezone(timedelta(hours=2))
SENS_STORE = Path(__file__).parent / "data" / "sens_history.json"
SENS_KEEP_DAYS = 180

_SENS_COMPANY_RE = {name: _compile(pats) for name, pats in config.SENS_COMPANIES.items()}
_SENS_MINING_RE = _compile(config.SENS_MINING_WORDS)
_SHARENET_ROW_RE = re.compile(
    r"sens_display\.php\?tdate=(\d{14})&(?:amp;)?seq=(\d+)&(?:amp;)?scode=([A-Z0-9]*)\"[^>]*>(.*?)</a>",
    re.S)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=20).read()


def _sharenet_sens() -> list[dict]:
    body = _get(config.SENS_SOURCES["sharenet"]).decode("utf-8", "replace")
    items = []
    for tdate, seq, code, headline in _SHARENET_ROW_RE.findall(body):
        headline = html.unescape(re.sub(r"\s+", " ", headline)).strip()
        items.append({
            "published": datetime.strptime(tdate, "%Y%m%d%H%M%S").replace(tzinfo=SAST).isoformat(),
            "headline": headline,
            "code": code,
            "link": f"https://www.sharenet.co.za/v3/sens_display.php?tdate={tdate}&seq={seq}&scode={code}",
            "source": "Sharenet",
        })
    return items


def _moneyweb_sens() -> list[dict]:
    parsed = feedparser.parse(_get(config.SENS_SOURCES["moneyweb"]))
    items = []
    for e in parsed.entries:
        try:
            published = parsedate_to_datetime(e.get("published", "")).isoformat()
        except Exception:
            continue
        items.append({
            "published": published,
            "headline": html.unescape(e.get("title", "")).strip(),
            "code": "",
            "link": e.get("link", ""),
            "source": "Moneyweb",
        })
    return items


def _sens_key(headline: str) -> str:
    return re.sub(r"[^a-z0-9]", "", headline.lower())[:90]


def _load_sens_store() -> list[dict]:
    try:
        return json.loads(SENS_STORE.read_text(encoding="utf-8"))
    except Exception:
        return []


@st.cache_data(ttl=20 * 60, show_spinner="Fetching SENS announcements…")
def get_sens() -> tuple[pd.DataFrame, list[str]]:
    """SENS announcements: fresh fetch merged with the locally saved history.

    Returns (dataframe, list of source errors).
    """
    errors = []
    fresh = []
    # Sharenet has the full list for ~2 days; Moneyweb (last 10 only) is the fallback
    for name, fn in [("Sharenet", _sharenet_sens), ("Moneyweb", _moneyweb_sens)]:
        try:
            fresh += fn()
            if fresh:
                break
        except Exception as ex:
            errors.append(f"{name}: {ex}")

    # Merge with saved history so the list grows beyond the ~2 days the sources show
    merged = {}
    for item in _load_sens_store() + fresh:
        merged.setdefault(_sens_key(item["headline"]), item)
    cutoff = datetime.now(timezone.utc) - timedelta(days=SENS_KEEP_DAYS)
    items = [i for i in merged.values() if datetime.fromisoformat(i["published"]) >= cutoff]
    try:
        SENS_STORE.parent.mkdir(exist_ok=True)
        SENS_STORE.write_text(json.dumps(items, indent=1), encoding="utf-8")
    except Exception as ex:
        errors.append(f"Could not save SENS history: {ex}")

    cols = ["published", "company", "headline", "code", "mining", "link", "source"]
    if not items:
        return pd.DataFrame(columns=cols), errors
    df = pd.DataFrame(items)
    df["published"] = pd.to_datetime(df["published"], utc=True).dt.tz_convert(SAST)
    df["company"] = df["headline"].apply(
        lambda h: next((n for n, rx in _SENS_COMPANY_RE.items() if rx.search(h)), ""))
    df["mining"] = (df["company"] != "") | df["headline"].str.contains(_SENS_MINING_RE)
    df = df.sort_values("published", ascending=False).reset_index(drop=True)
    return df[cols], errors


def feed_status() -> dict[str, int]:
    """How many items each feed returned (for the sidebar)."""
    df = get_news()
    return df["feed"].value_counts().to_dict() if len(df) else {}
