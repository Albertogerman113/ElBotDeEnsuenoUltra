import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="DreamBot: Monitor de Operaciones", layout="wide")

st.title("💎 AGENTE DE INGRESOS: MONITOR Y EJECUCIÓN")
st.write(f"_{datetime.now().strftime('%H:%M:%S')} - Vigilando con precisión divina_")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Panel de Control")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("⚡ ¡INICIAR MONITORIZACIÓN!")

MARKETS = ['SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'ETH/USD:USD', 'DOT/USD:USD', 'BTC/USD:USD']

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        # 1. BALANCE
        balance = exchange.fetch_total_balance()
        capital = float(balance.get('USD', 6.55))
        st.metric("Margen Total (Equity)", f"${capital:.4f} USD")
        
        # 2. SECCIÓN DE POSICIONES (BLINDADA)
        st.subheader("📡 Operaciones Activas en Kraken")
        pos_placeholder = st.empty()
        
        st.subheader("🔍 Radar de Próximas Entradas")
        radar_placeholder = st.empty()
        log = st.expander("📝 Bitácora de Movimientos", expanded=True)

        while True:
            # --- ANALIZAR POSICIONES SIN ERRORES ---
            try:
                posiciones = exchange.fetch_positions()
                pos_activas = []
                for p in posiciones:
                    # Verificación de contratos (evita NoneType)
                    raw_contracts = p.get('contracts')
                    if raw_contracts is not None and float(raw_contracts) > 0:
                        # Extraer datos con protección total
                        def safe_float(val):
                            try: return float(val) if val is not None else 0.0
                            except: return 0.0

                        contracts = safe_float(p.get('contracts'))
                        pnl = safe_float(p.get('unrealizedPnl'))
                        entrada = safe_float(p.get('entryPrice'))
                        actual = safe_float(p.get('markPrice'))
                        simbolo = p.get('symbol', 'N/A')
                        lado = str(p.get('side', 'N/A')).upper()
                        
                        pos_activas.append({
                            "ACTIVO": simbolo,
                            "LADO": lado,
                            "CONTRATOS": contracts,
                            "ENTRADA": f"${entrada:.4f}",
                            "ACTUAL": f"${actual:.4f}",
                            "P&L (USD)": f"${pnl:.4f}",
                            "ESTADO": "✅ GANANDO" if pnl > 0 else "⏳ EN ESPERA"
                        })
                        
                        # Cierre automático para interés compuesto
                        if pnl > 0.04: 
                            side_cierre = 'sell' if str(lado).lower() == 'long' else 'buy'
                            exchange.create_market_order(simbolo, side_cierre, contracts, params={'reduceOnly': True})
                            log.success(f"💰 COSECHADA: {simbolo} con ${pnl:.2f}")

                if pos_activas:
                    pos_placeholder.table(pd.DataFrame(pos_activas))
                else:
                    pos_placeholder.info("Esperando que el mercado toque zona de entrada...")
            except Exception as e:
                pos_placeholder.warning(f"Sincronizando posiciones... ({e})")

            # --- RADAR DE ENTRADAS ---
            radar_data = []
            for symbol in MARKETS:
                try:
                    bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=20)
                    if not bars: continue
                    df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                    precio = float(df['c'].iloc[-1])
                    ma = df['c'].mean()
                    std = df['c'].std()
                    b_inf = ma - (1.6 * std)
                    dist = ((precio - b_inf) / b_inf) * 100
                    status = "🔥 ENTRANDO" if precio <= b_inf else "⏳ CAZANDO"
                    radar_data.append({"ACTIVO": symbol, "PRECIO": precio, "DISTANCIA": f"{max(0, dist):.3f}%", "ESTADO": status})

                    # Disparo si hay espacio
                    if status == "🔥 ENTRANDO" and len(pos_activas) < 2:
                        qty = round((capital * 30) / precio, 1)
                        exchange.create_market_order(symbol, 'buy', qty)
                        log.success(f"✅ COMPRA REAL: {symbol}")
                except: continue

            if radar_data:
                radar_placeholder.table(pd.DataFrame(radar_data))
            
            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")
        time.sleep(15)
else:
    st.info("Activa el Agente para monitorear tus operaciones.")