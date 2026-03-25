import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="DreamBot 💎 Providencia 100x", layout="wide")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { color: #00ff88 !important; font-family: 'Orbitron'; }
    .stProgress > div > div { background: linear-gradient(90deg, #00ff88, #00ccff); }
</style>
""", unsafe_allow_html=True)

BIBLE_QUOTES = [
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Todo lo puedo en Cristo que me fortalece. (Filipenses 4:13)",
    "Si puedes creer, al que cree todo le es posible. (Marcos 9:23)"
]

# --- PARÁMETROS AGRESIVOS ---
TP_MOVIMIENTO = 0.45   
APALANCAMIENTO = 45    
MAX_POSICIONES = 6     
REENTRADA_PCT = -1.5   

# --- FUNCIONES DE SEGURIDAD (Blindadas) ---
def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

def round_qty(symbol, qty):
    if 'BTC' in symbol: return round(qty, 3)
    if 'ETH' in symbol: return round(qty, 2)
    return round(qty, 1) if any(x in symbol for x in ['SOL', 'DOT', 'ADA', 'XRP']) else round(qty, 0)

def calc_indicators(df):
    c = df['c'].astype(float)
    # RSI con seguro total
    diff = c.diff()
    gain = diff.clip(lower=0).ewm(span=14, adjust=False).mean()
    loss = (-diff).clip(lower=0).ewm(span=14, adjust=False).mean()
    rs = gain / (loss + 0.0000000001) 
    df['rsi'] = 100 - (100 / (1 + rs + 0.0000000001))
    # Bollinger
    ma = c.rolling(20).mean()
    std = c.rolling(20).std()
    df['bb_low'] = ma - (1.6 * std)
    return df

# --- AGENTE PRINCIPAL ---
st.title("💎 AGENTE DE PROVIDENCIA: MULTIPLICACIÓN 24/7")
st.write(f"_{random.choice(BIBLE_QUOTES)}_")

with st.sidebar:
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("🚀 ACTIVAR COSECHA 24/7", value=True)

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        # Dashboard Inicial
        c1, c2 = st.columns(2)
        ph_cap = c1.empty()
        ph_meta = c2.empty()
        ph_prog = st.empty()
        
        st.subheader("📊 Tus Semillas (Posiciones Activas)")
        ph_pos = st.empty()
        
        st.subheader("📡 Radar de Oportunidades")
        ph_radar = st.empty()
        
        log = st.expander("📝 Bitácora de Bendiciones", expanded=True)

        while True:
            # 1. ACTUALIZAR ESTADO
            balance = exchange.fetch_total_balance()
            equity = safe_float(balance.get('USD', 5.61))
            avail = safe_float(balance.get('info', {}).get('marginAvailable', equity * 0.4))

            # UI Update con seguro de división por cero
            ph_cap.metric("Capital Actual", f"${equity:.4f} USD")
            ph_meta.metric("Meta", "$100.00 USD")
            meta_val = 100.0
            prog_val = min(100.0, (equity / (meta_val if meta_val > 0 else 1.0)) * 100)
            ph_prog.progress(int(max(0, prog_val)), text=f"Progreso: {prog_val:.2f}%")

            # 2. GESTIÓN DE POSICIONES
            pos_info = []
            n_pos = 0
            posiciones = exchange.fetch_positions()
            for p in posiciones:
                qty = safe_float(p.get('contracts', 0))
                if qty > 0:
                    n_pos += 1
                    sym, side = p['symbol'], p['side'].upper()
                    entry, mark, pnl = safe_float(p['entryPrice']), safe_float(p['markPrice']), safe_float(p['unrealizedPnl'])
                    
                    # Move % con seguro
                    move = ((mark - entry) / (entry if entry > 0 else 1.0) * 100) if side == 'LONG' else ((entry - mark) / (entry if entry > 0 else 1.0) * 100)
                    
                    if move >= TP_MOVIMIENTO:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        log.success(f"💰 Cosechados ${pnl:.2f} en {sym}")
                    elif move <= REENTRADA_PCT and avail > 1.2:
                        re_qty = round_qty(sym, (avail * 0.2 * APALANCAMIENTO) / (mark if mark > 0 else 1.0))
                        if re_qty > 0:
                            exchange.create_market_order(sym, 'buy' if side == 'LONG' else 'sell', re_qty)
                            log.warning(f"🛡️ Reforzando {sym}")

                    pos_info.append({"ACTIVO": sym, "ROI%": f"{move:+.2f}%", "PNL": f"${pnl:+.4f}"})

            ph_pos.table(pd.DataFrame(pos_info) if pos_info else pd.DataFrame(columns=["Cazando entradas..."]))

            # 3. RADAR DE DISPARO
            radar_data = []
            markets = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'DOT/USD:USD']
            for sym in markets:
                try:
                    bars = exchange.fetch_ohlcv(sym, timeframe='5m', limit=25)
                    df = calc_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                    last = df.iloc[-1]
                    
                    # Seguro para distancia BB
                    bb_l = safe_float(last['bb_low'])
                    dist = ((last['c'] - bb_l) / (bb_l if bb_l > 0 else 1.0)) * 100
                    
                    status = "🔥 ENTRANDO" if last['c'] <= bb_l and last['rsi'] < 35 else "⏳ CAZANDO"
                    radar_data.append({"ACTIVO": sym, "PRECIO": f"${last['c']:.2f}", "FALTA%": f"{max(0, dist):.2f}%", "ESTADO": status})

                    if status == "🔥 ENTRANDO" and n_pos < MAX_POSICIONES and avail > 1.5:
                        qty_buy = round_qty(sym, (avail * 0.25 * APALANCAMIENTO) / (last['c'] if last['c'] > 0 else 1.0))
                        if qty_buy > 0:
                            exchange.create_market_order(sym, 'buy', qty_buy)
                            log.info(f"🚀 Entrada en {sym}")
                            n_pos += 1
                except: continue

            ph_radar.table(pd.DataFrame(radar_data))
            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Sincronizando... {e}")
        time.sleep(10)
        st.rerun()