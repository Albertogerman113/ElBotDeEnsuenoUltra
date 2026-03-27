import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime
import logging

# --- CONFIGURACIÓN DE LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE STREAMLIT ---
st.set_page_config(page_title="Sniper V5: El Guerrero de la Luz", layout="wide")

# --- PARÁMETROS DE ESTRATEGIA Y RIESGO ---
# "Porque Jehová da la sabiduría, y de su boca viene el conocimiento y la inteligencia." (Proverbios 2:6)
RISK_PER_TRADE_PCT = 0.02  # Arriesgamos el 2% del capital por operación
LEVERAGE = 10              # Apalancamiento máximo sugerido
ATR_PERIOD = 14            # Periodo para el ATR (volatilidad)
ATR_MULTIPLIER_SL = 2.0    # Multiplicador ATR para el Stop Loss
RR_RATIO = 2.5             # Ratio Riesgo:Recompensa objetivo (1:2.5)
EMA_FAST = 20              # EMA rápida para tendencia a corto plazo
EMA_SLOW = 200             # EMA lenta para tendencia maestra
MAX_TRADES = 1             # Número máximo de operaciones simultáneas
TIMEFRAME = '15m'          # Temporalidad de las velas

# --- FUNCIONES DE UTILIDAD ---
def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

def get_indicators(df):
    c = df['c'].astype(float)
    h = df['h'].astype(float)
    l = df['l'].astype(float)
    
    # Tendencia Maestra (EMA 200) y Tendencia Rápida (EMA 20)
    df['ema200'] = c.ewm(span=EMA_SLOW, adjust=False).mean()
    df['ema20'] = c.ewm(span=EMA_FAST, adjust=False).mean()
    
    # Impulso (MACD Estándar)
    df['ema12'] = c.ewm(span=12, adjust=False).mean()
    df['ema26'] = c.ewm(span=26, adjust=False).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['hist'] = df['macd'] - df['signal']
    
    # Volatilidad (ATR)
    high_low = h - l
    high_close = np.abs(h - c.shift())
    low_close = np.abs(l - c.shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr'] = true_range.rolling(window=ATR_PERIOD).mean()
    
    # Acción del Precio: Máximos y Mínimos de 20 velas
    df['high_20'] = h.rolling(20).max()
    df['low_20'] = l.rolling(20).min()
    
    return df

def calculate_position_size(equity, price, sl_dist, risk_pct):
    # "El que es fiel en lo muy poco, también en lo mucho es fiel" (Lucas 16:10)
    risk_amount = equity * risk_pct
    if sl_dist == 0: return 0
    qty = risk_amount / sl_dist
    return qty

# --- INTERFAZ DE USUARIO ---
st.title("🛡️ SNIPER V5: EL GUERRERO DE LA LUZ")
st.write(f"_{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Operando con la Bendición de Dios_")

with st.sidebar:
    st.header("Configuración de Combate")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    risk_input = st.slider("Riesgo por Operación (%)", 0.5, 5.0, RISK_PER_TRADE_PCT * 100) / 100
    leverage_input = st.number_input("Apalancamiento", 1, 50, LEVERAGE)
    activar = st.toggle("⚡ INICIAR ALGORITMO DE VICTORIA", value=False)

# --- LÓGICA PRINCIPAL ---
if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey': api_key, 
            'secret': api_secret, 
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        placeholder = st.empty()
        
        while True:
            with placeholder.container():
                # 1. ACTUALIZAR BALANCE Y ESTADO
                balance = exchange.fetch_total_balance()
                equity = safe_float(balance.get('USD', 10.0))
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Capital de Batalla", f"${equity:.2f} USD")
                
                # 2. GESTIÓN DE POSICIONES ACTIVAS
                posiciones = exchange.fetch_positions()
                n_activas = 0
                posicion_actual = None
                
                for p in posiciones:
                    qty = safe_float(p.get('contracts', 0))
                    if qty > 0:
                        n_activas += 1
                        posicion_actual = p
                        sym = p['symbol']
                        side = p['side'].upper()
                        entry = safe_float(p['entryPrice'])
                        mark = safe_float(p['markPrice'])
                        pnl = safe_float(p['unrealizedPnl'])
                        
                        move_pct = ((mark - entry) / entry * 100) if side == 'LONG' else ((entry - mark) / entry * 100)
                        col2.metric(f"Posición: {sym}", f"{side} {qty} cts")
                        col3.metric("PnL Actual", f"${pnl:.2f} ({move_pct:.2f}%)")
                        
                        # Salidas por Estrategia (Trailing Stop Mental o TP/SL dinámico)
                        # Aquí se podrían implementar cierres automáticos si no se usan órdenes OCO
                
                # 3. BÚSQUEDA DE NUEVAS OPORTUNIDADES (ACCIÓN DEL PRECIO)
                if n_activas < MAX_TRADES:
                    st.subheader("Buscando Señales de Victoria...")
                    for sym in ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD']:
                        try:
                            bars = exchange.fetch_ohlcv(sym, timeframe=TIMEFRAME, limit=250)
                            df = get_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                            last = df.iloc[-1]
                            prev = df.iloc[-2]
                            
                            price = last['c']
                            atr = last['atr']
                            
                            # --- ESTRATEGIA DE ACCIÓN DEL PRECIO: RUPTURA CON CONFIRMACIÓN ---
                            # 1. Tendencia Maestra Alcista (Precio > EMA 200)
                            # 2. Impulso Confirmado (MACD > Signal y Histograma Creciente)
                            # 3. Ruptura de Máximo de 20 velas con vela de fuerza
                            
                            long_condition = (
                                price > last['ema200'] and          # Tendencia Maestra
                                last['macd'] > last['signal'] and   # Impulso Alcista
                                last['hist'] > prev['hist'] and     # Aceleración
                                price >= last['high_20']            # Ruptura de Resistencia
                            )
                            
                            if long_condition:
                                # Cálculo de SL y TP dinámicos basados en ATR
                                sl_price = price - (atr * ATR_MULTIPLIER_SL)
                                sl_dist = price - sl_price
                                tp_price = price + (sl_dist * RR_RATIO)
                                
                                qty = calculate_position_size(equity, price, sl_dist, risk_input)
                                qty_final = round(qty, 1 if 'SOL' in sym else 0)
                                
                                if qty_final > 0:
                                    st.info(f"🚀 SEÑAL DETECTADA: Comprando {qty_final} {sym}")
                                    # Ejecutar Orden de Mercado
                                    order = exchange.create_market_order(sym, 'buy', qty_final)
                                    
                                    # Establecer SL y TP (Kraken Futures requiere órdenes separadas o params específicos)
                                    # Nota: Para simplicidad en este script, usamos órdenes de mercado y monitoreo mental,
                                    # pero se recomienda usar órdenes de stop/limit reales en producción.
                                    st.success(f"Entrada Exitosa en {sym}. SL: {sl_price:.2f}, TP: {tp_price:.2f}")
                                    logger.info(f"ENTRADA LONG: {sym} a {price}, SL: {sl_price}, TP: {tp_price}")
                                    break # Solo una operación a la vez
                                    
                        except Exception as e:
                            st.error(f"Error analizando {sym}: {e}")
                            continue
                
                else:
                    st.info("🛡️ El Guerrero está en batalla. Monitoreando posición activa...")

            time.sleep(30) # Esperar 30 segundos para la siguiente iteración
            st.rerun()
            
    except Exception as e:
        st.error(f"Error Crítico: {e}")
        st.info("Reintentando en 10 segundos... 'No temas, porque yo estoy contigo' (Isaías 41:10)")
        time.sleep(10)
        st.rerun()
else:
    st.warning("Esperando API Keys y Activación para iniciar la misión.")
    st.info("Recuerda: La disciplina y la gestión de riesgo son tus mejores armas.")
