import streamlit as st
import pandas as pd
import ta

# Usta'nın Yeni Reel Kasası: ~1000$ (PIERVERSE sonrası)
st.set_page_config(page_title="V24.9: Master's Eye", layout="wide")
st.title("🦅 OKX Sniper V24.9: The Master's Eye")

def get_usta_style_signal(df):
    # Senin son grafikteki (image_7339ab.png) değerlerin simülasyonu
    last = df.iloc[-1]
    prev_resistance = 0.4785 # Mavi Çizgi
    target_resistance = 0.5029 # Sarı Çizgi
    
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    # GİRİŞ: Fiyat mavi çizgi üzerindeyse ve RSI güçlüyse (image_7339ab.png)
    if last['c'] >= prev_resistance and rsi > 60:
        return {
            "SIDE": "LONG",
            "ENTRY": last['c'],
            "TP": target_resistance, # Doğrudan sarı çizgiye kilitlen
            "SL": prev_resistance * 0.985 # Altına sarkarsa 5$ stop kuralı
        }
    return None

st.success(f"💰 Reel Kasa: $994.0+ | 🛡️ Strateji: Mavi Giriş - Sarı Çıkış Aktif")
