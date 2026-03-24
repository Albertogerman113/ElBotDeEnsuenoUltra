import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="DreamBot: Cosecha 100x", layout="wide")

# Citas de Poder
BIBLE_QUOTES = [
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Todo lo puedo en Cristo que me fortalece. (Filipenses 4:13)",
    "Al que cree todo le es posible. (Marcos 9:23)"
]

st.title("💎 AGENTE DE INGRESOS: COSECHA Y MULTIPLICACIÓN")
st.write(f"_{random.choice(BIBLE_QUOTES)}_")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Activación del Agente")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    meta_diaria = st.number_input("Meta del Día (USD)", value=100.0)
    activar = st.toggle("⚡ INICIAR COSECHA 24/7")

# Mercados optimizados para capital pequeño
MARKETS = ['SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'DOT/USD:USD', 'ETH/USD:USD', 'BTC/USD:USD']

# --- FUNCIÓN DE SEGURIDAD PARA DATOS ---
def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

# --- CUERPO DEL AGENTE ---
if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        
        # Dashboard de Métricas
        col_inv, col_meta, col_prog = st.columns(3)
        inv_placeholder = col_inv.empty()
        meta_placeholder = col_meta.empty()
        prog_placeholder = col_prog.empty()
        
        st.subheader("📡 Operaciones Activas y Análisis")
        pos_table_placeholder = st.empty()
        
        st.divider()
        log_expander = st.expander("📝 Bitácora de Cosecha en Tiempo Real", expanded=True)
        
        while True:
            # 1. ACTUALIZAR BALANCE REAL
            balance = exchange.fetch_total_balance()
            total_equity = balance.get('USD', 6.55)
            # Margen disponible para nuevas órdenes
            try: available_margin = float(balance['info']['marginAvailable'])
            except: available_margin = total_equity * 0.5

            inv_placeholder.metric("Capital Real", f"${total_equity:.4f} USD")
            meta_placeholder.metric("Meta Objetivo", f"${meta_diaria} USD")
            progreso = min(100.0, (total_equity / meta_diaria) * 100)
            prog_placeholder.progress(int(progreso), text=f"Progreso a la Meta: {progreso:.2f}%")

            # 2. GESTIÓN DE POSICIONES (COSECHADOR AL VUELO)
            try:
                posiciones = exchange.fetch_positions()
                activas_list = []
                for p in posiciones:
                    contracts = safe_float(p.get('contracts'))
                    if contracts > 0:
                        pnl_usd = safe_float(p.get('unrealizedPnl'))
                        entry_p = safe_float(p.get('entryPrice'))
                        mark_p = safe_float(p.get('markPrice'))
                        symbol = p.get('symbol')
                        side = str(p.get('side', 'N/A')).upper()
                        
                        # Cálculo de movimiento porcentual
                        if entry_p > 0:
                            move_pct = ((mark_p - entry_p) / entry_p) * 100 if side == 'LONG' else ((entry_p - mark_p) / entry_p) * 100
                        else:
                            move_pct = 0.0

                        activas_list.append({
                            "ACTIVO": symbol,
                            "ROI %": f"{move_pct:.2f}%",
                            "PNL USD": f"${pnl_usd:.4f}",
                            "ESTADO": "🔥 LISTO" if move_pct >= 0.5 else "⏳ CRECIENDO"
                        })

                        # GATILLO DE CIERRE: 0.5% de movimiento = 25% ROI real a 50x
                        if move_pct >= 0.5:
                            side_cierre = 'sell' if side == 'LONG' else 'buy'
                            exchange.create_market_order(symbol, side_cierre, contracts, params={'reduceOnly': True})
                            log_expander.success(f"💰 COSECHADA: {symbol} con +{move_pct:.2f}% de movimiento (${pnl_usd:.2f})")
                            st.components.v1.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-07.mp3"></audio>""", height=0)

                if activas_list:
                    pos_table_placeholder.table(pd.DataFrame(activas_list))
                else:
                    pos_table_placeholder.info("Cuentas limpias. El Agente está buscando nuevas entradas...")
            except Exception as e:
                log_expander.error(f"Error analizando posiciones: {e}")

            # 3. RADAR DE ENTRADA (MÁXIMA PRIORIDAD)
            # Solo busca entrar si no hay demasiadas posiciones (máximo 3 para proteger margen)
            if len(activas_list) < 3:
                for symbol in MARKETS:
                    try:
                        bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=20)
                        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        precio = df['c'].iloc[-1]
                        ma = df['c'].mean()
                        std = df['c'].std()
                        b_inf = ma - (1.6 * std)
                        
                        if precio <= b_inf:
                            # Interés Compuesto: Usa el margen disponible con 40x
                            qty = (available_margin * 40) / precio
                            # Redondear según activo (simplificado)
                            if 'ETH' in symbol: qty = round(qty, 3)
                            elif 'SOL' in symbol or 'DOT' in symbol: qty = round(qty, 1)
                            else: qty = round(qty, 0)
                            
                            if qty > 0:
                                log_expander.info(f"🚀 {symbol} en zona. Abriendo orden real...")
                                exchange.create_market_order(symbol, 'buy', qty)
                                log_expander.success(f"🔥 Orden de {symbol} ejecutada.")
                                time.sleep(5)
                    except: continue

            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Error de Conexión: {e}")
        time.sleep(20)
else:
    st.info("Agente en espera. Activa el switch para iniciar la multiplicación de ingresos.")