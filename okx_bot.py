import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - High Speed Price Action
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "pa_sniper_db.json"

def load_db():
    # Güncel kasanı 981$ olarak güncelledim kanka
    default = {"balance": 981.0, "trades": []}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return default
    return default

def save_db(balance, trades):
    with open(DB_FILE, "w") as f: json.dump({"balance": balance, "trades": trades}, f)

db_data = load_db()
st.session_state.update(db_data)

# --- PRICE ACTION BREAKOUT SİSTEMİ ---
def get_pa_signal(df):
    if len(df) < 20: return None
    last = df.iloc[-1]
    # Son 15 mumun en yüksek ve en düşüğü (Senin sarı ve mavi çizgilerin gibi)
    high_level = df['h'].iloc[-15:-1].max()
    low_level = df['l'].iloc[-15:-1].min()
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    # YUKARI KIRILIM (Sarıyı yukarı patlatırsa)
    if last['c'] > high_level and rsi < 65:
        return "LONG"
    # AŞAĞI KIRILIM (Senin yaptığın: Aşağı kırılım gelince giriş)
    if last['c'] < low_level and rsi > 35:
        return "SHORT"
    return None

st.set_page_config(page_title="PA Sniper V20.8", layout="wide")
st.title("🎯 Price Action Sniper: 981$ Real Trade")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif", f"{len(active_trades)} / 5")
c3.info("Strateji: Breakout (8x İzole)")

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
                    if cl3.button("KAPAT", key=f"cl_{idx}"):
                        st.session_state.balance += pnl_usd
                        st.session_state.trades[idx]['status'] = 'Kapandı'
                        save_db(st.session_state.balance, st.session_state.trades)
                        st.rerun()

                # Otomatik Hedef: Senin kazandığın 8.5$ gibi %8.5 TP / %5 SL
                if pnl_pct >= 8.5 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# --- KIRILIM TARAYICI ---
if len(active_trades) < 5:
    with st.spinner("🔎 Kırılım Bekleyen Pariteler Taranıyor..."):
        markets = exchange.load_markets()
        all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
        
        for s in all_syms[:70]: # En hacimli 70 parite
            if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
            if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
            
            try:
                # 500k$ Hacim altı ile vakit kaybetme
                ticker = exchange.fetch_ticker(s)
                if ticker.get('quoteVolume', 0) < 500000: continue

                bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=30)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_pa_signal(df)
                
                if side:
                    margin_val = st.session_state.balance * 0.10 # %10 Margin
                    new_trade = {"coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": round(margin_val, 2), "status": "Açık", "time": str(datetime.now())}
                    st.session_state.trades.append(new_trade)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

time.sleep(4)
st.rerun()
