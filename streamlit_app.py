import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="DreamBot: Análisis en Vivo", layout="wide")

st.title("💎 AGENTE DE INGRESOS: ANÁLISIS Y EJECUCIÓN")
st.write(f"_{datetime.now().strftime('%H:%M:%S')} - Vigilando tus activos con precisión_")

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
        
        # 1. BALANCE Y CAPITAL
        balance = exchange.fetch_total_balance()
        capital = float(balance.get('USD', 0))
        st.metric("Margen Total (Equity)", f"${capital:.4f} USD")
        
        # 2. SECCIÓN DE POSICIONES ABIERTAS (Lo que pediste)
        st.subheader("📡 Operaciones Activas en Kraken")
        pos_placeholder = st.empty()
        
        # 3. RADAR DE MERCADO
        st.subheader("🔍 Radar de Próximas Entradas")
        radar_placeholder = st.empty()
        
        log = st.expander("📝 Bitácora de Movimientos", expanded=True)

        while True:
            # --- PARTE A: ANALIZAR LO QUE ESTÁ ABIERTO ---
            try:
                posiciones = exchange.fetch_positions()
                pos_activas = []
                for p in posiciones:
                    contracts = p.get('contracts')
                    if contracts is not None and float(contracts) > 0:
                        pnl = float(p.get('unrealizedPnl', 0))
                        entrada = float(p.get('entryPrice', 0))
                        actual = float(p.get('markPrice', 0))
                        lado = p.get('side').upper()
                        simbolo = p.get('symbol')
                        
                        # Análisis de la operación
                        estado_op = "✅ GANANDO" if pnl > 0 else "❌ EN ESPERA"
                        consejo = "Mantener" if pnl < 0.05 else "🔥 LISTO PARA COSECHAR"
                        
                        pos_activas.append({
                            "ACTIVO": simbolo,
                            "LADO": lado,
                            "CONTRATOS": contracts,
                            "PRECIO ENTRADA": entrada,
                            "PRECIO ACTUAL": actual,
                            "P&L (USD)": f"${pnl:.4f}",
                            "ANÁLISIS": estado_op,
                            "ACCIÓN": consejo
                        })
                        
                        # Cierre automático si hay ganancia para interés compuesto
                        if pnl > 0.04: 
                            side_cierre = 'sell' if p['side'] == 'long' else 'buy'
                            exchange.create_market_order(simbolo, side_cierre, float(contracts), params={'reduceOnly': True})
                            log.success(f"💰 CERRADA: {simbolo} con ${pnl:.2f} de ganancia.")

                if pos_activas:
                    pos_placeholder.table(pd.DataFrame(pos_activas))
                else:
                    pos_placeholder.info("No hay operaciones abiertas en este momento. El bot está cazando.")
            except Exception as e:
                pos_placeholder.error(f"Error leyendo posiciones: {e}")

            # --- PARTE B: RADAR DE PRÓXIMAS ENTRADAS ---
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
                    
                    dist_inf = ((precio - b_inf) / b_inf) * 100
                    status = "🔥 ¡ZONA DE DISPARO!" if precio <= b_inf else "⏳ CAZANDO"
                    
                    radar_data.append({"ACTIVO": symbol, "PRECIO": precio, "DISTANCIA A BANDA": f"{max(0, dist_inf):.3f}%", "ESTADO": status})

                    # Ejecución de nueva orden si hay margen
                    if status == "🔥 ¡ZONA DE DISPARO!" and len(pos_activas) < 2:
                        poder = capital * 30
                        qty = round(poder / precio, 1)
                        log.info(f"🚀 Intentando abrir {symbol}...")
                        exchange.create_market_order(symbol, 'buy', qty)
                        log.success(f"✅ ORDEN ABIERTA: {symbol}")
                except: continue

            if radar_data:
                radar_placeholder.table(pd.DataFrame(radar_data))
            
            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Error de Sistema: {e}")
        time.sleep(15)
else:
    st.info("Activa el Agente para ver tus operaciones abiertas y el análisis de mercado.")