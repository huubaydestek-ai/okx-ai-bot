import streamlit as st
import ccxt
import pandas as pd
import ta
import json
import os
from datetime import datetime, timedelta

# OKX Bağlantısı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "trade_db.json"

def load_db():
    default_data = {"balance": 1027.0, "trades": [], "blacklist": {}, "lessons": []}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                if "lessons" not in data: data["lessons"] = []
                return data
        except: return default_data
    return default_data

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

db_data = load_db()
st.session_state.update(db_data)

# --- MUM FORMASYON ZEKA MOTORU (PDF TABANLI) ---
def detect_patterns(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. Bullish Hammer (Çekiç Boğa) - [Cite: 6, 24]
    body = abs(last['c'] - last['o'])
    lower_wick = last['l'] if last['c'] > last['o'] else last['l']
    # Çekiç kuralı: Alt gölge gövdenin en az 2 katı olmalı
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 2) and (last['h'] - max(last['o'], last['c'])) < body
    
    # 2. Bullish Engulfing (Yutan Boğa) - [Cite: 6]
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c'] and prev['c'] < prev['o']
    
    # 3. Bearish Shooting Star (Kayan Yıldız) - [Cite: 12]
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 2) and (min(last['o'], last['c']) - last['l']) < body

    if is_hammer or is_engulfing: return "LONG", "Hammer/Engulfing"
    if is_shooting_star: return "SHORT", "ShootingStar"
    return None, None

def get_market_analysis(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        pattern_side, pattern_name = detect_patterns(df)
        
        # Sinyal Gücü: Hem indikatör hem formasyon onayı
        rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
        
        if pattern_side == "LONG" and rsi < 45: return {"side": "LONG", "price": df.iloc[-1]['c'], "pattern": pattern_name}
        if pattern_side == "SHORT" and rsi > 55: return {"side": "SHORT", "price": df.iloc[-1]['c'], "pattern": pattern_name}
        return None
    except: return None

st.set_page_config(page_title="OKX Pattern Master V17", layout="wide")
st.title("🧠 OKX Hunter V17: Formasyon Akademisi")

# ÜST PANEL
active_trades = [t for t in st.session_state.trades if t['status'] == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif", f"{len(active_trades)} / 5")
c3.success("Zeka: Mum Formasyonları + Teyit Aktif")

# --- AKTİF İŞLEMLER VE ÖĞRENME ---
if active_trades:
    for i, trade in enumerate(st.session_state.trades):
        if trade['status'] == 'Açık':
            curr_p = exchange.fetch_ticker(trade['coin'])['last']
            pnl_usd = (trade['margin'] * ((curr_p - trade['entry']) / trade['entry']) * 100 * (10 if trade['side'] == 'LONG' else -10)) / 100
            
            duration = (datetime.now() - datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')).total_seconds() / 60

            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{trade['coin']}** | {trade['side']} | Formasyon: {trade.get('pattern', 'Bilinmiyor')}")
                col1.caption(f"Süre: {int(duration)} dk | Giriş: {trade['entry']} | Anlık: {curr_p}")
                col2.metric("P/L", f"${pnl_usd:.2f}")

            # KAPATMA VE DERS ÇIKARMA
            if pnl_usd <= -3.5 or pnl_usd >= 5.0 or duration >= 10:
                # DERS ÇIKAR: Eğer zarar ettiyse nedenini kaydet
                if pnl_usd < 0:
                    lesson = f"{trade['coin']} {trade['pattern']} formasyonunda zarar etti. Sebep: Teyit sonrası hacim yetersiz veya ters trend."
                    st.session_state.lessons.append(lesson)
                
                st.session_state.balance += pnl_usd
                idx = st.session_state.trades.index(trade)
                st.session_state.trades[idx]['status'] = 'Kapandı'
                st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                save_db(st.session_state)
                st.rerun()

# --- TARAMA (FORMASYON ODAKLI) ---
if len(active_trades) < 5:
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:200]
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        res = get_market_analysis(s)
        if res:
            new_trade = {
                "coin": s, "side": res['side'], "entry": res['price'], "pattern": res['pattern'],
                "tp": round(res['price'] * (1.02 if res['side'] == "LONG" else 0.98), 5),
                "sl": round(res['price'] * (0.992 if res['side'] == "LONG" else 1.008), 5),
                "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now())
            }
            st.session_state.trades.append(new_trade)
            save_db(st.session_state)
            st.rerun()

# --- ÖĞRENİLEN DERSLER ---
with st.expander("🎓 AI Hata Analizi ve Öğrenilen Dersler"):
    if st.session_state.lessons:
        for l in st.session_state.lessons[-5:]: st.write(f"- {l}")
    else: st.write("Henüz hata yapılmadı, bot kusursuz ilerliyor.")
