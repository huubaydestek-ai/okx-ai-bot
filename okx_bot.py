import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - Hatasız Pro Bağlantı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "pro_polished_db.json"

def load_db():
    default = {"balance": 981.0, "trades": []}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return default
    return default

def save_db(balance, trades):
    with open(DB_FILE, "w") as f:
        json.dump({"balance": balance, "trades": trades}, f)

db_data = load_db()
st.session_state.update(db_data)

# --- SENİN 15M KIRILIM METODUN (Sarı/Mavi) ---
def get_pa_signal(df):
    if len(df) < 25: return None
    last = df.iloc[-1]
    res = df['h'].iloc[-20:-1].max() # Sarı (Direnç)
    sup = df['l'].iloc[-20:-1].min() # Mavi (Destek)
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    if last['c'] > res and 45 < rsi < 65: return "LONG"
    if last['c'] < sup and 35 < rsi < 55: return "SHORT"
    return None

st.set_page_config(page_title="OKX Pro Sniper", layout="wide")

# Şık Siyah Kart Tasarımı
st.markdown("""
    <style>
    .trade-card {
        background-color: #1a1c23;
        border-radius: 12px;
        padding: 20px;
        border-left: 6px solid #3e4251;
        margin-bottom: 15px;
        color: white;
    }
    .pnl-pos { color: #00ff88; font-weight: bold; }
    .pnl-neg { color: #ff4b4b; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 OKX Pro Sniper: 981$ Real Trade")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.info("Metot: 15
