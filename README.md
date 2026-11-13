# Mining Tracker

A Streamlit dashboard tracking mining shares (South Africa, rest of Africa, global),
key commodity prices (in USD and ZAR) and mining news.

## Hosted Dashboard (Free Url On GitHub Pages)

`docs/index.html` is a TV-style Overview page in the Fraser McGill template colours (dark navy
background, FM blue #0083CA and orange #F5B75E): price metrics and today's biggest movers at the top,
the SA gold and PGM miners vs the rand metal price charts and the latest stories below, and the
FM Superbru leaderboard in a sidebar on the right.
A free GitHub Action runs `build_data.py` on a schedule and publishes `docs/data.json`;
the page reads it every 5 minutes. Superbru loads live from the Google Sheet every 60 seconds
(if the sheet can't be reached, the last saved standings in `index.html` are shown).
Charts use Plotly (`docs/plotly.min.js`, MIT licence). Text uses Avenir Next where the computer has
it, otherwise Source Sans 3 (`docs/fonts`, SIL Open Font Licence). Both are stored in the repo, so
nothing loads from other sites.

### Setup (once)

1. Create a free GitHub account and a new **public** repository (free Pages needs a public repo,
   so anyone with the link can see the page).
2. Upload everything in this folder **except** `.streamlit/secrets.toml` (it's in `.gitignore`).
   Make sure the hidden `.github` folder is included.
3. Repo **Settings > Pages > Build and deployment > Source: GitHub Actions**.
4. **Actions** tab > *Update mining dashboard* > **Run workflow**. After ~3 minutes the page is live at
   `https://<your-username>.github.io/<repo-name>/`.

### Schedule

Weekdays every 30 minutes from 05:00 to 21:30 SAST, weekends every 4 hours (edit the `cron` lines in
`.github/workflows/update-dashboard.yml`). GitHub sometimes starts scheduled runs a few minutes late.
Each run commits the new data, which also keeps the schedule from being switched off for inactivity.

### If a source fails

If Yahoo Finance or the news feeds block a run, the previous data is kept and the footer
dot in the Superbru sidebar turns orange. The **Run workflow** button retries straight away.

### Updating the Superbru fallback

The live list comes from the Apps Script URL in `RUGBY_LB_URL` (in `docs/index.html`). The
`RUGBY_FALLBACK` list just below it is only shown when that URL fails.

## First-time setup (new computer)

1. Install Python 3.12 or newer from https://www.python.org/downloads/ and tick
   **"Add python.exe to PATH"** during installation.
2. Unzip this folder somewhere (e.g. Documents\Mining_Tracker).
3. Double-click **`run.bat`**. The first run takes a few minutes while it installs the
   packages; after that it opens the dashboard in your browser at http://localhost:8501.

## Run it

- **Double-click `run.bat`**, or
- **In VS Code:** open this folder, press `F5` (uses *Run Mining Tracker* in `.vscode/launch.json`), or
- **Terminal:** `%USERPROFILE%\.venvs\mining-tracker\Scripts\python.exe -m streamlit run app.py`

### Start it automatically every morning

1. Press **Win + R**, type `shell:startup` and press Enter. A folder opens.
2. In this project folder, right-click `start_dashboard.vbs` → **Show more options** →
   **Create shortcut**, then drag the shortcut into the Startup folder.
3. In your browser, set `http://localhost:8501` as a page that opens on start-up
   (Edge: Settings → Start, home, and new tab page → Open these pages;
   Chrome: Settings → On start-up → Open a specific page).

The dashboard then starts silently whenever you log in (no window), and loads fresh data when the
browser opens it. It is only reachable from this computer. To stop it, run `stop_dashboard.bat`;
to stop it starting at login, delete the shortcut from the Startup folder.

The dashboard opens at http://localhost:8501. Prices refresh every 15 minutes, news every 30;
use **Refresh data** in the sidebar to force it.

## Markets tab

- **Sector heatmap**: every tracked company, box size = market value in USD (converted with live
  FX rates), colour = performance over 1D / 1W / 1M / YTD. Region boxes show the
  market-value-weighted average.
- **JSE indices**: Top 40, All Share and SA Resources against the rand gold price.
  (Yahoo has no history for the Resource 10 index.)
- **Commodity ratios**: gold/silver, gold/platinum and platinum/palladium against their 1-year average.
- **Valuations**: market value, P/E, forward P/E, dividend yield, P/B, EV/EBITDA and distance
  from the 52-week high (Yahoo Finance, refreshed twice a day).

## Company tab

Pick any tracked company to see: price and performance, market value (local and US$), dividend
yield, forward P/E, a 52-week range bar, analyst target and consensus, a share price chart (optionally
compared with the company's main commodity), five years of dividends, key dates (results,
ex-dividend), a company profile, and the news and SENS announcements that mention it.
Data from Yahoo Finance, cached for 6 hours.

## Calendar tab

Results and dividend dates for every tracked company:

- **Coming up**: the next 30 days, 90 days or 6 months, grouped by month.
- **Recent results & dividend SENS** from tracked companies.
- **Timeline**: six months back and forward (faded = past, solid = confirmed, hollow = estimated).
- **By company**: last and next results, last and next ex-dividend date, dividends over 12 months.

*Confirmed* dates come from Yahoo Finance. *Estimated* dates are projected from each company's
usual rhythm: half-yearly results for JSE, London, ASX and Hong Kong listings (plus BHP and Rio
Tinto), quarterly for US and Canada, and dividends from the usual gap between payments.

## Article summaries

Stories from the direct feeds (Mining Weekly, Mining.com, The Northern Miner, Mining Review Africa,
Australian Mining, African Business, Moneyweb, IOL Business) show the publisher's own short summary
under the headline. Google News stories are marked *headline only* because Google doesn't provide
summaries or direct links, and each Google search is capped at 15 stories (`GOOGLE_MAX_PER_SEARCH`
in `data.py`). If a direct-feed story has no summary, a **Preview** button loads the article's
opening paragraphs. The News tab can hide headline-only stories.

## AI summaries

The **Generate today's briefing** button (Overview tab) and the **Summarise** buttons (News and
JSE SENS tabs) send the prices, headlines and SENS headlines shown on the dashboard to Claude
and display a written summary. To switch them on:

1. Create an API key at https://console.anthropic.com (API Keys). Usage is billed to that account;
   a briefing typically costs a few US cents.
2. In the `.streamlit` folder, copy `secrets.toml.example` to `secrets.toml` and paste the key in.
3. Restart the dashboard.

Summaries are cached for an hour, so pressing the button again doesn't re-bill. The model is set
by `AI_MODEL` in `config.py`. If the model declines a request, the API automatically retries on a
fallback model (`fallbacks="default"` in `ai.py`).

## JSE SENS

The **JSE SENS** tab lists company announcements from Sharenet's public SENS page (15-minute
delay), with Moneyweb's SENS feed as a fallback. The JSE's own site blocks automated access.
Those pages only show about two days, so every refresh saves announcements to
`data/sens_history.json` and the history builds up over time (kept for 180 days).
Headlines are matched to companies using `SENS_COMPANIES` in `config.py`.

## Files

| File | What it does |
|---|---|
| `config.py` | Watchlists, commodities, news feeds, SENS companies and tagging keywords. **Edit this to change what's tracked.** |
| `data.py` | Fetches prices (Yahoo Finance via `yfinance`), news (RSS) and SENS; tags news by region/commodity |
| `ai.py` | AI briefings and summaries via the Claude API |
| `app.py` | The dashboard layout |

The Python environment lives in `%USERPROFILE%\.venvs\mining-tracker` (outside OneDrive on purpose).
To rebuild it: delete that folder and run `run.bat`.

## Data notes

- Prices are from Yahoo Finance: unofficial, ~15 min delayed. Fine for monitoring, not for trading or redistribution.
- JSE prices are converted from cents to rand; LSE from pence to pounds.
- Copper is converted from USD/lb to USD/t. Iron ore is the SGX 62% Fe future.
- Uranium (Sprott Physical Uranium Trust) and lithium (LIT ETF) are proxies, not spot prices.
- Not covered by free sources: thermal coal (Richards Bay), manganese, chrome, rhodium. Options: Trading Economics, Metals-API, Argus, Fastmarkets, or Johnson Matthey's published PGM prices.

## Ideas for later

- AI summary of full SENS announcement text (not just headlines)
- Daily email or Teams digest
- Host it for the team (Streamlit Community Cloud, Azure App Service) or rebuild in Power BI
