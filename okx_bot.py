import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - %100 Stabil Pro Bağlantı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "final_bullet_db.json"

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

# --- SENİN 15M KIRILIM STRATEJİN ---
def get_pa_signal(df):
    if len(df) < 25: return None
    last = df.iloc[-1]
    res = df['h'].iloc[-20:-1].max() 
    sup = df['l'].iloc[-20:-1].min()
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    if last['c'] > res and 45 < rsi < 65: return "LONG"
    if last['c'] < sup and 35 < rsi < 55: return "SHORT"
    return None

st.set_page_config(page_title="OKX Pro Sniper V21.3", layout="wide")

# O SEVDİĞİN SİYAH ŞIK TASARIM
st.markdown("""
    <style>
    .trade-card {
        background-color: #0e1117;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #30363d;
        margin-bottom: 15px;
    }
    .pnl-pos { color: #00ff88; font-weight: bold; font-size: 1.5em; }
    .pnl-neg { color: #ff4b4b; font-weight: bold; font-size: 1.5em; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 OKX Pro Sniper: 981$ Final Edition")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.success("Metot: 15m Price Action")

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
                    <div style="display: flex; justify-content: space-between;">
                        <div>
                            <h3 style="margin:0;">{trade['coin']} | {trade['side']}</h3>
                            <small style="color: gray;">8x İzole | Teminat: ${trade['margin']}</small>
                        </div>
                        <div style="text-align: right;">
                            <span class="{'pnl-pos' if pnl_usd >= 0 else 'pnl-neg'}">
                                ${pnl_usd:.2f} ({pnl_pct:.2f}%)
                            </span>
                        </div>
                    </div>
                    <div style="margin-top:15px; font-size: 0.9em; display: flex; justify-content: space-between;">
                        <span>📍 Giriş: <b>{trade['entry']}</b> | ⚡ Anlık: <b>{curr_p}</b></span>
                        <span>🎯 TP: <span style="color: #00ff88;">{tp_price:.4f}</span> | 🛡️ SL: <span style="color: #ff4b4b;">{sl_price:.4f}</span></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Kapat: {trade['coin']}", key=f"btn_{idx}"):
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()

                if pnl_pct >= 8.5 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except:
                continue

# --- TARAYICI ---
if len(active_trades) < 5:
    with st.spinner("🔎 Market taranıyor..."):
        try:
            markets = exchange.load_markets()
            all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
            for s in all_syms[:75]:
                if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
                if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
                
                ticker = exchange.fetch_ticker(s)
                if ticker.get('quoteVolume', 0) < 200000: continue
                
                bars = exchange.fetch_ohlcv(s, timeframe='15m', limit=40)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_pa_signal(df)
                
                if side:
                    margin_val = st.session_state.balance * 0.10
                    new_t = {"coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": round(margin_val, 2), "status": "Açık", "time": str(datetime.now())}
                    st.session_state.trades.append(new_t)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
        except:
            pass

time.sleep(5)
st.rerun()
