import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - Profesyonel Bağlantı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "legend_return_db.json"

def load_db():
    # Gerçek kasanı 971$ olarak buraya çiviledim kanka
    default = {"balance": 971.0, "trades": []}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return default
    return default

def save_db(balance, trades):
    with open(DB_FILE, "w") as f: json.dump({"balance": balance, "trades": trades}, f)

db_data = load_db()
st.session_state.update(db_data)

# --- EFSANE PDF SİSTEMİ (1.5x İĞNE) ---
def get_pdf_signal(df):
    if len(df) < 15: return None
    last = df.iloc[-1]; prev = df.iloc[-2]
    body = abs(last['c'] - last['o']) + 0.000001
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    # 1062$ yapan o meşhur oranlar
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 1.5) and rsi < 35
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 1.5) and rsi > 65
    is_engulfing = (last['c'] > prev['o'] and last['o'] < prev['c'] and rsi < 40)

    if (is_hammer or is_engulfing): return "LONG"
    if is_shooting_star: return "SHORT"
    return None

st.set_page_config(page_title="OKX Legend Return V20.7", layout="wide")
st.title("🔥 OKX Legend Return: 971$ Sniper")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# TEMİZ ÜST PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Mevcut Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.success("Mod: Kaliteli Sniper & İzole 8x")

# --- POZİSYON TAKİBİ ---
if active_trades:
    st.subheader("🚀 Canlı Pozisyonlar")
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                with st.container(border=True):
                    col_info, col_pnl, col_btn = st.columns([3, 2, 1])
                    with col_info:
                        st.markdown(f"**{trade['coin']}** ({trade['side']}) | G: `{trade['entry']}`")
                        st.caption(f"İzole Margin: ${trade['margin']} | 8x")
                    with col_pnl:
                        st.metric("P/L", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")
                    with col_btn:
                        if st.button("KAPAT", key=f"leg_{idx}", use_container_width=True):
                            st.session_state.balance += pnl_usd
                            st.session_state.trades[idx]['status'] = 'Kapandı'
                            save_db(st.session_state.balance, st.session_state.trades)
                            st.rerun()

                # Otomatik TP/SL: %7.5 Kâr veya %5 Zarar
                if pnl_pct >= 7.5 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# --- PROFESYONEL TARAMA MOTORU ---
if len(active_trades) < 5:
    with st.spinner("🔎 Efsanevi fırsatlar taranıyor..."):
        markets = exchange.load_markets()
        all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
        
        for s in all_syms:
            if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
            if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
            
            try:
                # Tekrar 1M$ Hacim Şartı
                ticker = exchange.fetch_ticker(s)
                if ticker.get('quoteVolume', 0) < 1000000: continue

                bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=20)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_pdf_signal(df)
                
                if side:
                    margin_val = st.session_state.balance * 0.10
                    new_t = {"coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": round(margin_val, 2), "status": "Açık", "time": str(datetime.now())}
                    st.session_state.trades.append(new_t)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

time.sleep(4)
st.rerun()
