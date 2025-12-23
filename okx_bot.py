import streamlit as st
import ccxt
import pandas as pd
import ta
import time as t_module
import json
import os
from datetime import datetime

# OKX Bağlantısı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "trade_db.json"

def load_db():
    default = {"balance": 1048.0, "trades": []}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else default
        except: pass
    return default

def save_db(balance, trades):
    # Sadece JSON'a uygun verileri kaydederek TypeError'ı engelliyoruz
    with open(DB_FILE, "w") as f:
        json.dump({"balance": balance, "trades": trades}, f)

db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]

# --- PDF FORMASYON SİSTEMİ ---
def get_pdf_signal(df):
    if len(df) < 5: return None
    last = df.iloc[-1]; prev = df.iloc[-2]
    body = abs(last['c'] - last['o']) + 0.000001
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 1.5)
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c']
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 1.5)
    if (is_hammer or is_engulfing): return "LONG"
    if is_shooting_star: return "SHORT"
    return None

st.set_page_config(page_title="OKX Ultimate Hunter V19.4", layout="wide")
st.title("🏹 OKX Ultimate Hunter V19.4")

# --- ÜST PANEL ---
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa Bakiyesi", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.success("Mod: Full Detay + PDF Zekası")

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
                liq_p = trade['entry'] * (1 - (1 / trade['kaldırac'])) if trade['side'] == "LONG" else trade['entry'] * (1 + (1 / trade['kaldırac']))

                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([1.5, 2, 2, 1])
                    with col1:
                        st.write(f"### {trade['coin']}")
                        st.markdown(f"**{trade['side']} | {trade['kaldırac']}x**")
                        st.caption(f"⏱️ {int(duration)} dk")
                    with col2:
                        st.write(f"📌 G: `{trade['entry']}`")
                        st.write(f"⚡ A: `{curr_p}`")
                        st.write(f"💀 **Liq:** `{liq_p:.5f}`")
                    with col3:
                        st.metric("P/L", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")
                        st.write(f"🎯 TP: `{trade['tp']}` | 🛡️ SL: `{trade['sl']}`")
                    with col4:
                        if st.button("KAPAT", key=f"btn_{idx}", use_container_width=True):
                            st.session_state.balance += pnl_usd
                            st.session_state.trades[idx]['status'] = 'Kapandı'
                            st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                            save_db(st.session_state.balance, st.session_state.trades)
                            st.rerun()

                if duration >= 10 or pnl_usd <= -4.0 or pnl_usd >= 7.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# --- TÜM MARKET TARAMA (HACİM ESNEK) ---
if len(active_trades) < 5:
    st.subheader("🔎 Fırsat Avcısı")
    markets = exchange.load_markets()
    all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
    
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
        
        try:
            ticker = exchange.fetch_ticker(s)
            if ticker.get('quoteVolume', 0) < 1000000: continue # 1M$ hacim (Yeterli akış)

            bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=20)
            df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            side = get_pdf_signal(df)
            
            if side:
                new_t = {
                    "coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": 50.0, "kaldırac": 10,
                    "tp": round(df['c'].iloc[-1] * (1.03 if side == "LONG" else 0.97), 6),
                    "sl": round(df['c'].iloc[-1] * (0.992 if side == "LONG" else 1.008), 6),
                    "status": "Açık", "time": str(datetime.now())
                }
                st.session_state.trades.append(new_t)
                save_db(st.session_state.balance, st.session_state.trades)
                st.rerun()
        except: continue

# --- İŞLEM GEÇMİŞİ ---
st.divider()
st.subheader("📜 İşlem Geçmişi")
df_history = pd.DataFrame([t for t in st.session_state.trades if t.get('status') == 'Kapandı'])
if not df_history.empty:
    st.dataframe(df_history[['time', 'coin', 'side', 'pnl_final']].sort_values(by='time', ascending=False), use_container_width=True)

t_module.sleep(10)
st.rerun()
