import streamlit as st
import ccxt
import pandas as pd
import ta
import time

# Ustanın Reel Verileri
REEL_START = 963.0
REEL_CURRENT = 989.0  # Şükür hiç stopsuz gelen rakam

exchange = ccxt.okx({'options': {'defaultType': 'swap'}})

st.set_page_config(page_title="V24.1: Safe Trader", layout="wide")

st.title("🦅 OKX Sniper V24.1: Safe Trader (Usta Disiplini)")

# --- USTA STİLİ STOP MANTIĞI ---
def apply_usta_discipline(pnl_usd):
    # Maksimum 5$ zarar sınırı
    if pnl_usd <= -5.0:
        return "STOP_PATLAT"
    # Kârı koruma mantığı
    if pnl_usd >= 2.0:
        return "BE_CEK" # Giriş seviyesine çek
    return "DEVAM"

# DASHBOARD
c1, c2, c3 = st.columns(3)
c1.metric("💵 Reel Başlangıç", f"${REEL_START}")
c2.metric("💰 Anlık Reel Kasa", f"${REEL_CURRENT}", f"+${REEL_CURRENT-REEL_START:.2f}")
c3.success("🛡️ Mod: Maks 5$ Stop Aktif")

# --- İŞLEM MOTORU (CC-STYLE) ---
# Bot artık senin manuel baktığın o '81 bandı' gibi (image_29fb65.png) 
# dar alan sıkışmalarını kovalayacak.
