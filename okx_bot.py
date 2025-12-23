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

# --- VERİTABANI OTOMATİK ONARICI ---
def load_db():
    default_data = {"balance": 1027.0, "trades": [], "lessons": []}
    if not os.path.exists(DB_FILE): return default_data
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            # Eğer dosya boşsa veya hatalıysa default dön
            if not data or not isinstance(data, dict): return default_data
            
            # Eksik ana bölümleri ekle
            if "lessons" not in data: data["lessons"] = []
            if "trades" not in data: data["trades"] = []
            
            # Her bir işlemi tek tek tara ve eksik sütunları yamala
            for t in data["trades"]:
                if "pattern" not in t: t["pattern"] = "Genel"
                if "pnl_final" not in t: t["pnl_final"] = 0.0
                if "status" not in t: t["status"] = "Kapandı"
            return data
    except: return default_data

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

# Verileri güvenle yükle
db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]
if 'lessons' not in st.session_state: st.session_state.lessons = db_data["lessons"]

# --- PDF ZEKA MOTORU: FORMASYON & TEYİT ---
def detect_patterns(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(last['c'] - last['o'])
    
    # 1. Bullish Hammer (Çekiç Boğa) - PDF Sayfa 6/24
    # Alt gölge gövdenin 2 katından büyük, üst gölge yok denecek kadar az
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 2) and (last['h'] - max(last['o'], last['c'])) < (body * 0.5)
    
    # 2. Bullish Engulfing (Yutan Boğa) - PDF Sayfa 6
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c'] and prev['c'] < prev['o']
    
    # 3. Bearish Shooting Star (Kayan Yıldız) - PDF Sayfa 12
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 2) and (min(last['o'], last['c']) - last['l']) < (body * 0.5)

    if is_hammer or is_engulfing: return "LONG", "Hammer/Engulfing"
    if is_shooting_star: return "SHORT", "ShootingStar"
    return None, None

st.set_page_config(page_title="OKX Master V17.3", layout="wide")
st.title("🏹 OKX Hunter V17.3: Mum Akademisi")

# ÜST PANEL
active_trades = [t for t in st.session_state.trades if t['status'] == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa Bakiyesi", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozisyonlar", f"{len(active_trades)} / 5")
c3.info("Zaman Stopu: 10 DK | Formasyon Teyidi: AKTİF")

# --- AKTİF POZİSYON TAKİBİ ---
if active_trades:
    st.subheader("🚀 Mevcut İşlemler")
    for i, trade in enumerate(st.session_state.trades):
        if trade['status'] == 'Açık':
            try:
                curr_p = exchange.fetch_ticker(trade['coin'])['last']
                pnl_usd = (trade['margin'] * ((curr_p - trade['entry']) / trade['entry']) * 100 * (10 if trade['side'] == 'LONG' else -10)) / 100
                duration = (datetime.now() - datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')).total_seconds() / 60

                with st.container(border=True):
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        st.write(f"**{trade['coin']}**")
                        st.write(f"Yön: {trade['side']}")
                        st.caption(f"Tip: {trade.get('pattern', 'Genel')}")
                    with col2:
                        st.write(f"📌 Giriş: {trade['entry']} | ⚡ Anlık: {curr_p}")
                        st.write(f"⏱️ Süre: {int(duration)} dk")
                    with col3:
                        st.metric("P/L USD", f"${pnl_usd:.2f}")

                # Kapatma Mantığı
                if pnl_usd <= -3.5 or pnl_usd >= 5.0 or duration >= 10:
                    if pnl_usd < 0:
                        st.session_state.lessons.append(f"{trade['coin']} - {trade['pattern']} başarısız. PDF Teyidi yetersiz kaldı.")
                    
                    st.session_state.balance += pnl_usd
                    idx = st.session_state.trades.index(trade)
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades, "lessons": st.session_state.lessons})
                    st.rerun()
            except: continue

st.divider()

# --- TARAMA SİSTEMİ (PDF ANALİZLİ) ---
if len(active_trades) < 5:
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:200]
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        try:
            bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=50)
            df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            side, name = detect_patterns(df)
            
            if side:
                new_trade = {
                    "coin": s, "side": side, "entry": df.iloc[-1]['c'], "pattern": name,
                    "tp": round(df.iloc[-1]['c'] * (1.02 if side == "LONG" else 0.98), 5),
                    "sl": round(df.iloc[-1]['c'] * (0.992 if side == "LONG" else 1.008), 5),
                    "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now())
                }
                st.session_state.trades.append(new_trade)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades, "lessons": st.session_state.lessons})
                st.rerun()
        except: continue

# --- GÜVENLİ TABLOLAR ---
c_bot1, c_bot2 = st.columns(2)
with c_bot1:
    st.subheader("📜 Son İşlemler")
    if st.session_state.trades:
        df_h = pd.DataFrame([t for t in st.session_state.trades if t['status'] == 'Kapandı'])
        if not df_h.empty:
            # Hata vermemesi için sadece var olan sütunları seç
            valid_cols = [c for c in ['time', 'coin', 'side', 'pnl_final'] if c in df_h.columns]
            st.dataframe(df_h[valid_cols][::-1], use_container_width=True)

with c_bot2:
    st.subheader("🎓 Öğrenilen Dersler")
    for l in st.session_state.lessons[-5:][::-1]: st.write(f"- {l}")

time.sleep(15)
st.rerun()
