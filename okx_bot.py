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

# --- PDF FORMASYON SİSTEMİ ---
def get_pdf_signal(df):
    last = df.iloc[-1]; prev = df.iloc[-2]
    body = abs(last['c'] - last['o'])
    # Hammer & Engulfing (PDF Sayfa 6)
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 2) and (last['h'] - max(last['o'], last['c'])) < (body * 0.5)
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c'] and prev['c'] < prev['o']
    # Shooting Star (PDF Sayfa 12)
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 2) and (min(last['o'], last['c']) - last['l']) < (body * 0.5)

    if (is_hammer or is_engulfing): return "LONG"
    if is_shooting_star: return "SHORT"
    return None

st.set_page_config(page_title="OKX Sniper V19.1", layout="wide")
st.title("🏹 OKX Sniper V19.1: Detaylı Panel")

# --- ÜST PANEL ---
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa Bakiyesi", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.success("Zeka: PDF + Detaylı Takip")

# --- AKTİF POZİSYONLAR ---
if active_trades:
    st.subheader("🚀 Mevcut Pozisyonlar")
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (trade['kaldırac'] if trade['side'] == 'LONG' else -trade['kaldırac'])
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                duration = (datetime.now() - datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')).total_seconds() / 60
                
                # Tahmini Liq Fiyatı (İzole 10x için yaklaşık %9-10 ters hareket)
                if trade['side'] == "LONG":
                    liq_p = trade['entry'] * (1 - (1 / trade['kaldırac']))
                else:
                    liq_p = trade['entry'] * (1 + (1 / trade['kaldırac']))

                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([1.5, 2, 2, 1])
                    
                    with col1:
                        st.write(f"### {trade['coin']}")
                        st.markdown(f"**{trade['side']} | {trade['kaldırac']}x**")
                        st.write(f"💰 **Margin:** ${trade['margin']}")
                        st.caption(f"⏱️ {int(duration)} dk")
                    
                    with col2:
                        st.write(f"📌 Giriş: `{trade['entry']}`")
                        st.write(f"⚡ Anlık: `{curr_p}`")
                        st.write(f"💀 **Liq:** `{liq_p:.5f}`")
                    
                    with col3:
                        st.write(f"🎯 **TP:** `{trade['tp']}`")
                        st.write(f"🛡️ **SL:** `{trade['sl']}`")
                        st.metric("P/L", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")
                    
                    with col4:
                        if st.button("KAPAT", key=f"man_{idx}", use_container_width=True):
                            st.session_state.balance += pnl_usd
                            st.session_state.trades[idx]['status'] = 'Kapandı'
                            st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                            save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                            st.rerun()

                # Otomatik Kapanış (10 dk veya Hedefler)
                if duration >= 10 or pnl_usd <= -3.8 or pnl_usd >= 6.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.rerun()
            except: continue

st.divider()

# --- SNIPER TARAMA ---
if len(active_trades) < 5:
    st.subheader("🔎 Sinyal Gözlemcisi")
    symbols = [s for s in exchange.load_markets() if '/USDT' in s][:120]
    for s in symbols:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
        
        try:
            ticker = exchange.fetch_ticker(s)
            if ticker.get('quoteVolume', 0) < 3000000: continue

            bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=50)
            df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            pdf_side = get_pdf_signal(df)
            rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
            
            if (pdf_side == "LONG" and rsi < 40) or (pdf_side == "SHORT" and rsi > 60):
                new_t = {
                    "coin": s, "side": pdf_side, "entry": df['c'].iloc[-1], "kaldırac": 10, "margin": 50.0,
                    "tp": round(df['c'].iloc[-1] * (1.025 if pdf_side == "LONG" else 0.975), 6),
                    "sl": round(df['c'].iloc[-1] * (0.992 if pdf_side == "LONG" else 1.008), 6),
                    "status": "Açık", "time": str(datetime.now())
                }
                st.session_state.trades.append(new_t)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()
        except: continue

time.sleep(15)
st.rerun()
