import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - Otonom Bağlantı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "autonomous_sniper_db.json"

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

# --- BOTUN ÖĞRENDİĞİ OTONOM FİYAT HAREKETİ ---
def get_autonomous_signal(df):
    if len(df) < 20: return None
    last = df.iloc[-1]
    # Fiyatın sıkıştığı kutunun sınırları (image_1da565.png)
    resistance = df['h'].iloc[-15:-1].max() 
    support = df['l'].iloc[-15:-1].min()
    
    # Bot artık sadece fiyata bakar: Kırılım var mı?
    if last['c'] > resistance: return "LONG"
    if last['c'] < support: return "SHORT"
    return None

st.set_page_config(page_title="Autonomous Sniper V22.0", layout="wide")

st.markdown("""
    <style>
    .trade-card {
        background-color: #0b0e11;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #2b2f36;
        margin-bottom: 10px;
    }
    .pnl-pos { color: #00ff88; font-weight: bold; }
    .pnl-neg { color: #ff4b4b; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🤖 OKX Autonomous Sniper: Serbest Mod")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Mevcut Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif İşlem", f"{len(active_trades)} / 5")
c3.info("Durum: Kendi Haline Bırakıldı (Full Action)")

# --- TAKİP SİSTEMİ ---
if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                st.markdown(f"""
                <div class="trade-card">
                    <div style="display: flex; justify-content: space-between;">
                        <b>{trade['coin']} | {trade['side']}</b>
                        <span class="{'pnl-pos' if pnl_usd >= 0 else 'pnl-neg'}">%{pnl_pct:.2f} (${pnl_usd:.2f})</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Manuel Kapat: {trade['coin']}", key=f"close_{idx}"):
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()

                if pnl_pct >= 8.5 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# --- SERBEST TARAMA ---
if len(active_trades) < 5:
    with st.status("🚀 Bot Kendi Kararını Veriyor...", expanded=True):
        try:
            markets = exchange.load_markets()
            all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
            for s in all_syms[:120]: # Daha fazla coin
                if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
                if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
                
                bars = exchange.fetch_ohlcv(s, timeframe='15m', limit=30)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_autonomous_signal(df)
                
                if side:
                    margin_v = st.session_state.balance * 0.10
                    new_t = {"coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": round(margin_v, 2), "status": "Açık", "time": str(datetime.now())}
                    st.session_state.trades.append(new_t)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
        except: pass

time.sleep(2)
st.rerun()
