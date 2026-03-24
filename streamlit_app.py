import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="DreamBot Ultra", layout="wide")

# --- ESTILOS CORREGIDOS ---
st.markdown("""
    <style>
    .main { background-color: #020C1B; }
    .stMetric { border: 1px solid #64FFDA; padding: 10px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- CITAS BÍBLICAS ---
BIBLE_QUOTES = [
    "Encomienda al SEÑOR tu camino, confía en él, y él hará. (Salmo 37:5)",
    "Todo lo puedo en Cristo que me fortalece. (Filipenses 4:13)",
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Si puedes creer, al que cree todo le es posible. (Marcos 9:23)"
]

# --- CLASE DEL BOT AUTÓNOMO ---
class DreamBotCloud:
    def __init__(self, api_key, secret):
        self.exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        self.symbols = ['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD']
        self.leverage = 10

    def obtener_datos(self, symbol):
        try:
            bars = self.exchange.fetch_ohlcv(symbol, timeframe='5m', limit=30)
            df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
            df['ma'] = df['close'].rolling(window=20).mean()
            df['std'] = df['close'].rolling(window=20).std()
            df['lower'] = df['ma'] - (2 * df['std'])
            df['upper'] = df['ma'] + (2 * df['std'])
            return df
        except:
            return None

    def ejecutar_ciclo(self):
        logs = []
        try:
            # 1. Revisar balance real
            balance = self.exchange.fetch_total_balance()
            usd_actual = balance.get('USD', 0.0)
            
            # 2. Revisar posiciones abiertas para no duplicar
            posiciones = self.exchange.fetch_positions()
            pos_activas = [p['symbol'] for p in posiciones if float(p.get('contracts', 0)) > 0]

            for s in self.symbols:
                df = self.obtener_datos(s)
                if df is None: continue
                
                last = df.iloc[-1]
                precio = last['close']
                
                # LÓGICA DE ENTRADA (Si no hay posición abierta en este activo)
                if s not in pos_activas:
                    if precio <= last['lower']:
                        # ENTRAR LONG
                        qty = (usd_actual * self.leverage * 0.9) / precio
                        self.exchange.create_market_order(s, 'buy', qty)
                        logs.append(f"🟢 {s}: Orden LONG abierta a ${precio}")
                    elif precio >= last['upper']:
                        # ENTRAR SHORT
                        qty = (usd_actual * self.leverage * 0.9) / precio
                        self.exchange.create_market_order(s, 'sell', qty)
                        logs.append(f"🔴 {s}: Orden SHORT abierta a ${precio}")
                
                # LÓGICA DE SALIDA (Si hay posición, revisar profit)
                else:
                    for p in posiciones:
                        if p['symbol'] == s:
                            pnl = float(p.get('unrealizedPnl', 0))
                            # Cerramos si ganamos 15% del margen o perdemos 10%
                            if pnl > (float(p['initialMargin']) * 0.15) or pnl < -(float(p['initialMargin']) * 0.10):
                                side_cierre = 'sell' if p['side'] == 'long' else 'buy'
                                self.exchange.create_market_order(s, side_cierre, p['contracts'], params={'reduceOnly': True})
                                logs.append(f"💰 {s}: Posición cerrada. PNL: ${pnl}")

            return usd_actual, logs
        except Exception as e:
            return 0, [f"❌ Error: {str(e)}"]

# --- INTERFAZ DE USUARIO ---
st.title("💎 EL BOT DE ENSUEÑO: ULTRA")
st.write(f"_{random.choice(BIBLE_QUOTES)}_")

# Configuración en el Sidebar
with st.sidebar:
    st.header("🔐 Credenciales")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    run_bot = st.toggle("🚀 ACTIVAR TRADING")

if run_bot and api_key and api_secret:
    bot = DreamBotCloud(api_key, api_secret)
    
    # Contenedores para actualizar datos
    col1, col2 = st.columns(2)
    with col1:
        metrica_balance = st.empty()
    with col2:
        metrica_tiempo = st.empty()
        
    log_box = st.expander("Ver Monitor de Actividad", expanded=True)
    
    # Bucle de refresco (Streamlit refresca la página para simular 24/7)
    while True:
        saldo, mensajes = bot.ejecutar_ciclo()
        
        metrica_balance.metric("Saldo en Kraken Futures", f"${saldo:.2f} USD")
        metrica_tiempo.text(f"Última actualización: {datetime.now().strftime('%H:%M:%S')}")
        
        for msg in mensajes:
            log_box.write(msg)
            
        time.sleep(30) # Espera 30 segundos entre escaneos
        st.rerun() # Reinicia la app para actualizar datos
else:
    st.info("Ingresa tus llaves y activa el switch para comenzar a operar.")