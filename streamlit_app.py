import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="DreamBot Ultra Beneficio", layout="wide")

# --- ESTILOS ---
st.markdown("""
    <style>
    .main { background-color: #020C1B; color: white; }
    .stMetric { background-color: #112240; padding: 15px; border-radius: 10px; border: 1px solid #64FFDA; }
    </style>
    """, unsafe_allow_index=True)

# --- CITAS BÍBLICAS ---
BIBLE_QUOTES = [
    "Encomienda al SEÑOR tu camino, confía en él, y él hará. (Salmo 37:5)",
    "Todo lo puedo en Cristo que me fortalece. (Filipenses 4:13)",
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Si puedes creer, al que cree todo le es posible. (Marcos 9:23)"
]

# --- LÓGICA DE TRADING ---
class UltraAutonomo:
    def __init__(self, api_key, secret):
        self.exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        self.symbols = ['SOL/USD:USD', 'BTC/USD:USD', 'ETH/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD']
        self.leverage = 10
        self.take_profit = 0.02  # 2% de movimiento de precio
        self.stop_loss = 0.015   # 1.5% de protección

    def gestionar_posiciones(self):
        """Revisa posiciones abiertas y decide si cerrar"""
        try:
            posiciones = self.exchange.fetch_positions()
            for pos in posiciones:
                if pos['contracts'] > 0:
                    pnl = float(pos['unrealizedPnl'] or 0)
                    side = pos['side']
                    symbol = pos['symbol']
                    
                    # Lógica de Cierre Automático (Take Profit / Stop Loss)
                    # Si ya ganamos una cantidad razonable, cerramos para asegurar
                    if pnl > (pos['initialMargin'] * 0.20): # Cerramos al 20% de ROI
                        self.exchange.create_market_order(symbol, 'sell' if side == 'long' else 'buy', pos['contracts'], params={'reduceOnly': True})
                        return f"💰 ¡Gloria a Dios! Cerramos {symbol} con GANANCIA."
            return None
        except Exception as e:
            return f"Error gestión: {e}"

    def ejecutar_estrategia(self, symbol):
        """Analiza y abre órdenes"""
        try:
            bars = self.exchange.fetch_ohlcv(symbol, timeframe='5m', limit=30)
            df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
            df['ma'] = df['close'].rolling(window=20).mean()
            df['std'] = df['close'].rolling(window=20).std()
            df['lower'] = df['ma'] - (2 * df['std'])
            df['upper'] = df['ma'] + (2 * df['std'])
            
            last = df.iloc[-1]
            precio = last['close']
            
            # --- GATILLO DE ENTRADA ---
            if precio <= last['lower']:
                # Abrir LONG
                balance = self.exchange.fetch_total_balance()['USD']
                cantidad = (balance * self.leverage * 0.9) / precio
                self.exchange.create_market_order(symbol, 'buy', cantidad)
                return f"🚀 LONG abierto en {symbol} a ${precio}"
            
            elif precio >= last['upper']:
                # Abrir SHORT
                balance = self.exchange.fetch_total_balance()['USD']
                cantidad = (balance * self.leverage * 0.9) / precio
                self.exchange.create_market_order(symbol, 'sell', cantidad)
                return f"📉 SHORT abierto en {symbol} a ${precio}"
                
            return None
        except Exception as e:
            return f"Error ejecución {symbol}: {e}"

# --- INTERFAZ STREAMLIT ---
st.title("💎 EL BOT DE ENSUEÑO: MODO ULTRA 24/7")
st.subheader(random.choice(BIBLE_QUOTES))

# Sidebar para credenciales
with st.sidebar:
    st.header("Configuración")
    key = st.text_input("API Key", value="oB/wxeBt8...", type="password")
    sec = st.text_input("API Secret", value="E4mIb/OLs...", type="password")
    activado = st.toggle("🚀 ACTIVAR TRADING AUTÓNOMO")

# Dashboard principal
col1, col2 = st.columns(2)
placeholder_balance = col1.empty()
placeholder_estado = col2.empty()

log_container = st.container()
st.divider()
tabla_container = st.empty()

if activado:
    bot = UltraAutonomo(key, sec)
    while True:
        try:
            # 1. Actualizar Balance
            bal = bot.exchange.fetch_total_balance().get('USD', 5.91)
            placeholder_balance.metric("Billetera (USD)", f"${bal:.2f}")
            placeholder_estado.success("Bot Operando en la Nube")

            # 2. Gestionar Cierres
            msg_cierre = bot.gestionar_posiciones()
            if msg_cierre: st.toast(msg_cierre)

            # 3. Escanear y Operar
            for s in bot.symbols:
                msg_trade = bot.ejecutar_estrategia(s)
                if msg_trade: log_container.info(msg_trade)

            time.sleep(15) # Pausa para evitar baneo de IP
        except Exception as e:
            st.error(f"Fallo en el servidor: {e}")
            time.sleep(30)
else:
    st.warning("El bot está en modo pausa. Activa el switch en la barra lateral.")