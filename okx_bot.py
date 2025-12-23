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
DB_FILE = "global_isolated_db.json"

def load_db():
    # Gerçek kasan 971$ olarak güncellendi
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

# --- İZOLE PDF SİSTEMİ ---
def get_pdf_signal(df):
    if len(df) < 20: return None
    last = df.iloc[-1]; prev = df.iloc[-2]
    body = abs(last['c'] - last['o']) + 0.000001
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    # İzole modda sağlam formasyonlar (1.35x İğne Oranı)
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 1.35) and rsi < 42
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c'] and rsi < 45
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 1.35) and rsi > 58

    if (is_hammer or is_engulfing): return "LONG"
    if is_shooting_star: return "SHORT"
    return None

st.set_page_config(page_title="OKX Isolated Sniper V20.1", layout="wide")
st.title("🛡️ OKX Global Sniper: İZOLE MOD")

# --- ÜST PANEL ---
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa (Isolated)", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.error("MARJİN TİPİ: İZOLE (8x)")

if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                # 8x İzole P/L Hesaplama
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                # İzole Likidasyon Tahmini (%12.5 hareket terste kalırsa)
                liq_p = trade['entry'] * 0.875 if trade['side'] == "LONG" else trade['entry'] * 1.125

                with st.container(border=True):
                    col_info, col_pnl, col_btn = st.columns([2.5, 2, 1.5])
                    with col_info:
                        st.markdown(f"### {trade['coin']} ({trade['side']})")
                        st.write(f"📌 **Giriş:** `{trade['entry']}` | ⚡ **Anlık:** `{curr_p}`")
                        st.caption(f"Margin: ${trade['margin']} (İzole) | 💀 Liq: {liq_p:.5f}")
                    with col_pnl:
                        st.metric("P/L %", f"{pnl_pct:.2f}%", f"${pnl_usd:.2f}")
                        st.write(f"🎯 Hedef: %9.00 | 🛑 Stop: -%5.00")
                    with col_btn:
                        if st.button("POZİSYONU KAPAT", key=f"iso_cl_{idx}", use_container_width=True):
                            st.session_state.balance += pnl_usd
                            st.session_state.trades[idx]['status'] = 'Kapandı'
                            st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                            save_db(st.session_state.balance, st.session_state.trades)
                            st.rerun()

                # Otomatik Hedef ve Stop (İzole Güvenliği)
                if pnl_pct >= 9.0 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# --- TARAMA ---
if len(active_trades) < 5:
    with st.spinner("💎 İzole fırsatlar taranıyor..."):
        markets = exchange.load_markets()
        all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
        for s in all_syms:
            if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
            if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
            try:
                # Gerçek pazar hacmi kontrolü (Minimum 500k$)
                if exchange.fetch_ticker(s).get('quoteVolume', 0) < 500000: continue
                bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=15)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_pdf_signal(df)
                if side:
                    margin_amount = st.session_state.balance * 0.10 # Kasanın %10'u izole edilir
                    new_t = {"coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": round(margin_amount, 2), "status": "Açık", "time": str(datetime.now())}
                    st.session_state.trades.append(new_t)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

time.sleep(4)
st.rerun()
