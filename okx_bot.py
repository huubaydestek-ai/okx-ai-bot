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

# --- TERTEMİZ VERİ YÜKLEME ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                # Sadece temel verileri al, karmaşayı temizle
                clean_data = {
                    "balance": data.get("balance", 1027.0),
                    "trades": [t for t in data.get("trades", []) if "coin" in t]
                }
                return clean_data
        except: pass
    return {"balance": 1027.0, "trades": []}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f)

db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]

def get_market_analysis(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['RSI'] = ta.momentum.rsi(df['c'], window=14)
        indicator_bb = ta.volatility.BollingerBands(close=df["c"], window=20, window_dev=2)
        df['bb_h'] = indicator_bb.bollinger_hband()
        df['bb_l'] = indicator_bb.bollinger_lband()
        last = df.iloc[-1]
        return {"price": last['c'], "rsi": round(last['RSI'], 2), "bb_h": last['bb_h'], "bb_l": last['bb_l']}
    except: return None

st.set_page_config(page_title="OKX Hunter V18", layout="wide")
st.title("🏹 OKX Hunter V18: Seri Mod")

# ÜST PANEL
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Mevcut Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.success("Strateji: RSI + Bollinger (10dk Limit)")

# --- AKTİF POZİSYONLAR ---
if active_trades:
    st.subheader("🚀 Aktif Pozisyonlar")
    for trade in st.session_state.trades:
        if trade.get('status') == 'Açık':
            try:
                curr_p = exchange.fetch_ticker(trade['coin'])['last']
                # PNL Hesaplama
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (trade['kaldırac'] if trade['side'] == 'LONG' else -trade['kaldırac'])
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                # Süre Hesaplama
                start_time = datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')
                duration_mins = (datetime.now() - start_time).total_seconds() / 60

                with st.container(border=True):
                    col1, col2, col3 = st.columns([1.5, 2, 1])
                    with col1:
                        st.write(f"### {trade['coin']}")
                        color = "green" if trade['side'] == "LONG" else "red"
                        st.markdown(f"**Yön:** :{color}[{trade['side']}] | **{trade['kaldırac']}x**")
                        st.write(f"**Teminat:** ${trade['margin']}")
                        st.caption(f"⏱️ {int(duration_mins)} dk'dır açık")
                    with col2:
                        st.write(f"📌 Giriş: {trade['entry']} | ⚡ Anlık: {curr_p}")
                        st.write(f"🎯 TP: {trade['tp']} | 🛡️ SL: {trade['sl']}")
                    with col3:
                        st.metric("P/L USD", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")

                # KAPATMA MANTIĞI: TP/SL veya 10 DAKİKA KURALI
                is_target = (trade['side'] == 'LONG' and (curr_p >= trade['tp'] or curr_p <= trade['sl'])) or \
                            (trade['side'] == 'SHORT' and (curr_p <= trade['tp'] or curr_p >= trade['sl']))
                
                # 10 dakika geçtiyse ve kar/zarar varsa hemen kapat (Zaman Stopu)
                if is_target or duration_mins >= 10:
                    st.session_state.balance += pnl_usd
                    idx = st.session_state.trades.index(trade)
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.rerun()
            except: continue

st.divider()

# --- TARAMA SİSTEMİ ---
if len(active_trades) < 5:
    st.subheader("🎯 Alpha Sinyal Gözlemcisi")
    all_syms = [s for s in exchange.load_markets() if '/USDT' in s][:200]
    pending_list = []
    
    for s in all_syms:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        a = get_market_analysis(s)
        if a:
            side = None
            if a['rsi'] < 38 and a['price'] < a['bb_l']: side = "LONG"
            elif a['rsi'] > 62 and a['price'] > a['bb_h']: side = "SHORT"
            
            if (a['rsi'] < 45 or a['rsi'] > 55):
                pending_list.append({"Coin": s, "RSI": a['rsi'], "Fiyat": a['price']})

            if side:
                new_trade = {
                    "coin": s, "side": side, "entry": a['price'],
                    "tp": round(a['price'] * (1.02 if side == "LONG" else 0.98), 5),
                    "sl": round(a['price'] * (0.992 if side == "LONG" else 1.008), 5),
                    "margin": 50.0, "kaldırac": 10, "status": "Açık", "time": str(datetime.now())
                }
                st.session_state.trades.append(new_trade)
                save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                st.rerun()
    
    if pending_list:
        st.write("🔎 **Radardaki Coinler:**")
        st.dataframe(pd.DataFrame(pending_list).sort_values(by="RSI").head(10), use_container_width=True)

# İŞLEM GEÇMİŞİ
st.subheader("📜 İşlem Geçmişi")
if st.session_state.trades:
    df_h = pd.DataFrame([t for t in st.session_state.trades if t.get('status') == 'Kapandı'])
    if not df_h.empty:
        st.dataframe(df_h[['time', 'coin', 'side', 'entry', 'pnl_final']][::-1], use_container_width=True)

time.sleep(15)
st.rerun()
