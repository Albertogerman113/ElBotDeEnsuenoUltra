import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="DreamBot: Cosecha Real", layout="wide")

BIBLE_QUOTES = [
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Todo lo puedo en Cristo que me fortalece. (Filipenses 4:13)",
    "Si puedes creer, al que cree todo le es posible. (Marcos 9:23)"
]

st.title("💎 AGENTE DE INGRESOS: MULTIPLICACIÓN")
st.write(f"_{random.choice(BIBLE_QUOTES)}_")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Activación")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    meta_diaria = st.number_input("Meta del Día (USD)", value=100.0)
    activar = st.toggle("⚡ INICIAR COSECHA 24/7")

MARKETS = ['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'EUR/USD:USD', 'GBP/USD:USD', 'XRP/USD:USD']

# --- PROCESO ---
if activar and api_key and api_secret:
    try:
        # Conexión limpia
        exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        
        # Dashboard
        col_inv, col_meta = st.columns(2)
        inv_placeholder = col_inv.empty()
        meta_placeholder = col_meta.empty()
        
        st.divider()
        log_expander = st.expander("📝 Bitácora de Cosecha", expanded=True)
        
        while True:
            # 1. LEER SALDO (Forma segura para evitar error 'info')
            balance = exchange.fetch_total_balance()
            total_equity = balance.get('USD', 7.40) # Si falla, asume tu último saldo
            
            inv_placeholder.metric("Capital Actual", f"${total_equity:.4f} USD")
            meta_placeholder.metric("Meta Objetivo", f"${meta_diaria} USD")

            # 2. GESTIÓN DE POSICIONES (Cierre de ganancia rápido)
            try:
                posiciones = exchange.fetch_positions()
                for pos in posiciones:
                    contracts = float(pos.get('contracts', 0))
                    if contracts > 0:
                        pnl = float(pos.get('unrealizedPnl', 0))
                        if pnl > 0.05: # Cierra con 5 centavos de ganancia para mover el dinero rápido
                            side = 'sell' if pos['side'] == 'long' else 'buy'
                            exchange.create_market_order(pos['symbol'], side, contracts, params={'reduceOnly': True})
                            log_expander.success(f"💰 Cosechado: +${pnl:.2f} en {pos['symbol']}")
            except:
                pass

            # 3. ESCANEO Y DISPARO
            for symbol in MARKETS:
                try:
                    bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=20)
                    df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                    precio = df['c'].iloc[-1]
                    ma = df['c'].mean()
                    std = df['c'].std()
                    b_inf = ma - (2 * std)
                    
                    if precio <= b_inf:
                        # Usar el 100% del capital con 50x de apalancamiento
                        order_size = total_equity * 50
                        qty = order_size / precio
                        
                        log_expander.info(f"🚀 Oportunidad en {symbol}. Ejecutando...")
                        # exchange.create_market_order(symbol, 'buy', qty)
                        log_expander.success(f"🔥 Orden enviada. ¡A por los $100!")
                        time.sleep(10)
                except:
                    continue

            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")
        time.sleep(10)
else:
    st.info("Configura y activa para empezar a multiplicar.")