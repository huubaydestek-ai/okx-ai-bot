import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - Hatasız Bağlantı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "final_stabil_db.json"

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

# --- 15M KIRILIM STRATEJİSİ ---
def get_15m_signal(df):
    if len(df) < 25: return None
    last = df.iloc[-1]
    # Direnç ve Destek (Senin Sarı/Mavi Çizgilerin)
    resistance = df['h'].iloc[-20:-1].max() 
    support = df['l'].iloc[-20:-1].min()
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    if last['c'] > resistance and 45 < rsi < 65: return "LONG"
    if last['c'] < support and 35 < rsi < 55: return "SHORT"
    return None

st.set_page_config(page_title="Hatasız 15m Sniper", layout="wide")
st.title("🎯 Hatasız 15m Sniper: 981$ Live")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif", f"{len(active_trades)} / 5")
c3.success("Zaman Dilimi: 15m (8x İzole)")

# --- TAKİP ---
if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                with st.container(border=True):
                    cl1, cl2, cl3 = st.columns([3, 2, 1])
                    cl1.write(f"### {trade['coin']} | {trade['side']}")
                    cl2.metric("P/L %", f"{pnl_pct:.2f}%", f"${pnl_usd:.2f}")
                    if cl3.button("KAPAT", key=f"cl_btn_{idx}"):
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

# --- TARAMA ---
if len(active_trades) < 5:
    with st.status("🔎 15 Dakikalık Kırılımlar Taranıyor...", expanded=True):
        markets = exchange.load_markets()
        all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
        
        for s in all_syms[:70]:
            if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
            if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
            
            try:
                ticker = exchange.fetch_ticker(s)
                if ticker.get('quoteVolume', 0) < 300000: continue

                bars = exchange.fetch_ohlcv(s, timeframe='15m', limit=40)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_15m_signal(df)
                
                if side:
                    margin_val = st.session_state.balance * 0.10
                    new_trade = {
                        "coin": s, "side": side, "entry": df['c'].iloc[-1], 
                        "margin": round(margin_val, 2), "status": "Açık", 
                        "time": str(datetime.now())
                    }
                    st.session_state.trades.append(new_trade)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

time.sleep(5)
st.rerun()
