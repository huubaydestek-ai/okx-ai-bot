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

# --- ARAYÜZ AYARLARI ---
st.set_page_config(page_title="OKX AI Scalper V8", layout="wide")
st.title("🧠 OKX AI Scalper - Profesyonel İzleme Paneli")

# ÜST BİLGİ PANELİ
active_trades = [t for t in st.session_state.trades if t['status'] == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Toplam Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozisyonlar", f"{len(active_trades)} / 3")
c3.write(f"🕒 Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}")

st.divider()

# --- AÇIK POZİSYONLARIN DETAYLI TAKİBİ ---
if active_trades:
    st.subheader("🚀 Mevcut İşlemler (Canlı Veri)")
    for i, trade in enumerate(st.session_state.trades):
        if trade['status'] == 'Açık':
            # Canlı Fiyat Çekme
            try:
                curr_p = exchange.fetch_ticker(trade['coin'])['last']
            except: continue
            
            # PNL Hesaplama
            pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (trade['kaldırac'] if trade['side'] == 'LONG' else -trade['kaldırac'])
            pnl_usd = (trade['margin'] * pnl_pct) / 100
            
            # Görsel Kart Tasarımı
            with st.container(border=True):
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col1:
                    st.markdown(f"### {trade['coin']}")
                    st.info(f"**{trade['side']} | {trade['kaldırac']}x**")
                    
                with col2:
                    st.write(f"📌 **Giriş:** {trade['entry']}")
                    st.write(f"⚡ **Anlık:** {curr_p}")
                    st.write(f"🎯 **Hedef (TP):** {trade['tp']} | 🛡️ **Durdurma (SL):** {trade['sl']}")
                    
                with col3:
                    label = "Kar/Zarar (USD)"
                    st.metric(label, f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")
            
                # Kapatma Mantığı
                is_win = (trade['side'] == 'LONG' and curr_p >= trade['tp']) or (trade['side'] == 'SHORT' and curr_p <= trade['tp'])
                is_loss = (trade['side'] == 'LONG' and curr_p <= trade['sl']) or (trade['side'] == 'SHORT' and curr_p >= trade['sl'])
                
                if is_win or is_loss:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[i]['status'] = 'Kapandı'
                    st.session_state.trades[i]['exit_p'] = curr_p
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.balloons() if is_win else st.error("İşlem Stop Oldu.")
                    st.rerun()

st.divider()

# --- CANLI TARAMA GÜNLÜĞÜ ---
if len(active_trades) < 3:
    st.subheader("🔍 Pazar Taraması")
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:50]
    
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        
        analysis = get_market_analysis(s)
        if analysis:
            # Sinyal Mantığı
            side = None
            if analysis['rsi'] < 42 and analysis['price'] < analysis['ema']: side = "LONG"
            elif analysis['rsi'] > 58 and analysis['price'] > analysis['ema']: side = "SHORT"
            
            if side:
                new_trade = {
                    "coin": s, "side": side, "entry": analysis['price'],
                    "tp": analysis['price'] * (1.015 if side == "LONG" else 0.985),
                    "sl": analysis['price'] * (0.992 if side == "LONG" else 1.008),
                    "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now())
                }
                st.session_state.trades.append(new_trade)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.toast(f"Fırsat Yakalandı: {s} {side}")
                st.rerun()

# GEÇMİŞ TABLOSU
with st.expander("📜 İşlem Geçmişi"):
    if st.session_state.trades:
        st.dataframe(pd.DataFrame(st.session_state.trades)[::-1], use_container_width=True)

time.sleep(15)
st.rerun()
                # (Daha önceki dinamik risk hesaplamalı işlem açma bloğunu buraya ekle)



