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

# --- 1. MADDE: KALICI VERİTABANI ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {"balance": 1007.65, "trades": []}
    return {"balance": 1000.0, "trades": []}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]

# --- DAHA GÜÇLÜ ANALİZ MOTORU ---
def get_market_analysis(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        
        # İndikatörler
        df['RSI'] = ta.momentum.rsi(df['c'], window=14)
        df['EMA_20'] = ta.trend.ema_indicator(df['c'], window=20)
        # Bollinger Bantları
        indicator_bb = ta.volatility.BollingerBands(close=df["c"], window=20, window_dev=2)
        df['bb_high'] = indicator_bb.bollinger_hband()
        df['bb_low'] = indicator_bb.bollinger_lband()
        # ATR (Volatilite Ölçer)
        df['ATR'] = ta.volatility.average_true_range(df['h'], df['l'], df['c'], window=14)
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        return {
            "price": last['c'], "rsi": last['RSI'], "ema": last['EMA_20'],
            "bb_h": last['bb_high'], "bb_l": last['bb_low'], "atr": last['ATR']
        }
    except: return None

# --- ARAYÜZ ---
st.set_page_config(page_title="OKX Alpha V10", layout="wide")
st.title("🎖️ OKX Alpha V10: Profesyonel Scalper")

c1, c2, c3 = st.columns(3)
c1.metric("💰 Toplam Kasa", f"${st.session_state.balance:.2f}")
active_trades = [t for t in st.session_state.trades if t['status'] == 'Açık']
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 3")
c3.write(f"🕒 Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}")

# --- 2. MADDE: TRAILING STOP & POZİSYON TAKİBİ ---
if active_trades:
    for i, trade in enumerate(st.session_state.trades):
        if trade['status'] == 'Açık':
            try:
                curr_p = exchange.fetch_ticker(trade['coin'])['last']
            except: continue
            
            pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (trade['kaldırac'] if trade['side'] == 'LONG' else -trade['kaldırac'])
            pnl_usd = (trade['margin'] * pnl_pct) / 100

            # Dinamik Trailing: Kâr %0.5'i geçerse SL'i giriş fiyatına çek (BE: Break Even)
            if pnl_pct > 0.5 and trade.get('trailing_active') != True:
                st.session_state.trades[i]['sl'] = trade['entry']
                st.session_state.trades[i]['trailing_active'] = True
                st.toast(f"🛡️ {trade['coin']} için Stop Giriş Seviyesine Çekildi (Kâr Korunuyor)")

            with st.container(border=True):
                col1, col2, col3 = st.columns([1, 2, 1])
                with col1: st.subheader(trade['coin']); st.caption(f"{trade['side']} | 10x")
                with col2: st.write(f"📌 Giriş: {trade['entry']} | ⚡ Anlık: {curr_p}"); st.write(f"🎯 TP: {trade['tp']} | 🛡️ SL: {trade['sl']}")
                with col3: st.metric("Anlık PNL", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")

            # Kapanış Kontrolü
            is_win = (trade['side'] == 'LONG' and curr_p >= trade['tp']) or (trade['side'] == 'SHORT' and curr_p <= trade['tp'])
            is_loss = (trade['side'] == 'LONG' and curr_p <= trade['sl']) or (trade['side'] == 'SHORT' and curr_p >= trade['sl'])
            
            if is_win or is_loss:
                st.session_state.balance += pnl_usd
                st.session_state.trades[i]['status'] = 'Kapandı'
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()

st.divider()

# --- GELİŞMİŞ SİNYAL TARAMA ---
if len(active_trades) < 3:
    st.subheader("🔍 Alpha Sinyal Taraması")
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:60]
    
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        a = get_market_analysis(s)
        if a:
            side = None
            # PROFESYONEL KRİTER: RSI + Bollinger Alt/Üst Bant + EMA Onayı
            if a['rsi'] < 35 and a['price'] < a['bb_l'] and a['price'] < a['ema']:
                side = "LONG" # Aşırı satım + Bant dışı + Trend altı (Tepki beklentisi)
            elif a['rsi'] > 65 and a['price'] > a['bb_h'] and a['price'] > a['ema']:
                side = "SHORT" # Aşırı alım + Bant dışı + Trend üstü (Düşüş beklentisi)
            
            if side:
                new_trade = {
                    "coin": s, "side": side, "entry": a['price'],
                    "tp": a['price'] * (1.02 if side == "LONG" else 0.98), # %2 Hedef
                    "sl": a['price'] * (0.99 if side == "LONG" else 1.01), # %1 Stop
                    "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now())
                }
                st.session_state.trades.append(new_trade)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()

# GEÇMİŞ LİSTESİ (HER ZAMAN GÖRÜNÜR)
st.subheader("📜 İşlem Geçmişi")
if st.session_state.trades:
    history_df = pd.DataFrame([t for t in st.session_state.trades if t['status'] == 'Kapandı'])
    if not history_df.empty:
        st.dataframe(history_df[::-1], use_container_width=True)

time.sleep(15)
st.rerun()
