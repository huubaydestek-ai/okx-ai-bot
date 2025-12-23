import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Global - %100 Stabil & Detaylı Bağlantı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "autonomous_sniper_db.json"

def load_db():
    default = {"balance": 981.0, "trades": []}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return default
    return default

def save_db(balance, trades):
    with open(DB_FILE, "w") as f:
        json.dump({"balance": balance, "trades": trades}, f)

db_data = load_db()
st.session_state.update(db_data)

# --- OTONOM KIRILIM METODU ---
def get_autonomous_signal(df):
    if len(df) < 20: return None
    last = df.iloc[-1]
    resistance = df['h'].iloc[-15:-1].max() 
    support = df['l'].iloc[-15:-1].min()
    if last['c'] > resistance: return "LONG"
    if last['c'] < support: return "SHORT"
    return None

st.set_page_config(page_title="OKX Visionary Sniper", layout="wide")

# ŞIK SİYAH KART TASARIMI
st.markdown("""
    <style>
    .trade-card {
        background-color: #0e1117;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #30363d;
        margin-bottom: 15px;
    }
    .pnl-pos { color: #00ff88; font-weight: bold; font-size: 1.6em; }
    .pnl-neg { color: #f85149; font-weight: bold; font-size: 1.6em; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 OKX Autonomous Sniper: Canlı Takip")

active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']

# PANEL
c1, c2, c3 = st.columns(3)
c1.metric("💰 Mevcut Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozisyonlar", f"{len(active_trades)} / 5")
c3.success("Durum: İşlemler Takip Ediliyor")

# --- CANLI POZİSYON DETAYLARI ---
if active_trades:
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                # TP ve SL Fiyatlarını Hesapla (8x Kaldıraç Hesaba Dahil)
                # TP %8.5 kâr için fiyat değişimi: %8.5 / 8 = %1.0625
                tp_price = trade['entry'] * (1 + (0.085/8)) if trade['side'] == 'LONG' else trade['entry'] * (1 - (0.085/8))
                sl_price = trade['entry'] * (1 - (0.05/8)) if trade['side'] == 'LONG' else trade['entry'] * (1 + (0.05/8))

                st.markdown(f"""
                <div class="trade-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h3 style="margin:0;">{trade['coin']} | {trade['side']}</h3>
                            <span style="color: #888; font-size: 0.9em;">Tip: İZOLE 8x | Teminat: <b>${trade['margin']}</b></span>
                        </div>
                        <div style="text-align: right;">
                            <span class="{'pnl-pos' if pnl_usd >= 0 else 'pnl-neg'}">
                                ${pnl_usd:.2f} ({pnl_pct:.2f}%)
                            </span>
                        </div>
                    </div>
                    <div style="margin-top: 15px; display: flex; justify-content: space-between; font-size: 0.95em; border-top: 1px solid #30363d; padding-top: 10px;">
                        <span>📌 Giriş: <b>{trade['entry']}</b> | ⚡ Anlık: <b>{curr_p}</b></span>
                        <span>🎯 TP: <b style="color: #00ff88;">{tp_price:.4f}</b> | 🛡️ SL: <b style="color: #ff4b4b;">{sl_price:.4f}</b></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"POZİSYONU KAPAT: {trade['coin']}", key=f"cl_{idx}"):
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()

                # Otomatik TP/SL Kontrolü
                if pnl_pct >= 8.5 or pnl_pct <= -5.0:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
            except: continue

# --- TARAYICI (EĞER YER VARSA) ---
if len(active_trades) < 5:
    with st.spinner("🔎 Boş slotlar için fırsat aranıyor..."):
        try:
            markets = exchange.load_markets()
            all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
            for s in all_syms[:100]:
                if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
                if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
                
                bars = exchange.fetch_ohlcv(s, timeframe='15m', limit=30)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_autonomous_signal(df)
                
                if side:
                    # Kasanın %10'u ile işleme gir (981$ / 10 = ~98$)
                    margin_v = st.session_state.balance * 0.10
                    new_t = {"coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": round(margin_v, 2), "status": "Açık", "time": str(datetime.now())}
                    st.session_state.trades.append(new_t)
                    save_db(st.session_state.balance, st.session_state.trades)
                    st.rerun()
        except: pass

time.sleep(5)
st.rerun()
