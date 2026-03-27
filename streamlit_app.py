"""
╔══════════════════════════════════════════════════════════════════╗
║          SNIPER V5.1 - PRICE ACTION WARRIOR (CORREGIDO)          ║
║          Estrategias: Ruptura, FVG, OB, Estructura de Mercado    ║
╚══════════════════════════════════════════════════════════════════╝

MEJORAS V5.1:
1. Persistencia de SL/TP dinámicos en st.session_state.
2. Lógica de cierre basada en niveles reales de SL/TP, no porcentajes fijos.
3. Trailing Stop funcional que asegura ganancias (Breakeven a +1R).
4. Gestión de PnL Realizado para estadísticas precisas.
5. Protección contra cierres prematuros en pérdida.
"""

import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone
import json

# ══════════════════════════════════════════
# CONFIGURACIÓN GLOBAL
# ══════════════════════════════════════════
st.set_page_config(
    page_title="SNIPER V5.1 | Price Action Warrior",
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
RISK_PCT = 0.02          # 2% de riesgo por trade
RR_RATIO = 2.0           # Take profit = 2x el Stop Loss
MAX_POSITIONS = 2
TRAILING_TRIGGER = 1.0   # Activar trailing al llegar a 1R de ganancia
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
    icons = {"INFO": "ℹ️", "TRADE": "🚀", "WIN": "💰", "LOSS": "🛡️", 
             "WARN": "⚠️", "ERROR": "❌", "SCAN": "🔍"}
    icon = icons.get(level, "•")
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = []
    st.session_state.trade_log.insert(0, f"[{now}] {icon} {msg}")
    st.session_state.trade_log = st.session_state.trade_log[:100]

# ══════════════════════════════════════════
# MOTOR DE ANÁLISIS TÉCNICO - PRICE ACTION
# ══════════════════════════════════════════

def calcular_indicadores(df):
    """Indicadores basados en Price Action puro"""
    c = df['c'].astype(float)
    h = df['h'].astype(float)
    l = df['l'].astype(float)
    o = df['o'].astype(float)

    # EMAs de tendencia
    df['ema20']  = c.ewm(span=20,  adjust=False).mean()
    df['ema50']  = c.ewm(span=50,  adjust=False).mean()
    df['ema200'] = c.ewm(span=200, adjust=False).mean()

    # ATR (Average True Range) - para calcular SL dinámico
    tr1 = h - l
    tr2 = abs(h - c.shift(1))
    tr3 = abs(l - c.shift(1))
    df['atr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

    # RSI
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))

    # Volumen relativo
    df['vol_ma'] = df['v'].astype(float).rolling(20).mean()
    df['vol_ratio'] = df['v'].astype(float) / df['vol_ma']

    # Cuerpo de vela
    df['body'] = abs(c - o)
    df['wick_up'] = h - pd.concat([c, o], axis=1).max(axis=1)
    df['wick_dn'] = pd.concat([c, o], axis=1).min(axis=1) - l
    df['is_bullish'] = c > o
    df['is_bearish'] = c < o

    return df

def detectar_estructura_mercado(df, lookback=20):
    """Detecta Break of Structure (BOS) y Change of Character (CHoCH)"""
    highs = df['h'].astype(float).values
    lows  = df['l'].astype(float).values
    
    recent = min(lookback, len(df)-2)
    swings_h = []
    swings_l = []
    
    for i in range(3, len(df)-1):
        if highs[i] == max(highs[max(0,i-3):i+2]):
            swings_h.append((i, highs[i]))
        if lows[i] == min(lows[max(0,i-3):i+2]):
            swings_l.append((i, lows[i]))
    
    if len(swings_h) < 2 or len(swings_l) < 2:
        return 'neutral', None, None

    last_hh = swings_h[-1][1]
    prev_hh = swings_h[-2][1]
    last_ll = swings_l[-1][1]
    prev_ll = swings_l[-2][1]
    
    if last_hh > prev_hh and last_ll > prev_ll:
        return 'bullish', last_ll, last_hh
    elif last_hh < prev_hh and last_ll < prev_ll:
        return 'bearish', last_ll, last_hh
    else:
        return 'neutral', last_ll, last_hh

def detectar_order_blocks(df, n=5):
    """Order Block: La última vela bajista antes de un movimiento alcista fuerte"""
    obs_bull = []
    obs_bear = []
    c = df['c'].astype(float).values
    o = df['o'].astype(float).values
    for i in range(2, len(df)-n):
        move_up = (c[i+n] - c[i]) / c[i] * 100
        if o[i] > c[i] and move_up > 1.5:
            obs_bull.append({'idx': i, 'top': o[i], 'bot': c[i], 'mid': (o[i] + c[i]) / 2, 'tipo': 'bull'})
        move_dn = (c[i] - c[i+n]) / c[i] * 100
        if c[i] > o[i] and move_dn > 1.5:
            obs_bear.append({'idx': i, 'top': c[i], 'bot': o[i], 'mid': (c[i] + o[i]) / 2, 'tipo': 'bear'})
    return obs_bull[-3:], obs_bear[-3:]

def detectar_fvg(df):
    """Fair Value Gap"""
    fvgs_bull = []
    fvgs_bear = []
    h = df['h'].astype(float).values
    l = df['l'].astype(float).values
    for i in range(1, len(df)-1):
        if l[i+1] > h[i-1]:
            fvgs_bull.append({'bot': h[i-1], 'top': l[i+1], 'idx': i})
        if h[i+1] < l[i-1]:
            fvgs_bear.append({'bot': h[i+1], 'top': l[i-1], 'idx': i})
    return fvgs_bull[-3:], fvgs_bear[-3:]

def detectar_pin_bar(df):
    """Pin Bar: mecha larga + cuerpo pequeño"""
    last = df.iloc[-1]
    body = abs(float(last['c']) - float(last['o']))
    wick_up = float(last['h']) - max(float(last['c']), float(last['o']))
    wick_dn = min(float(last['c']), float(last['o'])) - float(last['l'])
    total_range = float(last['h']) - float(last['l'])
    if total_range == 0: return None
    if wick_dn > total_range * 0.6 and body < total_range * 0.3:
        return 'bull_pin'
    if wick_up > total_range * 0.6 and body < total_range * 0.3:
        return 'bear_pin'
    return None

def detectar_inside_bar(df):
    """Inside Bar: compresión"""
    if len(df) < 3: return False
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    return (float(curr['h']) < float(prev['h']) and float(curr['l']) > float(prev['l']))

# ══════════════════════════════════════════
# MOTOR DE SEÑALES - CONFLUENCIA
# ══════════════════════════════════════════

def generar_senal(df_15m, df_1h, symbol):
    """Genera señal de trading combinando múltiples factores"""
    if len(df_15m) < 210 or len(df_1h) < 50:
        return None
    
    df_15m = calcular_indicadores(df_15m.copy())
    df_1h  = calcular_indicadores(df_1h.copy())
    
    last   = df_15m.iloc[-1]
    precio = float(last['c'])
    atr    = float(last['atr'])
    rsi    = float(last['rsi'])
    
    # Tendencia 1h
    estructura_1h, _, _ = detectar_estructura_mercado(df_1h)
    ema50_1h  = float(df_1h.iloc[-1]['ema50'])
    ema200_1h = float(df_1h.iloc[-1]['ema200'])
    tendencia_1h = 'bull' if ema50_1h > ema200_1h and estructura_1h == 'bullish' else \
                   'bear' if ema50_1h < ema200_1h and estructura_1h == 'bearish' else 'neutral'
    
    # Estructura 15m
    estructura_15m, _, _ = detectar_estructura_mercado(df_15m)
    obs_bull, obs_bear = detectar_order_blocks(df_15m)
    fvgs_bull, fvgs_bear = detectar_fvg(df_15m)
    pin = detectar_pin_bar(df_15m)
    inside = detectar_inside_bar(df_15m)
    vol_ok = float(last['vol_ratio']) > 1.2
    
    score_long = 0
    score_short = 0
    razon_long = []
    razon_short = []
    
    if tendencia_1h == 'bull': score_long += 2; razon_long.append("Tendencia 1h alcista")
    if estructura_15m == 'bullish': score_long += 1; razon_long.append("Estructura 15m alcista")
    if precio > float(last['ema200']): score_long += 1; razon_long.append("Precio sobre EMA200")
    for ob in obs_bull:
        if abs(precio - ob['mid']) / precio < 0.005: score_long += 2; razon_long.append(f"En OB bull @{ob['mid']:.2f}")
    for fvg in fvgs_bull:
        if fvg['bot'] <= precio <= fvg['top']: score_long += 2; razon_long.append(f"En FVG bull")
    if pin == 'bull_pin': score_long += 2; razon_long.append("Pin Bar alcista")
    if inside: score_long += 1; razon_long.append("Inside Bar")
    if 40 < rsi < 65: score_long += 1; razon_long.append(f"RSI favorable")
    if vol_ok: score_long += 1; razon_long.append("Volumen elevado")
    
    if tendencia_1h == 'bear': score_short += 2; razon_short.append("Tendencia 1h bajista")
    if estructura_15m == 'bearish': score_short += 1; razon_short.append("Estructura 15m bajista")
    if precio < float(last['ema200']): score_short += 1; razon_short.append("Precio bajo EMA200")
    for ob in obs_bear:
        if abs(precio - ob['mid']) / precio < 0.005: score_short += 2; razon_short.append(f"En OB bear @{ob['mid']:.2f}")
    for fvg in fvgs_bear:
        if fvg['bot'] <= precio <= fvg['top']: score_short += 2; razon_short.append(f"En FVG bear")
    if pin == 'bear_pin': score_short += 2; razon_short.append("Pin Bar bajista")
    if inside: score_short += 1; razon_short.append("Inside Bar")
    if 35 < rsi < 60: score_short += 1; razon_short.append(f"RSI favorable")
    if vol_ok: score_short += 1; razon_short.append("Volumen elevado")
    
    MIN_SCORE = 5
    if score_long >= MIN_SCORE and score_long > score_short:
        sl = precio - (atr * 1.5)
        tp = precio + (atr * 1.5 * RR_RATIO)
        return {'side': 'long', 'precio': precio, 'sl': sl, 'tp': tp, 'atr': atr, 'score': score_long, 'razones': razon_long}
    elif score_short >= MIN_SCORE and score_short > score_long:
        sl = precio + (atr * 1.5)
        tp = precio - (atr * 1.5 * RR_RATIO)
        return {'side': 'short', 'precio': precio, 'sl': sl, 'tp': tp, 'atr': atr, 'score': score_short, 'razones': razon_short}
    return None

# ══════════════════════════════════════════
# GESTIÓN DE CAPITAL Y POSICIONES
# ══════════════════════════════════════════

def calcular_tamano_posicion(equity, precio, sl, leverage):
    riesgo_usd = equity * RISK_PCT
    distancia_sl = abs(precio - sl) / precio
    if distancia_sl == 0: return 0
    tamano_nominal = riesgo_usd / distancia_sl
    qty = tamano_nominal / precio
    if (qty * precio) / leverage > equity * 0.45:
        qty = (equity * 0.45 * leverage) / precio
    return qty

def gestionar_posiciones(posiciones, exchange):
    """Maneja TP, SL y trailing de posiciones abiertas con persistencia"""
    if 'active_trades' not in st.session_state:
        st.session_state.active_trades = {}
    
    n_activas = 0
    for p in posiciones:
        qty = safe_float(p.get('contracts', 0))
        if qty <= 0: continue
        
        n_activas += 1
        sym   = p['symbol']
        side  = p['side'].upper()
        mark  = safe_float(p.get('markPrice'))
        pnl   = safe_float(p.get('unrealizedPnl'))
        
        # Recuperar niveles persistentes
        trade_data = st.session_state.active_trades.get(sym)
        if not trade_data:
            # Si no hay datos persistentes (ej. bot reiniciado), intentar reconstruir
            entry = safe_float(p.get('entryPrice'))
            st.session_state.active_trades[sym] = {
                'entry': entry, 'sl': entry * 0.985 if side == 'LONG' else entry * 1.015,
                'tp': entry * 1.03 if side == 'LONG' else entry * 0.97, 'trailing': False
            }
            trade_data = st.session_state.active_trades[sym]
            log(f"Reconstruyendo niveles para {sym}", "WARN")

        sl = trade_data['sl']
        tp = trade_data['tp']
        entry = trade_data['entry']
        
        # Lógica de Cierre Real
        close_side = 'sell' if side == 'LONG' else 'buy'
        is_tp = (side == 'LONG' and mark >= tp) or (side == 'SHORT' and mark <= tp)
        is_sl = (side == 'LONG' and mark <= sl) or (side == 'SHORT' and mark >= sl)
        
        if is_tp:
            try:
                exchange.create_market_order(sym, close_side, qty, params={'reduceOnly': True})
                log(f"💰 TP ALCANZADO: {sym} | PnL: ${pnl:.4f}", "WIN")
                st.session_state.stats['wins'] += 1
                st.session_state.stats['total_pnl'] += pnl
                del st.session_state.active_trades[sym]
            except Exception as e: log(f"Error TP {sym}: {e}", "ERROR")
            
        elif is_sl:
            try:
                exchange.create_market_order(sym, close_side, qty, params={'reduceOnly': True})
                log(f"🛡️ SL ACTIVADO: {sym} | PnL: ${pnl:.4f}", "LOSS")
                st.session_state.stats['losses'] += 1
                st.session_state.stats['total_pnl'] += pnl
                del st.session_state.active_trades[sym]
            except Exception as e: log(f"Error SL {sym}: {e}", "ERROR")
            
        # Trailing Stop: si ganamos 1R, mover SL a Breakeven
        elif not trade_data.get('trailing', False):
            dist_r = abs(entry - sl)
            trigger_price = entry + dist_r if side == 'LONG' else entry - dist_r
            if (side == 'LONG' and mark >= trigger_price) or (side == 'SHORT' and mark <= trigger_price):
                st.session_state.active_trades[sym]['sl'] = entry # Mover a Breakeven
                st.session_state.active_trades[sym]['trailing'] = True
                log(f"📈 Trailing activado en {sym}: SL movido a Breakeven", "INFO")
                
    return n_activas

# ══════════════════════════════════════════
# INTERFAZ Y LOOP
# ══════════════════════════════════════════

st.markdown("# 🎯 SNIPER V5.1 — PRICE ACTION WARRIOR")
st.caption(f"Sistema Corregido | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

with st.sidebar:
    st.markdown("### 🔐 Credenciales Kraken")
    api_key    = st.text_input("API Key", type="password", key="apikey")
    api_secret = st.text_input("API Secret", type="password", key="apisecret")
    st.markdown("---")
    leverage_ui  = st.slider("Apalancamiento", 2, 20, LEVERAGE)
    risk_pct_ui  = st.slider("Riesgo por trade (%)", 1, 5, 2)
    modo = st.radio("Selecciona:", ["🔍 Solo Análisis (Paper)", "⚡ Trading Real"])
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
        log("Bot Sniper V5.1 Iniciado. 'No temas, porque yo estoy contigo' (Isaías 41:10)", "INFO")
        
        while True:
            # 1. Balance
            try:
                balance = exchange.fetch_total_balance()
                equity = safe_float(balance.get('USD', 0))
            except: equity = 0.0
            
            capital_ph.markdown(f"""<div class="metric-card"><b>💼 Capital</b><br><span style="font-size:1.5em; color:#4a9eff">${equity:.4f} USD</span><br>
            <small>W: {st.session_state.stats['wins']} | L: {st.session_state.stats['losses']} | PnL: ${st.session_state.stats['total_pnl']:.4f}</small></div>""", unsafe_allow_html=True)
            
            # 2. Gestionar Posiciones
            try:
                posiciones = exchange.fetch_positions()
                n_activas = gestionar_posiciones(posiciones, exchange)
            except Exception as e:
                posiciones, n_activas = [], 0
                log(f"Error fetch_positions: {e}", "ERROR")
            
            # Mostrar Posiciones
            pos_info = ""
            for p in posiciones:
                if safe_float(p.get('contracts', 0)) > 0:
                    sym = p['symbol']
                    side = p['side'].upper()
                    pnl = safe_float(p.get('unrealizedPnl'))
                    mark = safe_float(p.get('markPrice'))
                    entry = safe_float(p.get('entryPrice'))
                    trade_data = st.session_state.active_trades.get(sym, {})
                    sl_val = trade_data.get('sl', 0)
                    tp_val = trade_data.get('tp', 0)
                    move = ((mark-entry)/entry*100) if side=='LONG' else ((entry-mark)/entry*100)
                    color = "#00ff88" if pnl >= 0 else "#ff4466"
                    pos_info += f"""<div style="color:{color}; margin:4px 0"><b>{sym.split('/')[0]}</b> {side} | PnL: ${pnl:+.4f}<br>
                    <small>Entry: {entry:.2f} | SL: {sl_val:.2f} | TP: {tp_val:.2f}</small></div>"""
            
            posicion_ph.markdown(f"""<div class="metric-card"><b>📊 Posiciones ({n_activas}/{MAX_POSITIONS})</b><br>{pos_info if pos_info else 'Sin posiciones'}</div>""", unsafe_allow_html=True)
            
            # 3. Buscar Señales
            senales_encontradas = []
            if n_activas < MAX_POSITIONS:
                for sym in SYMBOLS:
                    try:
                        bars_15m = exchange.fetch_ohlcv(sym, TIMEFRAME_ENTRY, limit=BARS_LIMIT)
                        bars_1h  = exchange.fetch_ohlcv(sym, TIMEFRAME_TREND, limit=BARS_LIMIT)
                        senal = generar_senal(pd.DataFrame(bars_15m, columns=['ts','o','h','l','c','v']), 
                                              pd.DataFrame(bars_1h,  columns=['ts','o','h','l','c','v']), sym)
                        if senal:
                            senal['symbol'] = sym
                            senales_encontradas.append(senal)
                            if modo == "⚡ Trading Real":
                                qty = calcular_tamano_posicion(equity, senal['precio'], senal['sl'], leverage_ui)
                                if qty > 0:
                                    if 'BTC' in sym: qty = round(qty, 5)
                                    elif 'ETH' in sym: qty = round(qty, 4)
                                    else: qty = round(qty, 2)
                                    exchange.create_market_order(sym, 'buy' if senal['side'] == 'long' else 'sell', qty)
                                    st.session_state.active_trades[sym] = {'entry': senal['precio'], 'sl': senal['sl'], 'tp': senal['tp'], 'trailing': False}
                                    log(f"ORDEN EJECUTADA: {senal['side'].upper()} {qty} {sym}", "TRADE")
                                    n_activas += 1
                                    if n_activas >= MAX_POSITIONS: break
                    except Exception as e: log(f"Error analizando {sym}: {str(e)[:50]}", "ERROR")
            
            # Mostrar Señales
            senales_html = ""
            for s in senales_encontradas:
                color = '#00ff88' if s['side']=='long' else '#ff4466'
                senales_html += f"""<div style="border-left: 3px solid {color}; padding-left: 8px; margin: 8px 0;">
                <span style="color:{color}"><b>{s['side'].upper()}</b> — {s['symbol'].split('/')[0]}</span><br>
                <small>Entry: {s['precio']:.2f} | SL: {s['sl']:.2f} | TP: {s['tp']:.2f} | Score: {s['score']}</small></div>"""
            senal_ph.markdown(f"""<div class="metric-card"><b>🎯 Señales</b><br>{senales_html if senales_html else 'Esperando confluencia...'}</div>""", unsafe_allow_html=True)
            
            log_ph.markdown(f"""<div class="metric-card" style="max-height:200px; overflow-y:auto; font-family:monospace; font-size:0.8em">{"<br>".join(st.session_state.trade_log[:20])}</div>""", unsafe_allow_html=True)
            time.sleep(30)
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Error: {e}")
        time.sleep(15)
        st.rerun()
else:
    st.info("💡 Ingresa credenciales y activa el bot. 'El que es fiel en lo muy poco, también en lo mucho es fiel' (Lucas 16:10)")
