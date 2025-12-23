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
    with open(DB_FILE, "w") as f:
        json.dump(data, f)

db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]

st.set_page_config(page_title="OKX Hunter V18.4", layout="wide")
st.title("🛡️ OKX Hunter V18.4: Toparlanma Modu")

# --- ÜST PANEL ---
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.error("Mod: Hacim Odaklı & Sıkı Filtre")

# --- AKTİF POZİSYONLAR ---
if active_trades:
    st.subheader("🚀 Mevcut Pozlar")
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (10 if trade['side'] == 'LONG' else -10)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                duration_mins = (datetime.now() - datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')).total_seconds() / 60

                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([1.5, 2, 1, 1])
                    with col1:
                        st.write(f"**{trade['coin']}** ({trade['side']})")
                        st.caption(f"⏱️ {int(duration_mins)} dk")
                    with col2:
                        st.write(f"G: {trade['entry']} | A: {curr_p}")
                    with col3:
                        st.metric("P/L USD", f"${pnl_usd:.2f}")
                    with col4:
                        if st.button("KAPAT", key=f"cl_{trade['coin']}_{idx}"):
                            st.session_state.balance += pnl_usd
                            st.session_state.trades[idx]['status'] = 'Kapandı'
                            st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                            save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                            st.rerun()

                # AKILLI TAHLİYE: 10 dk limit veya sert zarar
                if duration_mins >= 10 or pnl_usd <= -3.5 or pnl_usd >= 6.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.rerun()
            except: continue

# --- HACİM ODAKLI TARAMA ---
if len(active_trades) < 5:
    st.subheader("🔎 Hacimli Coin Arama")
    symbols = [s for s in exchange.load_markets() if '/USDT' in s][:150]
    for s in symbols:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
        
        try:
            # Hacim Kontrolü Ekledik
            ticker = exchange.fetch_ticker(s)
            hacim_24h = ticker.get('quoteVolume', 0)
            if hacim_24h < 5000000: continue # 5 Milyon dolar altı hacmi olanlara bakma (Ölü coin önleyici)

            bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=50)
            df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
            bb = ta.volatility.BollingerBands(df['c'])
            bb_h, bb_l = bb.bollinger_hband().iloc[-1], bb.bollinger_lband().iloc[-1]
            curr_fiyat = df['c'].iloc[-1]
            
            side = None
            if rsi < 32 and curr_fiyat < bb_l: side = "LONG" # Daha sıkı giriş
            elif rsi > 68 and curr_fiyat > bb_h: side = "SHORT" # Daha sıkı giriş
            
            if side:
                new_t = {
                    "coin": s, "side": side, "entry": curr_fiyat,
                    "tp": round(curr_fiyat * (1.02 if side == "LONG" else 0.98), 6),
                    "sl": round(curr_fiyat * (0.993 if side == "LONG" else 1.007), 6),
                    "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now())
                }
                st.session_state.trades.append(new_t)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()
        except: continue

time.sleep(15)
st.rerun()
