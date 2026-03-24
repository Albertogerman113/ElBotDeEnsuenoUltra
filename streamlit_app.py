import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Agente de Ingresos: Multiplicación Divina", layout="wide")

st.title("💎 AGENTE DE INGRESOS: EJECUCIÓN TOTAL")
st.write(f"_{datetime.now().strftime('%H:%M:%S')} - Operando con Fe y Estrategia_")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Activación Final")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    activar = st.toggle("⚡ ¡INICIAR COSECHA REAL!")

MARKETS = ['SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'ETH/USD:USD', 'DOT/USD:USD']

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        # Dashboard Principal
        balance = exchange.fetch_total_balance()
        capital = float(balance.get('USD', 6.55))
        st.metric("Capital Actual", f"${capital:.4f} USD")
        
        st.subheader("📡 Radar de Proximidad en Tiempo Real")
        radar_placeholder = st.empty()
        log = st.expander("📝 Bitácora de Operaciones Reales", expanded=True)

        while True:
            radar_data = []
            
            # 1. GESTIÓN DE POSICIONES EXISTENTES (Cierre de ganancia)
            try:
                pos = exchange.fetch_positions()
                for p in pos:
                    contracts = p.get('contracts')
                    if contracts is not None and float(contracts) > 0:
                        pnl = float(p.get('unrealizedPnl', 0))
                        if pnl > 0.02: 
                            side = 'sell' if p['side'] == 'long' else 'buy'
                            exchange.create_market_order(p['symbol'], side, float(contracts), params={'reduceOnly': True})
                            log.success(f"💰 GANANCIA COSECHADA: +${pnl:.2f} en {p['symbol']}")
            except Exception as e:
                pass

            # 2. ESCANEO DE MERCADO
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
                    status = "🔥 ¡ENTRANDO!" if precio <= b_inf else "⏳ BUSCANDO"
                    
                    radar_data.append({"ACTIVO": symbol, "PRECIO": precio, "FALTA %": f"{max(0, dist_inf):.3f}%", "ESTADO": status})

                    # 3. DISPARO REAL
                    if status == "🔥 ¡ENTRANDO!":
                        # Usamos 30x para estar súper seguros de que Kraken acepte con los $6.55
                        poder_compra = capital * 30 
                        qty = round(poder_compra / precio, 2)
                        
                        log.info(f"🚀 {symbol} detectado. Intentando abrir orden...")
                        try:
                            order = exchange.create_market_order(symbol, 'buy', qty)
                            log.success(f"✅ ORDEN ABIERTA EN {symbol}. ¡Gloria a Dios!")
                            st.components.v1.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-07.mp3"></audio>""", height=0)
                            time.sleep(30)
                        except Exception as e:
                            # Intento de rescate con tamaño mínimo
                            log.warning(f"Ajustando tamaño por seguridad...")
                            try:
                                exchange.create_market_order(symbol, 'buy', round(qty * 0.7, 2))
                                log.success(f"✅ Orden abierta con ajuste de margen.")
                            except:
                                log.error(f"Kraken no permitió la entrada en {symbol}.")
                except:
                    continue

            # Actualizar Interfaz
            if radar_data:
                radar_placeholder.table(pd.DataFrame(radar_data))
            
            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Error de Sistema: {e}")
        time.sleep(15)
else:
    st.info("Configura tus llaves y activa el bot. El Agente está listo.")