import streamlit as st
import ccxt
import pandas as pd
import time
import threading
from datetime import datetime
import random
from collections import defaultdict

# Configuración de la página
st.set_page_config(
    page_title="💎 El Bot de Ensueño Ultra 💎",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
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
if 'open_positions' not in st.session_state:
    st.session_state.open_positions = {}
if 'bot_thread' not in st.session_state:
    st.session_state.bot_thread = None

@st.cache_resource
def get_bot_engine():
    """Motor del bot que corre en segundo plano"""
    return BotEngine()

class BotEngine:
    def __init__(self):
        self.running = False
        self.exchange = None
        self.log_messages = []
        self.open_positions = {}
        self.last_quote_time = time.time()
        
    def log(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        msg = f"[{ts}] {message}"
        self.log_messages.append(msg)
        if len(self.log_messages) > 100:
            self.log_messages.pop(0)
    
    def initialize_exchange(self, api_key, api_secret):
        """Inicializa la conexión con Kraken Futures"""
        try:
            self.exchange = ccxt.krakenfutures({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
            })
            self.log("✅ Conexión con Kraken Futures establecida.")
            return True
        except Exception as e:
            self.log(f"❌ Error de conexión: {str(e)}")
            return False
    
    def audit_open_positions(self):
        """Auditoría de posiciones abiertas al iniciar"""
        try:
            if not self.exchange:
                return
            
            positions = self.exchange.fetch_positions()
            self.log("🔍 Auditando posiciones abiertas...")
            
            for pos in positions:
                if pos.get('contracts', 0) > 0:
                    symbol = pos['symbol']
                    contracts = pos['contracts']
                    entry_price = pos.get('contractSize', 0)
                    current_price = pos.get('markPrice', 0)
                    
                    self.open_positions[symbol] = {
                        'contracts': contracts,
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'side': pos.get('side', 'long'),
                        'pnl': pos.get('percentage', 0)
                    }
                    
                    self.log(f"📍 Posición abierta encontrada: {symbol} | {contracts} contratos | PnL: {pos.get('percentage', 0):.2f}%")
            
            if not self.open_positions:
                self.log("✅ No hay posiciones abiertas. Listo para nuevas operaciones.")
        except Exception as e:
            self.log(f"⚠️ Error en auditoría: {str(e)}")
    
    def get_balance(self):
        """Obtiene el saldo actual de la cuenta"""
        try:
            if not self.exchange:
                return 0.0
            balance = self.exchange.fetch_total_balance()
            return balance.get('USD', 0.0)
        except:
            return 0.0
    
    def check_and_close_positions(self):
        """Verifica y cierra posiciones según TP o señal contraria"""
        try:
            if not self.exchange or not self.open_positions:
                return
            
            for symbol in list(self.open_positions.keys()):
                pos = self.open_positions[symbol]
                
                # Obtener datos del mercado
                bars = self.exchange.fetch_ohlcv(symbol, timeframe='5m', limit=50)
                df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
                
                df['ma'] = df['close'].rolling(window=20).mean()
                df['std'] = df['close'].rolling(window=20).std()
                df['upper'] = df['ma'] + (2 * df['std'])
                df['lower'] = df['ma'] - (2 * df['std'])
                
                last = df.iloc[-1]
                precio_actual = last['close']
                
                # Lógica de cierre
                should_close = False
                close_reason = ""
                
                if pos['side'] == 'long':
                    # Para LONG: cerrar si toca banda superior (TP) o si baja mucho
                    if precio_actual >= last['upper']:
                        should_close = True
                        close_reason = "TP alcanzado (banda superior)"
                    elif precio_actual < pos['entry_price'] * 0.95:  # Stop loss del 5%
                        should_close = True
                        close_reason = "Stop Loss activado"
                
                elif pos['side'] == 'short':
                    # Para SHORT: cerrar si toca banda inferior (TP) o si sube mucho
                    if precio_actual <= last['lower']:
                        should_close = True
                        close_reason = "TP alcanzado (banda inferior)"
                    elif precio_actual > pos['entry_price'] * 1.05:  # Stop loss del 5%
                        should_close = True
                        close_reason = "Stop Loss activado"
                
                if should_close:
                    try:
                        if pos['side'] == 'long':
                            self.exchange.create_market_sell_order(symbol, pos['contracts'])
                        else:
                            self.exchange.create_market_buy_order(symbol, pos['contracts'])
                        
                        self.log(f"✅ POSICIÓN CERRADA en {symbol} | Razón: {close_reason} | PnL: {pos['pnl']:.2f}%")
                        del self.open_positions[symbol]
                    except Exception as e:
                        self.log(f"❌ Error cerrando posición en {symbol}: {str(e)}")
        
        except Exception as e:
            self.log(f"⚠️ Error en cierre de posiciones: {str(e)}")
    
    def scan_and_trade(self, symbols, base_leverage, max_leverage, investment_per_trade, real_trading_mode):
        """Escanea el mercado y abre operaciones si hay oportunidades"""
        try:
            if not self.exchange:
                return []
            
            # Verificar saldo
            balance = self.get_balance()
            if balance <= 0:
                self.log(f"⚠️ SALDO INSUFICIENTE: ${balance:.2f}. El bot está en pausa hasta tener fondos.")
                return []
            
            scan_data = []
            
            for symbol in symbols:
                try:
                    bars = self.exchange.fetch_ohlcv(symbol, timeframe='5m', limit=50)
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
                        self.log(f"🎯 ¡OPORTUNIDAD ORO en {symbol}! LONG con {lev_sug}x")
                        
                        if real_trading_mode and symbol not in self.open_positions:
                            try:
                                amount_to_buy = investment_per_trade / precio
                                order = self.exchange.create_market_buy_order(symbol, amount_to_buy, {'leverage': lev_sug})
                                self.open_positions[symbol] = {
                                    'contracts': amount_to_buy,
                                    'entry_price': precio,
                                    'side': 'long',
                                    'pnl': 0.0
                                }
                                self.log(f"✅ ORDEN LONG EJECUTADA en {symbol} | Cantidad: {amount_to_buy:.4f} | Apalancamiento: {lev_sug}x")
                            except Exception as trade_e:
                                self.log(f"❌ ERROR al ejecutar LONG en {symbol}: {str(trade_e)}")
                    
                    elif precio >= last['upper']:
                        signal = "🔴 SHORT"
                        prox = 0.0
                        fuerza_ruptura = abs(precio - last['upper']) / last['upper']
                        lev_sug = min(max_leverage, int(base_leverage + (fuerza_ruptura * 1000)))
                        self.log(f"🎯 ¡OPORTUNIDAD ORO en {symbol}! SHORT con {lev_sug}x")
                        
                        if real_trading_mode and symbol not in self.open_positions:
                            try:
                                amount_to_sell = investment_per_trade / precio
                                order = self.exchange.create_market_sell_order(symbol, amount_to_sell, {'leverage': lev_sug})
                                self.open_positions[symbol] = {
                                    'contracts': amount_to_sell,
                                    'entry_price': precio,
                                    'side': 'short',
                                    'pnl': 0.0
                                }
                                self.log(f"✅ ORDEN SHORT EJECUTADA en {symbol} | Cantidad: {amount_to_sell:.4f} | Apalancamiento: {lev_sug}x")
                            except Exception as trade_e:
                                self.log(f"❌ ERROR al ejecutar SHORT en {symbol}: {str(trade_e)}")
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
                    self.log(f"⚠️ Error escaneando {symbol}: {str(e)}")
            
            return scan_data
        
        except Exception as e:
            self.log(f"❌ Error en escaneo: {str(e)}")
            return []

# Header
st.markdown("# 🌟 EL BOT DE ENSUEÑO: ULTRA BENEFICIO 🌟")
st.markdown(f"### ✨ *{st.session_state.current_quote}*")

# Sidebar para configuración
with st.sidebar:
    st.markdown("## ⚙️ CONFIGURACIÓN API")
    api_key = st.text_input("API Key de Kraken Futures", type="password", key="api_key")
    api_secret = st.text_input("API Secret de Kraken Futures", type="password", key="api_secret")
    
    st.markdown("## 📊 PARÁMETROS DEL BOT")
    base_leverage = st.slider("Apalancamiento Base", 5, 20, 10)
    max_leverage = st.slider("Apalancamiento Máximo", 25, 50, 50)
    scan_interval = st.slider("Intervalo de Escaneo (segundos)", 3, 10, 5)
    investment_per_trade = st.number_input("Inversión por Operación (USD)", min_value=5.0, value=10.0, step=5.0)
    
    st.markdown("## ⚠️ MODO DE TRADING REAL")
    real_trading_mode = st.checkbox("Activar Trading Real (¡Usa bajo tu propio riesgo!)")
    if real_trading_mode:
        st.warning("¡ADVERTENCIA! El trading real puede resultar en pérdidas de capital. Empieza con montos pequeños.")

    st.markdown("## 🎯 ACTIVOS A MONITOREAR")
    symbols = st.multiselect(
        "Selecciona los activos",
        ['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'LINK/USD:USD', 'DOT/USD:USD', 'AVAX/USD:USD'],
        default=['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD']
    )

# Obtener el motor del bot
bot_engine = get_bot_engine()

# Métricas principales
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("ESTADO", "🟢 CORRIENDO" if st.session_state.running else "🔴 DETENIDO")

with col2:
    balance = bot_engine.get_balance()
    st.metric("BILLETERA", f"${balance:.2f} USD")

with col3:
    st.metric("POSICIONES ABIERTAS", len(bot_engine.open_positions))

# Botones de control
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("🚀 ACTIVAR MODO ULTRA", key="start_btn", use_container_width=True):
        if not api_key or not api_secret:
            st.error("Por favor, ingresa tu API Key y Secret para iniciar el bot.")
        else:
            if bot_engine.initialize_exchange(api_key, api_secret):
                bot_engine.audit_open_positions()
                st.session_state.running = True
                st.rerun()
            else:
                st.error("No se pudo conectar a Kraken Futures.")

with col_btn2:
    if st.button("🛑 DETENER BOT", key="stop_btn", use_container_width=True):
        st.session_state.running = False
        bot_engine.log("⛔ Bot detenido por el usuario.")
        st.rerun()

st.divider()

# Tabla de escaneo
st.markdown("## 📈 MONITOR DE OPORTUNIDADES EN TIEMPO REAL")

if st.session_state.running:
    scan_results = bot_engine.scan_and_trade(symbols, base_leverage, max_leverage, investment_per_trade, real_trading_mode)
    bot_engine.check_and_close_positions()
    
    if scan_results:
        df_results = pd.DataFrame(scan_results)
        st.dataframe(df_results, use_container_width=True, hide_index=True)
    
    # Mostrar posiciones abiertas
    if bot_engine.open_positions:
        st.markdown("### 📍 POSICIONES ABIERTAS")
        pos_data = []
        for symbol, pos in bot_engine.open_positions.items():
            pos_data.append({
                "ACTIVO": symbol,
                "LADO": pos['side'].upper(),
                "CONTRATOS": f"{pos['contracts']:.4f}",
                "PRECIO ENTRADA": f"${pos['entry_price']:.2f}",
                "PnL": f"{pos['pnl']:.2f}%"
            })
        df_positions = pd.DataFrame(pos_data)
        st.dataframe(df_positions, use_container_width=True, hide_index=True)
    
    time.sleep(scan_interval)
    st.rerun()
else:
    st.info("🔴 El bot está detenido. Presiona 🚀 ACTIVAR MODO ULTRA para comenzar.")

st.divider()

# Log de actividad
st.markdown("## 📋 LOG DE ACTIVIDAD")
if bot_engine.log_messages:
    for msg in bot_engine.log_messages[-30:]:
        st.text(msg)
else:
    st.info("Ningún evento registrado aún.")
