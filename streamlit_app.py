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
    "Al que cree todo le es posible. (Marcos 9:23)"
]

# --- PARÁMETROS DE ELITE (SIN STOP LOSS) ---
TP_ROI_REAL = 0.40     # Cosecha al 0.4% de movimiento (ROI ~20% con 50x)
APALANCAMIENTO = 50    # Máximo poder para cuenta pequeña
MAX_POSICIONES = 6     # Diversificación total
DISTANCIA_REENTRADA = -1.2 # Si cae 1.2%, promediamos compra

# --- FUNCIONES DE SEGURIDAD ---
def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

def round_qty(symbol, qty):
    if 'BTC' in symbol: return round(qty, 3)
    if 'ETH' in symbol: return round(qty, 2)
    if any(x in symbol for x in ['SOL', 'DOT', 'ADA', 'XRP']): return round(qty, 1)
    return round(qty, 0)

def calc_indicators(df):
    c = df['c'].astype(float)
    # RSI Blindado contra division by zero
    diff = c.diff()
    gain = diff.clip(lower=0).ewm(span=14, adjust=False).mean()
    loss = (-diff).clip(lower=0).ewm(span=14, adjust=False).mean()
    rs = gain / (loss + 0.00000001) # El seguro contra el error
    df['rsi'] = 100 - (100 / (1 + rs))
    # Bandas de Bollinger para rebote
    ma = c.rolling(20).mean()
    std = c.rolling(20).std()
    df['bb_low'] = ma - (1.6 * std)
    return df

# --- AGENTE PRINCIPAL ---
st.title("💎 AGENTE DE PROVIDENCIA: MULTIPLICACIÓN 24/7")
st.write(f"_{random.choice(BIBLE_QUOTES)}_")

with st.sidebar:
    st.header("🔐 Acceso")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("🚀 ACTIVAR COSECHA 24/7", value=True)

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        while True:
            # 1. ACTUALIZAR ESTADO REAL
            balance = exchange.fetch_total_balance()
            equity = safe_float(balance.get('USD', 5.61))
            avail = safe_float(balance.get('info', {}).get('marginAvailable', equity * 0.4))

            c1, c2 = st.columns(2)
            c1.metric("Capital Actual", f"${equity:.4f} USD")
            c2.metric("Meta", "$100.00 USD")
            st.progress(int(min(100, (equity/100)*100)), text=f"Progreso: {equity:.2f}%")

            # 2. GESTIÓN DE POSICIONES (SOLO COSECHAR GANANCIA)
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
                    
                    # COSECHAR (TP)
                    if move >= TP_ROI_REAL:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        st.success(f"💰 ¡Cosechado! +${pnl:.2f} en {sym}")
                    
                    # PROMEDIAR (Si el precio baja, compramos más para mejorar el precio)
                    elif move <= DISTANCIA_REENTRADA and avail > 1.0:
                        re_qty = round_qty(sym, (avail * 0.2 * APALANCAMIENTO) / mark)
                        if re_qty > 0:
                            exchange.create_market_order(sym, 'buy' if side == 'LONG' else 'sell', re_qty)
                            st.warning(f"🛡️ Reforzando {sym} para salir en verde más rápido.")

                    pos_info.append({"ACTIVO": sym, "ROI%": f"{move:+.2f}%", "VALOR": f"${pnl:+.4f}"})

            st.subheader("📊 Tus Semillas (Posiciones)")
            st.table(pd.DataFrame(pos_info) if pos_info else pd.DataFrame(columns=["Buscando entradas..."]))

            # 3. RADAR DE DISPARO (CAZADOR)
            markets = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'DOT/USD:USD']
            for sym in markets:
                try:
                    bars = exchange.fetch_ohlcv(sym, timeframe='5m', limit=25)
                    df = calc_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                    last = df.iloc[-1]
                    
                    # Entramos si el precio está barato (RSI < 35) y toca banda baja
                    if last['c'] <= last['bb_low'] and last['rsi'] < 35 and n_pos < MAX_POSICIONES and avail > 1.2:
                        qty_buy = round_qty(sym, (avail * 0.20 * APALANCAMIENTO) / last['c'])
                        if qty_buy > 0:
                            exchange.create_market_order(sym, 'buy', qty_buy)
                            st.info(f"🚀 Plantando nueva semilla en {sym}")
                            n_pos += 1
                except: continue

            time.sleep(12)
            st.rerun()

    except Exception as e:
        st.error(f"Sincronizando... {e}")
        time.sleep(10)
        st.rerun()