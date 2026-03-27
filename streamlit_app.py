import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sniper V4: El Guerrero", layout="wide")

# PARÁMETROS DE SUPERVIVENCIA (PROTECCIÓN TOTAL)
LEVERAGE = 10          # 10x máximo. Necesitamos 10% de margen de caída.
TP_PCT = 1.5           # Buscamos movimientos del 1.5% (15% de ganancia real)
SL_PCT = 1.0           # Si cae 1%, cortamos sin piedad. Perder $0.10 es mejor que $10.
MAX_TRADES = 1         # Una sola moneda, la más fuerte.

def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

def get_indicators(df):
    c = df['c'].astype(float)
    # Tendencia Maestra (EMA 200)
    df['ema200'] = c.ewm(span=200, adjust=False).mean()
    # Impulso (MACD simplificado)
    df['ema12'] = c.ewm(span=12, adjust=False).mean()
    df['ema26'] = c.ewm(span=26, adjust=False).mean()
    df['macd'] = df['ema12'] - df['ema26']
    # Volatilidad
    df['high_max'] = df['h'].rolling(20).max()
    return df

st.title("🛡️ SNIPER V4: ESTRATEGIA DE RUPTURA")
st.write(f"_{datetime.now().strftime('%H:%M:%S')} - Operando con Sabiduría y Fuerza_")

with st.sidebar:
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("⚡ INICIAR ALGORITMO DE FUERZA", value=True)

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        while True:
            balance = exchange.fetch_total_balance()
            equity = safe_float(balance.get('USD', 10.0))
            
            st.metric("Capital de Batalla", f"${equity:.4f} USD")
            
            # 1. CHECAR POSICIONES
            posiciones = exchange.fetch_positions()
            n_activas = 0
            for p in posiciones:
                qty = safe_float(p.get('contracts', 0))
                if qty > 0:
                    n_activas += 1
                    sym, side = p['symbol'], p['side'].upper()
                    entry, mark, pnl = safe_float(p['entryPrice']), safe_float(p['markPrice']), safe_float(p['unrealizedPnl'])
                    move = ((mark - entry) / entry * 100) if side == 'LONG' else ((entry - mark) / entry * 100)
                    
                    # Salidas de Seguridad
                    if move >= TP_PCT:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        st.success(f"💰 META ALCANZADA en {sym}")
                    elif move <= -SL_PCT:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        st.error(f"🛡️ SL ACTIVADO: Protegimos el capital.")

            # 2. BUSCAR ENTRADA (SOLO SI EL MERCADO SUBE)
            if n_activas < MAX_TRADES:
                for sym in ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD']:
                    try:
                        bars = exchange.fetch_ohlcv(sym, timeframe='15m', limit=210)
                        df = get_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                        last = df.iloc[-1]
                        
                        # ESTRATEGIA DE RUPTURA:
                        # 1. El precio está ARRIBA de la EMA 200 (Tendencia alcista confirmada).
                        # 2. El MACD es positivo (Hay fuerza).
                        # 3. El precio rompe el máximo de las últimas 20 velas.
                        if last['c'] > last['ema200'] and last['macd'] > 0 and last['c'] >= last['high_max']:
                            qty = (equity * LEVERAGE * 0.9) / last['c']
                            exchange.create_market_order(sym, 'buy', round(qty, 1 if 'SOL' in sym else 0))
                            st.info(f"🚀 ENTRADA POR RUPTURA: {sym}")
                    except: continue

            time.sleep(20)
            st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")
        time.sleep(10)