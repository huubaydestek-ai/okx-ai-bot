import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime, timedelta

# OKX Bağlantısı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "trade_db.json"

def load_db():
    default_data = {"balance": 1027.0, "trades": [], "blacklist": {}}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                if "blacklist" not in data: data["blacklist"] = {}
                return data
        except: return default_data
    return default_data

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]
if 'blacklist' not in st.session_state: st.session_state.blacklist = db_data["blacklist"]

# --- HATA DERSİ: KARA LİSTE KONTROLÜ ---
def is_blacklisted(symbol):
    if symbol in st.session_state.blacklist:
        expiry = datetime.strptime(st.session_state.blacklist[symbol], '%Y-%m-%d %H:%M:%S.%f')
        if datetime.now() < expiry: return True
    return False

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

st.set_page_config(page_title="OKX Self-Learning V16", layout="wide")
st.title("🧠 OKX Hunter V16: Öğrenen Algoritma")

# ÜST PANEL
active_trades = [t for t in st.session_state.trades if t['status'] == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Mevcut Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.info("Zaman Stopu: **ZORUNLU 10DK** | Hata Payı: **Öğreniliyor**")

# --- AKTİF POZİSYONLAR VE KATI KONTROL ---
if active_trades:
    st.subheader("🚀 Aktif Pozisyonlar")
    for i, trade in enumerate(st.session_state.trades):
        if trade['status'] == 'Açık':
            try:
                curr_p = exchange.fetch_ticker(trade['coin'])['last']
            except: continue
            
            pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (trade['kaldırac'] if trade['side'] == 'LONG' else -trade['kaldırac'])
            pnl_usd = (trade['margin'] * pnl_pct) / 100
            
            start_time = datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')
            duration = datetime.now() - start_time
            mins_passed = duration.total_seconds() / 60

            with st.container(border=True):
                col1, col2, col3 = st.columns([1.5, 2, 1])
                with col1:
                    st.write(f"### {trade['coin']} ({trade['side']})")
                    st.write(f"⏱️ **Süre:** {int(mins_passed)} dk {int(duration.total_seconds()%60)} sn")
                    st.caption(f"Marjin: ${trade['margin']} | 10x")
                with col2:
                    st.write(f"📌 Giriş: {trade['entry']} | ⚡ Anlık: {curr_p}")
                    st.write(f"🎯 TP: {trade['tp']} | 🛡️ SL: {trade['sl']}")
                with col3:
                    st.metric("P/L USD", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")

            # KAPATMA MANTIĞI (GÜÇLENDİRİLMİŞ)
            is_target = (trade['side'] == 'LONG' and (curr_p >= trade['tp'] or curr_p <= trade['sl'])) or \
                        (trade['side'] == 'SHORT' and (curr_p <= trade['tp'] or curr_p >= trade['sl']))
            
            # KATI ZAMAN STOPU: 10 dk dolduysa kâr/zarar fark etmeksizin çık (Fırsat kaçırmamak için)
            is_time_force = mins_passed >= 10.0 
            
            if is_target or is_time_force:
                st.session_state.balance += pnl_usd
                idx = st.session_state.trades.index(trade)
                st.session_state.trades[idx]['status'] = 'Kapandı'
                st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                
                # EĞER STOP OLDUYSA (ZARAR), COİNİ KARA LİSTEYE AL
                if pnl_usd < 0:
                    st.session_state.blacklist[trade['coin']] = str(datetime.now() + timedelta(minutes=30))
                    st.toast(f"❌ {trade['coin']} Zarar Yazdı. 30 Dakika Analiz Edilecek (Girilmeyecek).")
                
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades, "blacklist": st.session_state.blacklist})
                st.rerun()

st.divider()

# --- ÖĞRENEN TARAMA SİSTEMİ ---
if len(active_trades) < 5:
    st.subheader("🎯 Alpha Sinyal Gözlemcisi")
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:200]
    pending_list = []
    
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        if is_blacklisted(s): continue # HATA YAPILAN COİNDEN UZAK DUR
        
        a = get_market_analysis(s)
        if a:
            side = None
            if a['rsi'] < 36 and a['price'] < a['bb_l']: side = "LONG" # RSI 38'den 36'ya çekildi (Daha sağlam giriş)
            elif a['rsi'] > 64 and a['price'] > a['bb_h']: side = "SHORT"
            
            if side:
                new_trade = {
                    "coin": s, "side": side, "entry": a['price'],
                    "tp": round(a['price'] * (1.015 if side == "LONG" else 0.985), 5), # %1.5 TP
                    "sl": round(a['price'] * (0.993 if side == "LONG" else 1.007), 5), # %0.7 SL
                    "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now()), "pnl_final": 0
                }
                st.session_state.trades.append(new_trade)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades, "blacklist": st.session_state.blacklist})
                st.rerun()

# GEÇMİŞ
st.subheader("📜 Detaylı İşlem Geçmişi")
if st.session_state.trades:
    df_h = pd.DataFrame([t for t in st.session_state.trades if t['status'] == 'Kapandı'])
    if not df_h.empty: st.dataframe(df_h[['time', 'coin', 'side', 'entry', 'pnl_final']][::-1], use_container_width=True)

time.sleep(15)
st.rerun()
