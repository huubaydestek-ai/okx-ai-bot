import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - Disiplinli Bağlantı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "global_stabilizer_db.json"

def load_db():
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

# --- DİSİPLİNLİ SİNYAL SİSTEMİ ---
def get_pdf_signal(df):
    if len(df) < 10: return None
    last = df.iloc[-1]; prev = df.iloc[-2]
    body = abs(last['c'] - last['o']) + 0.000001
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    # 1.15x iğne oranı: Saçma sapan her şeye dalmasın
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 1.15) and rsi < 45
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 1.15) and rsi > 55
    is_engulfing = (last['c'] > prev['o'] and last['o'] < prev['c'])

    if (is_hammer or is_engulfing): return "LONG"
    if is_shooting_star: return "SHORT"
    return None

st.set_page_config(page_title="OKX Stabilizer V20.6", layout="wide")
st.title("🛡️ The Stabilizer: Disiplinli Scalper")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# ÜST PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Mevcut Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.success("Durum: Disiplinli Tarama")

# --- POZİSYON YÖNETİMİ ---
if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                with st.container(border=True):
                    cl1, cl2, cl3 = st.columns([3, 2, 1])
                    cl1.markdown(f"**{trade['coin']}** ({trade['side']}) | Giriş: `{trade['entry']}`")
                    cl2.metric("P/L %", f"{pnl_pct:.2f}%", f"${pnl_usd:.2f}")
                    if cl3.button("KAPAT", key=f"btn_s_{idx}"):
                        st.session_state.balance += pnl_usd
                        st.session_state.trades[idx]['status'] = 'Kapandı'
                        save_db(st.session_state.balance, st.session_state.trades)
                        st.rerun()

                # TP/SL Kontrolü (%7.5 TP, %5 SL)
                if pnl_pct >= 7.5 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# --- DİSİPLİNLİ TARAMA MOTORU ---
# SADECE 5 İŞLEM SINIRI VARSA ÇALIŞIR
if len(active_trades) < 5:
    with st.status("🔎 Market disiplinli bir şekilde taranıyor...", expanded=True):
        markets = exchange.load_markets()
        all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
        
        for s in all_syms[:60]: # En hacimli 60 parite yeterli
            # Her döngüde sınırı tekrar kontrol et (Sızıntıyı önler)
            current_active = [t for t in st.session_state.trades if t.get('status') == 'Açık']
            if len(current_active) >= 5: 
                break
                
            if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
            
            try:
                # 300k$ Hacim Şartı (Kalite için)
                ticker = exchange.fetch_ticker(s)
                if ticker.get('quoteVolume', 0) < 300000: continue

                bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=15)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_pdf_signal(df)
                
                if side:
                    margin_val = st.session_state.balance * 0.10
                    new_trade = {
                        "coin": s, "side": side, "entry": df['c'].iloc[-1], 
                        "margin": round(margin_val, 2), "status": "Açık", 
                        "time": str(datetime.now())
                    }
                    st.session_state.trades.append(new_trade)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

time.sleep(3)
st.rerun()
