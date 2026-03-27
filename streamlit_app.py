import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Genesis 3000 💎", layout="wide")

# PARÁMETROS DE ELITE (Ajustados para RECUPERAR)
APALANCAMIENTO = 20    # Bajamos a 20x para aguantar más el precio
TP_TARGET = 1.0        # Buscamos 1% de subida (Ganancia real del 20%)
SL_EMERGENCIA = -3.5   # Más aire para no salir por "ruido"
MAX_BALAS = 1          # ¡SOLO UNA BALA! Con $4.60 no podemos dividirnos.

def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

def calc_indicators(df):
    c = df['c'].astype(float)
    # RSI
    diff = c.diff()
    gain = diff.clip(lower=0).ewm(span=14, adjust=False).mean()
    loss = (-diff).clip(lower=0).ewm(span=14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    # Bollinger y Tendencia
    df['ma200'] = c.rolling(200).mean() # Filtro de tendencia mayor
    df['bb_low'] = c.rolling(20).mean() - (2 * c.rolling(20).std())
    return df

st.title("💎 GENESIS: OPERACIÓN RECUPERACIÓN")
st.write(f"_{datetime.now().strftime('%H:%M:%S')} - Con paciencia se alcanza la meta_")

with st.sidebar:
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("⚡ INICIAR RECUPERACIÓN", value=True)

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        c1, c2 = st.columns(2)
        ph_cap = c1.empty()
        ph_pos = st.empty()
        log = st.expander("📝 Registro de Cosecha", expanded=True)

        while True:
            balance = exchange.fetch_total_balance()
            equity = safe_float(balance.get('USD', 4.6))
            avail = safe_float(balance.get('info', {}).get('marginAvailable', equity * 0.5))

            ph_cap.metric("Capital Actual", f"${equity:.4f} USD")

            # 1. GESTIÓN DE POSICIONES
            posiciones = exchange.fetch_positions()
            n_activas = 0
            for p in posiciones:
                qty = safe_float(p.get('contracts', 0))
                if qty > 0:
                    n_activas += 1
                    sym, side = p['symbol'], p['side'].upper()
                    entry, mark, pnl = safe_float(p['entryPrice']), safe_float(p['markPrice']), safe_float(p['unrealizedPnl'])
                    move = ((mark - entry) / entry * 100) if side == 'LONG' else ((entry - mark) / entry * 100)
                    
                    if move >= TP_TARGET:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        log.success(f"💰 COSECHADO: +${pnl:.2f}")
                    elif move <= SL_EMERGENCIA:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        log.error(f"🛡️ ESCUDO: Protección de capital activada.")

            # 2. ENTRADA DE ALTA PRECISIÓN (SNIPER)
            if n_activas < MAX_BALAS:
                # Nos enfocamos solo en las que tienen más fuerza hoy
                for sym in ['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD']:
                    try:
                        bars = exchange.fetch_ohlcv(sym, timeframe='5m', limit=200)
                        df = calc_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                        last = df.iloc[-1]
                        prev = df.iloc[-2]
                        
                        # LA NUEVA REGLA:
                        # 1. RSI sobrevendido (<35)
                        # 2. Toca banda baja
                        # 3. ¡LA VELA ES VERDE! (Confirmación de giro: precio actual > apertura)
                        if last['c'] <= last['bb_low'] and last['rsi'] < 35 and last['c'] > last['o']:
                            qty_buy = (equity * APALANCAMIENTO * 0.8) / last['c']
                            exchange.create_market_order(sym, 'buy', round(qty_buy, 1 if 'SOL' in sym else 0))
                            log.info(f"🎯 DISPARO CONFIRMADO en {sym}")
                    except: continue

            time.sleep(15)
            st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")
        time.sleep(10)