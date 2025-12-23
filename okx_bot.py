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
        bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['RSI'] = ta.momentum.rsi(df['c'], window=14)
        df['EMA_20'] = ta.trend.ema_indicator(df['c'], window=20)
        last = df.iloc[-1]
        
        # Analiz verilerini geri döndürelim ki ekrana yazabilelim
        return {
            "price": last['c'],
            "rsi": round(last['RSI'], 2),
            "ema": round(last['EMA_20'], 4),
            "vol": last['v']
        }
    except: return None

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

# TARAMA BÖLÜMÜNÜ ŞU ŞEKİLDE GÜNCELLE:
if len(active_trades) < 3:
    st.subheader("🔍 Canlı Tarama Günlüğü")
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:50] # Hız için 50 ideal
    
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        
        analysis = get_market_analysis(s)
        if analysis:
            # EKRANA CANLI DURUM YAZDIRMA (İşte burası önemli!)
            with st.status(f"İnceleniyor: {s}", expanded=False):
                st.write(f"Fiyat: {analysis['price']} | RSI: {analysis['rsi']} | EMA: {analysis['ema']}")
                
                # Karar Mekanizması
                side = None
                if analysis['rsi'] < 45 and analysis['price'] < analysis['ema']:
                    side = "LONG"
                    st.success(f"✅ LONG SİNYALİ! RSI ({analysis['rsi']}) düşük ve fiyat EMA altında.")
                elif analysis['rsi'] > 55 and analysis['price'] > analysis['ema']:
                    side = "SHORT"
                    st.warning(f"✅ SHORT SİNYALİ! RSI ({analysis['rsi']}) yüksek ve fiyat EMA üstünde.")
                else:
                    st.write("❌ Kriterler karşılanmadı. Beklemede...")

            if side:
                # İşlem açma kodları buraya gelecek...
                # (Daha önceki dinamik risk hesaplamalı işlem açma bloğunu buraya ekle)

