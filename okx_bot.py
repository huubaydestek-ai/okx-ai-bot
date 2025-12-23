import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Bağlantısı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "trade_db.json"

# --- VERİTABANI YÖNETİMİ ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {"balance": 1000.0, "trades": []}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

# --- BAŞLANGIÇ ---
db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]

def get_market_analysis(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['RSI'] = ta.momentum.rsi(df['c'], window=14)
        df['EMA_20'] = ta.trend.ema_indicator(df['c'], window=20)
        last = df.iloc[-1]
        return {"price": last['c'], "rsi": round(last['RSI'], 2), "ema": round(last['EMA_20'], 4)}
    except: return None

# --- ARAYÜZ ---
st.set_page_config(page_title="OKX Pro Scalper V9", layout="wide")
st.title("🛡️ OKX AI Pro: Risk Yönetimi Paneli")

# ÜST PANEL
active_trades = [t for t in st.session_state.trades if t['status'] == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Net Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 3")
c3.info(f"Mod: **İZOLE MARJİN** | Kaldıraç: **10x**")

st.divider()

# --- AKTİF İŞLEMLER ---
if active_trades:
    for i, trade in enumerate(st.session_state.trades):
        if trade['status'] == 'Açık':
            try:
                curr_p = exchange.fetch_ticker(trade['coin'])['last']
            except: continue
            
            # PNL ve Tahmini Kar/Zarar
            pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (trade['kaldırac'] if trade['side'] == 'LONG' else -trade['kaldırac'])
            pnl_usd = (trade['margin'] * pnl_pct) / 100
            
            # Hedef Hesaplamaları (TP/SL olduğunda ne olur?)
            tp_dist = abs(trade['tp'] - trade['entry']) / trade['entry'] * 100 * trade['kaldırac']
            sl_dist = abs(trade['sl'] - trade['entry']) / trade['entry'] * 100 * trade['kaldırac']
            target_win = (trade['margin'] * tp_dist) / 100
            target_loss = (trade['margin'] * sl_dist) / 100

            with st.container(border=True):
                col1, col2, col3 = st.columns([1.2, 2, 1.2])
                
                with col1:
                    st.subheader(trade['coin'])
                    st.caption(f"Yön: {trade['side']} | Tip: İZOLE")
                    st.write(f"💵 **Teminat:** ${trade['margin']}")
                
                with col2:
                    st.write(f"📌 **Giriş:** {trade['entry']} | ⚡ **Anlık:** {curr_p}")
                    st.write(f"🎯 **TP:** {trade['tp']} ( +${target_win:.2f} )")
                    st.write(f"🛡️ **SL:** {trade['sl']} ( -${target_loss:.2f} )")
                
                with col3:
                    st.metric("Anlık PNL", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")

                # Kapanış Kontrolü
                if (trade['side'] == 'LONG' and (curr_p >= trade['tp'] or curr_p <= trade['sl'])) or \
                   (trade['side'] == 'SHORT' and (curr_p <= trade['tp'] or curr_p >= trade['sl'])):
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[i]['status'] = 'Kapandı'
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.rerun()

st.divider()

# --- ANALİZ VE TARAMA ---
if len(active_trades) < 3:
    st.subheader("🔍 Pazar Analizi")
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:50]
    
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        
        analysis = get_market_analysis(s)
        if analysis:
            side = None
            if analysis['rsi'] < 42 and analysis['price'] < analysis['ema']: side = "LONG"
            elif analysis['rsi'] > 58 and analysis['price'] > analysis['ema']: side = "SHORT"
            
            if side:
                new_trade = {
                    "coin": s, "side": side, "entry": analysis['price'],
                    "tp": analysis['price'] * (1.012 if side == "LONG" else 0.988), # %1.2 TP
                    "sl": analysis['price'] * (0.995 if side == "LONG" else 1.005), # %0.5 SL
                    "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now())
                }
                st.session_state.trades.append(new_trade)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()

time.sleep(15)
st.rerun()
