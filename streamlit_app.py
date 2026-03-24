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
#  CONSTANTES
# ─────────────────────────────────────────────
BIBLE_QUOTES = [
    "La bendición del SEÑOR es la que enriquece. (Proverbios 10:22)",
    "Todo lo puedo en Cristo que me fortalece. (Filipenses 4:13)",
    "Al que cree todo le es posible. (Marcos 9:23)",
    "Porque yo sé los planes que tengo para ustedes... planes para darles futuro y esperanza. (Jeremías 29:11)",
]

# Fallback si la descarga de mercados falla
MARKETS_FALLBACK = [
    'BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD', 'XRP/USD:USD',
    'ADA/USD:USD', 'DOT/USD:USD', 'LINK/USD:USD', 'AVAX/USD:USD',
    'MATIC/USD:USD', 'ATOM/USD:USD', 'LTC/USD:USD', 'UNI/USD:USD',
]

# Parámetros internos — el bot decide solo
APALANCAMIENTO = 20
TP_PCT         = 0.8   # Take profit %
SL_PCT         = 0.5   # Stop loss %
MAX_POS        = 3     # Máx posiciones simultáneas


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except Exception:
        return default


def get_base(symbol: str) -> str:
    return symbol.split('/')[0]


def round_qty(symbol: str, qty: float) -> float:
    base = get_base(symbol)
    if 'BTC'  in base: return round(qty, 3)
    if 'ETH'  in base: return round(qty, 2)
    if base in ('SOL', 'DOT', 'LINK', 'AVAX'): return round(qty, 1)
    return round(qty, 0)


def get_min_qty(base: str) -> float:
    defaults = {
        'BTC': 0.001, 'ETH': 0.01,  'SOL': 0.1,
        'XRP': 1.0,   'ADA': 1.0,   'DOT': 0.1,
        'LINK': 0.1,  'AVAX': 0.1,  'MATIC': 1.0,
        'ATOM': 0.1,  'LTC': 0.01,  'UNI': 0.1,
    }
    return defaults.get(base, 0.1)


def get_active_markets(exchange) -> list:
    """
    Descarga TODOS los futuros perpetuos activos de Kraken,
    filtra por liquidez y ordena por volumen 24h DESC.
    El bot escanea primero los mercados más activos.
    """
    try:
        markets = exchange.load_markets()
        tickers = exchange.fetch_tickers()
        result  = []
        for sym, mkt in markets.items():
            if not sym.endswith(':USD'):
                continue
            if not mkt.get('active', False):
                continue
            ticker = tickers.get(sym, {})
            vol = safe_float(ticker.get('quoteVolume', ticker.get('baseVolume', 0)))
            if vol > 0:
                result.append((sym, vol))
        result.sort(key=lambda x: x[1], reverse=True)
        symbols = [s for s, _ in result]
        return symbols if symbols else MARKETS_FALLBACK
    except Exception:
        return MARKETS_FALLBACK


def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c = df['c'].astype(float)
    df['ema9']     = c.ewm(span=9,  adjust=False).mean()
    df['ema21']    = c.ewm(span=21, adjust=False).mean()
    delta          = c.diff()
    gain           = delta.clip(lower=0)
    loss           = (-delta).clip(lower=0)
    avg_g          = gain.ewm(span=14, adjust=False).mean()
    avg_l          = loss.ewm(span=14, adjust=False).mean()
    rs             = avg_g / avg_l.replace(0, np.nan)
    df['rsi']      = 100 - (100 / (1 + rs))
    ma20           = c.rolling(20).mean()
    std20          = c.rolling(20).std()
    df['bb_upper'] = ma20 + 2 * std20
    df['bb_lower'] = ma20 - 2 * std20
    return df


def evaluate_signal(df: pd.DataFrame) -> dict:
    last     = df.iloc[-1]
    precio   = safe_float(last['c'])
    rsi      = safe_float(last['rsi'])
    ema9     = safe_float(last['ema9'])
    ema21    = safe_float(last['ema21'])
    bb_l     = safe_float(last['bb_lower'])
    bb_u     = safe_float(last['bb_upper'])
    dist_pct = ((precio - bb_l) / bb_l * 100) if bb_l > 0 else 999

    if precio <= bb_l and rsi < 38:
        signal = "🔥 LONG"
    elif precio >= bb_u and rsi > 62:
        signal = "⚡ SHORT"
    else:
        signal = "⏳ ESPERA"

    return {
        "signal":   signal,
        "rsi":      round(rsi, 1),
        "precio":   precio,
        "dist_pct": round(dist_pct, 3),
        "ema9":     round(ema9, 4),
        "ema21":    round(ema21, 4),
    }


def calc_position_size(available_margin: float, precio: float) -> float:
    # Multiplicador 40x igual al código original — probado desde $6 USD
    return (available_margin * 40) / precio


# ─────────────────────────────────────────────
#  ESTADO DE SESIÓN
# ─────────────────────────────────────────────
for key, default in [
    ('operaciones', []),
    ('ganancia_total', 0.0),
    ('ciclos', 0),
    ('markets_cache', []),
    ('markets_last_update', 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────
st.markdown("## 💎 DREAMBOT — AGENTE DE COSECHA 100×")
st.caption(f"_{random.choice(BIBLE_QUOTES)}_")

# ─────────────────────────────────────────────
#  SIDEBAR — solo lo esencial
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔐 Activación del Agente")
    api_key    = st.text_input("API Key",    type="password")
    api_secret = st.text_input("API Secret", type="password")

    st.divider()
    meta_diaria = st.number_input("🎯 Meta del Día (USD)", value=100.0, min_value=1.0)
    st.caption("El agente toma todas las decisiones automáticamente 🙏")

    st.divider()
    activar = st.toggle("⚡ ¡INICIAR COSECHA 24/7!", value=False)
    if activar:
        st.success("🟢 Agente ACTIVO")
    else:
        st.warning("🔴 Agente en espera")

# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────
if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey':          api_key,
            'secret':          api_secret,
            'enableRateLimit': True,
        })

        # Descubrir mercados al arrancar (se refresca cada 10 min)
        ahora = time.time()
        if not st.session_state.markets_cache or (ahora - st.session_state.markets_last_update) > 600:
            with st.spinner("🔭 Descubriendo todos los mercados de Kraken Futures..."):
                st.session_state.markets_cache       = get_active_markets(exchange)
                st.session_state.markets_last_update = ahora

        MARKETS = st.session_state.markets_cache

        # ── Placeholders de UI ──
        c1, c2, c3, c4 = st.columns(4)
        ph_capital  = c1.empty()
        ph_meta     = c2.empty()
        ph_ganancia = c3.empty()
        ph_ciclos   = c4.empty()
        ph_progreso = st.empty()

        st.markdown("### 📡 Posiciones Activas")
        ph_posiciones = st.empty()

        ph_radar_title = st.empty()
        ph_radar       = st.empty()

        st.markdown("### 📊 Historial de Cierres")
        ph_historial = st.empty()

        with st.expander("📝 Bitácora en Tiempo Real", expanded=False):
            ph_log = st.empty()
        log_msgs = []

        def log(msg: str, tipo: str = "info"):
            ts     = datetime.now().strftime("%H:%M:%S")
            prefix = {"ok": "✅", "warn": "⚠️", "err": "❌", "info": "ℹ️"}.get(tipo, "ℹ️")
            log_msgs.insert(0, f"`{ts}` {prefix} {msg}")
            ph_log.markdown("\n\n".join(log_msgs[:40]))

        # ════════════════════════════════════════════
        #  LOOP PRINCIPAL
        # ════════════════════════════════════════════
        while True:
            st.session_state.ciclos += 1

            # 1. BALANCE
            try:
                balance          = exchange.fetch_total_balance()
                total_equity     = safe_float(balance.get('USD', 0))
                info_b           = balance.get('info', {})
                available_margin = safe_float(info_b.get('marginAvailable', total_equity * 0.5))
            except Exception as e:
                log(f"Balance error: {e}", "err")
                total_equity, available_margin = 0.0, 0.0

            ph_capital.metric("💰 Capital Real",    f"${total_equity:.4f}")
            ph_meta.metric("🎯 Meta del Día",        f"${meta_diaria:.2f}")
            ph_ganancia.metric("📈 Ganancia Sesión", f"${st.session_state.ganancia_total:.4f}")
            ph_ciclos.metric("🔁 Ciclos",            str(st.session_state.ciclos))
            progreso = min(100.0, (st.session_state.ganancia_total / meta_diaria) * 100)
            ph_progreso.progress(int(max(0, progreso)), text=f"Progreso hacia meta: {progreso:.2f}%")

            # 2. GESTIÓN DE POSICIONES ABIERTAS
            pos_info = []
            n_pos    = 0
            try:
                posiciones = exchange.fetch_positions()
                for p in posiciones:
                    contracts = safe_float(p.get('contracts'))
                    if contracts <= 0:
                        continue
                    n_pos  += 1
                    symbol  = p.get('symbol', '')
                    side    = str(p.get('side', '')).upper()
                    entry_p = safe_float(p.get('entryPrice'))
                    mark_p  = safe_float(p.get('markPrice'))
                    pnl_usd = safe_float(p.get('unrealizedPnl'))

                    if entry_p > 0:
                        move_pct = (mark_p - entry_p) / entry_p * 100 if side == 'LONG' \
                                   else (entry_p - mark_p) / entry_p * 100
                    else:
                        move_pct = 0.0

                    estado = "🔥 COSECHAR" if move_pct >= TP_PCT else (
                             "🛑 STOP"    if move_pct <= -SL_PCT else "⏳ CRECIENDO")

                    pos_info.append({
                        "ACTIVO":  symbol,
                        "LADO":    side,
                        "ENTRADA": f"${entry_p:.4f}",
                        "ACTUAL":  f"${mark_p:.4f}",
                        "ROI%":    f"{move_pct:+.2f}%",
                        "PNL USD": f"${pnl_usd:.4f}",
                        "ESTADO":  estado,
                    })

                    if estado in ("🔥 COSECHAR", "🛑 STOP"):
                        side_close = 'sell' if side == 'LONG' else 'buy'
                        try:
                            exchange.create_market_order(
                                symbol, side_close, contracts,
                                params={'reduceOnly': True}
                            )
                            tipo_cierre = "✅ TP" if estado == "🔥 COSECHAR" else "🛑 SL"
                            st.session_state.ganancia_total += pnl_usd
                            st.session_state.operaciones.append({
                                "Hora":   datetime.now().strftime("%H:%M:%S"),
                                "Activo": symbol,
                                "Tipo":   tipo_cierre,
                                "ROI%":   f"{move_pct:+.2f}%",
                                "PNL":    f"${pnl_usd:.4f}",
                            })
                            log(f"{tipo_cierre} {symbol} → {move_pct:+.2f}% / ${pnl_usd:.4f}", "ok")
                        except Exception as e:
                            log(f"Error cierre {symbol}: {e}", "err")

            except Exception as e:
                log(f"Error posiciones: {e}", "warn")

            if pos_info:
                ph_posiciones.dataframe(pd.DataFrame(pos_info), use_container_width=True)
            else:
                ph_posiciones.info("Sin posiciones abiertas — escaneando mercados...")

            # 3. RADAR — escanea TODOS los mercados descubiertos
            # Refresca lista de mercados cada 10 min
            ahora = time.time()
            if (ahora - st.session_state.markets_last_update) > 600:
                try:
                    MARKETS = get_active_markets(exchange)
                    st.session_state.markets_cache       = MARKETS
                    st.session_state.markets_last_update = ahora
                    log(f"Mercados actualizados: {len(MARKETS)} activos encontrados", "info")
                except Exception:
                    pass

            ph_radar_title.markdown(
                f"### 🔍 Radar de Señales — **{len(MARKETS)} mercados** escaneados (EMA + RSI + Bollinger)"
            )

            radar_data = []
            for symbol in MARKETS:
                try:
                    bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=50)
                    if len(bars) < 25:
                        continue
                    df  = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                    df  = calc_indicators(df)
                    sig = evaluate_signal(df)

                    radar_data.append({
                        "ACTIVO":   symbol,
                        "PRECIO":   f"${sig['precio']:.4f}",
                        "RSI":      sig['rsi'],
                        "SEÑAL":    sig['signal'],
                        "DIST BB%": f"{sig['dist_pct']:.3f}%",
                    })

                    # Abrir posición si hay señal
                    if sig['signal'] != "⏳ ESPERA" and n_pos < MAX_POS and available_margin > 1:
                        base    = get_base(symbol)
                        min_q   = get_min_qty(base)
                        raw_qty = calc_position_size(available_margin, sig['precio'])
                        qty     = round_qty(symbol, raw_qty)

                        if qty > 0:
                            direction = 'buy' if 'LONG' in sig['signal'] else 'sell'
                            try:
                                exchange.create_market_order(symbol, direction, qty)
                                n_pos += 1
                                log(f"ENTRADA {sig['signal']}: {symbol} × {qty} @ ${sig['precio']:.4f}", "ok")
                            except Exception as e:
                                log(f"Error apertura {symbol}: {e}", "err")
                        else:
                            log(f"Qty baja {symbol}: {qty} < {min_q}", "warn")

                except Exception:
                    continue

            if radar_data:
                df_radar = pd.DataFrame(radar_data)
                # Señales activas primero
                df_radar_sorted = pd.concat([
                    df_radar[df_radar['SEÑAL'] != "⏳ ESPERA"],
                    df_radar[df_radar['SEÑAL'] == "⏳ ESPERA"],
                ]).reset_index(drop=True)
                ph_radar.dataframe(df_radar_sorted, use_container_width=True)

            # 4. HISTORIAL
            if st.session_state.operaciones:
                ph_historial.dataframe(
                    pd.DataFrame(st.session_state.operaciones[:30]),
                    use_container_width=True
                )
            else:
                ph_historial.caption("Aún no hay cierres en esta sesión.")

            time.sleep(15)
            st.rerun()

    except Exception as e:
        st.error(f"⚠️ Error de conexión: {e}")
        time.sleep(15)
        st.rerun()

elif activar and (not api_key or not api_secret):
    st.warning("🔑 Ingresa tu API Key y Secret en el panel lateral.")
else:
    st.markdown("""
    <div style='text-align:center; padding: 3rem 0; opacity:0.5;'>
        <h3>Agente en espera</h3>
        <p>Activa el switch en el panel lateral para comenzar la cosecha.</p>
    </div>
    """, unsafe_allow_html=True)
