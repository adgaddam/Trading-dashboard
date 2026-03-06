import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import math

st.set_page_config(layout="wide", page_title="Sector & Peer Sync Dashboard")
st.title("Advanced Top-Down Sector Dashboard")

# --- 1. SECTOR & WEIGHTAGE DATABASE ---
# You can expand this dictionary with more NSE indices and stocks. 
# Format: {"Index Symbol": {"Name": "Display Name", "Constituents": {"STOCK.NS": Weightage}}}
SECTORS = {
    "^NSEBANK": {
        "Name": "NIFTY BANK",
        "Constituents": {"HDFCBANK.NS": 29.5, "ICICIBANK.NS": 23.1, "AXISBANK.NS": 9.8, "SBIN.NS": 9.5, "KOTAKBANK.NS": 9.1, "INDUSINDBK.NS": 5.4}
    },
    "^CNXMETAL": {
        "Name": "NIFTY METAL",
        "Constituents": {"TATASTEEL.NS": 22.0, "HINDALCO.NS": 18.0, "JSWSTEEL.NS": 15.0, "VEDL.NS": 10.0, "COALINDIA.NS": 8.0, "NMDC.NS": 5.0}
    },
    "^CNXAUTO": {
        "Name": "NIFTY AUTO",
        "Constituents": {"M&M.NS": 20.0, "TATAMOTORS.NS": 16.0, "MARUTI.NS": 15.0, "BAJAJ-AUTO.NS": 8.0, "EICHERMOT.NS": 6.0, "HEROMOTOCO.NS": 5.0}
    },
    "^CNXIT": {
        "Name": "NIFTY IT",
        "Constituents": {"INFY.NS": 27.0, "TCS.NS": 25.0, "HCLTECH.NS": 10.0, "WIPRO.NS": 8.0, "TECHM.NS": 7.0, "LTIM.NS": 6.0}
    }
}

# Helper to build a flat list of all stocks for the first dropdown
all_stocks = []
for sec_data in SECTORS.values():
    all_stocks.extend(list(sec_data["Constituents"].keys()))
all_stocks = sorted(list(set(all_stocks)))

# Helper to find a stock's parent sector
def get_parent_sector(stock_sym):
    for sec_sym, sec_data in SECTORS.items():
        if stock_sym in sec_data["Constituents"]:
            return sec_sym, sec_data
    return None, None

# --- 2. USER INTERFACE ---
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    target_stock = st.selectbox("1. Select Target Stock", all_stocks)

# Auto-identify sector based on target stock
parent_sec_sym, parent_sec_data = get_parent_sector(target_stock)

with col2:
    # Custom Timeframe Mapping Engine
    tf_options = {
        "Yearly": {"yf": "1mo", "rule": "YE", "period": "max"},
        "Half Yearly": {"yf": "1mo", "rule": "6ME", "period": "max"},
        "Quarterly": {"yf": "3mo", "rule": None, "period": "max"},
        "Monthly": {"yf": "1mo", "rule": None, "period": "max"},
        "Weekly": {"yf": "1wk", "rule": None, "period": "5y"},
        "Daily": {"yf": "1d", "rule": None, "period": "2y"},
        "240 min": {"yf": "60m", "rule": "240min", "period": "60d"},
        "125 min": {"yf": "5m", "rule": "125min", "period": "60d"},
        "15 min": {"yf": "15m", "rule": None, "period": "60d"},
        "3 min": {"yf": "1m", "rule": "3min", "period": "7d"}
    }
    selected_tf = st.selectbox("2. Select Timeframe", list(tf_options.keys()), index=5)

with col3:
    if parent_sec_sym:
        # Sort peers by weightage for the dropdown
        peers_dict = parent_sec_data["Constituents"]
        peer_list = [f"{sym} ({weight}%)" for sym, weight in sorted(peers_dict.items(), key=lambda item: item[1], reverse=True) if sym != target_stock]
        
        selected_peers_raw = st.multiselect(
            f"3. Select Peers from {parent_sec_data['Name']} (Min 1, Max 4)", 
            peer_list, 
            default=peer_list[:2], # Defaults to the top 2 highest weighted peers
            max_selections=4
        )
        # Extract just the symbol from the string "SYMBOL (XX%)"
        selected_peers = [p.split(" ")[0] for p in selected_peers_raw]
    else:
        st.warning("Sector data not found for this stock.")
        selected_peers = []

# --- 3. DATA FETCHING & RESAMPLING ENGINE ---
if not selected_peers:
    st.error("Please select at least 1 peer to compare.")
    st.stop()

all_symbols = [target_stock, parent_sec_sym] + selected_peers
tf_config = tf_options[selected_tf]

@st.cache_data(ttl=60)
def fetch_and_resample(symbols, yf_interval, period, resample_rule):
    data_dict = {}
    for sym in symbols:
        df = yf.download(sym, period=period, interval=yf_interval, progress=False)
        if df.empty:
            continue
            
        # Flatten MultiIndex columns if using newer yfinance versions
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        # Pandas Mathematical Resampling for custom timeframes
        if resample_rule:
            ohlc_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}
            df = df.resample(resample_rule).agg(ohlc_dict).dropna()
            
        data_dict[sym] = df
    return data_dict

with st.spinner(f"Fetching and processing {selected_tf} data..."):
    market_data = fetch_and_resample(all_symbols, tf_config["yf"], tf_config["period"], tf_config["rule"])

# --- 4. DYNAMIC GRID & TRADINGVIEW CHARTING ---
if market_data:
    # Calculate grid size dynamically based on number of assets
    total_charts = len(all_symbols)
    cols = 2
    rows = math.ceil(total_charts / 2)

    # Build subplot titles dynamically
    titles = [f"Target: {target_stock}", f"Sector: {parent_sec_data['Name']}"] + [f"Peer: {p}" for p in selected_peers]

    fig = make_subplots(
        rows=rows, cols=cols, 
        subplot_titles=titles,
        shared_xaxes=True, # Synchronizes zooming and panning across all charts
        vertical_spacing=0.1,
        horizontal_spacing=0.05
    )

    def plot_tv_candle(fig, df, row, col, name):
        if not df.empty:
            fig.add_trace(
                go.Candlestick(
                    x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=name,
                    # TradingView exact color codes
                    increasing_line_color='rgba(8,153,129,1)', increasing_fillcolor='rgba(8,153,129,1)',
                    decreasing_line_color='rgba(242,54,69,1)', decreasing_fillcolor='rgba(242,54,69,1)'
                ),
                row=row, col=col
            )
            fig.update_xaxes(rangeslider_visible=False, row=row, col=col)

    # Plot everything dynamically into the grid
    for idx, sym in enumerate(all_symbols):
        r = (idx // 2) + 1
        c = (idx % 2) + 1
        plot_tv_candle(fig, market_data.get(sym, pd.DataFrame()), r, c, sym)

    # Apply dark mode and strict panning mode
    fig.update_layout(
        height=400 * rows, 
        template="plotly_dark", 
        showlegend=False, 
        dragmode='pan',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Failed to fetch data from Yahoo Finance.")
