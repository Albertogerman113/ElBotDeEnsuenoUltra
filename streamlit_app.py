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

# ─── CSS Personalizado ───────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@700&display=swap');

html, body, [class*="css"] {
    font-family: 'Share Tech Mono', monospace;
    background-color: #0a0a0f;
    color: #e0ffe0;
}
h1, h2, h3 { font-family: 'Orbitron', monospace; color: #00ff88; }
.stMetric label  { color: #aaffcc !important; font-size: 0.75rem; }
.stMetric [data-testid="stMetricValue"] { color: #00ff88 !important; font-size: 1.4rem; font-weight: 700; }
.stProgress > div > div { background: linear-gradient(90deg, #00ff88, #00ccff); border-radius: 4px; }
div[data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #00ff8844; }
.stDataFrame { border: 1px solid #00ff8833; border-radius: 8px; }
.stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────
BIBLE_QUOTES = [
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Todo lo puedo en Cristo que me fortalece. (Filipenses 4:13)",
    "Al que cree todo le es posible. (Marcos 9:23)",
    "Porque yo sé los planes que tengo para ustedes... planes para darles futuro y esperanza. (Jeremías 29:11)",
]

MARKETS = [
    'SOL/USD:USD', 'XRP/USD:USD', 'ADA/USD:USD',
    'DOT/USD:USD', 'ETH/USD:USD', 'BTC/USD:USD'
]

# Mínimos de cantidad por símbolo (para Kraken Futures)
MIN_QTY = {
    'BTC': 0.001, 'ETH': 0.01, 'SOL': 0.1,
    'XRP': 1.0,   'ADA': 1.0,  'DOT': 0.1,
}

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except Exception:
        return default


def get_base(symbol: str) -> str:
    """Extrae el activo base del símbolo, ej. 'SOL/USD:USD' → 'SOL'."""
    return symbol.split('/')[0]


def round_qty(symbol: str, qty: float) -> float:
    base = get_base(symbol)
    if 'BTC' in base:  return round(qty, 3)
    if 'ETH' in base:  return round(qty, 2)
    if 'SOL' in base or 'DOT' in base: return round(qty, 1)
    return round(qty, 0)


def calc_indicators(df: pd.DataFrame):
    """
    Calcula:
      - EMA rápida (9) y lenta (21)
      - RSI (14)
      - Bollinger Bands (20, 2σ)
    Devuelve el DataFrame enriquecido.
    """
    c = df['c'].astype(float)

    # EMAs
    df['ema9']  = c.ewm(span=9,  adjust=False).mean()
    df['ema21'] = c.ewm(span=21, adjust=False).mean()

    # RSI
    delta = c.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = gain.ewm(span=14, adjust=False).mean()
    avg_l = loss.ewm(span=14, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))

    # Bollinger
    ma20     = c.rolling(20).mean()
    std20    = c.rolling(20).std()
    df['bb_upper'] = ma20 + 2 * std20
    df['bb_lower'] = ma20 - 2 * std20
    df['bb_mid']   = ma20

    return df


def evaluate_signal(df: pd.DataFrame) -> dict:
    """
    Lógica de señal mejorada:
      LONG  → precio toca BB inferior  + RSI < 35  + EMA9 cruza ↑ EMA21
      SHORT → precio toca BB superior  + RSI > 65  + EMA9 cruza ↓ EMA21
      NONE  → sin señal clara

    Retorna dict con 'signal', 'rsi', 'precio', 'dist_pct', 'ema9', 'ema21'
    """
    last   = df.iloc[-1]
    prev   = df.iloc[-2]

    precio = safe_float(last['c'])
    rsi    = safe_float(last['rsi'])
    ema9   = safe_float(last['ema9'])
    ema21  = safe_float(last['ema21'])
    bb_l   = safe_float(last['bb_lower'])
    bb_u   = safe_float(last['bb_upper'])

    ema_cross_up   = safe_float(prev['ema9']) <= safe_float(prev['ema21']) and ema9 > ema21
    ema_cross_down = safe_float(prev['ema9']) >= safe_float(prev['ema21']) and ema9 < ema21

    dist_pct = ((precio - bb_l) / bb_l * 100) if bb_l > 0 else 999

    if precio <= bb_l and rsi < 38:
        signal = "🔥 LONG"
    elif precio >= bb_u and rsi > 62:
        signal = "⚡ SHORT"
    else:
        signal = "⏳ ESPERA"

    return {
        "signal": signal,
        "rsi":    round(rsi, 1),
        "precio": precio,
        "dist_pct": round(dist_pct, 3),
        "ema9":   round(ema9, 4),
        "ema21":  round(ema21, 4),
    }


def calc_position_size(available_margin: float, precio: float, apalancamiento: int = 20) -> float:
    """
    Usa el 15 % del margen disponible con el apalancamiento configurado.
    Conservador pero suficientemente activo.
    """
    capital_en_riesgo = available_margin * 0.15
    return (capital_en_riesgo * apalancamiento) / precio


# ─────────────────────────────────────────────
#  ESTADO DE SESIÓN
# ─────────────────────────────────────────────
if 'operaciones' not in st.session_state:
    st.session_state.operaciones = []   # historial de cierres
if 'ganancia_total' not in st.session_state:
    st.session_state.ganancia_total = 0.0
if 'ciclos' not in st.session_state:
    st.session_state.ciclos = 0

# ─────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────
st.markdown("## 💎 DREAMBOT — AGENTE DE COSECHA 100×")
st.caption(f"_{random.choice(BIBLE_QUOTES)}_")

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔐 Activación del Agente")
    api_key    = st.text_input("API Key",    type="password")
    api_secret = st.text_input("API Secret", type="password")

    st.divider()
    meta_diaria = st.number_input("🎯 Meta del Día (USD)", value=100.0, min_value=1.0)
    st.caption("El agente toma todas las decisiones automáticamente 🙏")
    st.divider()

    # Parámetros internos — el bot decide solo
    apalancamiento = 20
    tp_pct         = 0.8
    sl_pct         = 0.5
    max_pos        = 3

    activar = st.toggle("⚡ ¡INICIAR COSECHA 24/7!", value=False)
    if activar:
        st.success("🟢 Agente ACTIVO")
    else:
        st.warning("🔴 Agente en espera")

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey':          api_key,
            'secret':          api_secret,
            'enableRateLimit': True,
        })

        # ── Métricas superiores ──────────────────────
        c1, c2, c3, c4 = st.columns(4)
        ph_capital  = c1.empty()
        ph_meta     = c2.empty()
        ph_ganancia = c3.empty()
        ph_ciclos   = c4.empty()
        ph_progreso = st.empty()

        # ── Posiciones activas ───────────────────────
        st.markdown("### 📡 Posiciones Activas")
        ph_posiciones = st.empty()

        # ── Radar de señales ─────────────────────────
        st.markdown("### 🔍 Radar de Señales (EMA + RSI + Bollinger)")
        ph_radar = st.empty()

        # ── Historial de cierres ─────────────────────
        st.markdown("### 📊 Historial de Cierres")
        ph_historial = st.empty()

        # ── Bitácora ─────────────────────────────────
        with st.expander("📝 Bitácora en Tiempo Real", expanded=False):
            ph_log = st.empty()
        log_msgs = []

        def log(msg: str, tipo: str = "info"):
            ts = datetime.now().strftime("%H:%M:%S")
            prefix = {"ok": "✅", "warn": "⚠️", "err": "❌", "info": "ℹ️"}.get(tipo, "ℹ️")
            log_msgs.insert(0, f"`{ts}` {prefix} {msg}")
            ph_log.markdown("\n\n".join(log_msgs[:30]))

        # ════════════════════════════════════════════
        #  LOOP PRINCIPAL
        # ════════════════════════════════════════════
        while True:
            st.session_state.ciclos += 1

            # ── 1. BALANCE ───────────────────────────
            try:
                balance        = exchange.fetch_total_balance()
                total_equity   = safe_float(balance.get('USD', 0))
                info           = balance.get('info', {})
                available_margin = safe_float(info.get('marginAvailable', total_equity * 0.5))
            except Exception as e:
                log(f"Balance error: {e}", "err")
                total_equity, available_margin = 0.0, 0.0

            ph_capital.metric("💰 Capital Real",       f"${total_equity:.4f}")
            ph_meta.metric("🎯 Meta del Día",           f"${meta_diaria:.2f}")
            ph_ganancia.metric("📈 Ganancia Sesión",    f"${st.session_state.ganancia_total:.4f}")
            ph_ciclos.metric("🔁 Ciclos",               str(st.session_state.ciclos))
            progreso = min(100.0, (st.session_state.ganancia_total / meta_diaria) * 100)
            ph_progreso.progress(int(max(0, progreso)), text=f"Progreso hacia meta: {progreso:.2f}%")

            # ── 2. GESTIÓN DE POSICIONES ABIERTAS ────
            pos_info = []
            n_pos    = 0
            try:
                posiciones = exchange.fetch_positions()
                for p in posiciones:
                    contracts = safe_float(p.get('contracts'))
                    if contracts <= 0:
                        continue

                    n_pos   += 1
                    symbol   = p.get('symbol', '')
                    side     = str(p.get('side', '')).upper()
                    entry_p  = safe_float(p.get('entryPrice'))
                    mark_p   = safe_float(p.get('markPrice'))
                    pnl_usd  = safe_float(p.get('unrealizedPnl'))

                    # ROI sobre el movimiento de precio
                    if entry_p > 0:
                        if side == 'LONG':
                            move_pct = (mark_p - entry_p) / entry_p * 100
                        else:
                            move_pct = (entry_p - mark_p) / entry_p * 100
                    else:
                        move_pct = 0.0

                    estado = "🔥 COSECHAR" if move_pct >= tp_pct else (
                             "🛑 STOP"    if move_pct <= -sl_pct else "⏳ CRECIENDO")

                    pos_info.append({
                        "ACTIVO":   symbol,
                        "LADO":     side,
                        "ENTRADA":  f"${entry_p:.4f}",
                        "ACTUAL":   f"${mark_p:.4f}",
                        "ROI%":     f"{move_pct:+.2f}%",
                        "PNL USD":  f"${pnl_usd:.4f}",
                        "ESTADO":   estado,
                    })

                    # ── Cierre automático (TP o SL) ──
                    if estado in ("🔥 COSECHAR", "🛑 STOP"):
                        side_close = 'sell' if side == 'LONG' else 'buy'
                        try:
                            exchange.create_market_order(
                                symbol, side_close, contracts,
                                params={'reduceOnly': True}
                            )
                            tipo_cierre = "TP" if estado == "🔥 COSECHAR" else "SL"
                            st.session_state.ganancia_total += pnl_usd
                            st.session_state.operaciones.append({
                                "Hora":   datetime.now().strftime("%H:%M:%S"),
                                "Activo": symbol,
                                "Tipo":   tipo_cierre,
                                "ROI%":   f"{move_pct:+.2f}%",
                                "PNL":    f"${pnl_usd:.4f}",
                            })
                            log(f"{tipo_cierre} ejecutado: {symbol} → {move_pct:+.2f}% / ${pnl_usd:.4f}", "ok")
                        except Exception as e:
                            log(f"Error al cerrar {symbol}: {e}", "err")

            except Exception as e:
                log(f"Error posiciones: {e}", "warn")

            if pos_info:
                ph_posiciones.dataframe(pd.DataFrame(pos_info), use_container_width=True)
            else:
                ph_posiciones.info("Sin posiciones abiertas — buscando señales...")

            # ── 3. RADAR DE SEÑALES ───────────────────
            radar_data = []
            for symbol in MARKETS:
                try:
                    bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=50)
                    if len(bars) < 25:
                        continue
                    df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                    df = calc_indicators(df)
                    sig = evaluate_signal(df)

                    radar_data.append({
                        "ACTIVO":    symbol,
                        "PRECIO":    f"${sig['precio']:.4f}",
                        "RSI":       sig['rsi'],
                        "EMA9":      sig['ema9'],
                        "EMA21":     sig['ema21'],
                        "DIST BB%":  f"{sig['dist_pct']:.3f}%",
                        "SEÑAL":     sig['signal'],
                    })

                    # ── Abrir nueva posición si hay señal ──
                    if sig['signal'] != "⏳ ESPERA" and n_pos < max_pos and available_margin > 1:
                        base = get_base(symbol)
                        min_q = MIN_QTY.get(base, 0.1)
                        raw_qty = calc_position_size(available_margin, sig['precio'], apalancamiento)
                        qty = round_qty(symbol, raw_qty)

                        if qty >= min_q:
                            direction = 'buy' if 'LONG' in sig['signal'] else 'sell'
                            try:
                                exchange.create_market_order(symbol, direction, qty)
                                n_pos += 1
                                log(f"ENTRADA {sig['signal']}: {symbol} × {qty} @ ${sig['precio']:.4f}", "ok")
                            except Exception as e:
                                log(f"Error al abrir {symbol}: {e}", "err")
                        else:
                            log(f"Qty insuficiente para {symbol}: {qty} < {min_q}", "warn")

                except Exception as e:
                    log(f"Error radar {symbol}: {e}", "warn")

            if radar_data:
                df_radar = pd.DataFrame(radar_data)
                ph_radar.dataframe(df_radar, use_container_width=True)

            # ── 4. HISTORIAL ─────────────────────────
            if st.session_state.operaciones:
                ph_historial.dataframe(
                    pd.DataFrame(st.session_state.operaciones[:20]),
                    use_container_width=True
                )
            else:
                ph_historial.caption("Aún no hay cierres registrados en esta sesión.")

            # ── Pausa y rerun ─────────────────────────
            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"⚠️ Error de conexión: {e}")
        st.info("Reintentando en 15 segundos...")
        time.sleep(15)
        st.rerun()

elif activar and (not api_key or not api_secret):
    st.warning("🔑 Ingresa tu API Key y Secret en el panel lateral para iniciar.")
else:
    st.markdown("""
    <div style='text-align:center; padding: 3rem 0; opacity: 0.6;'>
        <h3>Agente en espera</h3>
        <p>Activa el switch en el panel lateral para comenzar la cosecha.</p>
    </div>
    """, unsafe_allow_html=True)
