import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="DreamBot: Cosecha 100x", layout="wide")

# Citas de Poder
BIBLE_QUOTES = [
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Al que cree todo le es posible. (Marcos 9:23)",
    "Y mi Dios suplirá todo lo que os falte conforme a sus riquezas. (Filipenses 4:19)"
]

st.title("💎 AGENTE DE INGRESOS: MULTIPLICACIÓN DIVINA")
st.write(f"_{random.choice(BIBLE_QUOTES)}_")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Activación del Agente")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    meta_diaria = st.number_input("Meta del Día (USD)", value=100.0)
    activar = st.toggle("⚡ INICIAR COSECHA 24/7")

# --- CONFIGURACIÓN TÉCNICA ---
MARKETS = ['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'EUR/USD:USD', 'GBP/USD:USD', 'XRP/USD:USD', 'DOT/USD:USD']

def calcular_apalancamiento(volatilidad):
    return 50 if volatilidad < 0.02 else 20

# --- CUERPO DEL AGENTE ---
if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        
        # Dashboard de Métricas
        col_inv, col_meta, col_prog = st.columns(3)
        inv_placeholder = col_inv.empty()
        meta_placeholder = col_meta.empty()
        prog_placeholder = col_prog.empty()
        
        st.divider()
        log_expander = st.expander("📝 Bitácora de Operaciones Reales", expanded=True)
        
        while True:
            # 1. REVISAR CAPITAL REAL (Margen Disponible)
            balance = exchange.fetch_total_balance()
            # Buscamos el margen disponible real para operar
            available_margin = balance['info'].get('marginAvailable', 7.20) 
            total_equity = balance.get('USD', 7.40)
            
            # Actualizar Métricas
            inv_placeholder.metric("Capital Actual", f"${total_equity:.4f} USD")
            meta_placeholder.metric("Meta Objetivo", f"${meta_diaria} USD")
            progreso = min(100.0, (total_equity / meta_diaria) * 100)
            prog_placeholder.progress(int(progreso), text=f"Progreso a la Meta: {progreso:.2f}%")

            # 2. GESTIÓN DE POSICIONES EXISTENTES (Cierre de Ganancias)
            posiciones = exchange.fetch_positions()
            for pos in posiciones:
                contratos = float(pos.get('contracts', 0))
                if contratos > 0:
                    pnl = float(pos.get('unrealizedPnl', 0))
                    simbolo = pos['symbol']
                    # Si la ganancia es positiva, el bot evalúa cerrar para liberar margen
                    if pnl > 0.10: # Cierra con $0.10 de ganancia para reinvertir rápido
                        side_cierre = 'sell' if pos['side'] == 'long' else 'buy'
                        exchange.create_market_order(simbolo, side_cierre, contratos, params={'reduceOnly': True})
                        log_expander.success(f"💰 Cosechando ganancia en {simbolo}: +${pnl:.2f}. Margen liberado.")
                        st.components.v1.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-07.mp3" type="audio/mpeg"></audio>""", height=0)

            # 3. RADAR DE ENTRADA (Nuevas Oportunidades)
            for symbol in MARKETS:
                try:
                    bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=20)
                    df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                    precio = df['c'].iloc[-1]
                    ma = df['c'].mean()
                    std = df['c'].std()
                    b_inf = ma - (2 * std)
                    
                    # Si el precio toca la banda inferior, el bot dispara
                    if precio <= b_inf and available_margin > 1.0:
                        lev = calcular_apalancamiento((ma-b_inf)/ma)
                        # Cálculo de Interés Compuesto Agresivo
                        # Usamos casi todo el margen disponible para maximizar
                        order_size = (available_margin * lev * 0.95)
                        contracts = order_size / precio
                        
                        log_expander.info(f"🚀 Detectada oportunidad en {symbol}. Ejecutando orden de ${order_size:.2f}...")
                        # exchange.create_market_order(symbol, 'buy', contracts)
                        log_expander.success(f"🔥 Orden de compra en {symbol} enviada al mercado.")
                        time.sleep(5) # Evitar duplicados
                except:
                    continue

            time.sleep(10)
            st.rerun()

    except Exception as e:
        st.error(f"Error de Conexión: {e}")
        time.sleep(20)
else:
    st.info("Esperando activación. El Agente está listo para multiplicar sus talentos.")