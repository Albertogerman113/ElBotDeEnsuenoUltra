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
        try:
            if not self.exchange:
                return
            
            positions = self.exchange.fetch_positions()
            self.log("🔍 Auditando posiciones abiertas...")
            self.open_positions = {} # Limpiar antes de auditar
            
            for pos in positions:
                contracts = float(pos.get('contracts', 0))
                if contracts != 0:
                    symbol = pos.get('symbol', 'Unknown')
                    
                    # EXTRACCIÓN PROFUNDA DE PRECIO DE ENTRADA
                    # Kraken Futures a veces lo pone en 'entryPrice', otras en 'avgEntryPrice'
                    # o dentro del diccionario 'info'
                    info = pos.get('info', {})
                    entry_price = float(pos.get('entryPrice', 0) or 
                                      pos.get('avgEntryPrice', 0) or 
                                      info.get('entryPrice', 0) or 
                                      info.get('price', 0) or 0)
                    
                    # Si sigue siendo 0, intentamos obtenerlo del historial de órdenes (último recurso)
                    if entry_price == 0:
                        self.log(f"⚠️ Precio de entrada no encontrado para {symbol}, usando precio actual temporalmente.")
                        ticker = self.exchange.fetch_ticker(symbol)
                        entry_price = float(ticker['last'])
                    
                    current_price = float(pos.get('markPrice', 0) or 0)
                    side = pos.get('side', 'long').lower()
                    
                    self.open_positions[symbol] = {
                        'contracts': abs(contracts),
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'side': side,
                        'pnl': 0.0 # Se calculará dinámicamente
                    }
                    self.log(f"📍 Posición: {symbol} | {side.upper()} | Entrada: ${entry_price:.4f}")
            
            if not self.open_positions:
                self.log("✅ No hay posiciones abiertas.")
        except Exception as e:
            self.log(f"⚠️ Error en auditoría: {str(e)}")
    
    def get_balance(self):
        try:
            if not self.exchange:
                return 0.0
            balance = self.exchange.fetch_total_balance()
            return float(balance.get('USD', 0.0))
        except:
            return 0.0
    
    def check_and_close_positions(self):
        try:
            if not self.exchange or not self.open_positions:
                return
            
            for symbol in list(self.open_positions.keys()):
                pos = self.open_positions[symbol]
                
                # TICKER FORZADO: Obtener precio actual real del mercado
                ticker = self.exchange.fetch_ticker(symbol)
                precio_actual = float(ticker['last'])
                pos['current_price'] = precio_actual
                
                # CÁLCULO MANUAL DE PNL % (Soporte para Shorts)
                if pos['entry_price'] > 0:
                    if pos['side'] == 'long':
                        pos['pnl'] = ((precio_actual - pos['entry_price']) / pos['entry_price']) * 100
                    else: # short
                        pos['pnl'] = ((pos['entry_price'] - precio_actual) / pos['entry_price']) * 100
                
                # Obtener Bandas de Bollinger para decisión de cierre
                bars = self.exchange.fetch_ohlcv(symbol, timeframe='5m', limit=50)
                df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
                df['ma'] = df['close'].rolling(window=20).mean()
                df['std'] = df['close'].rolling(window=20).std()
                df['upper'] = df['ma'] + (2 * df['std'])
                df['lower'] = df['ma'] - (2 * df['std'])
                
                last = df.iloc[-1]
                
                should_close = False
                reason = ""
                
                if pos['side'] == 'long':
                    if precio_actual >= last['upper']:
                        should_close = True
                        reason = "TP (Banda Superior)"
                    elif precio_actual < pos['entry_price'] * 0.95:
                        should_close = True
                        reason = "Stop Loss (5%)"
                elif pos['side'] == 'short':
                    if precio_actual <= last['lower']:
                        should_close = True
                        reason = "TP (Banda Inferior)"
                    elif precio_actual > pos['entry_price'] * 1.05:
                        should_close = True
                        reason = "Stop Loss (5%)"
                
                if should_close:
                    try:
                        if pos['side'] == 'long':
                            self.exchange.create_market_sell_order(symbol, pos['contracts'])
                        else:
                            self.exchange.create_market_buy_order(symbol, pos['contracts'])
                        self.log(f"✅ CERRADA: {symbol} | {reason} | PnL: {pos['pnl']:.2f}%")
                        del self.open_positions[symbol]
                    except Exception as e:
                        self.log(f"❌ Error cerrando {symbol}: {str(e)}")
        except Exception as e:
            self.log(f"⚠️ Error en gestión de cierre: {str(e)}")
    
    def scan_and_trade(self, symbols, base_leverage, max_leverage, investment, real_mode):
        try:
            if not self.exchange: return []
            balance = self.get_balance()
            if balance <= 0:
                self.log(f"⚠️ SALDO 0. Pausado.")
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
                    precio = float(last['close'])
                    dist_inf = ((precio - last['lower']) / last['lower']) * 100
                    dist_sup = ((last['upper'] - precio) / precio) * 100
                    
                    signal, prox, lev = "ESPERANDO...", 0.0, base_leverage
                    
                    if precio <= last['lower']:
                        signal, prox = "🟢 LONG", 0.0
                        lev = min(max_leverage, int(base_leverage + (abs(precio - last['lower'])/last['lower'] * 1000)))
                        if real_mode and symbol not in self.open_positions:
                            amt = investment / precio
                            self.exchange.create_market_buy_order(symbol, amt, {'leverage': lev})
                            self.open_positions[symbol] = {'contracts': amt, 'entry_price': precio, 'side': 'long', 'pnl': 0.0}
                            self.log(f"🚀 LONG: {symbol} {lev}x")
                    elif precio >= last['upper']:
                        signal, prox = "🔴 SHORT", 0.0
                        lev = min(max_leverage, int(base_leverage + (abs(precio - last['upper'])/last['upper'] * 1000)))
                        if real_mode and symbol not in self.open_positions:
                            amt = investment / precio
                            self.exchange.create_market_sell_order(symbol, amt, {'leverage': lev})
                            self.open_positions[symbol] = {'contracts': amt, 'entry_price': precio, 'side': 'short', 'pnl': 0.0}
                            self.log(f"🚀 SHORT: {symbol} {lev}x")
                    else:
                        if dist_inf < dist_sup: signal, prox = "📍 CERCA LONG", dist_inf
                        else: signal, prox = "📍 CERCA SHORT", dist_sup
                        if prox < 0.1: lev = 25
                    
                    scan_data.append({"ACTIVO": symbol, "PRECIO": f"${precio:.2f}", "ESTADO": signal, "FALTA %": f"{prox:.3f}%", "LEV": f"{lev}x"})
                except: continue
            return scan_data
        except: return []

@st.cache_resource
def get_bot_engine():
    return BotEngine()

bot_engine = get_bot_engine()

# Header
st.markdown("# 🌟 EL BOT DE ENSUEÑO: ULTRA BENEFICIO 🌟")
st.markdown(f"### ✨ *{st.session_state.current_quote}*")

# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ CONFIGURACIÓN")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    base_lev = st.slider("Lev Base", 5, 20, 10)
    max_lev = st.slider("Lev Max", 25, 50, 50)
    inv = st.number_input("Inversión (USD)", min_value=5.0, value=10.0)
    real_mode = st.checkbox("TRADING REAL")
    symbols = st.multiselect("Activos", ['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD'], default=['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD'])

# Métricas
c1, c2, c3 = st.columns(3)
c1.metric("ESTADO", "🟢 CORRIENDO" if st.session_state.running else "🔴 DETENIDO")
c2.metric("BILLETERA", f"${bot_engine.get_balance():.2f}")
c3.metric("POSICIONES", len(bot_engine.open_positions))

# Controles
cb1, cb2 = st.columns(2)
if cb1.button("🚀 INICIAR", use_container_width=True):
    if api_key and api_secret:
        if bot_engine.initialize_exchange(api_key, api_secret):
            bot_engine.audit_open_positions()
            st.session_state.running = True
            st.rerun()
if cb2.button("🛑 DETENER", use_container_width=True):
    st.session_state.running = False
    st.rerun()

st.divider()

# Tablas
if st.session_state.running:
    # Primero gestionamos posiciones para actualizar PnL
    bot_engine.check_and_close_positions()
    # Luego escaneamos nuevas oportunidades
    res = bot_engine.scan_and_trade(symbols, base_lev, max_lev, inv, real_mode)
    
    if res: st.table(pd.DataFrame(res))
    
    if bot_engine.open_positions:
        st.markdown("### 📍 POSICIONES ABIERTAS")
        pos_list = []
        for s, p in bot_engine.open_positions.items():
            pnl_val = p.get('pnl', 0.0)
            pos_list.append({
                "ACTIVO": s,
                "LADO": p['side'].upper(),
                "CONTRATOS": f"{p['contracts']:.4f}",
                "ENTRADA": f"${p['entry_price']:.4f}",
                "PRECIO ACTUAL": f"${p['current_price']:.4f}",
                "PnL %": f"{pnl_val:.2f}%"
            })
        st.table(pd.DataFrame(pos_list))
    
    # Actualizar cita
    if time.time() - st.session_state.last_quote_time > 60:
        st.session_state.current_quote = random.choice(BIBLE_QUOTES)
        st.session_state.last_quote_time = time.time()
    
    time.sleep(5)
    st.rerun()

st.divider()
st.markdown("## 📋 LOG")
for m in bot_engine.log_messages[-20:]: st.text(m)
