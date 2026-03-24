import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Agente de Multiplicación", layout="wide")

st.title("💎 AGENTE DE INGRESOS: EJECUCIÓN TOTAL")
st.write(f"_{datetime.now().strftime('%H:%M:%S')} - Operando bajo la bendición de Dios_")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Activación Real")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("⚡ ¡INICIAR COSECHA REAL AHORA!")

# Solo activos que aceptan capitales muy pequeños
MARKETS = ['SOL/USD:USD', 'XRP/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD']

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        
        # Dashboard
        balance = exchange.fetch_total_balance()
        capital = balance.get('USD', 6.66)
        st.metric("Capital Actual", f"${capital:.4f} USD")
        
        log = st.expander("📝 Registro de Cosecha Real", expanded=True)

        while True:
            # 1. REVISAR POSICIONES Y CERRAR GANANCIAS
            pos = exchange.fetch_positions()
            for p in pos:
                contracts = float(p.get('contracts', 0))
                if contracts > 0:
                    pnl = float(p.get('unrealizedPnl', 0))
                    # Si ya ganamos algo, cerramos para liberar el dinero
                    if pnl > 0.03: 
                        side = 'sell' if p['side'] == 'long' else 'buy'
                        exchange.create_market_order(p['symbol'], side, contracts, params={'reduceOnly': True})
                        log.success(f"💰 GANANCIA COSECHADA: +${pnl:.2f} en {p['symbol']}")

            # 2. BUSCAR ENTRADA Y DISPARAR DE VERDAD
            for symbol in MARKETS:
                bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=20)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                precio = df['c'].iloc[-1]
                ma = df['c'].mean()
                std = df['c'].std()
                b_inf = ma - (1.5 * std) # Ajustado a 1.5 para entrar más rápido
                
                if precio <= b_inf:
                    # USAMOS TODO EL PODER DE COMPRA (50x)
                    order_size = capital * 45 # Usamos 45x para dejar margen de error
                    qty = order_size / precio
                    
                    log.info(f"🚀 {symbol} en zona. DISPARANDO ORDEN REAL...")
                    
                    # --- ESTA ES LA LÍNEA QUE ACTIVA EL DINERO ---
                    try:
                        order = exchange.create_market_order(symbol, 'buy', qty)
                        log.success(f"✅ ORDEN EJECUTADA EN KRAKEN: {symbol}")
                        st.components.v1.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-07.mp3"></audio>""", height=0)
                    except Exception as e:
                        log.error(f"Kraken no dejó entrar: {e}")
                
            time.sleep(10)
            st.rerun()

    except Exception as e:
        st.error(f"Error de Conexión: {e}")
        time.sleep(10)
else:
    st.info("El bot está en espera. Activa el switch para que empiece a meter órdenes.")