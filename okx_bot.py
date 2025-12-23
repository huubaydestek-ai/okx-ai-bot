import ccxt
import pandas as pd
import ta
import time
import json
import os
from datetime import datetime

# OKX Bağlantısı
exchange = ccxt.okx({'options': {'defaultType': 'swap'}})
DB_FILE = "pa_15m_master_db.json"

def load_db():
    default = {"balance": 981.0, "trades": []}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return default
    return default

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

# --- SENİN STRATEJİN: 15M KIRILIM ---
def get_15m_signal(df):
    if len(df) < 25: return None
    last = df.iloc[-1]
    resistance = df['h'].iloc[-20:-1].max() # Sarı çizgi
    support = df['l'].iloc[-20:-1].min()    # Mavi çizgi
    rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
    
    if last['c'] > resistance and 45 < rsi < 65: return "LONG"
    if last['c'] < support and 35 < rsi < 55: return "SHORT"
    return None

print("🚀 Bot Motoru Başlatıldı... 7/24 Tarama Aktif.")

while True:
    try:
        data = load_db()
        active_trades = [t for t in data['trades'] if t['status'] == 'Açık']
        
        # 1. MEVCUT POZİSYONLARI KONTROL ET (TP/SL)
        for i, trade in enumerate(data['trades']):
            if trade['status'] == 'Açık':
                ticker = exchange.fetch_ticker(trade['coin'])
                curr_p = ticker['last']
                pnl_pct = ((curr_p - trade['entry']) / trade['entry']) * 100 * (8 if trade['side'] == 'LONG' else -8)
                
                if pnl_pct >= 8.5 or pnl_pct <= -5.0:
                    pnl_usd = (trade['margin'] * pnl_pct) / 100
                    data['balance'] += pnl_usd
                    data['trades'][i]['status'] = 'Kapandı'
                    print(f"✅ {trade['coin']} Kapatıldı. P/L: %{pnl_pct:.2f}")
                    save_db(data)

        # 2. YENİ FIRSAT ARA
        if len([t for t in data['trades'] if t['status'] == 'Açık']) < 5:
            markets = exchange.load_markets()
            all_syms = [s for s, m in markets.items() if m.get('swap') and '/USDT' in s]
            
            for s in all_syms[:80]:
                if any(t['coin'] == s and t['status'] == 'Açık' for t in data['trades']): continue
                ticker = exchange.fetch_ticker(s)
                if ticker.get('quoteVolume', 0) < 250000: continue
                
                bars = exchange.fetch_ohlcv(s, timeframe='15m', limit=40)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                side = get_15m_signal(df)
                
                if side:
                    margin = data['balance'] * 0.10
                    new_trade = {"coin": s, "side": side, "entry": df['c'].iloc[-1], "margin": round(margin, 2), "status": "Açık", "time": str(datetime.now())}
                    data['trades'].append(new_trade)
                    save_db(data)
                    print(f"🎯 YENİ İŞLEM: {s} ({side})")
                    break # Her döngüde bir tane aç, sistemi yorma

    except Exception as e:
        print(f"⚠️ Hata: {e}")
    
    time.sleep(10) # 10 saniyede bir döngü
