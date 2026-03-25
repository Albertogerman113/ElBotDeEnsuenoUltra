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
    "Encomienda al SEÑOR tu camino, confía en él, y él hará. (Salmo 37:5)",
    "Si puedes creer, al que cree todo le es posible. (Marcos 9:23)"
]

# --- PARÁMETROS AGRESIVOS ---
TP_MOVIMIENTO = 0.45   # Cosecha al 0.45% (ROI ~20% con apalancamiento)
APALANCAMIENTO = 45    
MAX_POSICIONES = 5     
REENTRADA_PCT = -1.5   # Promediar si cae

# --- FUNCIONES DE SEGURIDAD ---
def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

def round_qty(symbol, qty):
    if 'BTC' in symbol: return round(qty, 3)
    if 'ETH' in symbol: return round(qty, 2)
    if any(x in symbol for x in ['SOL', 'DOT', 'ADA']): return round(qty, 1)
    return round(qty, 0)

def calc_indicators(df):
    c = df['c'].astype(float)
    # RSI Blindado contra división por cero
    diff = c.diff()
    gain = diff.clip(lower=0).ewm(span=14, adjust=False).mean()
    loss = (-diff).clip(lower=0).ewm(span=14, adjust=False).mean()
    # Evitamos la división por cero sumando un valor ínfimo (1e-10)
    rs = gain / (loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    # Bandas de Bollinger
    ma = c.rolling(20).mean()
    std = c.rolling(20).std()
    df['bb_low'] = ma - (1.7 * std)
    return df

# --- AGENTE PRINCIPAL ---
st.title("💎 AGENTE DE PROVIDENCIA: MULTIPLICACIÓN 24/7")
st.write(f"_{random.choice(BIBLE_QUOTES)}_")

with st.sidebar:
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("🚀 ACTIVAR COSECHA NOCTURNA", value=True)

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        # Dashboard
        balance = exchange.fetch_total_balance()
        equity = safe_float(balance.get('USD', 6.66))
        avail = safe_float(balance.get('info', {}).get('marginAvailable', equity * 0.4))

        c1, c2 = st.columns(2)
        c1.metric("Capital Actual", f"${equity:.4f} USD")
        c2.metric("Meta", "$100.00 USD")
        
        st.subheader("📊 Posiciones Activas")
        ph_pos = st.empty()
        
        log = st.expander("📝 Bitácora de Bendiciones", expanded=True)

        while True:
            # 1. ACTUALIZAR DATOS
            balance = exchange.fetch_total_balance()
            equity = safe_float(balance.get('USD', equity))
            avail = safe_float(balance.get('info', {}).get('marginAvailable', avail))

            # 2. GESTIÓN DE POSICIONES (SOLO COSECHA O PROMEDIO)
            pos_info = []
            n_pos = 0
            posiciones = exchange.fetch_positions()
            for p in posiciones:
                qty = safe_float(p.get('contracts', 0))
                if qty > 0:
                    n_pos += 1
                    sym, side = p['symbol'], p['side'].upper()
                    entry, mark, pnl = safe_float(p['entryPrice']), safe_float(p['markPrice']), safe_float(p['unrealizedPnl'])
                    move = ((mark - entry) / entry * 100) if side == 'LONG' else ((entry - mark) / entry * 100)
                    
                    if move >= TP_MOVIMIENTO:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        log.success(f"💰 Cosechados ${pnl:.2f} en {sym}")
                    elif move <= REENTRADA_PCT and avail > 1:
                        re_qty = round_qty(sym, (avail * 0.2 * APALANCAMIENTO) / mark)
                        if re_qty > 0:
                            exchange.create_market_order(sym, 'buy' if side == 'LONG' else 'sell', re_qty)
                            log.warning(f"🛡️ Reforzando {sym} para mejorar promedio.")

                    pos_info.append({"ACTIVO": sym, "ROI%": f"{move:+.2f}%", "PNL": f"${pnl:+.4f}", "STATUS": "OK"})

            ph_pos.table(pd.DataFrame(pos_info) if pos_info else pd.DataFrame(columns=["Buscando Entradas..."]))

            # 3. RADAR DE DISPARO
            markets = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'DOT/USD:USD']
            for sym in markets:
                try:
                    bars = exchange.fetch_ohlcv(sym, timeframe='5m', limit=25)
                    df = calc_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                    last = df.iloc[-1]
                    
                    if last['c'] <= last['bb_low'] and last['rsi'] < 35 and n_pos < MAX_POSICIONES and avail > 1.5:
                        qty_buy = round_qty(sym, (avail * 0.25 * APALANCAMIENTO) / last['c'])
                        if qty_buy > 0:
                            exchange.create_market_order(sym, 'buy', qty_buy)
                            log.info(f"🚀 Entrada en {sym} detectada.")
                            n_pos += 1
                except: continue

            time.sleep(12)
            st.rerun()

    except Exception as e:
        st.error(f"Reiniciando conexión... ({e})")
        time.sleep(10)
        st.rerun()