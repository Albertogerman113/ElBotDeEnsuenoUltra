import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime
import random

# ─────────────────────────────────────────────
#  CONFIGURACIÓN VISUAL (Para ver el progreso)
# ─────────────────────────────────────────────
st.set_page_config(page_title="DreamBot 💎 Providencia 100x", layout="wide")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { color: #00ff88 !important; font-family: 'Orbitron'; }
    .stProgress > div > div { background: linear-gradient(90deg, #00ff88, #00ccff); }
    body { background-color: #0e1117; color: white; }
</style>
""", unsafe_allow_html=True)

BIBLE_QUOTES = [
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Encomienda al SEÑOR tu camino, confía en él, y él hará. (Salmo 37:5)",
    "Si puedes creer, al que cree todo le es posible. (Marcos 9:23)"
]

# ─────────────────────────────────────────────
#  PARÁMETROS DE ELITE (El Bot decide solo)
# ─────────────────────────────────────────────
TP_MOVIMIENTO = 0.45   # Cosecha al 0.45% de subida (ROI ~20% a 50x)
APALANCAMIENTO = 45    # Poder de compra para cuenta de $6-$7
MAX_POSICIONES = 5     # Diversificación total
REENTRADA_PCT = -1.5   # Si cae 1.5%, compra un poco más para promediar

# ─────────────────────────────────────────────
#  FUNCIONES MAESTRAS
# ─────────────────────────────────────────────
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
    # RSI para no comprar en el techo
    diff = c.diff()
    gain = diff.clip(lower=0).ewm(span=14).mean()
    loss = (-diff).clip(lower=0).ewm(span=14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))
    # Bandas de Bollinger para el rebote
    ma = c.rolling(20).mean()
    std = c.rolling(20).std()
    df['bb_low'] = ma - (1.7 * std) # Sensibilidad alta
    return df

# ─────────────────────────────────────────────
#  EJECUCIÓN DEL AGENTE
# ─────────────────────────────────────────────
st.title("💎 AGENTE DE PROVIDENCIA: MULTIPLICACIÓN 24/7")
st.write(f"_{random.choice(BIBLE_QUOTES)}_")

with st.sidebar:
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("🚀 ACTIVAR COSECHA NOCTURNA", value=True)

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        # Dashboard Principal
        c1, c2, c3 = st.columns(3)
        ph_cap = c1.empty()
        ph_meta = c2.empty()
        ph_prog = st.empty()
        
        st.subheader("📊 Tus Semillas en Crecimiento (Posiciones)")
        ph_pos = st.empty()
        
        st.subheader("📡 Radar de Oportunidades Divinas")
        ph_radar = st.empty()
        
        log = st.expander("📝 Bitácora de Bendiciones (Trades)", expanded=True)

        while True:
            # 1. ESTADO DE CUENTA
            balance = exchange.fetch_total_balance()
            equity = safe_float(balance.get('USD', 6.66))
            avail = safe_float(balance.get('info', {}).get('marginAvailable', equity * 0.4))

            ph_cap.metric("Capital Actual", f"${equity:.4f} USD")
            ph_meta.metric("Meta", "$100.00 USD")
            ph_prog.progress(int(min(100, (equity/100)*100)), text=f"Progreso: {equity:.2f}%")

            # 2. GESTIÓN DE COSECHA (SIN STOP LOSS)
            pos_info = []
            n_pos = 0
            posiciones = exchange.fetch_positions()
            for p in posiciones:
                qty = safe_float(p.get('contracts', 0))
                if qty > 0:
                    n_pos += 1
                    sym = p['symbol']
                    side = p['side'].upper()
                    entry = safe_float(p['entryPrice'])
                    mark = safe_float(p['markPrice'])
                    pnl = safe_float(p['unrealizedPnl'])
                    
                    move = ((mark - entry) / entry * 100) if side == 'LONG' else ((entry - mark) / entry * 100)
                    
                    # COSECHAR (TP) O REENTRAR (PROMEDIAR)
                    if move >= TP_MOVIMIENTO:
                        exchange.create_market_order(sym, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                        log.success(f"💰 ¡GLORIA A DIOS! Cosechados ${pnl:.2f} en {sym}")
                        st.components.v1.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-07.mp3"></audio>""", height=0)
                    
                    elif move <= REENTRADA_PCT and avail > 1:
                        # Si baja, compramos un poco más para bajar el promedio (Martingala)
                        re_qty = round_qty(sym, (avail * 0.2 * APALANCAMIENTO) / mark)
                        if re_qty > 0:
                            exchange.create_market_order(sym, 'buy' if side == 'LONG' else 'sell', re_qty)
                            log.warning(f"🛡️ Reforzando posición en {sym} para salir más rápido.")

                    pos_info.append({"ACTIVO": sym, "ROI%": f"{move:+.2f}%", "VALOR": f"${pnl:+.4f}", "ESTADO": "Cosechando..." if move > 0 else "Aguantando..."})

            ph_pos.table(pd.DataFrame(pos_info) if pos_info else pd.DataFrame(columns=["Esperando Señal"]))

            # 3. RADAR DE DISPARO (CAZADOR)
            radar_data = []
            markets = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'DOT/USD:USD', 'LINK/USD:USD']
            for sym in markets:
                try:
                    bars = exchange.fetch_ohlcv(sym, timeframe='5m', limit=25)
                    df = calc_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                    last = df.iloc[-1]
                    dist = ((last['c'] - last['bb_low']) / last['bb_low']) * 100
                    
                    status = "🔥 ENTRANDO" if last['c'] <= last['bb_low'] and last['rsi'] < 35 else "⏳ CAZANDO"
                    radar_data.append({"ACTIVO": sym, "PRECIO": f"${last['c']:.4f}", "DISTANCIA": f"{max(0, dist):.2f}%", "STATUS": status})

                    if status == "🔥 ENTRANDO" and n_pos < MAX_POSICIONES and avail > 1.5:
                        qty_buy = round_qty(sym, (avail * 0.25 * APALANCAMIENTO) / last['c'])
                        if qty_buy > 0:
                            exchange.create_market_order(sym, 'buy', qty_buy)
                            log.info(f"🚀 Nueva semilla plantada: {sym} x{qty_buy}")
                            n_pos += 1
                except: continue

            ph_radar.table(pd.DataFrame(radar_data))
            time.sleep(12)
            st.rerun()

    except Exception as e:
        st.error(f"Sincronizando con el servidor... {e}")
        time.sleep(10)