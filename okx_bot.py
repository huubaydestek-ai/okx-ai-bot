import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Ayarı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "trade_db.json"

# VERİTABANI FONKSİYONLARI
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {"balance": 1000.0, "trades": []}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

# BAŞLANGIÇ
db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]

def get_market_analysis(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['RSI'] = ta.momentum.rsi(df['c'], window=14)
        df['EMA_20'] = ta.trend.ema_indicator(df['c'], window=20)
        df['EMA_50'] = ta.trend.ema_indicator(df['c'], window=50)
        last = df.iloc[-1]
        
        side = None
        if last['v'] > df['v'].mean(): # Hacim onayı
            if last['EMA_20'] > last['EMA_50'] and last['RSI'] < 35: side = "LONG"
            if last['EMA_20'] < last['EMA_50'] and last['RSI'] > 65: side = "SHORT"
        return side, last['c']
    except: return None, None

st.set_page_config(page_title="OKX AI Memory Bot", layout="wide")
st.title("🧠 OKX AI: Hafızalı Strateji Paneli")

# CANLI TAKİP VE KAYIT GÜNCELLEME
active_trades = [t for t in st.session_state.trades if t['status'] == 'Açık']

# ÜST PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa (Kalıcı)", f"")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 3")
if st.button("Hafızayı Sıfırla (1000$)"):
    save_db({"balance": 1000.0, "trades": []})
    st.rerun()

# İŞLEM TAKİBİ
for i, trade in enumerate(st.session_state.trades):
    if trade['status'] == 'Açık':
        curr_p = exchange.fetch_ticker(trade['coin'])['last']
        pnl = (curr_p - trade['entry']) / trade['entry'] * trade['margin'] * trade['kaldırac'] * (1 if trade['side'] == 'LONG' else -1)
        
        if (trade['side'] == 'LONG' and (curr_p >= trade['tp'] or curr_p <= trade['sl'])) or \
           (trade['side'] == 'SHORT' and (curr_p <= trade['tp'] or curr_p >= trade['sl'])):
            st.session_state.balance += pnl
            st.session_state.trades[i]['status'] = 'Kapandı'
            st.session_state.trades[i]['final_pnl'] = pnl
            save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
            st.rerun()

# TARAMA
if len(active_trades) < 3:
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:40]
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        side, price = get_market_analysis(s)
        if side:
            new_trade = {
                "coin": s, "side": side, "entry": price, 
                "tp": price * 1.015 if side == "LONG" else price * 0.985,
                "sl": price * 0.992 if side == "LONG" else price * 1.008,
                "margin": 50, "kaldırac": 10, "status": "Açık", "time": str(datetime.now())
            }
            st.session_state.trades.append(new_trade)
            save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
            st.rerun()

st.divider()
st.subheader("📜 Tüm İşlem Geçmişi (TP/SL Detaylı)")
if st.session_state.trades:
    st.dataframe(pd.DataFrame(st.session_state.trades)[::-1], use_container_width=True)

time.sleep(15)
st.rerun()
