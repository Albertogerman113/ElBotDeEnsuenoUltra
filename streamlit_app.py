import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Genesis 3000 💎", layout="wide")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { color: #00ff88 !important; font-family: 'Orbitron'; }
    .stProgress > div > div { background: linear-gradient(90deg, #00ff88, #00ccff); }
</style>
""", unsafe_allow_html=True)

# PARÁMETROS DE ELITE
APALANCAMIENTO = 25    
TP_TARGET = 0.75       
SL_EMERGENCIA = -2.0   # Este es el valor que faltaba conectar
MAX_BALAS = 2          

def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

def calc_indicators(df):
    c = df['c'].astype(float)
    diff = c.diff()
    gain = diff.clip(lower=0).ewm(span=14, adjust=False).mean()
    loss = (-diff).clip(lower=0).ewm(span=14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    df['ma50'] = c.rolling(50).mean()
    df['std'] = c.rolling(20).std()
    df['bb_low'] = c.rolling(20).mean() - (2 * df['std'])
    return df

st.title("💎 PROYECTO GENESIS: CAMINO A LOS $3000")
st.write("_'No temas, porque yo estoy contigo...' (Isaías 41:10)_")

with st.sidebar:
    st.header("🔐 Acceso")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("⚡ ACTIVAR ALGORITMO GENESIS", value=True)

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        c1, c2 = st.columns(2)
        ph_cap = c1.empty()
        ph_meta = c2.empty()
        ph_pos = st.empty()
        log = st.expander("📝 Registro de Cosecha", expanded=True)

        while True:
            # 1. ESTADO DE CUENTA
            balance = exchange.fetch_total_balance()
            equity = safe_float(balance.get('USD', 10.0))
            avail = safe_float(balance.get('info', {}).get('marginAvailable', equity * 0.4))

            ph_cap.metric("Capital de Batalla", f"${equity:.4f} USD")
            ph_meta.metric("Meta Final", "$3,000.00 USD")

            # 2. GESTIÓN DE POSICIONES
            posiciones = exchange.fetch_positions()
            n_activas = 0
            for p in posiciones:
                qty = safe_float(p.get('contracts', 0))
                if qty > 0:
                    n_activas += 1
                    sym, side = p['symbol'], p['side'].upper()
                    entry, mark, pnl = safe_float(p['entryPrice']), safe_float(p['markPrice']), safe_float(p['unrealizedPnl'])
                    move = ((mark - entry) / (entry if entry > 0 else 1) * 100) if side == 'LONG' else ((entry - mark) / (entry if entry > 0 else 1) * 100)
                    
                    # CIERRE POR GANANCIA
                    if move >= TP_TARGET:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        log.success(f"✅ GANANCIA: +${pnl:.2f} en {sym}")
                    
                    # CIERRE POR PROTECCIÓN (Corregido: SL_EMERGENCIA)
                    elif move <= SL_EMERGENCIA:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        log.error(f"🛡️ ESCUDO: Salvamos capital en {sym}")

            # 3. DISPARO FRANCOTIRADOR
            if n_activas < MAX_BALAS:
                for sym in ['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'XRP/USD:USD']:
                    try:
                        bars = exchange.fetch_ohlcv(sym, timeframe='5m', limit=60)
                        df = calc_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                        last = df.iloc[-1]
                        
                        if last['c'] <= last['bb_low'] and last['rsi'] < 35:
                            qty_buy = ((equity / 2) * APALANCAMIENTO) / last['c']
                            exchange.create_market_order(sym, 'buy', round(qty_buy, 1 if 'SOL' in sym else 0))
                            log.info(f"🎯 Disparo Sniper en {sym}")
                    except: continue

            time.sleep(12)
            st.rerun()

    except Exception as e:
        st.error(f"Reconectando... {e}")
        time.sleep(10)
        st.rerun()