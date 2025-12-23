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

# --- VERİTABANI VE HATA DÜZELTME ---
def load_db():
    default_data = {"balance": 1007.65, "trades": []}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                # Eksik sütunları kontrol et ve ekle
                for t in data.get("trades", []):
                    if "pnl_final" not in t: t["pnl_final"] = 0
                return data
        except: return default_data
    return default_data

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]

def get_market_analysis(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['RSI'] = ta.momentum.rsi(df['c'], window=14)
        indicator_bb = ta.volatility.BollingerBands(close=df["c"], window=20, window_dev=2)
        df['bb_h'] = indicator_bb.bollinger_hband()
        df['bb_l'] = indicator_bb.bollinger_lband()
        last = df.iloc[-1]
        return {"price": last['c'], "rsi": round(last['RSI'], 2), "bb_h": last['bb_h'], "bb_l": last['bb_l']}
    except: return None

st.set_page_config(page_title="OKX Hunter V13.1", layout="wide")
st.title("🛡️ OKX Hunter V13.1: Güvenlik & Fix")

# ÜST PANEL
active_trades = [t for t in st.session_state.trades if t['status'] == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Mevcut Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.warning("Güvenlik: LİQ TAKİBİ AKTİF")

# --- AKTİF POZİSYONLAR VE LİQ TAKİBİ ---
if active_trades:
    st.subheader("🚀 Aktif Pozisyonlar")
    for i, trade in enumerate(st.session_state.trades):
        if trade['status'] == 'Açık':
            try:
                curr_p = exchange.fetch_ticker(trade['coin'])['last']
            except: continue
            
            pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (trade['kaldırac'] if trade['side'] == 'LONG' else -trade['kaldırac'])
            pnl_usd = (trade['margin'] * pnl_pct) / 100
            
            # LİQ HESABI (10x için girişin +- %9-10'u)
            liq_price = trade['entry'] * (0.91 if trade['side'] == 'LONG' else 1.09)
            liq_dist = abs(curr_p - liq_price) / curr_p * 100

            with st.container(border=True):
                col1, col2, col3 = st.columns([1, 2, 1])
                with col1:
                    st.write(f"**{trade['coin']}**")
                    st.caption(f"{trade['side']} 10x")
                    st.error(f"💀 Liq: {liq_price:.4f}")
                with col2:
                    st.write(f"📌 Giriş: {trade['entry']} | ⚡ Anlık: {curr_p}")
                    st.write(f"🎯 TP: {trade['tp']} | 🛡️ SL: {trade['sl']}")
                    st.write(f"📏 Liq Mesafe: %{liq_dist:.2f}")
                with col3:
                    st.metric("P/L USD", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")

            if (trade['side'] == 'LONG' and (curr_p >= trade['tp'] or curr_p <= trade['sl'])) or \
               (trade['side'] == 'SHORT' and (curr_p <= trade['tp'] or curr_p >= trade['sl'])):
                st.session_state.balance += pnl_usd
                idx = st.session_state.trades.index(trade)
                st.session_state.trades[idx]['status'] = 'Kapandı'
                st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()

st.divider()

# --- TARAMA SİSTEMİ (200 COIN) ---
if len(active_trades) < 5:
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:200]
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        a = get_market_analysis(s)
        if a:
            side = None
            if a['rsi'] < 38 and a['price'] < a['bb_l']: side = "LONG"
            elif a['rsi'] > 62 and a['price'] > a['bb_h']: side = "SHORT"
            if side:
                new_trade = {
                    "coin": s, "side": side, "entry": a['price'],
                    "tp": round(a['price'] * (1.02 if side == "LONG" else 0.98), 5),
                    "sl": round(a['price'] * (0.992 if side == "LONG" else 1.008), 5),
                    "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now()), "pnl_final": 0
                }
                st.session_state.trades.append(new_trade)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()

# --- GEÇMİŞ TABLOSU (HATA DÜZELTİLMİŞ) ---
st.subheader("📜 İşlem Geçmişi")
if st.session_state.trades:
    closed_trades = [t for t in st.session_state.trades if t['status'] == 'Kapandı']
    if closed_trades:
        df_h = pd.DataFrame(closed_trades)
        # Sütunların varlığını kontrol et
        needed_cols = ['time', 'coin', 'side', 'entry', 'pnl_final']
        for col in needed_cols:
            if col not in df_h.columns: df_h[col] = "Veri Yok"
        
        st.dataframe(df_h[needed_cols][::-1], use_container_width=True)

time.sleep(15)
st.rerun()
