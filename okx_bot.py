import streamlit as st
import ccxt
import pandas as pd
import ta
import time as t_module # Hata veren time modülü düzeltildi
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

def save_db(data):
    # JSON hatası veren session_state objesi yerine temiz sözlük kaydediyoruz
    clean_data = {"balance": data.get("balance", 1048.0), "trades": data.get("trades", [])}
    with open(DB_FILE, "w") as f:
        json.dump(clean_data, f)

db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]

# --- PDF FORMASYON ZEKA SİSTEMİ (ESNETİLMİŞ) ---
def get_pdf_signal(df):
    last = df.iloc[-1]; prev = df.iloc[-2]
    body = abs(last['c'] - last['o']) + 0.000001
    # Formasyonları daha kolay yakalaması için oranları esnettim
    is_hammer = (min(last['o'], last['c']) - last['l']) > (body * 1.5)
    is_engulfing = last['c'] > prev['o'] and last['o'] < prev['c']
    is_shooting_star = (last['h'] - max(last['o'], last['c'])) > (body * 1.5)

    if (is_hammer or is_engulfing): return "LONG"
    if is_shooting_star: return "SHORT"
    return None

st.set_page_config(page_title="OKX Hyper Hunter", layout="wide")
st.title("🚀 OKX Hyper Hunter V19.3")

# --- ÜST PANEL ---
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.info("Mod: Hiper Tarama (Filtresiz)")

# --- AKTİF POZİSYONLAR ---
if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                curr_p = exchange.fetch_ticker(trade['coin'])['last']
                pnl_usd = (trade['margin'] * ((curr_p - trade['entry']) / trade['entry']) * 100 * (10 if trade['side'] == 'LONG' else -10)) / 100
                duration = (datetime.now() - datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')).total_seconds() / 60
                
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([1.5, 2, 1.5, 1])
                    col1.write(f"**{trade['coin']}** ({trade['side']})")
                    col2.write(f"G: {trade['entry']} | A: {curr_p}")
                    col3.metric("P/L", f"${pnl_usd:.2f}")
                    if col4.button("KAPAT", key=f"h_cl_{idx}"):
                        st.session_state.balance += pnl_usd
                        st.session_state.trades[idx]['status'] = 'Kapandı'
                        st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                        save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                        st.rerun()

                if duration >= 10 or pnl_usd <= -4.0 or pnl_usd >= 6.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.rerun()
            except: continue

st.divider()

# --- HİPER TARAMA (HIZLI VE TÜM MARKET) ---
if len(active_trades) < 5:
    st.subheader("⚡ Fırsatlar Taranıyor...")
    markets = exchange.load_markets()
    all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
    
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
        
        try:
            bars = exchange.fetch_ohlcv(s, timeframe='5m', limit=20)
            df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            side = get_pdf_signal(df)
            
            # Sinyal gelmesi için RSI filtresini kaldırdım, sadece PDF formasyonuna bakıyor
            if side:
                new_t = {
                    "coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": 50.0, "kaldırac": 10,
                    "tp": round(df['c'].iloc[-1] * (1.025 if side == "LONG" else 0.975), 6),
                    "sl": round(df['c'].iloc[-1] * (0.99 if side == "LONG" else 1.01), 6),
                    "status": "Açık", "time": str(datetime.now())
                }
                st.session_state.trades.append(new_t)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()
        except: continue

t_module.sleep(5) # Daha hızlı yenileme
st.rerun()
