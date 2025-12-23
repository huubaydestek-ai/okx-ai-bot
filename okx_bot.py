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

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                return {"balance": data.get("balance", 1048.0), "trades": data.get("trades", [])}
        except: pass
    return {"balance": 1048.0, "trades": []}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f)

db_data = load_db()
if 'balance' not in st.session_state: st.session_state.balance = db_data["balance"]
if 'trades' not in st.session_state: st.session_state.trades = db_data["trades"]

st.set_page_config(page_title="OKX Hunter V18.2", layout="wide")
st.title("🏹 OKX Hunter V18.2: Kapat Tuşu Fix")

# ÜST PANEL
active_trades = [t for t in st.session_state.trades if t.get('status') == 'Açık']
c1, c2, c3 = st.columns(3)
c1.metric("💰 Güncel Kasa", f"${st.session_state.balance:.2f}")
c2.metric("🔄 Aktif Pozlar", f"{len(active_trades)} / 5")
c3.info("Manuel Kapatma: AKTİF (Kırmızı Butonlar)")

# --- AKTİF POZİSYONLAR ---
if active_trades:
    st.subheader("🚀 Aktif Pozisyonlar")
    for idx, trade in enumerate(st.session_state.trades):
        if trade.get('status') == 'Açık':
            try:
                # Ticker bilgisini çek
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                
                # PNL Hesaplama
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (trade['kaldırac'] if trade['side'] == 'LONG' else -trade['kaldırac'])
                pnl_usd = (trade['margin'] * pnl_pct) / 100
                
                # Süre Hesaplama
                start_time = datetime.strptime(trade['time'], '%Y-%m-%d %H:%M:%S.%f')
                duration_mins = (datetime.now() - start_time).total_seconds() / 60

                # Görsel Kart Yapısı
                with st.container(border=True):
                    # Butonun görünmesi için sütun genişliklerini netleştirdik
                    col_info, col_price, col_pnl, col_action = st.columns([2, 2, 1.5, 1])
                    
                    with col_info:
                        color = "green" if trade['side'] == "LONG" else "red"
                        st.markdown(f"### {trade['coin']} (:{color}[{trade['side']}])")
                        st.caption(f"⏱️ {int(duration_mins)} dk | {trade['kaldırac']}x")
                    
                    with col_price:
                        st.write(f"📌 Giriş: `{trade['entry']}`")
                        st.write(f"⚡ Anlık: `{curr_p}`")
                    
                    with col_pnl:
                        st.metric("P/L USD", f"${pnl_usd:.2f}", f"{pnl_pct:.2f}%")
                    
                    with col_action:
                        # Butonun anahtarı (key) her satır için eşsiz olmalı
                        if st.button("KAPAT", key=f"close_{trade['coin']}_{idx}", type="primary", use_container_width=True):
                            st.session_state.balance += pnl_usd
                            st.session_state.trades[idx]['status'] = 'Kapandı'
                            st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                            save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                            st.toast(f"✅ {trade['coin']} kapatıldı!")
                            time.sleep(1)
                            st.rerun()

                # Otomatik Kapanma Kontrolü
                is_target = (trade['side'] == 'LONG' and (curr_p >= trade['tp'] or curr_p <= trade['sl'])) or \
                            (trade['side'] == 'SHORT' and (curr_p <= trade['tp'] or curr_p >= trade['sl']))
                
                if is_target or duration_mins >= 10:
                    st.session_state.balance += pnl_usd
                    st.session_state.trades[idx]['status'] = 'Kapandı'
                    st.session_state.trades[idx]['pnl_final'] = round(pnl_usd, 2)
                    save_db({"balance": st.session_state.balance, "trades": st.session_state.trades})
                    st.rerun()
            except Exception as e:
                continue

st.divider()

# --- SİNYAL TARAYICI (MAX 5 POZİSYON) ---
def get_market_analysis(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=50)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
        bb = ta.volatility.BollingerBands(df['c'])
        return {"price": df['c'].iloc[-1], "rsi": rsi, "bb_h": bb.bollinger_hband().iloc[-1], "bb_l": bb.bollinger_lband().iloc[-1]}
    except: return None

if len(active_trades) < 5:
    st.subheader("🎯 Sinyal Havuzu")
    symbols = [s for s in exchange.load_markets() if '/USDT' in s][:150]
    for s in symbols:
        if any(t['coin'] == s and t['status'] == 'Açık' for t in st.session_state.trades): continue
        if len([t for t in st.session_state.trades if t.get('status') == 'Açık']) >= 5: break
