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
DB_FILE = "trade_db_v2.json"

def load_db():
    default = {"balance": 1062.06, "trades": []}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return default
    return default

def save_db(balance, trades):
    with open(DB_FILE, "w") as f: json.dump({"balance": balance, "trades": trades}, f)

db_data = load_db()
st.session_state.update(db_data)

# --- PROFESYONEL 5M PDF SİSTEMİ ---
def get_pdf_signal(df):
    if len(df) < 14: return None
    last = df.iloc[-1]; prev = df.iloc[-2]
    body = abs(last['c'] - last['o']) + 0.000001
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    vol_avg = df['v'].mean()
    
    # PDF Sayfa 6/12 Formasyonları + RSI Şartı
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 1.5) and rsi < 35
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c'] and rsi < 40
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 1.5) and rsi > 65

    # Kalite Filtresi: Ortalama üstü hacim patlaması
    high_quality = last['v'] > (vol_avg * 1.1)

    if (is_hammer or is_engulfing) and high_quality: return "LONG"
    if is_shooting_star and high_quality: return "SHORT"
    return None

st.set_page_config(page_title="OKX Professional V19.9", layout="wide")
st.title("🎯 OKX Professional V19.9: 5m Sniper")

# Üst Panel
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.info("Zaman Dilimi: 5 Dakikalık (5m)")

# Pozisyon Takibi
if active_trades:
    st.subheader("🚀 Canlı İşlemler")
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (10 if trade['side'] == 'LONG' else -10)
                pnl_usd = (50.0 * pnl_pct) / 100
                duration = (datetime.now() - datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')).total_seconds() / 60
                
                with st.container(border=True):
                    col_i, col_p, col_b = st.columns([3, 2, 1])
                    with col_i:
                        st.markdown(f"**{trade['coin']}** ({trade['side']}) | G: `{trade['entry']}` | A: `{curr_p}`")
                        st.caption(f"⏱️ {int(duration)} dk | 💀 Liq: {trade['entry']*0.9:.4f}")
                    with col_p:
                        st.metric("P/L", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")
                    with col_b:
                        if st.button("KAPAT", key=f"cl_{idx}", use_container_width=True):
                            st.session_state.balance += pnl_usd
                            st.session_state.trades[idx]['status'] = 'Kapandı'
                            st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                            save_db(st.session_state.balance, st.session_state.trades)
                            st.rerun()

                # Zaman veya Zarar Durdurma
                if duration >= 15 or pnl_usd <= -4.5 or pnl_usd >= 7.5:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# 5m Pazar Taraması
if len(active_trades) < 5:
    with st.status("🔎 5m Mumlar Taranıyor (Kaliteli Fırsat)...", expanded=True):
        markets = exchange.load_markets()
        all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
        for s in all_syms:
            if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
            if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
            try:
                # 1M$ Hacim Şartı
                if exchange.fetch_ticker(s).get('quoteVolume', 0) < 1000000: continue 
                bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=20)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_pdf_signal(df)
                if side:
                    new_t = {"coin": s, "side": side, "entry": df['c'].iloc[-1], "status": "Açık", "time": str(datetime.now())}
                    st.session_state.trades.append(new_t)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

st.divider()
history = [t for t in st.session_state.trades if t.get('status') == 'Kapandı']
if history:
    st.subheader("📜 Son Kapanan İşlemler")
    st.table(pd.DataFrame(history).sort_index(ascending=False).head(5)[['time', 'coin', 'side', 'pnl_final']])

time.sleep(3)
st.rerun()
