"""
Markt & Portfolio Dashboard
----------------------------
Draai lokaal met:   streamlit run dashboard.py
Hosten (gratis):    https://streamlit.io/cloud  (koppel een GitHub-repo)

Benodigde packages (zet in requirements.txt):
    streamlit
    requests
    yfinance
"""

import streamlit as st
import requests
import yfinance as yf
import json
import os
from datetime import datetime

st.set_page_config(page_title="Markt & Portfolio Dashboard", layout="wide", page_icon="📊")

PORTFOLIO_FILE = "portfolio.json"
NFT_COLLECTIONS = {
    # slug -> weergavenaam. Zoek slugs op via https://opensea.io/collection/<slug>
    "boredapeyachtclub": "Bored Ape Yacht Club",
    "cryptopunks": "CryptoPunks",
    "pudgypenguins": "Pudgy Penguins",
    "cryptodickbutts-s3": "CryptoDickbutts",
}

# CoinGecko id -> weergavenaam, voor de crypto-prijzenrij bovenaan
CRYPTO_TICKERS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "sui": "SUI",
}

# ---------------------------------------------------------------------------
# Data ophalen
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)  # 5 minuten cache, scheelt onnodige calls
def get_crypto_prices():
    """Haalt in één call de prijs + 24u-verandering op voor alle CRYPTO_TICKERS."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": ",".join(CRYPTO_TICKERS.keys()),
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            },
            timeout=10,
        ).json()
        result = {}
        for coin_id, label in CRYPTO_TICKERS.items():
            if coin_id in r:
                result[label] = (r[coin_id]["usd"], r[coin_id].get("usd_24h_change", 0))
            else:
                result[label] = (None, None)
        return result
    except Exception:
        return {label: (None, None) for label in CRYPTO_TICKERS.values()}


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


@st.cache_data(ttl=3600)  # 1x per uur is genoeg, wordt dagelijks bijgewerkt
def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=10).json()
        data = r["data"][0]
        return int(data["value"]), data["value_classification"]
    except Exception:
        return None, None


@st.cache_data(ttl=900)
def get_nft_floor_prices():
    """Reservoir's publieke API, geen key nodig voor lage volumes.
    Documentatie: https://docs.reservoir.tools/reference/getcollectionsv7
    """
    results = {}
    for slug, name in NFT_COLLECTIONS.items():
        try:
            r = requests.get(
                "https://api.reservoir.tools/collections/v7",
                params={"slug": slug},
                headers={"accept": "*/*"},
                timeout=10,
            ).json()
            floor = r["collections"][0]["floorAsk"]["price"]["amount"]["native"]
            results[name] = floor
        except Exception:
            results[name] = None
    return results


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        return json.load(open(PORTFOLIO_FILE))
    return []


def save_portfolio(portfolio):
    json.dump(portfolio, open(PORTFOLIO_FILE, "w"))


@st.cache_data(ttl=300)
def get_price_for_asset(symbol: str):
    """Probeert eerst crypto (CoinGecko id = lowercase symbol), dan aandeel (yfinance)."""
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


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("📊 Markt & Portfolio Dashboard")
st.caption(f"Laatst bijgewerkt: {datetime.now().strftime('%d-%m-%Y %H:%M')}")

crypto_prices = get_crypto_prices()
sp500, sp500_change = get_index_price("^GSPC")
nasdaq, nasdaq_change = get_index_price("^IXIC")
fng_value, fng_label = get_fear_greed()

st.subheader("💰 Crypto")
crypto_cols = st.columns(len(CRYPTO_TICKERS))
for col, label in zip(crypto_cols, CRYPTO_TICKERS.values()):
    price, change = crypto_prices[label]
    col.metric(label, f"${price:,.2f}" if price else "n.b.",
               f"{change:+.2f}%" if change is not None else None)

st.subheader("📈 Markten")
col1, col2, col3 = st.columns(3)
col1.metric("S&P 500", f"{sp500:,.0f}" if sp500 else "n.b.",
            f"{sp500_change:+.2f}%" if sp500_change is not None else None)
col2.metric("Nasdaq", f"{nasdaq:,.0f}" if nasdaq else "n.b.",
            f"{nasdaq_change:+.2f}%" if nasdaq_change is not None else None)
col3.metric("Fear & Greed", f"{fng_value}" if fng_value else "n.b.", fng_label)

st.divider()

st.subheader("🖼️ NFT Floor Prices")
nft_prices = get_nft_floor_prices()
nft_cols = st.columns(len(nft_prices) or 1)
for col, (name, price) in zip(nft_cols, nft_prices.items()):
    col.metric(name, f"{price:.2f} ETH" if price else "n.b.")

st.divider()

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
