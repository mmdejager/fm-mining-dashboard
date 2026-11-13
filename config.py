"""Watchlists, commodities and news sources for the Mining Tracker.

Edit this file to add or remove companies, commodities or feeds.
Tickers are Yahoo Finance symbols:
  .JO = JSE (Johannesburg), .L = London, .TO = Toronto, .AX = Australia,
  .HK = Hong Kong, no suffix = New York.
"""

# --------------------------------------------------------------------------
# Companies by region
# --------------------------------------------------------------------------
COMPANIES = {
    "South Africa": [
        {"ticker": "AGL.JO", "name": "Anglo American", "commodity": "Diversified"},
        {"ticker": "ANG.JO", "name": "AngloGold Ashanti", "commodity": "Gold"},
        {"ticker": "GFI.JO", "name": "Gold Fields", "commodity": "Gold"},
        {"ticker": "HAR.JO", "name": "Harmony Gold", "commodity": "Gold"},
        {"ticker": "DRD.JO", "name": "DRDGold", "commodity": "Gold"},
        {"ticker": "PAN.JO", "name": "Pan African Resources", "commodity": "Gold"},
        {"ticker": "SSW.JO", "name": "Sibanye-Stillwater", "commodity": "PGMs / Gold"},
        {"ticker": "IMP.JO", "name": "Impala Platinum", "commodity": "PGMs"},
        {"ticker": "VAL.JO", "name": "Valterra Platinum", "commodity": "PGMs"},
        {"ticker": "NPH.JO", "name": "Northam Platinum", "commodity": "PGMs"},
        {"ticker": "KIO.JO", "name": "Kumba Iron Ore", "commodity": "Iron ore"},
        {"ticker": "ARI.JO", "name": "African Rainbow Minerals", "commodity": "Diversified"},
        {"ticker": "EXX.JO", "name": "Exxaro", "commodity": "Coal"},
        {"ticker": "TGA.JO", "name": "Thungela", "commodity": "Coal"},
        {"ticker": "S32.JO", "name": "South32", "commodity": "Diversified"},
    ],
    "Rest of Africa": [
        {"ticker": "IVN.TO", "name": "Ivanhoe Mines (DRC)", "commodity": "Copper"},
        {"ticker": "FM.TO", "name": "First Quantum (Zambia)", "commodity": "Copper"},
        {"ticker": "EDV.L", "name": "Endeavour Mining (W. Africa)", "commodity": "Gold"},
        {"ticker": "B", "name": "Barrick (Kibali, Loulo)", "commodity": "Gold / Copper"},
        {"ticker": "PRU.AX", "name": "Perseus Mining", "commodity": "Gold"},
        {"ticker": "BTO.TO", "name": "B2Gold (Mali, Namibia)", "commodity": "Gold"},
        {"ticker": "RSG.AX", "name": "Resolute Mining", "commodity": "Gold"},
        {"ticker": "MAU.TO", "name": "Montage Gold (Côte d'Ivoire)", "commodity": "Gold"},
        {"ticker": "ORE.TO", "name": "Orezone (Burkina Faso)", "commodity": "Gold"},
    ],
    "Global": [
        {"ticker": "BHP", "name": "BHP", "commodity": "Diversified"},
        {"ticker": "RIO", "name": "Rio Tinto", "commodity": "Diversified"},
        {"ticker": "GLEN.L", "name": "Glencore", "commodity": "Diversified"},
        {"ticker": "VALE", "name": "Vale", "commodity": "Iron ore / Nickel"},
        {"ticker": "FCX", "name": "Freeport-McMoRan", "commodity": "Copper"},
        {"ticker": "TECK", "name": "Teck Resources", "commodity": "Copper / Zinc"},
        {"ticker": "NEM", "name": "Newmont", "commodity": "Gold"},
        {"ticker": "AEM", "name": "Agnico Eagle", "commodity": "Gold"},
        {"ticker": "2899.HK", "name": "Zijin Mining", "commodity": "Copper / Gold"},
        {"ticker": "CCJ", "name": "Cameco", "commodity": "Uranium"},
    ],
}

# --------------------------------------------------------------------------
# Commodities, FX and proxies
#   factor converts the Yahoo quote into the display unit
# --------------------------------------------------------------------------
TROY_OZ = "oz"
COMMODITIES = [
    {"ticker": "GC=F", "name": "Gold", "unit": "USD/oz", "group": "Precious", "factor": 1},
    {"ticker": "SI=F", "name": "Silver", "unit": "USD/oz", "group": "Precious", "factor": 1},
    {"ticker": "PL=F", "name": "Platinum", "unit": "USD/oz", "group": "PGMs", "factor": 1},
    {"ticker": "PA=F", "name": "Palladium", "unit": "USD/oz", "group": "PGMs", "factor": 1},
    {"ticker": "HG=F", "name": "Copper", "unit": "USD/t", "group": "Base", "factor": 2204.62},
    {"ticker": "ALI=F", "name": "Aluminium", "unit": "USD/t", "group": "Base", "factor": 1},
    {"ticker": "TIO=F", "name": "Iron ore 62%", "unit": "USD/t", "group": "Bulk", "factor": 1},
    {"ticker": "BZ=F", "name": "Brent crude", "unit": "USD/bbl", "group": "Energy", "factor": 1},
    {"ticker": "SRUUF", "name": "Uranium (Sprott trust proxy)", "unit": "USD/unit", "group": "Energy", "factor": 1},
    {"ticker": "LIT", "name": "Lithium (LIT ETF proxy)", "unit": "USD/unit", "group": "Battery", "factor": 1},
]

FX_USDZAR = "ZAR=X"

# Converts each listing currency to USD (for comparing company sizes).
#   (ticker, invert): invert=True when the quote is "units per USD".
FX_TO_USD = {
    "ZAR": ("ZAR=X", True),
    "GBP": ("GBPUSD=X", False),
    "CAD": ("CAD=X", True),
    "AUD": ("AUDUSD=X", False),
    "HKD": ("HKD=X", True),
}

# JSE indices for the Markets tab
#   (Yahoo has no price history for the Resource 10 index, ^J210.JO)
INDICES = {
    "^J200.JO": "JSE Top 40",
    "^J203.JO": "JSE All Share",
    "^J258.JO": "JSE SA Resources",
}

# Commodities to also show in rand (needs USD/ZAR)
SHOW_IN_ZAR = {"Gold", "Platinum", "Palladium"}

# --------------------------------------------------------------------------
# News feeds (RSS)
# --------------------------------------------------------------------------
_GN = "https://news.google.com/rss/search?q={q}+when:7d&hl=en-ZA&gl=ZA&ceid=ZA:en"

# Direct feeds include a short article summary. "filter": True keeps only
# mining-related headlines (for general business feeds).
NEWS_FEEDS = [
    {"name": "Mining Weekly", "url": "https://www.miningweekly.com/page/latest-news/feed"},
    {"name": "Mining.com", "url": "https://www.mining.com/feed/"},
    {"name": "The Northern Miner", "url": "https://www.northernminer.com/feed/"},
    {"name": "Mining Review Africa", "url": "https://www.miningreview.com/feed/"},
    {"name": "Australian Mining", "url": "https://www.australianmining.com.au/feed/"},
    {"name": "African Business", "url": "https://african.business/feed", "filter": True},
    {"name": "Moneyweb", "url": "https://www.moneyweb.co.za/feed/", "filter": True},
    {"name": "IOL Business", "url": "https://iol.co.za/rss/iol/business/", "filter": True},
    # Google News searches widen coverage but carry headlines only (no summary)
    {"name": "Google News: SA mining",
     "url": _GN.format(q="mining+%22South+Africa%22")},
    {"name": "Google News: JSE miners",
     "url": _GN.format(q="%22Sibanye%22+OR+%22Harmony+Gold%22+OR+%22Gold+Fields%22+OR+%22Implats%22"
                         "+OR+%22Valterra%22+OR+%22Northam+Platinum%22+OR+%22Exxaro%22+OR+%22Kumba%22")},
    {"name": "Google News: Africa mining",
     "url": _GN.format(q="mining+(Ghana+OR+DRC+OR+Zambia+OR+Mali+OR+Namibia+OR+Zimbabwe+OR+Botswana)")},
    {"name": "Google News: Global majors",
     "url": _GN.format(q="mining+(BHP+OR+%22Rio+Tinto%22+OR+Glencore+OR+Vale+OR+Newmont+OR+Freeport-McMoRan)")},
    {"name": "Google News: Metals markets",
     "url": _GN.format(q="%22gold+price%22+OR+%22platinum+price%22+OR+%22copper+price%22+OR+%22iron+ore+price%22")},
]

# --------------------------------------------------------------------------
# JSE SENS announcements
#   Headlines are matched to companies by these name patterns (case-insensitive).
#   Any JSE-listed company can be added, not only the ones in COMPANIES.
# --------------------------------------------------------------------------
SENS_COMPANIES = {
    "Anglo American": ["anglo american plc", "anglo american limited"],
    "AngloGold Ashanti": ["anglogold"],
    "Gold Fields": ["gold fields"],
    "Harmony Gold": ["harmony gold"],
    "DRDGold": ["drdgold"],
    "Pan African Resources": ["pan african resources"],
    "Sibanye-Stillwater": ["sibanye"],
    "Impala Platinum": ["impala platinum", "implats"],
    "Valterra Platinum": ["valterra"],
    "Northam Platinum": ["northam"],
    "Kumba Iron Ore": ["kumba"],
    "African Rainbow Minerals": ["african rainbow minerals"],
    "Exxaro": ["exxaro"],
    "Thungela": ["thungela"],
    "South32": ["south32"],
    "Glencore": ["glencore"],
    "BHP": ["bhp group"],
    "Sasol Mining / Sasol": ["sasol limited"],
    "Assore / Afrimat": ["afrimat", "assore"],
    "Merafe / Jubilee / Sylvania": ["merafe", "jubilee metals", "sylvania platinum"],
    "Tharisa / Orion / Master Drilling": ["tharisa", "orion minerals", "master drilling"],
}

# Generic words that flag a SENS headline as mining-related (for the "all mining" view)
SENS_MINING_WORDS = ["mining", "mines", "minerals", "resources limited", "gold", "platinum",
                     "coal", "iron ore", "manganese", "chrome", "copper", "diamond", "exploration"]

SENS_SOURCES = {
    "sharenet": "https://www.sharenet.co.za/v3/sens.php",
    "moneyweb": "https://www.moneyweb.co.za/feed/?post_type=mny_sens",
}

# --------------------------------------------------------------------------
# AI briefings (Claude API). Key comes from .streamlit/secrets.toml or the
# ANTHROPIC_API_KEY environment variable.
# --------------------------------------------------------------------------
AI_MODEL = "claude-opus-5-5"

# --------------------------------------------------------------------------
# Keyword tagging for news (lower-case)
# --------------------------------------------------------------------------
REGION_KEYWORDS = {
    "South Africa": [
        "south africa", "south african", "johannesburg", "jse", "mpumalanga", "limpopo",
        "rustenburg", "bushveld", "witwatersrand", "gauteng", "northern cape", "north west province",
        "eskom", "transnet", "mineral resources council", "dmre", "mantashe", "motsepe",
        "sibanye", "harmony gold", "gold fields", "implats", "impala platinum", "valterra", "amplats",
        "northam", "exxaro", "kumba", "thungela", "african rainbow", "drdgold", "pan african resources",
        "anglogold",
    ],
    "Rest of Africa": [
        "ghana", "drc", "congo", "zambia", "zimbabwe", "namibia", "botswana", "mali", "burkina",
        "guinea", "tanzania", "kenya", "mozambique", "madagascar", "côte d'ivoire", "ivory coast",
        "senegal", "niger", "nigeria", "egypt", "morocco", "sudan", "ethiopia", "angola", "malawi",
        "sierra leone", "liberia", "mauritania", "uganda", "ivanhoe", "kamoa", "first quantum",
        "endeavour mining", "kibali", "loulo", "perseus", "b2gold", "resolute mining", "montage gold",
        "orezone", "debswana",
    ],
}

COMMODITY_KEYWORDS = {
    "Gold": ["gold"],
    "Silver": ["silver"],
    "PGMs": ["platinum", "palladium", "rhodium", "pgm"],
    "Copper": ["copper"],
    "Iron ore": ["iron ore", "iron-ore"],
    "Coal": ["coal"],
    "Manganese / Chrome": ["manganese", "chrome", "chromite"],
    "Battery metals": ["lithium", "nickel", "cobalt", "graphite"],
    "Uranium": ["uranium"],
    "Diamonds": ["diamond"],
}
