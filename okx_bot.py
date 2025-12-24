import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - CC-Quality Engine
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "high_winrate_db.json"

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

st.set_page_config(page_title="OKX Sniper: CC-Style", layout="wide")

# Şık Siyah Kart Tasarımı (image_29fb65.png stilinde)
st.markdown("""
    <style>
    .trade-card {
        background-color: #0d1117;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #30363d;
        margin-bottom: 15px;
    }
    .pnl-pos { color: #00ff88; font-weight: bold; font-size: 1.6em; }
    .pnl-neg { color: #f85149; font-weight: bold; font-size: 1.6em; }
    .label { color: #8b949e; font-size: 0.85em; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 OKX Sniper: The CC Tracker")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# ÜST PANEL (image_29fb65.png verileriyle)
c1, c2, c3 = st.columns(3)
c1.metric("💰 Mevcut Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif İşlem", f"{len(active_trades)} / 5")
c3.info("Strateji: CC-Style Quality Filter")

# --- CANLI POZİSYON TAKİBİ ---
if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                # Dinamik TP/SL (Görseldeki gibi %8.5 ve %5)
                tp_price = trade['entry'] * (1 + (0.085/8)) if trade['side'] == 'LONG' else trade['entry'] * (1 - (0.085/8))
                sl_price = trade['entry'] * (1 - (0.05/8)) if trade['side'] == 'LONG' else trade['entry'] * (1 + (0.05/8))

                st.markdown(f"""
                <div class="trade-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h2 style="margin:0;">{trade['coin']} | {trade['side']}</h2>
                            <p class="label">8x İzole | Teminat: ${trade['margin']}</p>
                        </div>
                        <div style="text-align: right;">
                            <span class="{'pnl-pos' if pnl_usd >= 0 else 'pnl-neg'}">
                                ${pnl_usd:.2f} ({pnl_pct:.2f}%)
                            </span>
                        </div>
                    </div>
                    <div style="margin-top: 15px; border-top: 1px solid #30363d; padding-top: 10px; display: flex; justify-content: space-between;">
                        <span>📍 Giriş: <b>{trade['entry']}</b> | ⚡ Anlık: <b>{curr_p}</b></span>
                        <span>🎯 TP: <b style="color: #00ff88;">{tp_price:.4f}</b> | 🛡️ SL: <b style="color: #f85149;">{sl_price:.4f}</b></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Otomatik Kapanış Kontrolü
                if pnl_pct >= 8.5 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

time.sleep(5)
st.rerun()
