import streamlit as st
import ccxt
import pandas as pd
import time

# Usta Reel Kasa: 989.0$
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})

st.set_page_config(page_title="V24.2: Active Hunter", layout="wide")
st.title("🦅 OKX Sniper V24.2: Active Hunter")

# Üst Panel
st.info(f"💰 Reel Kasa: $989.0 | 🛡️ Maks Stop: 5$ | 🏹 Durum: Aktif Tarama")

# --- CANLI TARAMA MOTORU ---
def check_markets():
    try:
        markets = exchange.load_markets()
        symbols = [s for s, m in markets.items() if '/USDT' in s and m.get('swap')]
        
        st.write(f"🔎 {len(symbols)} parite taranıyor...")
        
        for s in symbols[:50]: # Örnekleme için ilk 50
            bars = exchange.fetch_ohlcv(s, timeframe='15m', limit=30)
            df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            
            # CC ve F Tarzı Sıkışma Analizi
            resistance = df['h'].iloc[-20:-1].max()
            current_price = df['c'].iloc[-1]
            
            # Eğer fiyat dirence %0.5 yakınsa log düş
            if current_price > (resistance * 0.995):
                st.write(f"👀 {s} dirence yaklaşıyor: {current_price} (Direnç: {resistance})")
                
    except Exception as e:
        st.error(f"Hata: {e}")

# Taramayı Başlat
if st.button("ŞİMDİ TARA VE AVLAN"):
    with st.spinner("Piyasa taranıyor..."):
        check_markets()
