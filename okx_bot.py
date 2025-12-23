import streamlit as st
import ccxt
import pandas as pd
import ta
import json
import os
from datetime import datetime

# OKX Bağlantısı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "trade_db.json"

# --- VERİTABANI ONARICI (HATA ÖNLEYİCİ) ---
def load_db():
    default_data = {"balance": 1027.0, "trades": [], "lessons": []}
    if not os.path.exists(DB_FILE):
        return default_data
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            # Kritik onarım: Eksik anahtarları ana sözlüğe ekle
            if "lessons" not in data: data["lessons"] = []
            if "trades" not in data: data["trades"] = []
            if "balance" not in data: data["balance"] = 1027.0
            
            # Her bir işlemi kontrol et ve eksik sütunları yamala
            for t in data["trades"]:
                if "pattern" not in t: t["pattern"] = "Bilinmiyor"
                if "pnl_final" not in t: t["pnl_final"] = 0.0
                if "status" not in t: t["status"] = "Kapandı"
                if "time" not in t: t["time"] = str(datetime.now())
                if "side" not in t: t["side"] = "Bilinmiyor"
                if "coin" not in t: t["coin"] = "Bilinmiyor"
            return data
    except Exception as e:
        st.error(f"Veritabanı onarılamadı, sıfırlanıyor: {e}")
        return default_data

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f)

# Verileri Yükle
db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]
if 'lessons' not in st.session_state: st.session_state.lessons = db_data["lessons"]

# --- PDF TEMELLİ MUM ANALİZİ ---
def detect_patterns(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(last['c'] - last['o'])
    
    # Bullish Hammer (Çekiç Boğa) -
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 2) and (last['h'] - max(last['o'], last['c'])) < body
    
    # Bullish Engulfing (Yutan Boğa) -
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c'] and prev['c'] < prev['o']
    
    # Bearish Shooting Star (Kayan Yıldız) -
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 2) and (min(last['o'], last['c']) - last['l']) < body

    if is_hammer or is_engulfing: return "LONG", "Hammer/Engulfing"
    if is_shooting_star: return "SHORT", "ShootingStar"
    return None, None

st.set_page_config(page_title="OKX Hunter V17.2", layout="wide")
st.title("🛡️ OKX Hunter V17.2: Hard Fix")

# ÜST PANEL
active_trades = [t for t in st.session_state.trades if t['status'] == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif", f"{len(active_trades)} / 5")
c3.info("PDF Zekası: ON | Hata Filtresi: ON")

# --- AKTİF İŞLEMLER ---
if active_trades:
    st.subheader("🚀 Aktif Pozisyonlar")
    for i, trade in enumerate(st.session_state.trades):
        if trade['status'] == 'Açık':
            try:
                curr_p = exchange.fetch_ticker(trade['coin'])['last']
                pnl_usd = (trade['margin'] * ((curr_p - trade['entry']) / trade['entry']) * 100 * (10 if trade['side'] == 'LONG' else -10)) / 100
                duration = (datetime.now() - datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')).total_seconds() / 60

                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    with col1:
                        st.write(f"**{trade['coin']}** ({trade['side']})")
                        st.caption(f"Formasyon: {trade.get('pattern', 'Bilinmiyor')}")
                    with col2:
                        st.write(f"Giriş: {trade['entry']} | Anlık: {curr_p}")
                        st.write(f"⏱️ Süre: {int(duration)} dk")
                    with col3:
                        st.metric("P/L", f"${pnl_usd:.2f}")

                # Kapanış
                if pnl_usd <= -3.5 or pnl_usd >= 5.0 or duration >= 10:
                    if pnl_usd < 0:
                        st.session_state.lessons.append(f"{trade['coin']} başarısız. PDF Teyidi yetersiz.")
                    
                    st.session_state.balance += pnl_usd
                    idx = st.session_state.trades.index(trade)
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades, "lessons": st.session_state.lessons})
                    st.rerun()
            except: continue

st.divider()

# --- TARAMA SİSTEMİ ---
if len(active_trades) < 5:
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:200]
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        try:
            bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=100)
            df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            pattern_side, pattern_name = detect_patterns(df)
            
            if pattern_side:
                new_trade = {
                    "coin": s, "side": pattern_side, "entry": df.iloc[-1]['c'], "pattern": pattern_name,
                    "tp": round(df.iloc[-1]['c'] * (1.02 if pattern_side == "LONG" else 0.98), 5),
                    "sl": round(df.iloc[-1]['c'] * (0.992 if pattern_side == "LONG" else 1.008), 5),
                    "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now()), "pnl_final": 0.0
                }
                st.session_state.trades.append(new_trade)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades, "lessons": st.session_state.lessons})
                st.rerun()
        except: continue

# --- GÜVENLİ GEÇMİŞ TABLOSU ---
st.subheader("📜 İşlem Geçmişi")
if st.session_state.trades:
    closed_trades = [t for t in st.session_state.trades if t['status'] == 'Kapandı']
    if closed_trades:
        df_h = pd.DataFrame(closed_trades)
        # Tabloyu basmadan önce sütunları garanti et
        safe_cols = ['time', 'coin', 'side', 'pnl_final']
        for c in safe_cols:
            if c not in df_h.columns: df_h[c] = "N/A"
            
        st.dataframe(df_h[safe_cols][::-1], use_container_width=True)

# --- DERSLER ---
with st.expander("🎓 AI Ders Notları"):
    for l in st.session_state.lessons[-5:]: st.write(f"- {l}")

time.sleep(15)
st.rerun()
