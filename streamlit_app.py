import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime
import random

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="DreamBot: Cosecha 100x", layout="wide")

# Citas de Poder (Sin alterar)
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
    activar = st.toggle("⚡ ¡INICIAR COSECHA 24/7!")

# Mercados (Tus mercados de confianza)
MARKETS = ['SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'DOT/USD:USD', 'ETH/USD:USD', 'BTC/USD:USD']

# Función de seguridad para evitar errores de tipo de dato
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
        
        # Dashboard de Métricas (Manteniendo tus métricas)
        col_inv, col_meta, col_prog = st.columns(3)
        inv_placeholder = col_inv.empty()
        meta_placeholder = col_meta.empty()
        prog_placeholder = col_prog.empty()
        
        # NUEVA SECCIÓN: MONITOREO DE POSICIONES ACTIVAS
        st.subheader("📡 Operaciones Activas en Kraken (Análisis de ROI)")
        pos_table_placeholder = st.empty()
        
        # RADAR DE PROXIMIDAD (Tu radar de siempre)
        st.subheader("🔍 Radar de Próximas Entradas")
        radar_placeholder = st.empty()
        
        st.divider()
        log_expander = st.expander("📝 Bitácora de Cosecha en Tiempo Real", expanded=True)
        
        while True:
            # 1. ACTUALIZAR BALANCE
            balance = exchange.fetch_total_balance()
            total_equity = balance.get('USD', 6.55)
            try: available_margin = float(balance['info']['marginAvailable'])
            except: available_margin = total_equity * 0.5

            inv_placeholder.metric("Capital Real", f"${total_equity:.4f} USD")
            meta_placeholder.metric("Meta Objetivo", f"${meta_diaria} USD")
            progreso = min(100.0, (total_equity / meta_diaria) * 100)
            prog_placeholder.progress(int(progreso), text=f"Progreso: {progreso:.2f}%")

            # 2. ACTUALIZACIÓN: ANÁLISIS Y CIERRE DE POSICIONES ABIERTAS
            pos_activas_info = []
            try:
                posiciones = exchange.fetch_positions()
                for p in posiciones:
                    contracts = safe_float(p.get('contracts'))
                    if contracts > 0:
                        pnl_usd = safe_float(p.get('unrealizedPnl'))
                        entry_p = safe_float(p.get('entryPrice'))
                        mark_p = safe_float(p.get('markPrice'))
                        symbol = p.get('symbol')
                        side = str(p.get('side', 'N/A')).upper()
                        
                        # Cálculo de ROI basado en movimiento de precio
                        move_pct = 0.0
                        if entry_p > 0:
                            move_pct = ((mark_p - entry_p) / entry_p) * 100 if side == 'LONG' else ((entry_p - mark_p) / entry_p) * 100

                        pos_activas_info.append({
                            "ACTIVO": symbol,
                            "ROI %": f"{move_pct:.2f}%",
                            "PNL USD": f"${pnl_usd:.4f}",
                            "ESTADO": "🔥 COSECHABLE" if move_pct >= 0.5 else "⏳ CRECIENDO"
                        })

                        # GATILLO DE CIERRE AUTOMÁTICO (ROI +25% aprox a 50x)
                        if move_pct >= 0.5:
                            side_cierre = 'sell' if side == 'LONG' else 'buy'
                            exchange.create_market_order(symbol, side_cierre, contracts, params={'reduceOnly': True})
                            log_expander.success(f"💰 COSECHADA: {symbol} con {move_pct:.2f}% de ganancia.")
                            st.components.v1.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-07.mp3"></audio>""", height=0)

                if pos_activas_info:
                    pos_table_placeholder.table(pd.DataFrame(pos_activas_info))
                else:
                    pos_table_placeholder.info("Esperando que el mercado toque zona de entrada...")
            except Exception as e:
                log_expander.warning(f"Sincronizando posiciones... {e}")

            # 3. RADAR DE ENTRADA (MANTENIENDO TU LÓGICA ANTERIOR)
            radar_data = []
            for symbol in MARKETS:
                try:
                    bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=20)
                    df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                    precio = df['c'].iloc[-1]
                    ma = df['c'].mean()
                    std = df['c'].std()
                    b_inf = ma - (1.6 * std)
                    dist = ((precio - b_inf) / b_inf) * 100
                    status = "🔥 ENTRANDO" if precio <= b_inf else "⏳ CAZANDO"
                    radar_data.append({"ACTIVO": symbol, "PRECIO": precio, "DISTANCIA": f"{max(0, dist):.3f}%", "ESTADO": status})

                    # Disparo de nueva orden (solo si hay margen y menos de 3 posiciones)
                    if status == "🔥 ENTRANDO" and len(pos_activas_info) < 3:
                        qty = (available_margin * 40) / precio
                        # Ajuste de decimales por activo
                        if 'ETH' in symbol: qty = round(qty, 3)
                        elif 'SOL' in symbol or 'DOT' in symbol: qty = round(qty, 1)
                        else: qty = round(qty, 0)
                        
                        if qty > 0:
                            exchange.create_market_order(symbol, 'buy', qty)
                            log_expander.success(f"✅ COMPRA REAL: {symbol} ejecutada.")
                except: continue

            if radar_data:
                radar_placeholder.table(pd.DataFrame(radar_data))
            
            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")
        time.sleep(15)
else:
    st.info("Agente en espera. Activa el switch para iniciar.")