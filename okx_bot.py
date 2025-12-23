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

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"balance": 1048.0, "trades": []}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

db_data = load_db()
st.session_state.update(db_data)

# --- PDF'TEN ÖĞRENİLEN FORMASYON ZEKA SİSTEMİ ---
def get_pdf_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(last['c'] - last['o'])
    
    # PDF Sayfa 6/24: Bullish Hammer (Çekiç) - Dipten Dönüş
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 2) and (last['h'] - max(last['o'], last['c'])) < (body * 0.5)
    
    # PDF Sayfa 6: Bullish Engulfing (Yutan)
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c'] and prev['c'] < prev['o']
    
    # PDF Sayfa 12: Shooting Star (Ayı Sinyali)
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 2) and (min(last['o'], last['c']) - last['l']) < (body * 0.5)

    if (is_hammer or is_engulfing): return "LONG"
    if is_shooting_star: return "SHORT"
    return None

st.set_page_config(page_title="OKX Hunter V19", layout="wide")
st.title("🏹 OKX Hunter V19: Sniper Mod")

# --- ÜST PANEL ---
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.info("Zeka: PDF Formasyon + Hacim Filtresi")

# --- AKTİF POZİSYONLAR VE MANUEL KAPAT ---
if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_usd = (trade['margin'] * ((curr_p - trade['entry']) / trade['entry']) * 100 * (10 if trade['side'] == 'LONG' else -10)) / 100
                duration = (datetime.now() - datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')).total_seconds() / 60

                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([1.5, 2, 1, 1])
                    col1.write(f"**{trade['coin']}** ({trade['side']})")
                    col2.write(f"Giriş: {trade['entry']} | Anlık: {curr_p}")
                    col3.metric("P/L USD", f"${pnl_usd:.2f}")
                    if col4.button("KAPAT", key=f"manual_{idx}"):
                        st.session_state.balance += pnl_usd
                        st.session_state.trades[idx]['status'] = 'Kapandı'
                        st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                        save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                        st.rerun()

                if duration >= 10 or pnl_usd <= -3.8 or pnl_usd >= 6.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.rerun()
            except: continue

# --- SNIPER TARAMA (HACİM + PDF) ---
if len(active_trades) < 5:
    st.subheader("🔎 Kaliteli Fırsat Aranıyor...")
    symbols = [s for s in exchange.load_markets() if '/USDT' in s][:120]
    for s in symbols:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
        
        try:
            ticker = exchange.fetch_ticker(s)
            if ticker.get('quoteVolume', 0) < 3000000: continue # Hacim alt sınırı (3M$ - Biraz esnettim sinyal gelsin diye)

            bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=50)
            df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            
            # PDF Sinyali + RSI Onayı
            pdf_side = get_pdf_signal(df)
            rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
            
            if (pdf_side == "LONG" and rsi < 40) or (pdf_side == "SHORT" and rsi > 60):
                new_t = {
                    "coin": s, "side": pdf_side, "entry": df['c'].iloc[-1],
                    "tp": round(df['c'].iloc[-1] * (1.025 if pdf_side == "LONG" else 0.975), 6),
                    "sl": round(df['c'].iloc[-1] * (0.99 if pdf_side == "LONG" else 1.01), 6),
                    "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now())
                }
                st.session_state.trades.append(new_t)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()
        except: continue

time.sleep(15)
st.rerun()
