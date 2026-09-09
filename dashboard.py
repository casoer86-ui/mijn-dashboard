"""
Markt Overzicht
----------------------------
Draai lokaal met:   streamlit run dashboard.py
Hosten (gratis):    https://streamlit.io/cloud  (koppel een GitHub-repo)

Benodigde packages (zet in requirements.txt):
    streamlit>=1.32
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
import os
from datetime import datetime

st.set_page_config(page_title="Markt Overzicht", layout="wide", page_icon="📊")

# OpenSea vereist een (gratis) API key. Zet 'm in Streamlit Cloud
# onder je app -> Settings -> Secrets als:  OPENSEA_API_KEY = "jouw_key_hier"
try:
    OPENSEA_API_KEY = st.secrets.get("OPENSEA_API_KEY", "")
except Exception:
    OPENSEA_API_KEY = ""

# ---------------------------------------------------------------------------
# Zwart thema + losse "kaartjes" per onderdeel
# ---------------------------------------------------------------------------

st.markdown("""
<style>
.stApp { background-color: #000000; }
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #111318;
    border: 1px solid #262a33;
    border-radius: 12px;
    padding: 4px 4px 10px 4px;
}
div[data-testid="stMetric"] {
    background-color: #111318;
    border: 1px solid #262a33;
    border-radius: 12px;
    padding: 10px 14px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Universums / vaste lijsten
# ---------------------------------------------------------------------------

TECH_50 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM",
    "ADBE", "AMD", "INTC", "CSCO", "QCOM", "TXN", "IBM", "NOW", "INTU", "AMAT",
    "MU", "ADI", "LRCX", "KLAC", "PANW", "SNPS", "CDNS", "MRVL", "FTNT", "ANSS",
    "CRWD", "WDAY", "TEAM", "DDOG", "ZS", "NET", "SNOW", "PLTR", "SHOP", "UBER",
    "ABNB", "DELL", "HPQ", "HPE", "STX", "WDC", "NXPI", "ON", "MCHP", "APP",
]

OTHER_LARGE_CAPS = [
    "JPM", "BAC", "WFC", "XOM", "CVX", "JNJ", "PFE", "UNH", "WMT", "PG",
    "KO", "PEP", "DIS", "NKE", "MCD", "HD", "LOW", "V", "MA", "PYPL",
    "F", "GM", "T", "VZ", "BA", "GE", "CAT",
]
STOCK_VOLUME_UNIVERSE = list(dict.fromkeys(TECH_50 + OTHER_LARGE_CAPS))

# Ticker -> domein, gebruikt om het bedrijfslogo op te halen via Clearbit
TICKER_DOMAINS = {
    "AAPL": "apple.com", "MSFT": "microsoft.com", "GOOGL": "google.com", "AMZN": "amazon.com",
    "NVDA": "nvidia.com", "META": "meta.com", "TSLA": "tesla.com", "AVGO": "broadcom.com",
    "ORCL": "oracle.com", "CRM": "salesforce.com", "ADBE": "adobe.com", "AMD": "amd.com",
    "INTC": "intel.com", "CSCO": "cisco.com", "QCOM": "qualcomm.com", "TXN": "ti.com",
    "IBM": "ibm.com", "NOW": "servicenow.com", "INTU": "intuit.com", "AMAT": "appliedmaterials.com",
    "MU": "micron.com", "ADI": "analog.com", "LRCX": "lamresearch.com", "KLAC": "kla.com",
    "PANW": "paloaltonetworks.com", "SNPS": "synopsys.com", "CDNS": "cadence.com", "MRVL": "marvell.com",
    "FTNT": "fortinet.com", "ANSS": "ansys.com", "CRWD": "crowdstrike.com", "WDAY": "workday.com",
    "TEAM": "atlassian.com", "DDOG": "datadoghq.com", "ZS": "zscaler.com", "NET": "cloudflare.com",
    "SNOW": "snowflake.com", "PLTR": "palantir.com", "SHOP": "shopify.com", "UBER": "uber.com",
    "ABNB": "airbnb.com", "DELL": "dell.com", "HPQ": "hp.com", "HPE": "hpe.com",
    "STX": "seagate.com", "WDC": "westerndigital.com", "NXPI": "nxp.com", "ON": "onsemi.com",
    "MCHP": "microchip.com", "APP": "applovin.com",
    "JPM": "jpmorganchase.com", "BAC": "bankofamerica.com", "WFC": "wellsfargo.com", "XOM": "exxonmobil.com",
    "CVX": "chevron.com", "JNJ": "jnj.com", "PFE": "pfizer.com", "UNH": "unitedhealthgroup.com",
    "WMT": "walmart.com", "PG": "pg.com", "KO": "coca-cola.com", "PEP": "pepsico.com",
    "DIS": "disney.com", "NKE": "nike.com", "MCD": "mcdonalds.com", "HD": "homedepot.com",
    "LOW": "lowes.com", "V": "visa.com", "MA": "mastercard.com", "PYPL": "paypal.com",
    "F": "ford.com", "GM": "gm.com", "T": "att.com", "VZ": "verizon.com",
    "BA": "boeing.com", "GE": "ge.com", "CAT": "caterpillar.com",
}

BANNER_CRYPTO_IDS = ["bitcoin", "solana", "ethereum"]

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
# Data ophalen
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_crypto_banner():
    """Prijs, 24u-verandering én logo voor BTC, SOL, ETH in één call."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "ids": ",".join(BANNER_CRYPTO_IDS)},
            timeout=10,
        ).json()
        result = {}
        for coin in r:
            result[coin["symbol"].upper()] = {
                "price": coin["current_price"],
                "change": coin.get("price_change_percentage_24h"),
                "logo": coin.get("image"),
            }
        return result
    except Exception:
        return {}


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
    """Niet-officiële CNN-databron (geen publieke API beschikbaar) — kan
    zonder aankondiging veranderen."""
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
def get_btc_daily_candles():
    """CoinGecko's gratis market_chart-endpoint geeft geen echte daily-OHLC
    terug, dus we bouwen dagcandles zelf op uit de ~uurlijkse prijspunten
    (open = eerste prijs van de dag, close = laatste, high/low = min/max)."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            params={"vs_currency": "usd", "days": 30},
            timeout=10,
        ).json()
        df = pd.DataFrame(r["prices"], columns=["ts", "price"])
        df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.date
        daily = df.groupby("date")["price"].agg(open="first", high="max", low="min", close="last")
        return daily
    except Exception:
        return pd.DataFrame(columns=["open", "high", "low", "close"])


@st.cache_data(ttl=900)
def get_nasdaq_daily_candles():
    try:
        hist = yf.Ticker("^IXIC").history(period="1mo")
        return hist[["Open", "High", "Low", "Close"]]
    except Exception:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close"])


@st.cache_data(ttl=900)
def get_nft_stats(eth_usd_price):
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
                "name": name, "floor_eth": floor_eth,
                "floor_usd": floor_usd, "volume_24h": volume_24h,
            }
        except Exception:
            results[slug] = {"name": name, "floor_eth": None, "floor_usd": None, "volume_24h": None}
    return results


# ---------------------------------------------------------------------------
# Render-helpers
# ---------------------------------------------------------------------------

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
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=50, b=10),
                       template="plotly_dark", paper_bgcolor="#111318")
    st.plotly_chart(fig, use_container_width=True)


def render_ranked_list(rows):
    """rows: lijst van dicts met keys name, value, logo (logo mag None zijn)."""
    for i, row in enumerate(rows, 1):
        c1, c2 = st.columns([1, 6])
        if row.get("logo"):
            try:
                c1.image(row["logo"], width=24)
            except Exception:
                c1.write("•")
        else:
            c1.write("•")
        c2.write(f"**{i}. {row['name']}** — {row['value']}")


# ---------------------------------------------------------------------------
# UI — titel
# ---------------------------------------------------------------------------

title_col1, title_col2 = st.columns([1, 10])
with title_col1:
    st.markdown(
        "<div style='font-size:42px; text-align:center;'>📊</div>",
        unsafe_allow_html=True,
    )  # Placeholder-icoon — zie toelichting in de chat over het logo
with title_col2:
    st.title("Markt Overzicht")
st.caption(f"Laatst bijgewerkt: {datetime.now().strftime('%d-%m-%Y %H:%M')}")

# ---------------------------------------------------------------------------
# UI — banner
# ---------------------------------------------------------------------------

crypto_banner = get_crypto_banner()
sp500, sp500_change = get_index_price("^GSPC")

banner_cols = st.columns(4)

with banner_cols[0]:
    with st.container(border=True):
        st.markdown("**SPX**")
        st.metric("S&P 500", f"{sp500:,.0f}" if sp500 else "n.b.",
                   f"{sp500_change:+.2f}%" if sp500_change is not None else None)

for col, symbol in zip(banner_cols[1:], ["BTC", "SOL", "ETH"]):
    data = crypto_banner.get(symbol, {})
    with col:
        with st.container(border=True):
            if data.get("logo"):
                st.image(data["logo"], width=28)
            st.metric(symbol, f"${data['price']:,.2f}" if data.get("price") else "n.b.",
                      f"{data['change']:+.2f}%" if data.get("change") is not None else None)

st.divider()

# ---------------------------------------------------------------------------
# UI — hoofdrij: links / midden (candlestick chart) / rechts
# ---------------------------------------------------------------------------

left_col, center_col, right_col = st.columns([1, 2.2, 1])

stock_data = get_stock_universe_data()
crypto_top100 = get_crypto_top100()

with left_col:
    with st.container(border=True):
        st.markdown("##### 📈 Top 5 tech stijgers")
        if not stock_data.empty:
            tech_df = stock_data[stock_data["ticker"].isin(TECH_50)]
            top_tech = tech_df.sort_values("pct_change", ascending=False).head(5)
            rows = [{"name": t, "value": f"{p:+.2f}%",
                     "logo": f"https://logo.clearbit.com/{TICKER_DOMAINS.get(t)}" if TICKER_DOMAINS.get(t) else None}
                    for t, p in zip(top_tech["ticker"], top_tech["pct_change"])]
            render_ranked_list(rows)
        else:
            st.write("n.b.")

    with st.container(border=True):
        st.markdown("##### 📊 Top 5 aandelen (volume)")
        if not stock_data.empty:
            top_vol = stock_data.sort_values("volume", ascending=False).head(5)
            rows = [{"name": t, "value": f"{v:,.0f}",
                     "logo": f"https://logo.clearbit.com/{TICKER_DOMAINS.get(t)}" if TICKER_DOMAINS.get(t) else None}
                    for t, v in zip(top_vol["ticker"], top_vol["volume"])]
            render_ranked_list(rows)
        else:
            st.write("n.b.")

    with st.container(border=True):
        fng_stocks_value, fng_stocks_label = get_fear_greed_stocks()
        render_gauge(fng_stocks_value, fng_stocks_label, "Fear & Greed — Aandelen")

with center_col:
    with st.container(border=True):
        st.markdown("##### ₿ Bitcoin vs Nasdaq — dagcandles")
        btc_daily = get_btc_daily_candles()
        nasdaq_daily = get_nasdaq_daily_candles()
        if not btc_daily.empty and not nasdaq_daily.empty:
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=btc_daily.index, open=btc_daily["open"], high=btc_daily["high"],
                low=btc_daily["low"], close=btc_daily["close"], name="Bitcoin",
                increasing_line_color="#f2a900", decreasing_line_color="#8a5c00",
                yaxis="y",
            ))
            fig.add_trace(go.Candlestick(
                x=nasdaq_daily.index, open=nasdaq_daily["Open"], high=nasdaq_daily["High"],
                low=nasdaq_daily["Low"], close=nasdaq_daily["Close"], name="Nasdaq",
                increasing_line_color="#00bfff", decreasing_line_color="#004a66",
                yaxis="y2",
            ))
            fig.update_layout(
                template="plotly_dark", height=560, paper_bgcolor="#111318",
                margin=dict(l=20, r=20, t=20, b=20),
                yaxis=dict(title="Bitcoin (USD)", side="left"),
                yaxis2=dict(title="Nasdaq", side="right", overlaying="y"),
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", y=1.05),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Bitcoin-candles zijn opgebouwd uit uurlijkse koersdata (geen native "
                "daily-OHLC beschikbaar via de gratis API) — Nasdaq-candles zijn wel "
                "de officiële dagkoersen."
            )
        else:
            st.write("Grafiekdata niet beschikbaar.")

with right_col:
    with st.container(border=True):
        st.markdown("##### 🚀 Top 5 crypto stijgers")
        if not crypto_top100.empty:
            top_gainers = crypto_top100.sort_values("price_change_percentage_24h", ascending=False).head(5)
            rows = [{"name": s.upper(), "value": f"{p:+.2f}%", "logo": img}
                    for s, p, img in zip(top_gainers["symbol"], top_gainers["price_change_percentage_24h"],
                                          top_gainers["image"])]
            render_ranked_list(rows)
        else:
            st.write("n.b.")

    with st.container(border=True):
        st.markdown("##### 💧 Top 5 munten (volume)")
        if not crypto_top100.empty:
            top_vol_crypto = crypto_top100.sort_values("total_volume", ascending=False).head(5)
            rows = [{"name": s.upper(), "value": f"${v:,.0f}", "logo": img}
                    for s, v, img in zip(top_vol_crypto["symbol"], top_vol_crypto["total_volume"],
                                          top_vol_crypto["image"])]
            render_ranked_list(rows)
        else:
            st.write("n.b.")

    with st.container(border=True):
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

eth_price = crypto_banner.get("ETH", {}).get("price")
nft_stats = get_nft_stats(eth_price)

nft_left, nft_right = st.columns([1.3, 2])

with nft_left:
    with st.container(border=True):
        st.markdown("##### Top 5 collecties (24u volume)")
        ranked = sorted(
            [v for v in nft_stats.values() if v["volume_24h"] is not None],
            key=lambda v: v["volume_24h"], reverse=True,
        )[:5]
        if ranked:
            rows = [{"name": v["name"], "value": f"{v['volume_24h']:,.1f} ETH", "logo": None} for v in ranked]
            render_ranked_list(rows)
        else:
            st.write("n.b.")

with nft_right:
    st.markdown("##### Uitgelicht")
    featured_cols = st.columns(3)
    for col, slug in zip(featured_cols, NFT_FEATURED_SLUGS):
        stats = nft_stats.get(slug, {})
        floor_eth = stats.get("floor_eth")
        floor_usd = stats.get("floor_usd")
        with col:
            with st.container(border=True):
                st.metric(
                    stats.get("name", slug),
                    f"{floor_eth:.3f} ETH" if floor_eth else "n.b.",
                    f"${floor_usd:,.0f}" if floor_usd else None,
                )
