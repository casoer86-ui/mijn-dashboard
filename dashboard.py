"""
Markt & Portfolio Dashboard
----------------------------
Draai lokaal met:   streamlit run dashboard.py
Hosten (gratis):    https://streamlit.io/cloud  (koppel een GitHub-repo)

Benodigde packages (zet in requirements.txt):
    streamlit
    requests
    yfinance
    plotly
    pandas
"""

import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
import os
from datetime import datetime

st.set_page_config(page_title="Markt & Portfolio Dashboard", layout="wide", page_icon="📊")

# OpenSea vereist een (gratis) API key. Zet 'm in Streamlit Cloud
# onder je app -> Settings -> Secrets als:  OPENSEA_API_KEY = "jouw_key_hier"
try:
    OPENSEA_API_KEY = st.secrets.get("OPENSEA_API_KEY", "")
except Exception:
    OPENSEA_API_KEY = ""

PORTFOLIO_FILE = "portfolio.json"

# ---------------------------------------------------------------------------
# Universums / vaste lijsten
# ---------------------------------------------------------------------------

# ~50 grote techbedrijven, gebruikt voor "top 5 tech stijgers"
TECH_50 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM",
    "ADBE", "AMD", "INTC", "CSCO", "QCOM", "TXN", "IBM", "NOW", "INTU", "AMAT",
    "MU", "ADI", "LRCX", "KLAC", "PANW", "SNPS", "CDNS", "MRVL", "FTNT", "ANSS",
    "CRWD", "WDAY", "TEAM", "DDOG", "ZS", "NET", "SNOW", "PLTR", "SHOP", "UBER",
    "ABNB", "DELL", "HPQ", "HPE", "STX", "WDC", "NXPI", "ON", "MCHP", "APP",
]

# Bredere set (tech + andere sectoren), gebruikt voor "top 5 by volume"
OTHER_LARGE_CAPS = [
    "JPM", "BAC", "WFC", "XOM", "CVX", "JNJ", "PFE", "UNH", "WMT", "PG",
    "KO", "PEP", "DIS", "NKE", "MCD", "HD", "LOW", "V", "MA", "PYPL",
    "F", "GM", "T", "VZ", "BA", "GE", "CAT",
]
STOCK_VOLUME_UNIVERSE = list(dict.fromkeys(TECH_50 + OTHER_LARGE_CAPS))

# Crypto-tickers voor de bovenste banner (CoinGecko id's)
BANNER_CRYPTO = {"bitcoin": "BTC", "solana": "SOL", "ethereum": "ETH"}

# NFT-collecties waarover we een top-5-by-volume ranking maken.
# BAYC, CryptoPunks en CryptoDickbutts krijgen daarnaast altijd hun eigen kaart.
NFT_COLLECTIONS = {
    "boredapeyachtclub": "BAYC",
    "cryptopunks": "CryptoPunks",
    "cryptodickbutts-s3": "CryptoDickbutts",
    "pudgypenguins": "Pudgy Penguins",
    "mutant-ape-yacht-club": "Mutant Ape Yacht Club",
    "azuki": "Azuki",
    "doodles-official": "Doodles",
    "clonex": "CloneX",
    "moonbirds": "Moonbirds",
    "milady": "Milady",
    "degods": "DeGods",
    "coolcats-nft": "Cool Cats",
    "meebits": "Meebits",
}
NFT_FEATURED_SLUGS = ["boredapeyachtclub", "cryptopunks", "cryptodickbutts-s3"]

# ---------------------------------------------------------------------------
# Data ophalen — crypto & aandelen
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_crypto_banner():
    """Prijs + 24u-verandering voor BTC, SOL, ETH."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": ",".join(BANNER_CRYPTO.keys()),
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            },
            timeout=10,
        ).json()
        result = {}
        for coin_id, label in BANNER_CRYPTO.items():
            if coin_id in r:
                result[label] = (r[coin_id]["usd"], r[coin_id].get("usd_24h_change", 0))
            else:
                result[label] = (None, None)
        return result
    except Exception:
        return {label: (None, None) for label in BANNER_CRYPTO.values()}


@st.cache_data(ttl=300)
def get_index_price(ticker: str):
    try:
        hist = yf.Ticker(ticker).history(period="2d")
        if len(hist) < 2:
            return hist["Close"].iloc[-1], 0
        last, prev = hist["Close"].iloc[-1], hist["Close"].iloc[-2]
        change = (last - prev) / prev * 100
        return last, change
    except Exception:
        return None, None


@st.cache_data(ttl=3600)
def get_fear_greed_crypto():
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=10).json()
        data = r["data"][0]
        return int(data["value"]), data["value_classification"]
    except Exception:
        return None, None


@st.cache_data(ttl=3600)
def get_fear_greed_stocks():
    """CNN's Fear & Greed index heeft geen officiële publieke API.
    Dit gebruikt hun eigen (onofficiële) data-endpoint — kan zonder
    aankondiging veranderen of tijdelijk niet werken."""
    try:
        r = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        ).json()
        score = r["fear_and_greed"]["score"]
        rating = r["fear_and_greed"]["rating"]
        return round(score), rating.replace("_", " ").title()
    except Exception:
        return None, None


@st.cache_data(ttl=900)
def get_stock_universe_data():
    """Eén batch-call voor het hele aandelenuniversum: laatste volume + dagverandering."""
    try:
        data = yf.download(
            tickers=STOCK_VOLUME_UNIVERSE,
            period="2d",
            group_by="ticker",
            progress=False,
            threads=True,
        )
        rows = []
        for ticker in STOCK_VOLUME_UNIVERSE:
            try:
                sub = data[ticker].dropna()
                if len(sub) < 2:
                    continue
                last_close, prev_close = sub["Close"].iloc[-1], sub["Close"].iloc[-2]
                volume = sub["Volume"].iloc[-1]
                pct_change = (last_close - prev_close) / prev_close * 100
                rows.append({"ticker": ticker, "volume": volume, "pct_change": pct_change})
            except Exception:
                continue
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame(columns=["ticker", "volume", "pct_change"])


@st.cache_data(ttl=900)
def get_crypto_top100():
    """Top 100 coins op marktkapitalisatie, met 24u volume en prijsverandering."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 100,
                "page": 1,
                "price_change_percentage": "24h",
            },
            timeout=10,
        ).json()
        return pd.DataFrame(r)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900)
def get_btc_vs_nasdaq():
    """30 dagen Bitcoin vs Nasdaq, beide geïndexeerd als % verandering
    zodat ze op dezelfde schaal vergelijkbaar zijn."""
    try:
        btc = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            params={"vs_currency": "usd", "days": 30},
            timeout=10,
        ).json()
        btc_df = pd.DataFrame(btc["prices"], columns=["ts", "price"])
        btc_df["date"] = pd.to_datetime(btc_df["ts"], unit="ms").dt.date
        btc_df = btc_df.groupby("date")["price"].last().reset_index()
        btc_df["pct"] = (btc_df["price"] / btc_df["price"].iloc[0] - 1) * 100

        nasdaq_hist = yf.Ticker("^IXIC").history(period="1mo")["Close"]
        nasdaq_pct = (nasdaq_hist / nasdaq_hist.iloc[0] - 1) * 100

        return btc_df["date"], btc_df["pct"], nasdaq_hist.index, nasdaq_pct
    except Exception:
        return None, None, None, None


@st.cache_data(ttl=900)
def get_nft_stats(eth_usd_price):
    """OpenSea API v2 — floor price + 24u-volume per collectie."""
    results = {}
    headers = {"accept": "application/json"}
    if OPENSEA_API_KEY:
        headers["x-api-key"] = OPENSEA_API_KEY
    for slug, name in NFT_COLLECTIONS.items():
        try:
            r = requests.get(
                f"https://api.opensea.io/api/v2/collections/{slug}/stats",
                headers=headers,
                timeout=10,
            ).json()
            floor_eth = r["total"]["floor_price"]
            floor_usd = floor_eth * eth_usd_price if (floor_eth and eth_usd_price) else None
            volume_24h = None
            for interval in r.get("intervals", []):
                if interval.get("interval") == "one_day":
                    volume_24h = interval.get("volume")
            results[slug] = {
                "name": name,
                "floor_eth": floor_eth,
                "floor_usd": floor_usd,
                "volume_24h": volume_24h,
            }
        except Exception:
            results[slug] = {"name": name, "floor_eth": None, "floor_usd": None, "volume_24h": None}
    return results


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        return json.load(open(PORTFOLIO_FILE))
    return []


def save_portfolio(portfolio):
    json.dump(portfolio, open(PORTFOLIO_FILE, "w"))


@st.cache_data(ttl=300)
def get_price_for_asset(symbol: str):
    symbol_clean = symbol.strip().lower()
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": symbol_clean, "vs_currencies": "usd"},
            timeout=10,
        ).json()
        if symbol_clean in r:
            return r[symbol_clean]["usd"]
    except Exception:
        pass
    try:
        hist = yf.Ticker(symbol.upper()).history(period="1d")
        if not hist.empty:
            return hist["Close"].iloc[-1]
    except Exception:
        pass
    return None


def render_gauge(value, label, title):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value if value is not None else 0,
        title={"text": f"{title}<br><span style='font-size:0.8em'>{label or 'n.b.'}</span>"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#444"},
            "steps": [
                {"range": [0, 25], "color": "#d64545"},
                {"range": [25, 45], "color": "#e08a3c"},
                {"range": [45, 55], "color": "#e0d13c"},
                {"range": [55, 75], "color": "#8bc44e"},
                {"range": [75, 100], "color": "#3fae4a"},
            ],
        },
    ))
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=50, b=10), template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)


def render_ranked_list(pairs, value_fmt):
    for i, (name, value) in enumerate(pairs, 1):
        st.write(f"**{i}. {name}** — {value_fmt(value)}")


# ---------------------------------------------------------------------------
# UI — banner
# ---------------------------------------------------------------------------

st.title("📊 Markt & Portfolio Dashboard")
st.caption(f"Laatst bijgewerkt: {datetime.now().strftime('%d-%m-%Y %H:%M')}")

crypto_banner = get_crypto_banner()
sp500, sp500_change = get_index_price("^GSPC")

b1, b2, b3, b4 = st.columns(4)
b1.metric("S&P 500", f"{sp500:,.0f}" if sp500 else "n.b.",
          f"{sp500_change:+.2f}%" if sp500_change is not None else None)
for col, label in zip([b2, b3, b4], ["BTC", "SOL", "ETH"]):
    price, change = crypto_banner.get(label, (None, None))
    col.metric(label, f"${price:,.2f}" if price else "n.b.",
               f"{change:+.2f}%" if change is not None else None)

st.divider()

# ---------------------------------------------------------------------------
# UI — hoofdrij: links / midden (chart) / rechts
# ---------------------------------------------------------------------------

left_col, center_col, right_col = st.columns([1, 2.2, 1])

stock_data = get_stock_universe_data()
crypto_top100 = get_crypto_top100()

with left_col:
    st.markdown("##### 📈 Top 5 tech stijgers")
    if not stock_data.empty:
        tech_df = stock_data[stock_data["ticker"].isin(TECH_50)]
        top_tech = tech_df.sort_values("pct_change", ascending=False).head(5)
        render_ranked_list(list(zip(top_tech["ticker"], top_tech["pct_change"])),
                            lambda v: f"{v:+.2f}%")
    else:
        st.write("n.b.")

    st.markdown("##### 📊 Top 5 aandelen (volume)")
    if not stock_data.empty:
        top_vol = stock_data.sort_values("volume", ascending=False).head(5)
        render_ranked_list(list(zip(top_vol["ticker"], top_vol["volume"])),
                            lambda v: f"{v:,.0f}")
    else:
        st.write("n.b.")

    fng_stocks_value, fng_stocks_label = get_fear_greed_stocks()
    render_gauge(fng_stocks_value, fng_stocks_label, "Fear & Greed — Aandelen")

with center_col:
    st.markdown("##### ₿ Bitcoin vs Nasdaq (30 dagen, % verandering)")
    btc_dates, btc_pct, nasdaq_dates, nasdaq_pct = get_btc_vs_nasdaq()
    if btc_dates is not None:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(btc_dates), y=list(btc_pct), name="Bitcoin",
                                  line=dict(color="#f2a900", width=2)))
        fig.add_trace(go.Scatter(x=list(nasdaq_dates), y=list(nasdaq_pct), name="Nasdaq",
                                  line=dict(color="#00bfff", width=2)))
        fig.update_layout(template="plotly_dark", height=480,
                           margin=dict(l=20, r=20, t=20, b=20),
                           yaxis_title="% verandering", legend=dict(orientation="h", y=1.05))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("Grafiekdata niet beschikbaar.")

with right_col:
    st.markdown("##### 🚀 Top 5 crypto stijgers")
    if not crypto_top100.empty:
        top_gainers = crypto_top100.sort_values("price_change_percentage_24h", ascending=False).head(5)
        render_ranked_list(list(zip(top_gainers["symbol"].str.upper(),
                                     top_gainers["price_change_percentage_24h"])),
                            lambda v: f"{v:+.2f}%")
    else:
        st.write("n.b.")

    st.markdown("##### 💧 Top 5 munten (volume)")
    if not crypto_top100.empty:
        top_vol_crypto = crypto_top100.sort_values("total_volume", ascending=False).head(5)
        render_ranked_list(list(zip(top_vol_crypto["symbol"].str.upper(),
                                     top_vol_crypto["total_volume"])),
                            lambda v: f"${v:,.0f}")
    else:
        st.write("n.b.")

    fng_crypto_value, fng_crypto_label = get_fear_greed_crypto()
    render_gauge(fng_crypto_value, fng_crypto_label, "Fear & Greed — Crypto")

st.divider()

# ---------------------------------------------------------------------------
# UI — NFT's
# ---------------------------------------------------------------------------

st.subheader("🖼️ NFT's")
if not OPENSEA_API_KEY:
    st.warning(
        "Geen OpenSea API key ingesteld — NFT-prijzen kunnen niet worden opgehaald. "
        "Zet 'm in je app-instellingen onder Secrets als OPENSEA_API_KEY."
    )

eth_price = crypto_banner.get("ETH", (None, None))[0]
nft_stats = get_nft_stats(eth_price)

nft_left, nft_right = st.columns([1.3, 2])

with nft_left:
    st.markdown("##### Top 5 collecties (24u volume)")
    ranked = sorted(
        [v for v in nft_stats.values() if v["volume_24h"] is not None],
        key=lambda v: v["volume_24h"], reverse=True,
    )[:5]
    if ranked:
        render_ranked_list([(v["name"], v["volume_24h"]) for v in ranked],
                            lambda v: f"{v:,.1f} ETH")
    else:
        st.write("n.b.")

with nft_right:
    st.markdown("##### Uitgelicht")
    featured_cols = st.columns(3)
    for col, slug in zip(featured_cols, NFT_FEATURED_SLUGS):
        stats = nft_stats.get(slug, {})
        floor_eth = stats.get("floor_eth")
        floor_usd = stats.get("floor_usd")
        col.metric(
            stats.get("name", slug),
            f"{floor_eth:.3f} ETH" if floor_eth else "n.b.",
            f"${floor_usd:,.0f}" if floor_usd else None,
        )

st.divider()

# ---------------------------------------------------------------------------
# UI — Portfolio
# ---------------------------------------------------------------------------

st.subheader("💼 Mijn Portfolio")

portfolio = load_portfolio()

with st.form("add_holding", clear_on_submit=True):
    c1, c2, c3 = st.columns([2, 1, 1])
    asset = c1.text_input("Asset (bv. bitcoin, AAPL, ethereum)")
    amount = c2.number_input("Aantal", min_value=0.0, step=0.01, format="%.4f")
    submitted = c3.form_submit_button("➕ Toevoegen")
    if submitted and asset and amount > 0:
        portfolio.append({"asset": asset, "amount": amount})
        save_portfolio(portfolio)
        st.rerun()

if portfolio:
    total_value = 0
    rows = []
    for holding in portfolio:
        price = get_price_for_asset(holding["asset"])
        value = price * holding["amount"] if price else None
        if value:
            total_value += value
        rows.append({
            "Asset": holding["asset"],
            "Aantal": holding["amount"],
            "Prijs": f"${price:,.2f}" if price else "n.b.",
            "Waarde": f"${value:,.2f}" if value else "n.b.",
        })

    st.table(rows)
    st.metric("Totale portfoliowaarde", f"${total_value:,.2f}")

    if st.button("🗑️ Portfolio legen"):
        save_portfolio([])
        st.rerun()
else:
    st.info("Nog geen holdings toegevoegd. Vul hierboven een asset en aantal in.")
