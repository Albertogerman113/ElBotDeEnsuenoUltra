import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime
import random

# ─────────────────────────────────────────────
#  CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="DreamBot 💎 Cosecha 100x",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@700&display=swap');
html, body, [class*="css"] {
    font-family: 'Share Tech Mono', monospace;
    background-color: #0a0a0f;
    color: #e0ffe0;
}
h1, h2, h3 { font-family: 'Orbitron', monospace; color: #00ff88; }
.stMetric label { color: #aaffcc !important; font-size: 0.75rem; }
.stMetric [data-testid="stMetricValue"] { color: #00ff88 !important; font-size: 1.4rem; font-weight: 700; }
.stProgress > div > div { background: linear-gradient(90deg, #00ff88, #00ccff); border-radius: 4px; }
div[data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #00ff8844; }
.stDataFrame { border: 1px solid #00ff8833; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  CONSTANTES DE PODER
# ─────────────────────────────────────────────
BIBLE_QUOTES = [
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Todo lo puedo en Cristo que me fortalece. (Filipenses 4:13)",
    "Al que cree todo le es posible. (Marcos 9:23)",
    "Porque yo sé los planes que tengo para ustedes... planes para darles futuro y esperanza. (Jeremías 29:11)",
]

# Parámetros Estratégicos - MODIFICADOS
APALANCAMIENTO = 40       # Máximo poder para cuenta de $6-$7 USD
TP_PCT         = 0.5       # Cerramos con 0.5% de movimiento (20% ROI real) para asegurar flujo
MAX_POS        = 4         # Diversificamos en 4 activos para no depender de uno solo

# ─────────────────────────────────────────────
#  HELPERS (Sin cambios en lógica base)
# ─────────────────────────────────────────────
def safe_float(val, default=0.0):
    try: return float(val) if val is not None else default
    except: return default

def round_qty(symbol: str, qty: float) -> float:
    base = symbol.split('/')[0]
    if 'BTC' in base: return round(qty, 3)
    if 'ETH' in base: return round(qty, 2)
    if base in ('SOL', 'DOT', 'LINK', 'AVAX'): return round(qty, 1)
    return round(qty, 0)

def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c = df['c'].astype(float)
    df['rsi'] = 100 - (100 / (1 + (c.diff().clip(lower=0).ewm(span=14).mean() / (-c.diff().clip(upper=0)).ewm(span=14).mean())))
    ma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df['bb_lower'] = ma20 - (1.6 * std20) # Banda más sensible para entrar rápido
    df['bb_upper'] = ma20 + (1.6 * std20)
    return df

# ─────────────────────────────────────────────
#  ESTADO DE SESIÓN
# ─────────────────────────────────────────────
for key, default in [('ganancia_total', 0.0), ('operaciones', []), ('ciclos', 0)]:
    if key not in st.session_state: st.session_state[key] = default

# ─────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────
st.markdown("## 💎 DREAMBOT — AGENTE DE COSECHA 100×")
st.caption(f"_{random.choice(BIBLE_QUOTES)}_")

with st.sidebar:
    st.header("🔐 Configuración")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    meta_diaria = st.number_input("🎯 Meta del Día (USD)", value=100.0)
    activar = st.toggle("⚡ ¡INICIAR COSECHA REAL!", value=False)

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        
        # UI Placeholders
        c1, c2, c3 = st.columns(3)
        ph_cap = c1.empty()
        ph_gan = c2.empty()
        ph_prog = st.empty()
        st.markdown("### 📡 Posiciones Activas (Sin Stop Loss)")
        ph_pos = st.empty()
        log_expander = st.expander("📝 Bitácora de Movimientos", expanded=True)

        while True:
            st.session_state.ciclos += 1
            balance = exchange.fetch_total_balance()
            equity = safe_float(balance.get('USD'))
            avail = safe_float(balance.get('info', {}).get('marginAvailable', equity * 0.5))

            ph_cap.metric("💰 Capital Actual", f"${equity:.4f}")
            ph_gan.metric("📈 Ganancia Sesión", f"${st.session_state.ganancia_total:.4f}")
            prog = min(100.0, (equity / meta_diaria) * 100)
            ph_prog.progress(int(prog), text=f"Camino a los $100: {prog:.2f}%")

            # 1. MONITOREO Y COSECHA (SOLO TAKE PROFIT)
            pos_info = []
            n_pos = 0
            posiciones = exchange.fetch_positions()
            for p in posiciones:
                qty = safe_float(p.get('contracts'))
                if qty > 0:
                    n_pos += 1
                    symbol = p['symbol']
                    side = p['side'].upper()
                    entry = safe_float(p['entryPrice'])
                    mark = safe_float(p['markPrice'])
                    pnl = safe_float(p['unrealizedPnl'])
                    
                    # Movimiento %
                    move = ((mark - entry) / entry * 100) if side == 'LONG' else ((entry - mark) / entry * 100)
                    
                    # LOGICA DE COSECHA: Solo cerramos si hay ganancia (TP)
                    estado = "🔥 COSECHAR" if move >= TP_PCT else "⏳ ESPERANDO VERDE"
                    
                    pos_info.append({"ACTIVO": symbol, "ROI%": f"{move:+.2f}%", "PNL USD": f"${pnl:.4f}", "ESTADO": estado})

                    if estado == "🔥 COSECHAR":
                        side_close = 'sell' if side == 'LONG' else 'buy'
                        exchange.create_market_order(symbol, side_close, qty, params={'reduceOnly': True})
                        st.session_state.ganancia_total += pnl
                        log_expander.success(f"💰 Cosechada ganancia en {symbol}: +${pnl:.2f}")
                        st.components.v1.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-07.mp3"></audio>""", height=0)

            ph_pos.dataframe(pd.DataFrame(pos_info) if pos_info else pd.DataFrame(columns=["Info"]), use_container_width=True)

            # 2. RADAR DE ENTRADA (Misma lógica ganadora)
            if n_pos < MAX_POS:
                markets = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD', 'DOT/USD:USD']
                for sym in markets:
                    try:
                        bars = exchange.fetch_ohlcv(sym, timeframe='5m', limit=30)
                        df = calc_indicators(pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v']))
                        last = df.iloc[-1]
                        
                        # Señal de entrada: RSI bajo y precio toca banda inferior
                        if last['c'] <= last['bb_lower'] and last['rsi'] < 40:
                            qty_to_buy = round_qty(sym, (avail * APALANCAMIENTO * 0.8) / last['c'])
                            if qty_to_buy > 0:
                                exchange.create_market_order(sym, 'buy', qty_to_buy)
                                log_expander.info(f"🚀 Abriendo {sym} para cosecha...")
                                time.sleep(2)
                    except: continue

            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"Sincronizando... {e}")
        time.sleep(10)
        st.rerun()