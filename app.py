import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

st.set_page_config(layout="wide", page_title="Top-Down Sync Dashboard")
st.title("Sector & Peer Sync Dashboard")

SECTOR_MAP = {
    "HDFCBANK.NS": {"sector": "^NSEBANK", "peers": ["ICICIBANK.NS", "SBIN.NS"]},
    "TATASTEEL.NS": {"sector": "^CNXMETAL", "peers": ["HINDALCO.NS", "JSWSTEEL.NS"]},
    "MARUTI.NS":   {"sector": "^CNXAUTO", "peers": ["M&M.NS", "TATAMOTORS.NS"]}
}

col1, col2 = st.columns(2)
with col1:
    selected_stock = st.selectbox("Select Target Stock", list(SECTOR_MAP.keys()))
with col2:
    selected_interval = st.selectbox("Select Timeframe", ["15m", "1h", "1d", "1wk"], index=2)

period = "1mo" if selected_interval in ["15m", "1h"] else "1y"

sector_symbol = SECTOR_MAP[selected_stock]["sector"]
peer_symbols = SECTOR_MAP[selected_stock]["peers"]
all_symbols = [selected_stock, sector_symbol] + peer_symbols

@st.cache_data(ttl=60)
def fetch_market_data(symbols, interval, period):
    data_dict = {}
    for sym in symbols:
        df = yf.download(sym, period=period, interval=interval, progress=False)
        if not df.empty:
            data_dict[sym] = df
    return data_dict

with st.spinner("Fetching synchronous market data..."):
    market_data = fetch_market_data(all_symbols, selected_interval, period)

if market_data:
    fig = make_subplots(
        rows=2, cols=2, 
        subplot_titles=(
            f"Target: {selected_stock}", 
            f"Sector: {sector_symbol}", 
            f"Peer 1: {peer_symbols[0]}", 
            f"Peer 2: {peer_symbols[1]}"
        ),
        shared_xaxes=True, 
        vertical_spacing=0.1,
        horizontal_spacing=0.05
    )

    def add_candlestick(fig, df, row, col, name):
        if not df.empty:
            open_col = df['Open'].squeeze() if isinstance(df['Open'], pd.DataFrame) else df['Open']
            high_col = df['High'].squeeze() if isinstance(df['High'], pd.DataFrame) else df['High']
            low_col = df['Low'].squeeze() if isinstance(df['Low'], pd.DataFrame) else df['Low']
            close_col = df['Close'].squeeze() if isinstance(df['Close'], pd.DataFrame) else df['Close']

            fig.add_trace(
                go.Candlestick(
                    x=df.index, open=open_col, high=high_col, low=low_col, close=close_col, name=name
                ),
                row=row, col=col
            )
            fig.update_xaxes(rangeslider_visible=False, row=row, col=col)

    add_candlestick(fig, market_data.get(selected_stock, pd.DataFrame()), 1, 1, "Stock")
    add_candlestick(fig, market_data.get(sector_symbol, pd.DataFrame()), 1, 2, "Sector")
    add_candlestick(fig, market_data.get(peer_symbols[0], pd.DataFrame()), 2, 1, "Peer 1")
    add_candlestick(fig, market_data.get(peer_symbols[1], pd.DataFrame()), 2, 2, "Peer 2")

    fig.update_layout(height=800, template="plotly_dark", showlegend=False, dragmode='pan')
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Failed to fetch data.")

