import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

st.set_page_config(page_title="DreamBot: Cazador Veloz", layout="wide")
st.title("💎 AGENTE DE INGRESOS: COSECHA INMEDIATA")
st.write(f"_{datetime.now().strftime('%H:%M:%S')} - Sin distracciones, solo resultados_")

with st.sidebar:
    st.header("🔐 Panel de Control")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("⚡ ¡INICIAR MONITORIZACIÓN!")

# Lista optimizada para ejecución rápida
MARKETS = ['DOT/USD:USD', 'SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'ETH/USD:USD']

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        balance = exchange.fetch_total_balance()
        capital = float(balance.get('USD', 6.55))
        st.metric("Capital Real (Equity)", f"${capital:.4f} USD")
        
        pos_placeholder = st.empty()
        radar_placeholder = st.empty()
        log = st.expander("📝 Registro de Cosecha Inmediata", expanded=True)

        while True:
            # --- 1. GESTIÓN Y LIMPIEZA DE POSICIONES ---
            pos_activas = []
            try:
                posiciones = exchange.fetch_positions()
                for p in posiciones:
                    qty = float(p.get('contracts', 0))
                    if qty > 0:
                        pnl = float(p.get('unrealizedPnl', 0))
                        simbolo = p.get('symbol')
                        side = p.get('side').upper()
                        pos_activas.append(p)
                        
                        # CIERRE AGRESIVO: Si ganamos $0.01 o si la otra moneda está "Entrando", cerramos.
                        # Esto libera los $6.55 para la nueva oportunidad.
                        if pnl > 0.01:
                            exchange.create_market_order(simbolo, 'sell' if side == 'LONG' else 'buy', qty, params={'reduceOnly': True})
                            log.success(f"💰 Cosecha rápida en {simbolo}: +${pnl:.2f}")

                if pos_activas:
                    pos_placeholder.table(pd.DataFrame([{"ACTIVO": x['symbol'], "P&L": x['unrealizedPnl']} for x in pos_activas]))
                else:
                    pos_placeholder.info("Cuentas limpias. Buscando la siguiente presa...")
            except: pass

            # --- 2. ESCANEO Y DISPARO SIN FILTROS ---
            radar_data = []
            for symbol in MARKETS:
                try:
                    bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=15)
                    df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                    precio = float(df['c'].iloc[-1])
                    ma = df['c'].mean()
                    std = df['c'].std()
                    b_inf = ma - (1.4 * std) # Bandas más apretadas para más acción
                    
                    dist = ((precio - b_inf) / b_inf) * 100
                    status = "🔥 ENTRANDO" if precio <= b_inf else "⏳ CAZANDO"
                    radar_data.append({"ACTIVO": symbol, "DISTANCIA": f"{max(0, dist):.3f}%", "ESTADO": status})

                    # DISPARO: Solo si no hay nada abierto para no saturar el margen
                    if status == "🔥 ENTRANDO" and not pos_activas:
                        log.info(f"🚀 Disparando todo a {symbol}...")
                        # Tamaño dinámico según el activo (Kraken min limits)
                        size_map = {'DOT/USD:USD': 5, 'SOL/USD:USD': 0.5, 'ADA/USD:USD': 20, 'XRP/USD:USD': 10, 'ETH/USD:USD': 0.01}
                        qty_to_buy = size_map.get(symbol, 1)
                        
                        try:
                            exchange.create_market_order(symbol, 'buy', qty_to_buy)
                            log.success(f"✅ ORDEN ABIERTA: {symbol}")
                            st.components.v1.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-07.mp3"></audio>""", height=0)
                        except Exception as e:
                            log.error(f"Error en {symbol}: {e}")
                except: continue

            radar_placeholder.table(pd.DataFrame(radar_data))
            time.sleep(10) # Refresco más rápido
            st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")
        time.sleep(10)