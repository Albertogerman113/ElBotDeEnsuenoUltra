import streamlit as st
import ccxt
import pandas as pd
import time
import threading
from datetime import datetime
import random

# Configuración de la página
st.set_page_config(
    page_title="💎 El Bot de Ensueño Ultra 💎",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado para móviles
st.markdown("""
    <style>
        body {
            background-color: #020C1B;
            color: #CCD6F6;
        }
        .main {
            background-color: #020C1B;
        }
        .stButton > button {
            background-color: #10B981;
            color: white;
            font-weight: bold;
            border-radius: 8px;
            padding: 10px 20px;
        }
        .stButton > button:hover {
            background-color: #059669;
        }
        .metric-card {
            background-color: #112240;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #64FFDA;
        }
    </style>
""", unsafe_allow_html=True)

# Citas Bíblicas
BIBLE_QUOTES = [
    "Encomienda al SEÑOR tu camino, confía en él, y él hará. (Salmo 37:5)",
    "Todo lo puedo en Cristo que me fortalece. (Filipenses 4:13)",
    "El SEÑOR es mi pastor; nada me faltará. (Salmo 23:1)",
    "Mira que te mando que te esfuerces y seas valiente. (Josué 1:9)",
    "Pedid, y se os dará; buscad, y hallaréis. (Mateo 7:7)",
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Porque yo sé los pensamientos que tengo acerca de vosotros, dice Jehová. (Jeremías 29:11)",
    "El que confía en el SEÑOR prosperará. (Proverbios 28:25)",
    "No te afanes por el día de mañana. (Mateo 6:34)",
    "Si puedes creer, al que cree todo le es posible. (Marcos 9:23)",
    "Bienaventurado el hombre que confía en el SEÑOR. (Proverbios 16:20)",
    "Deléitate asimismo en Jehová, y él te concederá los deseos de tu corazón. (Salmo 37:4)"
]

# Inicializar sesión
if 'running' not in st.session_state:
    st.session_state.running = False
if 'log_messages' not in st.session_state:
    st.session_state.log_messages = []
if 'current_quote' not in st.session_state:
    st.session_state.current_quote = random.choice(BIBLE_QUOTES)
if 'last_quote_time' not in st.session_state:
    st.session_state.last_quote_time = time.time()
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = []

# Header
st.markdown("# 🌟 EL BOT DE ENSUEÑO: ULTRA BENEFICIO 🌟")
st.markdown(f"### ✨ *{st.session_state.current_quote}*")

# Sidebar para configuración
with st.sidebar:
    st.markdown("## ⚙️ CONFIGURACIÓN API")
    api_key = st.text_input("oB/wxeBt8LMw9QndCptFxGgCWAUVv6Tr2VyCm7mnZ8+s8BMOn4rdWy4a", type="password", key="api_key")
    api_secret = st.text_input("E4mIb/OLs5Gb/St+ul5kXw7hWyw+WzW6vr8OM8OuFrZYsGMsplF4IE4UlTqv1YZztlkfwQLrhElbF9b6CwUjtGAA", type="password", key="api_secret")
    
    st.markdown("## 📊 PARÁMETROS DEL BOT")
    base_leverage = st.slider("Apalancamiento Base", 5, 20, 10)
    max_leverage = st.slider("Apalancamiento Máximo", 25, 50, 50)
    scan_interval = st.slider("Intervalo de Escaneo (segundos)", 3, 10, 5)
    
    st.markdown("## 🎯 ACTIVOS A MONITOREAR")
    symbols = st.multiselect(
        "Selecciona los activos",
        ['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'LINK/USD:USD', 'DOT/USD:USD', 'AVAX/USD:USD'],
        default=['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD']
    )

# Métricas principales
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("ESTADO", "🟢 CONECTADO" if st.session_state.running else "🔴 DESCONECTADO")

with col2:
    st.metric("BILLETERA", "$0.00 USD", delta="En tiempo real")

with col3:
    st.metric("APALANCAMIENTO", f"{base_leverage}x - {max_leverage}x", delta="Dinámico")

# Botones de control
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("🚀 ACTIVAR MODO ULTRA", key="start_btn", use_container_width=True):
        st.session_state.running = True
        st.session_state.log_messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Bot iniciado. Que Dios bendiga las operaciones.")
        st.rerun()

with col_btn2:
    if st.button("🛑 DETENER BOT", key="stop_btn", use_container_width=True):
        st.session_state.running = False
        st.session_state.log_messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⛔ Bot detenido.")
        st.rerun()

st.divider()

# Tabla de escaneo
st.markdown("## 📈 MONITOR DE OPORTUNIDADES EN TIEMPO REAL")

if st.session_state.running and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        
        # Obtener balance
        balance = exchange.fetch_total_balance()
        usd_balance = balance.get('USD', 0.0)
        
        # Actualizar cita cada minuto
        current_time = time.time()
        if current_time - st.session_state.last_quote_time > 60:
            st.session_state.current_quote = random.choice(BIBLE_QUOTES)
            st.session_state.last_quote_time = current_time
            st.rerun()
        
        # Escanear activos
        scan_data = []
        for symbol in symbols:
            try:
                bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=50)
                df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
                
                df['ma'] = df['close'].rolling(window=20).mean()
                df['std'] = df['close'].rolling(window=20).std()
                df['upper'] = df['ma'] + (2 * df['std'])
                df['lower'] = df['ma'] - (2 * df['std'])
                
                last = df.iloc[-1]
                precio = last['close']
                
                dist_inf = ((precio - last['lower']) / last['lower']) * 100
                dist_sup = ((last['upper'] - precio) / precio) * 100
                
                signal = "ESPERANDO..."
                prox = 0.0
                lev_sug = base_leverage
                
                if precio <= last['lower']:
                    signal = "🟢 LONG"
                    prox = 0.0
                    fuerza_ruptura = abs(precio - last['lower']) / last['lower']
                    lev_sug = min(max_leverage, int(base_leverage + (fuerza_ruptura * 1000)))
                    st.session_state.log_messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎯 ¡OPORTUNIDAD ORO en {symbol}! LONG con {lev_sug}x")
                elif precio >= last['upper']:
                    signal = "🔴 SHORT"
                    prox = 0.0
                    fuerza_ruptura = abs(precio - last['upper']) / last['upper']
                    lev_sug = min(max_leverage, int(base_leverage + (fuerza_ruptura * 1000)))
                    st.session_state.log_messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎯 ¡OPORTUNIDAD ORO en {symbol}! SHORT con {lev_sug}x")
                else:
                    if dist_inf < dist_sup:
                        signal = "📍 CERCA LONG"
                        prox = dist_inf
                        if prox < 0.1: lev_sug = 25
                    else:
                        signal = "📍 CERCA SHORT"
                        prox = dist_sup
                        if prox < 0.1: lev_sug = 25
                
                scan_data.append({
                    "ACTIVO": symbol,
                    "PRECIO": f"${precio:.2f}",
                    "ESTADO": signal,
                    "FALTA %": f"{prox:.3f}%",
                    "APALANCAMIENTO": f"{lev_sug}x"
                })
            except Exception as e:
                st.session_state.log_messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Error escaneando {symbol}: {str(e)}")
        
        # Mostrar tabla
        df_results = pd.DataFrame(scan_data)
        st.dataframe(df_results, use_container_width=True, hide_index=True)
        
        # Mostrar balance
        st.success(f"💰 **BILLETERA ACTUAL: ${usd_balance:.2f} USD**")
        
    except Exception as e:
        st.error(f"❌ Error de conexión: {str(e)}")
        st.info("Verifica que tus credenciales de Kraken Futures sean correctas.")
else:
    if not st.session_state.running:
        st.info("🔴 El bot está detenido. Presiona 🚀 ACTIVAR MODO ULTRA para comenzar.")
    else:
        st.warning("⚠️ Ingresa tus credenciales de API en la barra lateral para continuar.")

st.divider()

# Log de actividad
st.markdown("## 📋 LOG DE ACTIVIDAD")
log_container = st.container()

with log_container:
    if st.session_state.log_messages:
        for msg in st.session_state.log_messages[-20:]:  # Mostrar últimos 20 mensajes
            st.text(msg)
    else:
        st.info("Ningún evento registrado aún.")

# Auto-refresh cada 5 segundos si está corriendo
if st.session_state.running:
    time.sleep(5)
    st.rerun()
