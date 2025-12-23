import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - CC-Style Hunter Engine
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

# --- CC GİBİ KALİTELİ İŞLEM BULMA EĞİTİMİ ---
def get_cc_quality_signal(df):
    if len(df) < 30: return None
    last = df.iloc[-1]
    
    # 1. Kırılım Seviyeleri (Sarı ve Mavi Çizgiler)
    res = df['h'].iloc[-20:-1].max() 
    sup = df['l'].iloc[-20:-1].min()
    
    # 2. Hacim Filtresi (Fakeout Engelleme)
    avg_vol = df['v'].iloc[-10:-1].mean()
    vol_confirm = last['v'] > (avg_vol * 1.5) # Hacim %50 fazla olmalı
    
    # 3. Güç Filtresi (ADX ve RSI)
    adx = ta.trend.adx(df['h'], df['l'], df['c'], window=14).iloc[-1]
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    # CC GİBİ KALİTELİ GİRİŞ KOŞULLARI
    # Sadece kırılım yetmez, hacim ve trend gücü (ADX > 25) şart
    if last['c'] > res and vol_confirm and adx > 25:
        return "LONG"
    if last['c'] < sup and vol_confirm and adx > 25:
        return "SHORT"
    return None

st.set_page_config(page_title="High Win-Rate Sniper", layout="wide")

# Şık Dashboard Tasarımı
st.markdown("""
    <style>
    .trade-card { background-color: #0b0e11; border-radius: 12px; padding: 20px; border: 1px solid #30363d; margin-bottom: 15px; }
    .pnl-pos { color: #00ff88; font-weight: bold; font-size: 1.5em; }
    .pnl-neg { color: #f85149; font-weight: bold; font-size: 1.5em; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 OKX Sniper V23: CC-Quality Hunter")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# ÜST BİLGİ
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif (Kalite Odaklı)", f"{len(active_trades)} / 5")
c3.info("Strateji: CC-Style (Vol + ADX + PA)")

# --- İŞLEMLER ---
if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                tp_p = trade['entry'] * (1 + (0.085/8)) if trade['side'] == 'LONG' else trade['entry'] * (1 - (0.085/8))
                sl_p = trade['entry'] * (1 - (0.05/8)) if trade['side'] == 'LONG' else trade['entry'] * (1 + (0.05/8))

                st.markdown(f"""
                <div class="trade-card">
                    <div style="display: flex; justify-content: space-between;">
                        <div>
                            <h3 style="margin:0;">{trade['coin']} | {trade['side']}</h3>
                            <small>8x İzole | Teminat: ${trade['margin']}</small>
                        </div>
                        <div class="{'pnl-pos' if pnl_usd >= 0 else 'pnl-neg'}">${pnl_usd:.2f} (%{pnl_pct:.2f})</div>
                    </div>
                    <div style="margin-top:15px; border-top: 1px solid #1c2128; padding-top:10px; display: flex; justify-content: space-between;">
                        <span>📍 Giriş: {trade['entry']} | ⚡ Anlık: {curr_p}</span>
                        <span>🎯 TP: <b style="color:#00ff88;">{tp_p:.4f}</b> | 🛡️ SL: <b style="color:#f85149;">{sl_p:.4f}</b></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if pnl_pct >= 8.5 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# --- CC KALİTESİNDE TARAMA ---
if len(active_trades) < 5:
    with st.status("🔎 CC Kalitesinde İşlem Aranıyor...", expanded=False):
        try:
            markets = exchange.load_markets()
            all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
            for s in all_syms[:150]:
                if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
                if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
                
                bars = exchange.fetch_ohlcv(s, timeframe='15m', limit=40)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_cc_quality_signal(df)
                
                if side:
                    # Kasanın %10'uyla girmeye devam kanka
                    m_val = st.session_state.balance * 0.10
                    new_t = {"coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": round(m_val, 2), "status": "Açık", "time": str(datetime.now())}
                    st.session_state.trades.append(new_t)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
        except: pass

time.sleep(5)
st.rerun()
