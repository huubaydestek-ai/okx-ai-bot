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
    default = {"balance": 1048.0, "trades": []}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: return default
    return default

def save_db(balance, trades):
    with open(DB_FILE, "w") as f:
        json.dump({"balance": balance, "trades": trades}, f)

# Başlangıç Ayarları
db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]

# --- PDF ZEKA SİSTEMİ (TURBO) ---
def get_pdf_signal(df):
    if len(df) < 5: return None
    last = df.iloc[-1]; prev = df.iloc[-2]
    body = abs(last['c'] - last['o']) + 0.000001
    # PDF Sayfa 6 ve 12'deki formasyonlar
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 1.5)
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c']
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 1.5)
    if (is_hammer or is_engulfing): return "LONG"
    if is_shooting_star: return "SHORT"
    return None

st.set_page_config(page_title="OKX Turbo Hunter V19.6", layout="wide")
st.title("⚡ OKX Turbo Hunter V19.6")

# --- ÜST PANEL ---
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa Bakiyesi", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.info("Mod: Turbo Tarama & Anlık Kapanış")

# --- AKTİF POZİSYONLAR ---
if active_trades:
    st.subheader("🚀 Canlı Pozisyonlar")
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (10 if trade['side'] == 'LONG' else -10)
                pnl_usd = (50.0 * pnl_pct) / 100
                duration = (datetime.now() - datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')).total_seconds() / 60
                
                with st.container(border=True):
                    col_info, col_price, col_pnl, col_btn = st.columns([1.5, 2, 1.5, 1])
                    with col_info:
                        st.write(f"**{trade['coin']}** ({trade['side']})")
                        st.caption(f"⏱️ {int(duration)} dk")
                    with col_price:
                        st.write(f"G: `{trade['entry']}` | A: `{curr_p}`")
                    with col_pnl:
                        st.metric("P/L", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")
                    with col_btn:
                        # ANINDA KAPATMA VE YENİLEME
                        if st.button("KAPAT", key=f"fast_close_{idx}_{trade['coin']}", use_container_width=True):
                            st.session_state.balance += pnl_usd
                            st.session_state.trades[idx]['status'] = 'Kapandı'
                            st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                            save_db(st.session_state.balance, st.session_state.trades)
                            st.rerun() # BEKLEMEDEN DİREKT YENİDEN BAŞLAT

                # Otomatik Kapanış Limitleri
                if duration >= 10 or pnl_usd <= -4.0 or pnl_usd >= 7.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# --- ARALIKSIZ TARAMA ---
if len(active_trades) < 5:
    st.subheader("🔎 Yeni Fırsat Radarı")
    try:
        markets = exchange.load_markets()
        all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
        for s in all_syms:
            if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
            if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
            
            try:
                # Sinyal akışını hızlandırmak için hacim filtresini 300k$'a çektim
                ticker = exchange.fetch_ticker(s)
                if ticker.get('quoteVolume', 0) < 300000: continue

                bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=10)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_pdf_signal(df)
                
                if side:
                    new_t = {
                        "coin": s, "side": side, "entry": df['c'].iloc[-1], "status": "Açık",
                        "time": str(datetime.now()), "margin": 50.0, "kaldırac": 10
                    }
                    st.session_state.trades.append(new_t)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue
    except: pass

# --- GEÇMİŞ TABLOSU ---
st.divider()
history = [t for t in st.session_state.trades if t.get('status') == 'Kapandı']
if history:
    with st.expander("📜 İşlem Geçmişi (Son Başarılar)", expanded=False):
        st.table(pd.DataFrame(history)[['time', 'coin', 'side', 'pnl_final']].sort_index(ascending=False).head(10))

# TURBO REFRESH
time.sleep(3)
st.rerun()
