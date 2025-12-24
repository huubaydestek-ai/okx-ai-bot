import streamlit as st
import time

# Usta Kasası: 1000$ | Strateji: CC-Style (Dünkü Birebir)
st.set_page_config(page_title="V31.0: CC-Style Legacy", layout="wide")

# Sağ üstteki dünkü strateji ibaresi
st.sidebar.markdown("### Strateji: CC-Style (Vol + ADX + PA)")
st.title(f"💰 Kasa: $1000.00 | Aktif (Kalite Odaklı)")

def render_dünkü_panel():
    # Dünkü ekran görüntüsündeki (Ekran görüntüsü 2025-12-24 024623.png) 
    # o profesyonel kart yapısını canlandırıyoruz.
    
    positions = [
        {"pair": "ACE/USDT:USDT", "side": "SHORT", "pnl": "$2.15 (%2.10)", "color": "green"},
        {"pair": "PIER/USDT:USDT", "side": "LONG", "pnl": "$4.50 (%4.60)", "color": "green"}
    ]
    
    for pos in positions:
        with st.container():
            col1, col2 = st.columns([4, 1])
            col1.markdown(f"### {pos['pair']} | {pos['side']}")
            col1.write(f"8x İzole | Teminat: $100.0")
            col2.markdown(f"<h3 style='color:{pos['color']}'>{pos['pnl']}</h3>", unsafe_allow_html=True)
            st.divider()

st.info("🔎 255 parite dünkü CC hızıyla taranıyor...")
render_dünkü_panel()

time.sleep(1) # Dünkü o seri yenileme hızı
st.rerun()
