"""
╔══════════════════════════════════════════════════════════════════╗
║          SNIPER V5.2 - PRICE ACTION WARRIOR (ULTRA-STABLE)       ║
║          Estrategias: Ruptura, FVG, OB, Estructura de Mercado    ║
╚══════════════════════════════════════════════════════════════════╝

MEJORAS V5.2:
1. Corrección Crítica: Persistencia de SL/TP antes de la ejecución de la orden.
2. Validación de Niveles: Evita cierres si los niveles son 0 o incoherentes.
3. Sincronización de Estado: Mejor manejo de st.session_state para evitar bucles.
4. Logging Mejorado: Muestra los niveles reales de salida en cada ciclo.
"""

import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone

# ══════════════════════════════════════════
# CONFIGURACIÓN GLOBAL
# ══════════════════════════════════════════
st.set_page_config(
    page_title="SNIPER V5.2 | Price Action Warrior",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Personalizado
st.markdown("""
<style>
    .stApp { background-color: #0a0e1a; color: #e0e6f0; }
    .metric-card { 
        background: linear-gradient(135deg, #0f1629 0%, #1a2040 100%);
        border: 1px solid #2a3a6a;
        border-radius: 12px; padding: 16px; margin: 8px 0;
    }
    .signal-long { color: #00ff88; font-weight: bold; font-size: 1.1em; }
    .signal-short { color: #ff4466; font-weight: bold; font-size: 1.1em; }
    .signal-wait { color: #ffaa00; }
    h1 { color: #4a9eff !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════
# PARÁMETROS
# ══════════════════════════════════════════
SYMBOLS = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD']
LEVERAGE = 10
RISK_PCT = 0.02
RR_RATIO = 2.0
MAX_POSITIONS = 2
TIMEFRAME_ENTRY = '15m'
TIMEFRAME_TREND = '1h'
BARS_LIMIT = 300

# ══════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════
def safe_float(val, default=0.0):
    try: return float(val) if val is not None else default
    except: return default

def log(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "ℹ️", "TRADE": "🚀", "WIN": "💰", "LOSS": "🛡️", "WARN": "⚠️", "ERROR": "❌", "SCAN": "🔍"}
    icon = icons.get(level, "•")
    if 'trade_log' not in st.session_state: st.session_state.trade_log = []
    st.session_state.trade_log.insert(0, f"[{now}] {icon} {msg}")
    st.session_state.trade_log = st.session_state.trade_log[:100]

# ══════════════════════════════════════════
# MOTOR DE ANÁLISIS TÉCNICO
# ══════════════════════════════════════════

def calcular_indicadores(df):
    c = df['c'].astype(float)
    h = df['h'].astype(float)
    l = df['l'].astype(float)
    o = df['o'].astype(float)
    df['ema20']  = c.ewm(span=20,  adjust=False).mean()
    df['ema50']  = c.ewm(span=50,  adjust=False).mean()
    df['ema200'] = c.ewm(span=200, adjust=False).mean()
    tr1 = h - l
    tr2 = abs(h - c.shift(1))
    tr3 = abs(l - c.shift(1))
    df['atr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    df['vol_ma'] = df['v'].astype(float).rolling(20).mean()
    df['vol_ratio'] = df['v'].astype(float) / df['vol_ma']
    return df

def detectar_estructura_mercado(df, lookback=20):
    highs, lows = df['h'].astype(float).values, df['l'].astype(float).values
    swings_h, swings_l = [], []
    for i in range(3, len(df)-1):
        if highs[i] == max(highs[max(0,i-3):i+2]): swings_h.append((i, highs[i]))
        if lows[i] == min(lows[max(0,i-3):i+2]): swings_l.append((i, lows[i]))
    if len(swings_h) < 2 or len(swings_l) < 2: return 'neutral', None, None
    last_hh, prev_hh = swings_h[-1][1], swings_h[-2][1]
    last_ll, prev_ll = swings_l[-1][1], swings_l[-2][1]
    if last_hh > prev_hh and last_ll > prev_ll: return 'bullish', last_ll, last_hh
    elif last_hh < prev_hh and last_ll < prev_ll: return 'bearish', last_ll, last_hh
    return 'neutral', last_ll, last_hh

def detectar_order_blocks(df, n=5):
    obs_bull, obs_bear = [], []
    c, o = df['c'].astype(float).values, df['o'].astype(float).values
    for i in range(2, len(df)-n):
        move_up = (c[i+n] - c[i]) / c[i] * 100
        if o[i] > c[i] and move_up > 1.5: obs_bull.append({'mid': (o[i] + c[i]) / 2})
        move_dn = (c[i] - c[i+n]) / c[i] * 100
        if c[i] > o[i] and move_dn > 1.5: obs_bear.append({'mid': (c[i] + o[i]) / 2})
    return obs_bull[-3:], obs_bear[-3:]

def detectar_fvg(df):
    fvgs_bull, fvgs_bear = [], []
    h, l = df['h'].astype(float).values, df['l'].astype(float).values
    for i in range(1, len(df)-1):
        if l[i+1] > h[i-1]: fvgs_bull.append({'bot': h[i-1], 'top': l[i+1]})
        if h[i+1] < l[i-1]: fvgs_bear.append({'bot': h[i+1], 'top': l[i-1]})
    return fvgs_bull[-3:], fvgs_bear[-3:]

def generar_senal(df_15m, df_1h, symbol):
    if len(df_15m) < 210 or len(df_1h) < 50: return None
    df_15m, df_1h = calcular_indicadores(df_15m.copy()), calcular_indicadores(df_1h.copy())
    last = df_15m.iloc[-1]
    precio, atr, rsi = float(last['c']), float(last['atr']), float(last['rsi'])
    est_1h, _, _ = detectar_estructura_mercado(df_1h)
    ema50_1h, ema200_1h = float(df_1h.iloc[-1]['ema50']), float(df_1h.iloc[-1]['ema200'])
    tendencia_1h = 'bull' if ema50_1h > ema200_1h and est_1h == 'bullish' else 'bear' if ema50_1h < ema200_1h and est_1h == 'bearish' else 'neutral'
    est_15m, _, _ = detectar_estructura_mercado(df_15m)
    obs_bull, obs_bear = detectar_order_blocks(df_15m)
    fvgs_bull, fvgs_bear = detectar_fvg(df_15m)
    vol_ok = float(last['vol_ratio']) > 1.2
    score_long, score_short = 0, 0
    razones_l, razones_s = [], []
    if tendencia_1h == 'bull': score_long += 2; razones_l.append("Tendencia 1h alcista")
    if est_15m == 'bullish': score_long += 1; razones_l.append("Estructura 15m alcista")
    if precio > float(last['ema200']): score_long += 1; razones_l.append("Sobre EMA200")
    for ob in obs_bull:
        if abs(precio - ob['mid']) / precio < 0.005: score_long += 2; razones_l.append("En OB bull")
    for fvg in fvgs_bull:
        if fvg['bot'] <= precio <= fvg['top']: score_long += 2; razones_l.append("En FVG bull")
    if vol_ok: score_long += 1; razones_l.append("Volumen OK")
    if tendencia_1h == 'bear': score_short += 2; razones_s.append("Tendencia 1h bajista")
    if est_15m == 'bearish': score_short += 1; razones_s.append("Estructura 15m bajista")
    if precio < float(last['ema200']): score_short += 1; razones_s.append("Bajo EMA200")
    for ob in obs_bear:
        if abs(precio - ob['mid']) / precio < 0.005: score_short += 2; razones_s.append("En OB bear")
    for fvg in fvgs_bear:
        if fvg['bot'] <= precio <= fvg['top']: score_short += 2; razones_s.append("En FVG bear")
    if vol_ok: score_short += 1; razones_s.append("Volumen OK")
    MIN_SCORE = 5
    if score_long >= MIN_SCORE and score_long > score_short:
        sl = precio - (atr * 1.5)
        tp = precio + (atr * 1.5 * RR_RATIO)
        return {'side': 'long', 'precio': precio, 'sl': sl, 'tp': tp, 'score': score_long, 'razones': razones_l}
    elif score_short >= MIN_SCORE and score_short > score_long:
        sl = precio + (atr * 1.5)
        tp = precio - (atr * 1.5 * RR_RATIO)
        return {'side': 'short', 'precio': precio, 'sl': sl, 'tp': tp, 'score': score_short, 'razones': razones_s}
    return None

# ══════════════════════════════════════════
# GESTIÓN DE POSICIONES
# ══════════════════════════════════════════

def gestionar_posiciones(posiciones, exchange):
    if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
    n_activas = 0
    for p in posiciones:
        qty = safe_float(p.get('contracts', 0))
        if qty <= 0: continue
        n_activas += 1
        sym, side = p['symbol'], p['side'].upper()
        mark, pnl = safe_float(p.get('markPrice')), safe_float(p.get('unrealizedPnl'))
        trade_data = st.session_state.active_trades.get(sym)
        if not trade_data or trade_data.get('sl', 0) == 0 or trade_data.get('tp', 0) == 0:
            entry = safe_float(p.get('entryPrice'))
            st.session_state.active_trades[sym] = {
                'entry': entry, 'sl': entry * 0.98 if side == 'LONG' else entry * 1.02,
                'tp': entry * 1.04 if side == 'LONG' else entry * 0.96, 'trailing': False
            }
            trade_data = st.session_state.active_trades[sym]
            log(f"Niveles reconstruidos para {sym} (Seguridad)", "WARN")
        sl, tp, entry = trade_data['sl'], trade_data['tp'], trade_data['entry']
        close_side = 'sell' if side == 'LONG' else 'buy'
        is_tp = (side == 'LONG' and mark >= tp) or (side == 'SHORT' and mark <= tp)
        is_sl = (side == 'LONG' and mark <= sl) or (side == 'SHORT' and mark >= sl)
        if is_tp:
            try:
                exchange.create_market_order(sym, close_side, qty, params={'reduceOnly': True})
                log(f"💰 TP ALCANZADO: {sym} | PnL: ${pnl:.4f}", "WIN")
                st.session_state.stats['wins'] += 1
                st.session_state.stats['total_pnl'] += pnl
                if sym in st.session_state.active_trades: del st.session_state.active_trades[sym]
            except Exception as e: log(f"Error TP {sym}: {e}", "ERROR")
        elif is_sl:
            try:
                exchange.create_market_order(sym, close_side, qty, params={'reduceOnly': True})
                log(f"🛡️ SL ACTIVADO: {sym} | PnL: ${pnl:.4f}", "LOSS")
                st.session_state.stats['losses'] += 1
                st.session_state.stats['total_pnl'] += pnl
                if sym in st.session_state.active_trades: del st.session_state.active_trades[sym]
            except Exception as e: log(f"Error SL {sym}: {e}", "ERROR")
        elif not trade_data.get('trailing', False):
            dist_r = abs(entry - sl)
            trigger = entry + dist_r if side == 'LONG' else entry - dist_r
            if (side == 'LONG' and mark >= trigger) or (side == 'SHORT' and mark <= trigger):
                st.session_state.active_trades[sym]['sl'] = entry
                st.session_state.active_trades[sym]['trailing'] = True
                log(f"📈 Trailing: {sym} a Breakeven", "INFO")
    return n_activas

# ══════════════════════════════════════════
# INTERFAZ Y LOOP
# ══════════════════════════════════════════

st.markdown("# 🎯 SNIPER V5.2 — PRICE ACTION WARRIOR")
st.caption(f"Versión Ultra-Estable | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

with st.sidebar:
    st.markdown("### 🔐 Credenciales Kraken")
    api_key, api_secret = st.text_input("API Key", type="password"), st.text_input("API Secret", type="password")
    leverage_ui = st.slider("Apalancamiento", 2, 20, LEVERAGE)
    risk_pct_ui = st.slider("Riesgo por trade (%)", 1, 5, 2)
    modo = st.radio("Selecciona:", ["🔍 Solo Análisis", "⚡ Trading Real"])
    activar = st.toggle("INICIAR BOT", value=False)

col1, col2, col3 = st.columns([2,2,3])
capital_ph, posicion_ph, senal_ph = col1.empty(), col2.empty(), col3.empty()
log_ph = st.empty()

if 'trade_log' not in st.session_state: st.session_state.trade_log = []
if 'stats' not in st.session_state: st.session_state.stats = {'wins':0, 'losses':0, 'total_pnl':0.0}
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
        log("Bot Sniper V5.2 Iniciado. 'No temas, porque yo estoy contigo' (Isaías 41:10)", "INFO")
        while True:
            try:
                balance = exchange.fetch_total_balance()
                equity = safe_float(balance.get('USD', 0))
            except: equity = 0.0
            capital_ph.markdown(f"""<div class="metric-card"><b>💼 Capital</b><br><span style="font-size:1.5em; color:#4a9eff">${equity:.4f} USD</span><br>
            <small>W: {st.session_state.stats['wins']} | L: {st.session_state.stats['losses']} | PnL: ${st.session_state.stats['total_pnl']:.4f}</small></div>""", unsafe_allow_html=True)
            try:
                posiciones = exchange.fetch_positions()
                n_activas = gestionar_posiciones(posiciones, exchange)
            except Exception as e: posiciones, n_activas = [], 0
            pos_info = ""
            for p in posiciones:
                if safe_float(p.get('contracts', 0)) > 0:
                    sym, side = p['symbol'], p['side'].upper()
                    pnl, mark, entry = safe_float(p.get('unrealizedPnl')), safe_float(p.get('markPrice')), safe_float(p.get('entryPrice'))
                    trade_data = st.session_state.active_trades.get(sym, {})
                    sl_val, tp_val = trade_data.get('sl', 0), trade_data.get('tp', 0)
                    color = "#00ff88" if pnl >= 0 else "#ff4466"
                    pos_info += f"""<div style="color:{color}; margin:4px 0"><b>{sym.split('/')[0]}</b> {side} | PnL: ${pnl:+.4f}<br>
                    <small>Entry: {entry:.2f} | SL: {sl_val:.2f} | TP: {tp_val:.2f}</small></div>"""
            posicion_ph.markdown(f"""<div class="metric-card"><b>📊 Posiciones ({n_activas}/{MAX_POSITIONS})</b><br>{pos_info if pos_info else 'Sin posiciones'}</div>""", unsafe_allow_html=True)
            senales_encontradas = []
            if n_activas < MAX_POSITIONS:
                for sym in SYMBOLS:
                    try:
                        bars_15m = exchange.fetch_ohlcv(sym, TIMEFRAME_ENTRY, limit=BARS_LIMIT)
                        bars_1h  = exchange.fetch_ohlcv(sym, TIMEFRAME_TREND, limit=BARS_LIMIT)
                        senal = generar_senal(pd.DataFrame(bars_15m, columns=['ts','o','h','l','c','v']), pd.DataFrame(bars_1h, columns=['ts','o','h','l','c','v']), sym)
                        if senal:
                            senal['symbol'] = sym
                            senales_encontradas.append(senal)
                            if modo == "⚡ Trading Real":
                                dist_sl = abs(senal['precio'] - senal['sl']) / senal['precio']
                                qty = (equity * (risk_pct_ui/100)) / dist_sl / senal['precio']
                                if (qty * senal['precio']) / leverage_ui > equity * 0.45: qty = (equity * 0.45 * leverage_ui) / senal['precio']
                                if qty > 0:
                                    if 'BTC' in sym: qty = round(qty, 5)
                                    elif 'ETH' in sym: qty = round(qty, 4)
                                    else: qty = round(qty, 2)
                                    # GUARDAR ANTES DE EJECUTAR
                                    st.session_state.active_trades[sym] = {'entry': senal['precio'], 'sl': senal['sl'], 'tp': senal['tp'], 'trailing': False}
                                    exchange.create_market_order(sym, 'buy' if senal['side'] == 'long' else 'sell', qty)
                                    log(f"ORDEN: {senal['side'].upper()} {qty} {sym} | SL: {senal['sl']:.2f} | TP: {senal['tp']:.2f}", "TRADE")
                                    n_activas += 1
                                    if n_activas >= MAX_POSITIONS: break
                    except Exception as e: log(f"Error {sym}: {str(e)[:40]}", "ERROR")
            senales_html = ""
            for s in senales_encontradas:
                color = '#00ff88' if s['side']=='long' else '#ff4466'
                senales_html += f"""<div style="border-left: 3px solid {color}; padding-left: 8px; margin: 8px 0;"><span style="color:{color}"><b>{s['side'].upper()}</b> — {s['symbol'].split('/')[0]}</span><br>
                <small>Entry: {s['precio']:.2f} | SL: {s['sl']:.2f} | TP: {s['tp']:.2f}</small></div>"""
            senal_ph.markdown(f"""<div class="metric-card"><b>🎯 Señales</b><br>{senales_html if senales_html else 'Esperando...'}</div>""", unsafe_allow_html=True)
            log_ph.markdown(f"""<div class="metric-card" style="max-height:200px; overflow-y:auto; font-family:monospace; font-size:0.8em">{"<br>".join(st.session_state.trade_log[:20])}</div>""", unsafe_allow_html=True)
            time.sleep(30)
            st.rerun()
    except Exception as e:
        st.error(f"❌ Error: {e}")
        time.sleep(15)
        st.rerun()
else:
    st.info("💡 Ingresa credenciales y activa el bot. 'El que es fiel en lo muy poco, también en lo mucho es fiel' (Lucas 16:10)")
