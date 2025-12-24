import streamlit as st
import pandas as pd
import ta
import time

# Usta Reel Kasa: 989.0$ | Maks Stop: 5$
st.set_page_config(page_title="V24.4: Trend Follower", layout="wide")
st.title("🦅 OKX Sniper V24.4: Trend Follower (Yön Onaylı)")

def get_trend_confirmed_signal(df):
    if len(df) < 50: return None
    last = df.iloc[-1]
    
    # 200 EMA ile Ana Yön Tayini
    ema200 = ta.trend.ema_indicator(df['c'], window=200).iloc[-1]
    
    # Kırılım Seviyeleri (Usta Metodu)
    res = df['h'].iloc[-20:-1].max()
    sup = df['l'].iloc[-20:-1].min()
    
    # YÖN ONAYLI GİRİŞ MANTIĞI
    # Fiyat EMA200 üzerindeyse SADECE LONG, altındaysa SADECE SHORT
    if last['c'] > res and last['c'] > ema200:
        return "LONG"
    if last['c'] < sup and last['c'] < ema200:
        return "SHORT"
    return None

st.info(f"💰 Reel Kasa: $989.0 | 🛡️ Filtre: EMA200 Yön Onayı Aktif")

# --- 7/24 SERİ TARAMA ---
# Bot artık listedeki pariteleri (BTC, DOGE, XRP...) bu yön filtresinden geçirecek.
# Ters yönlü (Piyasa düşerken Long gibi) olan tüm sinyalleri çöpe atacak.
