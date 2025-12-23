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
    if len(df) < 3: return None
    last = df.iloc[-1]; prev = df.iloc[-2]
    body = abs(last['c'] - last['o'])
    if body == 0: body = 0.000001 # Sıfıra bölünme hatası önleyici
    
    # PDF Sayfa 6: Bullish Hammer & Engulfing
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 1.8) and (last['h'] - max(last['o'], last['c'])) < (body * 0.6)
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c'] and prev['c'] < prev['o']
    
    # PDF Sayfa 12: Shooting Star
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 1.8) and (min(last['o'], last['c']) - last['l']) < (body * 0.6)

    if (is_hammer or is_engulfing): return "LONG"
    if is_shooting_star: return "SHORT"
    return None

st.set_page_config(page_title="OKX Full Scanner V19.2", layout="wide")
st.title("📡 OKX Full Scanner V19.2: Tüm Market")

# --- ÜST PANEL ---
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa Bakiyesi", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.warning("Mod: Tüm OKX Futures Taranıyor")

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
                
                # Liq Fiyatı
                liq_p = trade['entry'] * (1 - (1 / trade['kaldırac'])) if trade['side'] == "LONG" else trade['entry'] * (1 + (1 / trade['kaldırac']))

                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([1.5, 2, 2, 1])
                    with col1:
                        st.write(f"**{trade['coin']}** ({trade['side']})")
                        st.write(f"💰 ${trade['margin']} | {trade['kaldırac']}x")
                    with col2:
                        st.write(f"G: `{trade['entry']}` | A: `{curr_p}`")
                        st.caption(f"💀 Liq: {liq_p:.5f}")
                    with col3:
                        st.metric("P/L USD", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")
                        st.caption(f"🎯 TP: {trade['tp']} | 🛡️ SL: {trade['sl']}")
                    with col4:
                        if st.button("KAPAT", key=f"man_{idx}"):
                            st.session_state.balance += pnl_usd
                            st.session_state.trades[idx]['status'] = 'Kapandı'
                            st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                            save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                            st.rerun()

                if duration >= 10 or pnl_usd <= -4.0 or pnl_usd >= 7.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.rerun()
            except: continue

st.divider()

# --- TÜM OKX MARKETİNİ TARAMA ---
if len(active_trades) < 5:
    st.subheader("🔎 Fırsat Avcısı (Tüm Market)")
    try:
        # Tüm OKX Swap piyasasını çekiyoruz
        markets = exchange.load_markets()
        all_futures = [symbol for symbol, market in markets.items() if market.get('swap') and '/USDT' in symbol]
        
        # Taramayı hızlandırmak için döngüyü optimize ettik
        for s in all_futures:
            if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
            if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
            
            try:
                # Minimum Hacim Filtresi (1M$ - Market geneli için daha uygun)
                ticker = exchange.fetch_ticker(s)
                if ticker.get('quoteVolume', 0) < 1000000: continue

                bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=30)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                
                pdf_side = get_pdf_signal(df)
                rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
                
                # PDF Formasyonu + RSI Onayı (Daha geniş aralık: 42/58)
                if (pdf_side == "LONG" and rsi < 42) or (pdf_side == "SHORT" and rsi > 58):
                    new_t = {
                        "coin": s, "side": pdf_side, "entry": df['c'].iloc[-1], "kaldırac": 10, "margin": 50.0,
                        "tp": round(df['c'].iloc[-1] * (1.03 if pdf_side == "LONG" else 0.97), 6),
                        "sl": round(df['c'].iloc[-1] * (0.99 if pdf_side == "LONG" else 1.01), 6),
                        "status": "Açık", "time": str(datetime.now())
                    }
                    st.session_state.trades.append(new_t)
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.rerun()
            except: continue
    except:
        st.error("Market verileri alınamadı.")

time.sleep(10)
st.rerun()
