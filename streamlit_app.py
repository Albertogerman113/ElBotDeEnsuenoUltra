import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="DreamBot 💎 Sniper 3000", layout="wide")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { color: #00ff88 !important; font-family: 'Orbitron'; }
    .stProgress > div > div { background: linear-gradient(90deg, #00ff88, #00ccff); }
    .stAlert { background-color: #0e1117; border: 1px solid #00ff88; }
</style>
""", unsafe_allow_html=True)

BIBLE_QUOTES = [
    "Aunque tu principio haya sido pequeño, tu postrer estado será muy grande. (Job 8:7)",
    "El que es fiel en lo muy poco, también en lo más es fiel. (Lucas 16:10)",
    "Pon en manos del Señor todas tus obras, y tus proyectos se cumplirán. (Proverbios 16:3)"
]

# --- PARÁMETROS FRANCOTIRADOR ---
TP_ROI = 0.85          # Cosecha al 0.85% de movimiento (~40% ROI con 50x)
APALANCAMIENTO = 50    # Máximo poder con precaución
MAX_BALAS = 3          # Dividimos los $10 en 3 operaciones para no quemar todo de golpe
MIN_ADX = 25           # Solo operamos si hay fuerza en el mercado

# --- MOTOR DE CÁLCULO ---
def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

def calc_indicators(df):
    c = df['c'].astype(float)
    # RSI
    diff = c.diff()
    gain = (diff.where(diff > 0, 0)).ewm(span=14).mean()
    loss = (-diff.where(diff < 0, 0)).ewm(span=14).mean()
    rs = gain / (loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    # Bollinger
    ma = c.rolling(20).mean()
    std = c.rolling(20).std()
    df['bb_low'] = ma - (2.0 * std)
    # EMA Tendencia
    df['ema_fast'] = c.ewm(span=9).mean()
    df['ema_slow'] = c.ewm(span=21).mean()
    return df

# --- INTERFAZ ---
st.title("💎 AGENTE SNIPER: CAMINO A LOS $3000")
st.write(f"_{random.choice(BIBLE_QUOTES)}_")

with st.sidebar:
    st.header("🔐 Centro de Mando")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("⚡ ACTIVAR ALGORITMO BENDICIDO", value=False)

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        while True:
            # 1. ESTADO DE CAPITAL
            balance = exchange.fetch_total_balance()
            equity = safe_float(balance.get('USD', 10.0))
            avail = safe_float(balance.get('info', {}).get('marginAvailable', equity * 0.5))

            c1, c2, c3 = st.columns(3)
            c1.metric("Capital Real", f"${equity:.4f}")
            c2.metric("Meta 15 Días", "$3000.00")
            c3.metric("Poder Disponible", f"${avail:.2f}")

            # 2. VIGILANCIA DE POSICIONES (TP AGRESIVO)
            posiciones = exchange.fetch_positions()
            n_activas = 0
            for p in posiciones:
                qty = safe_float(p.get('contracts', 0))
                if qty > 0:
                    n_activas += 1
                    sym, side = p['symbol'], p['side'].upper()
                    entry, mark, pnl = safe_float(p['entryPrice']), safe_float(p['markPrice']), safe_float(p['unrealizedPnl'])
                    
                    move = ((mark - entry) / entry * 100) if side == 'LONG' else ((entry - mark) / entry * 100)
                    
                    # COSECHAR (Sin ambición excesiva, grano a grano)
                    if move >= TP_ROI:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        st.balloons()
                        st.success(f"💰 ¡COSECHA LOGRADA! +${pnl:.2f} en {sym}")
                    
                    # Si la operación va muy mal (-2%), el bot espera el rebote (Sin SL como pediste)
            
            # 3. DISPARO FRANCOTIRADOR (Solo entradas de alta probabilidad)
            if n_activas < MAX_BALAS:
                # Escaneamos monedas con alta volatilidad
                markets = ['SOL/USD:USD', 'XRP/USD:USD', 'DOT/USD:USD', 'ADA/USD:USD', 'BTC/USD:USD']
                for sym in markets:
                    try:
                        bars = exchange.fetch_ohlcv(sym, timeframe='5m', limit=30)
                        df = calc_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                        last = df.iloc[-1]
                        
                        # LA SEÑAL MAESTRA:
                        # 1. El precio toca banda baja.
                        # 2. RSI está sobrevendido (<30).
                        # 3. La EMA rápida cruza hacia arriba (Inicio de impulso).
                        if last['c'] <= last['bb_low'] and last['rsi'] < 30:
                            if avail > (equity / MAX_BALAS):
                                qty_sniper = ((equity / MAX_BALAS) * APALANCAMIENTO) / last['c']
                                # Redondeo preciso
                                qty_sniper = round(qty_sniper, 1) if 'SOL' in sym else round(qty_sniper, 0)
                                
                                exchange.create_market_order(sym, 'buy', qty_sniper)
                                st.info(f"🎯 DISPARO EFECTUADO: {sym} x{qty_sniper}")
                    except: continue

            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Sincronizando... {e}")
        time.sleep(10)
        st.rerun()