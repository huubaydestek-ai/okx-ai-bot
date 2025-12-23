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

# VERİTABANI YÖNETİMİ
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {"balance": 1000.0, "trades": []}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

# BAŞLANGIÇ AYARLARI
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

st.set_page_config(page_title="OKX AI Scalper V7", layout="wide")
st.title("🧠 OKX AI Scalper - Şeffaf Analiz Modu")

# KASA PANELİ
active_trades = [t for t in st.session_state.trades if t['status'] == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif İşlemler", f"{len(active_trades)} / 3")
c3.write(f"Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}")

# AÇIK İŞLEMLERİ TAKİP ET
for i, trade in enumerate(st.session_state.trades):
    if trade['status'] == 'Açık':
        curr_p = exchange.fetch_ticker(trade['coin'])['last']
        pnl = (curr_p - trade['entry']) / trade['entry'] * trade['margin'] * trade['kaldırac'] * (1 if trade['side'] == 'LONG' else -1)
        
        with st.expander(f"LIVE: {trade['coin']} | PNL: ${pnl:.2f}", expanded=True):
            if (trade['side'] == 'LONG' and (curr_p >= trade['tp'] or curr_p <= trade['sl'])) or \
               (trade['side'] == 'SHORT' and (curr_p <= trade['tp'] or curr_p >= trade['sl'])):
                st.session_state.balance += pnl
                st.session_state.trades[i]['status'] = 'Kapandı'
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()

# CANLI TARAMA VE GÜNLÜK
if len(active_trades) < 3:
    st.subheader("🔍 Canlı Tarama Günlüğü (Neyi Bekliyoruz?)")
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:50]
    
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        
        analysis = get_market_analysis(s)
        if analysis:
            with st.status(f"İnceleniyor: {s}", expanded=False):
                st.write(f"Fiyat: {analysis['price']} | RSI: {analysis['rsi']} | EMA: {analysis['ema']}")
                
                side = None
                if analysis['rsi'] < 45 and analysis['price'] < analysis['ema']:
                    side = "LONG"
                elif analysis['rsi'] > 55 and analysis['price'] > analysis['ema']:
                    side = "SHORT"
                
                if side:
                    st.success(f"🚀 {side} Sinyali Bulundu! İşleme giriliyor...")
                    new_trade = {
                        "coin": s, "side": side, "entry": analysis['price'],
                        "tp": analysis['price'] * (1.015 if side == "LONG" else 0.985),
                        "sl": analysis['price'] * (0.992 if side == "LONG" else 1.008),
                        "margin": 50, "kaldırac": 10, "status": "Açık", "time": str(datetime.now())
                    }
                    st.session_state.trades.append(new_trade)
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.rerun()
                else:
                    st.write("❌ Kriterler uyuşmuyor, geçiliyor.")

time.sleep(15)
st.rerun()
                # İşlem açma kodları buraya gelecek...
                # (Daha önceki dinamik risk hesaplamalı işlem açma bloğunu buraya ekle)


