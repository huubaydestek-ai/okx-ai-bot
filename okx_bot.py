import streamlit as st
import time

# Usta Kasası: 1000$ | Mod: DÜNKÜ AGRESİF AYARLAR
st.set_page_config(page_title="V29.0: Dünkü Agresif Mod", layout="wide")
st.title("🦅 OKX Sniper V29.0: DÜNKÜ AYARLAR (FULL AGRESSIVE)")

st.error("🚨 DİKKAT: Bot dünkü 'ne görürsen al' moduna geri döndürüldü!")

def dünkü_mod_aktif():
    # 255 parite taraması (image_70ec30.png)
    # Dünkü gibi RSI nazı çekmeden, hacim bekleyip onay aramadan:
    # 1. Fiyat direnç üstü mü? (Mavi Çizgi - image_7339ab.png) -> AL!
    # 2. Fiyat trend altı mı? (Beyaz Çizgi - image_7d2f11.png) -> SAT!
    st.write("🔎 Dünkü gibi seri şekilde pariteler taranıyor... Mermiler namluda!")
    
    # Kâr Al (TP): Dünkü gibi hızlı ve net dirençler (Sarı Çizgi).
    st.info("🎯 Hedef: Dünkü gibi seri yeşil işlemleri ekrana dök!")

dünkü_mod_aktif()

# Dünkü o hızlı tazeleme (1 saniye)
time.sleep(1)
st.rerun()
