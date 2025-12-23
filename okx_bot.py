import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - %100 Stabil Bağlantı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "flawless_pro_db.json"

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
    res = df['h'].iloc[-20:-1].max() 
    sup = df['l'].iloc[-20:-1].min()
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    if last['c'] > res and 45 < rsi < 65: return "LONG"
    if last['c'] < sup and 35 < rsi < 55: return "SHORT"
    return None

st.set_page_config(page_title="OKX Pro Sniper V21.2", layout="wide")

# Şık Siyah Kart Tasarımı (Tırnaklar Çift Kontrol Edildi)
st.markdown("""
    <style>
    .trade-card {
        background-color: #111418;
        border-radius: 15px;
        padding: 25px;
        border: 1px solid #2d3139;
        margin-bottom: 20px;
        color: white;
    }
    .pnl-pos { color: #00ff88; font-weight: bold; }
    .pnl-neg { color: #ff4b4b; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 OKX Pro Sniper: Flawless Edition")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# ÜST PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.info("Metot: 15m Breakout Active")

# --- CANLI POZİSYONLAR ---
if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                tp_price = trade['entry'] * (1 + (0.085 / 8)) if trade['side'] == 'LONG' else trade['entry'] * (1 - (0.085 / 8))
                sl_price = trade['entry'] * (1 - (0.05 / 8)) if trade['side'] == 'LONG' else trade['entry'] * (1 + (0.05 / 8))

                st.markdown(f"""
                <div class="trade-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h2 style="margin:0; font-size: 1.8em;">{trade['coin']}</h2>
                            <p style="margin:0; color: #888;">Yön: {trade['side']} | 8x İzole | Teminat: ${trade['margin']}</p>
                        </div>
                        <div style="text-align: right;">
                            <p style="margin:0; font-size: 0.9em; color: #888;">Anlık PNL</p>
                            <p class="{'pnl-pos' if pnl_usd >= 0 else 'pnl-neg'}" style="margin:0; font-size: 2em;">
                                ${pnl_usd:.2f} ({pnl_pct:.2f}%)
                            </p>
                        </div>
                    </div>
                    <div style="margin-top: 20px; display: flex; justify-content: space-between; border-top: 1px solid #2d3139; padding-top: 15px;">
                        <span>📍 Giriş: <b>{trade['entry']}</b> | ⚡ Anlık: <b>{curr_p}</b></span>
                        <span>🎯 TP: <span style="color: #00ff88;">{tp_price:.4f}</span> | 🛡️ SL: <span style="color: #ff4b4b;">{sl_price:.4f}</span></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Kapat: {trade['coin']}", key=f"close_btn_{idx}"):
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()

                if pnl_pct >= 8.5 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
