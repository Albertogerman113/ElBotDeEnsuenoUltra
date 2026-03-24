import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Agente de Ingresos: Multiplicación Real", layout="wide")

st.title("💎 AGENTE DE INGRESOS: EJECUCIÓN TOTAL")
st.write(f"_{datetime.now().strftime('%H:%M:%S')} - Operando con Fe y Estrategia_")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Activación Final")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("⚡ ¡INICIAR COSECHA REAL!")

# Activos que aceptan fracciones pequeñas (Mejor para $6 USD)
MARKETS = ['SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'ETH/USD:USD']

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        
        # Balance Real
        balance = exchange.fetch_total_balance()
        capital = balance.get('USD', 6.66)
        st.metric("Capital Actual", f"${capital:.4f} USD")
        
        log = st.expander("📝 Registro de Operaciones Reales", expanded=True)

        while True:
            # 1. GESTIÓN DE POSICIONES
            pos = exchange.fetch_positions()
            for p in pos:
                contracts = float(p.get('contracts', 0))
                if contracts > 0:
                    pnl = float(p.get('unrealizedPnl', 0))
                    # Cosechamos rápido para que el interés compuesto gire más veces
                    if pnl > 0.02: 
                        side = 'sell' if p['side'] == 'long' else 'buy'
                        exchange.create_market_order(p['symbol'], side, contracts, params={'reduceOnly': True})
                        log.success(f"💰 GANANCIA COSECHADA: +${pnl:.2f} en {p['symbol']}")

            # 2. ESCANEO Y DISPARO AJUSTADO
            for symbol in MARKETS:
                bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=20)
                df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                precio = df['c'].iloc[-1]
                ma = df['c'].mean()
                std = df['c'].std()
                b_inf = ma - (1.6 * std) # Entramos un poco antes
                
                if precio <= b_inf:
                    # AJUSTE CRÍTICO: Usamos el 80% del poder de compra (40x aprox)
                    # Esto deja margen para que Kraken NO rechace por falta de fondos
                    poder_real = capital * 40 
                    qty = poder_real / precio
                    
                    log.info(f"🚀 {symbol} detectado. Intentando abrir orden...")
                    
                    try:
                        # Ejecución Real
                        order = exchange.create_market_order(symbol, 'buy', qty)
                        log.success(f"✅ ORDEN ABIERTA EN {symbol}. ¡Gloria a Dios!")
                        st.components.v1.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-07.mp3"></audio>""", height=0)
                        time.sleep(60) # Esperamos 1 minuto para dejar que la posición respire
                    except Exception as e:
                        # Si falla, intentamos con una cantidad un poco más pequeña automáticamente
                        try:
                            qty_segura = qty * 0.8
                            exchange.create_market_order(symbol, 'buy', qty_segura)
                            log.warning(f"⚠️ Reajustado tamaño a {qty_segura:.2f} por límites de Kraken.")
                        except:
                            log.error(f"❌ Kraken sigue rechazando: {str(e)[:50]}...")
                
            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Error de Conexión: {e}")
        time.sleep(15)
else:
    st.info("Configura y activa el switch. El mercado espera.")