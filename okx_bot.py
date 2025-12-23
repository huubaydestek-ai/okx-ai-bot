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
DB_FILE = "global_trade_db.json"

def load_db():
    # Gerçek kasanı buraya sabitledim kanka
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

# --- SAĞLAM PDF + RSI SİSTEMİ ---
def get_pdf_signal(df):
    if len(df) < 20: return None
    last = df.iloc[-1]; prev = df.iloc[-2]
    body = abs(last['c'] - last['o']) + 0.000001
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    # "Korkmasın" diye oranları 1.3'e çektim, RSI aralığını 40-60 yaptım
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 1.3) and rsi < 40
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c'] and rsi < 45
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 1.3) and rsi > 60

    if (is_hammer or is_engulfing): return "LONG"
    if is_shooting_star: return "SHORT"
    return None

st.set_page_config(page_title="OKX Global Sniper V20.0", layout="wide")
st.title("🦅 OKX Global Sniper V20.0: REAL CASH")

# --- ÜST PANEL (971$ ÖZEL) ---
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Gerçek Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.info(f"Strateji: 8x Kaldıraç | %10 Margin")

if active_trades:
    st.subheader("🎯 Takipteki İşlemler")
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                # 8x Kaldıraç Hesaplaması
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                with st.container(border=True):
                    col_info, col_pnl, col_btn = st.columns([3, 2, 1])
                    with col_info:
                        st.write(f"### {trade['coin']} ({trade['side']})")
                        st.write(f"**Giriş:** `{trade['entry']}` | **Anlık:** `{curr_p}`")
                        st.caption(f"Kaldıraç: 8x | Margin: ${trade['margin']}")
                    with col_pnl:
                        # %8-10 Kâr Hedefi Görselleştirme
                        st.metric("P/L %", f"{pnl_pct:.2f}%", f"${pnl_usd:.2f} USD")
                        st.progress(min(max((pnl_pct + 10) / 20, 0.0), 1.0)) # %10 Hedefine görsel bar
                    with col_btn:
                        if st.button("KAPAT", key=f"global_cl_{idx}", use_container_width=True):
                            st.session_state.balance += pnl_usd
                            st.session_state.trades[idx]['status'] = 'Kapandı'
                            st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                            save_db(st.session_state.balance, st.session_state.trades)
                            st.rerun()

                # Otomatik Hedef: %9 kârda veya %5 zararda (kasanın güvenliği için) kapat
                if pnl_pct >= 9.0 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# --- GÜVENLİ VE AKICI TARAMA ---
if len(active_trades) < 5:
    with st.spinner("💎 Kaliteli Fırsatlar Süzülüyor..."):
        markets = exchange.load_markets()
        all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
        for s in all_syms:
            if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
            if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
            try:
                # Gerçek işlem için hacmi 500k$ yaptık (Akış sağlar)
                ticker = exchange.fetch_ticker(s)
                if ticker.get('quoteVolume', 0) < 500000: continue 

                bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=20)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_pdf_signal(df)
                
                if side:
                    margin_amount = st.session_state.balance * 0.10 # Kasanın %10'u
                    new_t = {
                        "coin": s, "side": side, "entry": df['c'].iloc[-1], 
                        "margin": round(margin_amount, 2), "status": "Açık", 
                        "time": str(datetime.now())
                    }
                    st.session_state.trades.append(new_t)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

time.sleep(5)
st.rerun()
