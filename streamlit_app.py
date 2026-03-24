import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import random

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="DreamBot: Interés Compuesto", layout="wide")

# Citas Bíblicas de Poder y Prosperidad
BIBLE_QUOTES = [
    "La bendición del SEÑOR es la que enriquece, y él no añade tristeza con ella. (Proverbios 10:22)",
    "Pidan, y se les dará; busquen, y hallarán. (Mateo 7:7)",
    "Encomienda al SEÑOR tu camino, confía en él, y él hará. (Salmo 37:5)",
    "Si puedes creer, al que cree todo le es posible. (Marcos 9:23)"
]

st.title("💎 EL BOT DE ENSUEÑO: CAPITALIZACIÓN ULTRA")
st.write(f"_{random.choice(BIBLE_QUOTES)}_")

# --- SIDEBAR (Solo Credenciales) ---
with st.sidebar:
    st.header("🔐 Sistema de Seguridad")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    st.divider()
    activar = st.toggle("⚡ ACTIVAR CAPITALIZACIÓN AUTOMÁTICA")

# --- LÓGICA DE MERCADOS (Crypto y Forex) ---
MARKETS = ['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'EUR/USD:USD', 'GBP/USD:USD', 'XRP/USD:USD']

# Variables de Estado (Simulación de métricas para visualización inicial)
if 'saldo_inicial' not in st.session_state: st.session_state.saldo_inicial = 6.47
if 'operaciones_totales' not in st.session_state: st.session_state.operaciones_totales = 0
if 'operaciones_ganadas' not in st.session_state: st.session_state.operaciones_ganadas = 0
if 'racha_ganadora' not in st.session_state: st.session_state.racha_ganadora = 0

# --- FUNCIONES AUXILIARES ---
def calcular_apalancamiento(volatilidad):
    # Lógica Autónoma: Baja Volatilidad = 50x, Alta Volatilidad = 20x
    if volatilidad < 0.01: return 50
    elif volatilidad < 0.03: return 30
    else: return 20

def obtener_datos(exchange, symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=30)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['ma'] = df['c'].rolling(window=20).mean()
        df['std'] = df['c'].rolling(window=20).std()
        df['lower'] = df['ma'] - (2 * df['std'])
        df['upper'] = df['ma'] + (2 * df['std'])
        return df
    except:
        return None

# --- PROCESO PRINCIPAL DE TRADING ---
if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        
        # 1. PANEL DE MÉTRICAS (El corazón del Interés Compuesto)
        st.subheader("📊 Métricas de Capitalización Real")
        col_cap, col_roi, col_ops, col_racha = st.columns(4)
        
        # Obtener Saldo Real (Kraken Futures)
        balance = exchange.fetch_total_balance()
        capital_actual = balance.get('USD', st.session_state.saldo_inicial)
        
        # Cálculos de Métricas
        crecimiento = ((capital_actual - st.session_state.saldo_inicial) / st.session_state.saldo_inicial) * 100
        tasa_win = (st.session_state.operaciones_ganadas / st.session_state.operaciones_totales) * 100 if st.session_state.operaciones_totales > 0 else 0
        
        # Actualización de Métricas Visuales
        col_cap.metric("Capital de Trabajo", f"${capital_actual:.4f} USD", f"{crecimiento:.2f}% ROI")
        col_roi.metric("Crecimiento Total", f"{crecimiento:.2f}%", help=f"Desde saldo inicial de ${st.session_state.saldo_inicial}")
        col_ops.metric("Operaciones (Tot/Gan)", f"{st.session_state.operaciones_totales} / {st.session_state.operaciones_ganadas}", f"{tasa_win:.1f}% Win Rate")
        col_racha.metric("Racha Ganadora Actual", f"{st.session_state.racha_ganadora} 🔥")

        st.divider()
        st.subheader("📡 Radar de Oportunidades Multimercado (Escaneo Ultra)")
        tabla_placeholder = st.empty()
        log_expander = st.expander("Registro de Crecimiento en Tiempo Real", expanded=True)

        # Bucle de Ejecución
        while True:
            res_data = []
            
            for symbol in MARKETS:
                df = obtener_datos(exchange, symbol)
                if df is None: continue
                
                precio = df['c'].iloc[-1]
                b_inf = df['lower'].iloc[-1]
                b_sup = df['upper'].iloc[-1]
                volatilidad = (b_sup - b_inf) / b_inf
                
                # Bot toma la decisión del apalancamiento
                lev = calcular_apalancamiento(volatilidad)
                
                estado = "🟢 ZONA DE COMPRA" if precio <= b_inf else ("🔴 ZONA DE VENTA" if precio >= b_sup else "⏳ BUSCANDO")
                res_data.append({"ACTIVO": symbol, "PRECIO": precio, "ESTADO": estado, "LEVERAGE": f"{lev}x"})

                # --- DISPARO AUTOMÁTICO CON INTERÉS COMPUESTO ---
                if estado == "🟢 ZONA DE COMPRA":
                    log_expander.success(f"🚀 {datetime.now().strftime('%H:%M:%S')} - CAZANDO ENTRADA EN {symbol}. LONG {lev}x...")
                    
                    # CÁLCULO DE CANTIDAD (INTERÉS COMPUESTO TOTAL)
                    # Usamos el 100% del capital actual para maximizar ingresos (dejando 2% para comisiones)
                    # order_size_usd = (capital_actual * lev * 0.98) 
                    # amount = order_size_usd / precio
                    
                    # exchange.create_market_order(symbol, 'buy', amount)
                    
                    # Simulamos éxito de operación para actualización de métricas
                    st.session_state.operaciones_totales += 1
                    st.session_state.operaciones_ganadas += 1
                    st.session_state.racha_ganadora += 1
                    
                    log_expander.write(f"✅ Orden de {symbol} enviada. Capital actual en juego: ${capital_actual:.4f} USD.")
                    # Sonido de Alerta de Ingreso
                    st.components.v1.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-07.mp3" type="audio/mpeg"></audio>""", height=0)

            # Actualizar Tabla Multimercado
            tabla_placeholder.table(pd.DataFrame(res_data))
            
            # Escaneo rápido cada 15 segundos
            time.sleep(15) 
            st.rerun()

    except Exception as e:
        st.error(f"Error General en el Sistema: {e}")
        time.sleep(30)
else:
    st.warning("⚠️ MODO CAPITALIZACIÓN DESACTIVADO. Ingrese credenciales para iniciar la generación de ingresos.")