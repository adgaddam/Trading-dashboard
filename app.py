import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import math

# --- SYSTEM CONFIGURATION ---
st.set_page_config(layout="wide", page_title="GTF Sectoral Dashboard", initial_sidebar_state="expanded")

# --- DATABASE BLOCK ---
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
    }
}

all_stocks = sorted(list(set([sym for sec in SECTORS.values() for sym in sec["Constituents"].keys()])))

def get_parent_sector(stock_sym):
    for sec_sym, sec_data in SECTORS.items():
        if stock_sym in sec_data["Constituents"]:
            return sec_sym, sec_data
    return None, None

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("⚙️ Analysis Controls")
    target_stock = st.selectbox("1. Target Stock", all_stocks)
    
    parent_sec_sym, parent_sec_data = get_parent_sector(target_stock)
    
    tf_options = {
        "Monthly": {"yf": "1mo", "rule": None, "period": "max"},
        "Weekly": {"yf": "1wk", "rule": None, "period": "5y"},
        "Daily": {"yf": "1d", "rule": None, "period": "2y"},
        "240 min": {"yf": "60m", "rule": "240min", "period": "60d"},
        "125 min": {"yf": "5m", "rule": "125min", "period": "60d"},
        "15 min": {"yf": "15m", "rule": None, "period": "60d"},
        "3 min": {"yf": "1m", "rule": "3min", "period": "7d"}
    }
    selected_tf = st.selectbox("2. Timeframe", list(tf_options.keys()), index=2)
    
    if parent_sec_sym:
        peers_dict = parent_sec_data["Constituents"]
        peer_list = [f"{sym} ({weight}%)" for sym, weight in sorted(peers_dict.items(), key=lambda item: item[1], reverse=True) if sym != target_stock]
        selected_peers_raw = st.multiselect("3. Peers (Max 4)", peer_list, default=peer_list[:2], max_selections=4)
        selected_peers = [p.split(" ")[0] for p in selected_peers_raw]
    else:
        st.warning("Sector data missing.")
        selected_peers = []

    st.markdown("---")
    st.header("📱 Layout Mode")
    layout_mode = st.radio("Select Device View:", ["Desktop / Tablet (Grid)", "Smartphone (Stacked)"])

# --- MAIN DASHBOARD AREA ---
st.title(f"Top-Down Sync: {target_stock} & {parent_sec_data['Name'] if parent_sec_data else 'Sector'}")

if not selected_peers:
    st.error("Please select at least 1 peer from the sidebar to compare.")
    st.stop()

all_symbols = [target_stock, parent_sec_sym] + selected_peers
tf_config = tf_options[selected_tf]

# Data Pipeline
@st.cache_data(ttl=60)
def fetch_and_resample(symbols, yf_interval, period, resample_rule):
    data_dict = {}
    for sym in symbols:
        df = yf.download(sym, period=period, interval=yf_interval, progress=False)
        if df.empty: continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        if resample_rule:
            df = df.resample(resample_rule).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        data_dict[sym] = df
    return data_dict

with st.spinner(f"Aligning {selected_tf} zones..."):
    market_data = fetch_and_resample(all_symbols, tf_config["yf"], tf_config["period"], tf_config["rule"])

# --- TRADINGVIEW VISUAL ENGINE ---
if market_data:
    total_charts = len(all_symbols)
    
    if layout_mode == "Smartphone (Stacked)":
        cols = 1
        rows = total_charts
        chart_height = 350 * rows 
    else:
        cols = 2
        rows = math.ceil(total_charts / 2)
        chart_height = 400 * rows

    titles = [f"Target: {target_stock}", f"Sector: {parent_sec_data['Name']}"] + [f"Peer: {p}" for p in selected_peers]

    fig = make_subplots(
        rows=rows, cols=cols, subplot_titles=titles,
        shared_xaxes=True, vertical_spacing=0.08 if layout_mode == "Smartphone (Stacked)" else 0.1, horizontal_spacing=0.05
    )

    for idx, sym in enumerate(all_symbols):
        df = market_data.get(sym, pd.DataFrame())
        if df.empty: continue
        
        r = (idx // cols) + 1
        c = (idx % cols) + 1
        
        # Clean Candlestick implementation
        fig.add_trace(
            go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=sym,
                increasing_line_color='#089981', increasing_fillcolor='#089981',
                decreasing_line_color='#F23645', decreasing_fillcolor='#F23645'
            ), row=r, col=c
        )
        
        # Apply TradingView X-Axis styling (Remove weekends and clean grid)
        fig.update_xaxes(
            showgrid=True, gridwidth=1, gridcolor='#2B2B43', 
            zeroline=False, rangeslider_visible=False,
            rangebreaks=[dict(bounds=["sat", "mon"])], # Removes weekend gaps
            row=r, col=c
        )
        
        # Apply TradingView Y-Axis styling
        fig.update_yaxes(
            showgrid=True, gridwidth=1, gridcolor='#2B2B43', 
            zeroline=False, row=r, col=c
        )

    # Apply global TradingView Dark Theme
    fig.update_layout(
        height=chart_height, 
        paper_bgcolor='#131722', # TV Dark Background
        plot_bgcolor='#131722',  # TV Dark Plot Area
        font=dict(color='#B2B5BE'), # TV Text Color
        showlegend=False, 
        dragmode='pan', 
        margin=dict(l=10, r=10, t=40, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)
