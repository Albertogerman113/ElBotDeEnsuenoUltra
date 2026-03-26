import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="DreamBot 💎 Sniper V3", layout="wide")

# PARÁMETROS DE SUPERVIVENCIA
APALANCAMIENTO = 25    # Bajamos a 25x para tener 4% de aire (Súper necesario)
TP_MOVIMIENTO = 0.60   # Buscamos un 0.6% de subida
SL_PROTECCION = -2.5   # SI cae 2.5%, cerramos para SALVAR los $10. No más cuentas en cero.
MAX_OPERACIONES = 2    # Solo 2 balas a la vez para cuidar el margen

def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

def calc_indicators(df):
    c = df['c'].astype(float)
    # RSI
    diff = c.diff()
    gain = diff.clip(lower=0).ewm(span=14).mean()
    loss = (-diff).clip(lower=0).ewm(span=14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    # Media de Tendencia (Solo compramos si el precio está cerca de subir)
    df['ema_trend'] = c.ewm(span=50).mean()
    return df

st.title("🎯 SNIPER V3: EL RENACER DE LA CUENTA")
st.write("_'Siete veces cae el justo, y otras tantas se levanta' (Proverbios 24:16)_")

with st.sidebar:
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("🚀 INICIAR OPERACIÓN RESCATE", value=True)

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        while True:
            balance = exchange.fetch_total_balance()
            equity = safe_float(balance.get('USD', 10.0))
            avail = safe_float(balance.get('info', {}).get('marginAvailable', equity * 0.5))

            st.metric("Capital de Batalla", f"${equity:.4f} USD")

            # 1. GESTIÓN DE POSICIONES CON ESCUDO
            posiciones = exchange.fetch_positions()
            n_activas = 0
            for p in posiciones:
                qty = safe_float(p.get('contracts', 0))
                if qty > 0:
                    n_activas += 1
                    sym, entry, mark, side = p['symbol'], safe_float(p['entryPrice']), safe_float(p['markPrice']), p['side']
                    move = ((mark - entry) / entry * 100) if side == 'long' else ((entry - mark) / entry * 100)
                    
                    # COSECHAR GANANCIA
                    if move >= TP_MOVIMIENTO:
                        exchange.create_market_order(sym, 'sell' if side == 'long' else 'buy', qty, params={'reduceOnly': True})
                        st.success(f"💰 GANANCIA ASEGURADA en {sym}")
                    
                    # ESCUDO DE CAPITAL (Evita el cero)
                    elif move <= SL_PROTECCION:
                        exchange.create_market_order(sym, 'sell' if side == 'long' else 'buy', qty, params={'reduceOnly': True})
                        st.error(f"🛡️ ESCUDO ACTIVADO: Posición cerrada en {sym} para salvar capital.")

            # 2. ENTRADA DE ALTA PROBABILIDAD (Solo con tendencia)
            if n_activas < MAX_OPERACIONES:
                for sym in ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD', 'XRP/USD:USD']:
                    try:
                        bars = exchange.fetch_ohlcv(sym, timeframe='5m', limit=50)
                        df = calc_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                        last = df.iloc[-1]
                        
                        # ENTRADA: RSI sobrevendido Y tendencia empezando a subir
                        if last['rsi'] < 30 and last['c'] > last['ema_trend'] * 0.99:
                            qty = ((equity / 2) * APALANCAMIENTO) / last['c']
                            exchange.create_market_order(sym, 'buy', round(qty, 1 if 'SOL' in sym else 0))
                            st.info(f"🎯 Sniper disparó en {sym}")
                    except: continue

            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Reiniciando... {e}")
        time.sleep(10)