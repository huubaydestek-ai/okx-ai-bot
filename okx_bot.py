import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - Hatasız & Hızlı Bağlantı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "tea_sipper_db.json"

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

# --- SENİN AVAX'TA YAPTIĞIN 15M KIRILIM METODU ---
def get_pa_signal(df):
    if len(df) < 25: return None
    last = df.iloc[-1]
    res = df['h'].iloc[-20:-1].max() # Sarı Çizgi
    sup = df['l'].iloc[-20:-1].min() # Mavi Çizgi
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    # Senin short girişi: Destek altı kapanış + RSI onayı
    if last['c'] < sup and 30 < rsi < 55: return "SHORT"
    # Long girişi: Direnç üstü kapanış
    if last['c'] > res and 45 < rsi < 70: return "LONG"
    return None

st.set_page_config(page_title="Tea Sipper V21.4", layout="wide")

st.markdown("""
    <style>
    .trade-card {
        background-color: #0d1117;
        border-radius: 15px;
        padding: 20px;
        border: 1px solid #30363d;
        margin-bottom: 15px;
    }
    .pnl-pos { color: #00ff88; font-weight: bold; }
    .pnl-neg { color: #f85149; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 OKX Sniper: The Tea Sipper")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif", f"{len(active_trades)} / 5")
c3.success("Metot: 15m Price Action (Hatasız)")

# --- POZİSYONLAR ---
if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                with st.container():
                    st.markdown(f"""
                    <div class="trade-card">
                        <div style="display: flex; justify-content: space-between;">
                            <span style="font-size: 1.5em; font-weight: bold;">{trade['coin']} | {trade['side']}</span>
                            <span class="{'pnl-pos' if pnl_usd >= 0 else 'pnl-neg'}" style="font-size: 1.5em;">
                                ${pnl_usd:.2f} ({pnl_pct:.2f}%)
                            </span>
                        </div>
                        <p style="color: gray; font-size: 0.9em; margin: 10px 0;">8x İzole | Giriş: {trade['entry']} | Anlık: {curr_p}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"KAPAT {trade['coin']}", key=f"cl_{idx}"):
                        st.session_state.balance += pnl_usd
                        st.session_state.trades[idx]['status'] = 'Kapandı'
                        save_db(st.session_state.balance, st.session_state.trades)
                        st.rerun()

                if pnl_pct >= 8.5 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except Exception:
                continue

# --- TARAMA ---
if len(active_trades) < 5:
    with st.status("🔎 Market taranıyor...", expanded=False):
        try:
            markets = exchange.load_markets()
            all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
            for s in all_syms[:80]:
                if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
                if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
                
                ticker = exchange.fetch_ticker(s)
                if ticker.get('quoteVolume', 0) < 250000: continue
                
                bars = exchange.fetch_ohlcv(s, timeframe='15m', limit=40)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_pa_signal(df)
                
                if side:
                    margin_v = st.session_state.balance * 0.10
                    new_t = {"coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": round(margin_v, 2), "status": "Açık", "time": str(datetime.now())}
                    st.session_state.trades.append(new_t)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
        except Exception:
            pass

time.sleep(5)
st.rerun()
