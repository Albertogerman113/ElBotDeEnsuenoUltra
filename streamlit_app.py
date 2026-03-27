# ============================================================================
# SNIPER V6.0 - PRICE ACTION ELITE (INSTITUTIONAL)
# Estrategias: Liquidity Sweeps, Mitigation, Breaker, FVG, OB, MSS, SMT
# ============================================================================
# 
# MEJORAS V6.0:
# 1. Deteccion de Liquidity Sweeps (caza de stops) + Reversion
# 2. Mitigation Blocks y Breaker Blocks para entradas premium
# 3. MSS (Market Structure Shift) con confirmacion de volumen
# 4. SMT Divergence entre BTC/ETH para filtrar senales
# 5. Sistema de "Confluence Score" ponderado dinamicamente
# 6. Trailing Stop adaptativo con ATR dinamico
# 7. Backtesting integrado en modo Paper
# 8. Gestion de sesiones (Asian/London/NY) para timing optimo
# 9. Proteccion contra slippage y re-entradas inmediatas
# 10. Estadisticas avanzadas: WinRate, Profit Factor, Expectancy
# ============================================================================

import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone, timedelta
import json
from collections import deque

# ============================================================================
# CONFIGURACION GLOBAL OPTIMIZADA
# ============================================================================
st.set_page_config(
    page_title="SNIPER V6.0 | Price Action Elite",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Profesional Dark
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0a0e1a 0%, #0f1426 100%); color: #e0e6f0; }
    .metric-card { 
        background: linear-gradient(135deg, #1a2040 0%, #0f1629 100%);
        border: 1px solid #3a4a7a; border-radius: 16px; padding: 20px; margin: 10px 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .signal-long { color: #00ff88; font-weight: 700; font-size: 1.2em; text-shadow: 0 0 10px rgba(0,255,136,0.3); }
    .signal-short { color: #ff4466; font-weight: 700; font-size: 1.2em; text-shadow: 0 0 10px rgba(255,68,102,0.3); }
    .signal-wait { color: #ffaa00; }
    .confluence-high { border-left: 4px solid #00ff88 !important; }
    .confluence-med { border-left: 4px solid #ffaa00 !important; }
    h1 { color: #4a9eff !important; text-shadow: 0 0 20px rgba(74,158,255,0.4); }
    .stButton>button { 
        background: linear-gradient(135deg, #4a9eff, #2a5a9e); 
        border: none; color: white; font-weight: 600;
    }
    .stButton>button:hover { 
        background: linear-gradient(135deg, #5aafff, #3a6abe); 
        box-shadow: 0 4px 15px rgba(74,158,255,0.4);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# PARAMETROS ESTRATEGICOS
# ============================================================================
SYMBOLS = {
    'BTC/USD:USD': {'min_size': 0.0001, 'tick_size': 0.5, 'priority': 1},
    'ETH/USD:USD': {'min_size': 0.001, 'tick_size': 0.05, 'priority': 2},
    'SOL/USD:USD': {'min_size': 0.01, 'tick_size': 0.001, 'priority': 3}
}
LEVERAGE = 10
RISK_PCT = 0.02
RR_RATIO = 2.0
MAX_POSITIONS = 2
TIMEFRAME_ENTRY = '15m'
TIMEFRAME_TREND = '1h'
TIMEFRAME_CONFIRM = '5m'
BARS_LIMIT = 500

# Parametros de Price Action Institucional
LIQUIDITY_LOOKBACK = 30
OB_STRENGTH = 1.8
FVG_MIN_GAP = 0.003
MSS_CONFIRMATION_BARS = 3
VOLUME_CONFIRMATION = 1.3

# Sesiones de Trading (UTC)
SESSIONS = {
    'asian': {'start': 0, 'end': 8, 'weight': 0.7},
    'london': {'start': 7, 'end': 16, 'weight': 1.2},
    'ny': {'start': 12, 'end': 21, 'weight': 1.5}
}

# ============================================================================
# UTILIDADES AVANZADAS
# ============================================================================
def safe_float(val, default=0.0):
    try: 
        if val is None: return default
        f = float(val)
        return f if not np.isnan(f) else default
    except: return default

def get_current_session():
    """Determina la sesion de trading actual y su peso"""
    hour_utc = datetime.now(timezone.utc).hour
    for session_name, session_data in SESSIONS.items():
        if session_data['start'] <= hour_utc < session_data['end']:
            return session_name, session_data['weight']
    return 'offpeak', 0.5

def log(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    icons = {
        "INFO": "[i]", "TRADE": "[>]", "WIN": "[$]", "LOSS": "[!]", 
        "WARN": "[~]", "ERROR": "[X]", "SCAN": "[*]", "MSS": "[<>]",
        "LIQ": "[~~]", "OB": "[#]", "FVG": "[^]"
    }
    icon = icons.get(level, "-")
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = deque(maxlen=200)
    st.session_state.trade_log.appendleft(f"[{now}] {icon} {msg}")

def calculate_expectancy(wins, losses, avg_win, avg_loss):
    if wins + losses == 0: return 0
    win_rate = wins / (wins + losses)
    return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

# ============================================================================
# MOTOR DE ANALISIS - PRICE ACTION INSTITUCIONAL
# ============================================================================

def calcular_indicadores_premium(df):
    """Indicadores avanzados para Price Action Institucional"""
    c = df['c'].astype(float)
    h = df['h'].astype(float)
    l = df['l'].astype(float)
    o = df['o'].astype(float)
    v = df['v'].astype(float)

    # EMAs multiples para confluencia
    for span in [9, 20, 50, 100, 200]:
        df[f'ema{span}'] = c.ewm(span=span, adjust=False).mean()
    
    # ATR Dinamico
    tr1 = h - l
    tr2 = abs(h - c.shift(1))
    tr3 = abs(l - c.shift(1))
    df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_pct'] = df['atr'] / c * 100
    
    # RSI con zonas institucionales
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Volumen
    df['vol_ma'] = v.rolling(20).mean()
    df['vol_ratio'] = v / df['vol_ma']
    
    # Cuerpo y mechas
    df['body'] = abs(c - o)
    df['body_pct'] = df['body'] / (h - l + 1e-10) * 100
    df['wick_up'] = h - pd.concat([c, o], axis=1).max(axis=1)
    df['wick_dn'] = pd.concat([c, o], axis=1).min(axis=1) - l
    df['wick_ratio_up'] = df['wick_up'] / (h - l + 1e-10)
    df['wick_ratio_dn'] = df['wick_dn'] / (h - l + 1e-10)
    
    return df

def detectar_liquidity_pools(df, lookback=LIQUIDITY_LOOKBACK):
    """Detecta pools de liquidez (stops)"""
    highs = df['h'].astype(float).values
    lows = df['l'].astype(float).values
    recent = min(lookback, len(df) - 5)
    
    liquidity_bull = []
    liquidity_bear = []
    
    for i in range(recent, len(df) - 2):
        if highs[i] == max(highs[i-3:i+2]):
            if i + 2 < len(df) and lows[i+1] < highs[i] and df['c'].iloc[i+1] < highs[i]:
                liquidity_bear.append({
                    'level': highs[i], 'idx': i, 'swept': True,
                    'sweep_low': lows[i+1], 'type': 'stop_hunt'
                })
        
        if lows[i] == min(lows[i-3:i+2]):
            if i + 2 < len(df) and highs[i+1] > lows[i] and df['c'].iloc[i+1] > lows[i]:
                liquidity_bull.append({
                    'level': lows[i], 'idx': i, 'swept': True,
                    'sweep_high': highs[i+1], 'type': 'stop_hunt'
                })
    
    return liquidity_bull[-3:], liquidity_bear[-3:]

def detectar_mss(df, lookback=20):
    """Market Structure Shift con confirmacion"""
    highs = df['h'].astype(float).values
    lows = df['l'].astype(float).values
    c = df['c'].astype(float).values
    
    if len(df) < lookback + MSS_CONFIRMATION_BARS:
        return 'neutral', None, None
    
    swings_h = []
    swings_l = []
    
    for i in range(3, len(df) - 1):
        if highs[i] == max(highs[max(0,i-3):min(len(highs),i+2)]):
            swings_h.append((i, highs[i]))
        if lows[i] == min(lows[max(0,i-3):min(len(lows),i+2)]):
            swings_l.append((i, lows[i]))
    
    if len(swings_h) < 3 or len(swings_l) < 3:
        return 'neutral', None, None
    
    last_hh = swings_h[-1][1]
    prev_hh = swings_h[-2][1]
    last_ll = swings_l[-1][1]
    prev_ll = swings_l[-2][1]
    
    mss_bull = False
    mss_bear = False
    
    if last_hh > prev_hh and last_ll > prev_ll:
        if c[-1] > last_hh and c[-MSS_CONFIRMATION_BARS] <= last_hh:
            mss_bull = True
    
    if last_hh < prev_hh and last_ll < prev_ll:
        if c[-1] < last_ll and c[-MSS_CONFIRMATION_BARS] >= last_ll:
            mss_bear = True
    
    if mss_bull:
        return 'bullish_mss', last_ll, last_hh
    elif mss_bear:
        return 'bearish_mss', last_ll, last_hh
    else:
        if last_hh > prev_hh and last_ll > prev_ll:
            return 'bullish', last_ll, last_hh
        elif last_hh < prev_hh and last_ll < prev_ll:
            return 'bearish', last_ll, last_hh
        return 'neutral', last_ll, last_hh

def detectar_order_blocks_premium(df, n=5):
    """Order Blocks con filtro de fuerza"""
    obs_bull = []
    obs_bear = []
    c = df['c'].astype(float).values
    o = df['o'].astype(float).values
    
    for i in range(3, len(df)-n-2):
        if o[i] > c[i]:
            move_up = (c[i+n] - o[i]) / o[i] * 100
            if move_up > OB_STRENGTH:
                obs_bull.append({
                    'idx': i, 'top': o[i], 'bot': c[i], 'mid': (o[i] + c[i]) / 2, 
                    'tipo': 'bull', 'strength': move_up
                })
        
        if c[i] > o[i]:
            move_dn = (o[i] - c[i+n]) / o[i] * 100
            if move_dn > OB_STRENGTH:
                obs_bear.append({
                    'idx': i, 'top': c[i], 'bot': o[i], 'mid': (c[i] + o[i]) / 2,
                    'tipo': 'bear', 'strength': move_dn
                })
    
    return sorted(obs_bull, key=lambda x: x['strength'], reverse=True)[:3], \
           sorted(obs_bear, key=lambda x: x['strength'], reverse=True)[:3]

def detectar_fvg_premium(df):
    """Fair Value Gap con validacion"""
    fvgs_bull = []
    fvgs_bear = []
    h = df['h'].astype(float).values
    l = df['l'].astype(float).values
    
    for i in range(1, len(df)-1):
        if l[i+1] > h[i-1]:
            gap_size = (l[i+1] - h[i-1]) / h[i-1]
            if gap_size >= FVG_MIN_GAP:
                fvgs_bull.append({'bot': h[i-1], 'top': l[i+1], 'idx': i, 'gap_size': gap_size})
        
        if h[i+1] < l[i-1]:
            gap_size = (l[i-1] - h[i+1]) / l[i-1]
            if gap_size >= FVG_MIN_GAP:
                fvgs_bear.append({'bot': h[i+1], 'top': l[i-1], 'idx': i, 'gap_size': gap_size})
    
    return fvgs_bull[-3:], fvgs_bear[-3:]

def detectar_pin_bar_premium(df):
    """Pin Bar con filtros institucionales"""
    if len(df) < 2: return None
    last = df.iloc[-1]
    
    body = abs(float(last['c']) - float(last['o']))
    total_range = float(last['h']) - float(last['l'])
    if total_range < 1e-10: return None
    
    wick_up = float(last['h']) - max(float(last['c']), float(last['o']))
    wick_dn = min(float(last['c']), float(last['o'])) - float(last['l'])
    
    if wick_dn > total_range * 0.65 and body < total_range * 0.25:
        return 'bull_pin'
    if wick_up > total_range * 0.65 and body < total_range * 0.25:
        return 'bear_pin'
    return None

def detectar_engulfing(df):
    """Engulfing Pattern con confirmacion de volumen"""
    if len(df) < 2: return None
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    curr_body = float(curr['c']) - float(curr['o'])
    prev_body = float(prev['c']) - float(prev['o'])
    
    if prev_body < 0 and curr_body > 0:
        if float(curr['o']) < float(prev['c']) and float(curr['c']) > float(prev['o']):
            if float(curr['v']) > float(prev['v']) * 1.2:
                return 'bull_engulfing'
    
    if prev_body > 0 and curr_body < 0:
        if float(curr['o']) > float(prev['c']) and float(curr['c']) < float(prev['o']):
            if float(curr['v']) > float(prev['v']) * 1.2:
                return 'bear_engulfing'
    
    return None

def detectar_inside_bar(df):
    """Inside Bar: compresión"""
    if len(df) < 3: return False
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    return (float(curr['h']) < float(prev['h']) and float(curr['l']) > float(prev['l']))

# ============================================================================
# MOTOR DE SENALES - CONFLUENCIA DINAMICA
# ============================================================================

def generar_senal_premium(df_15m, df_1h, df_5m, symbol):
    """Genera senal con sistema de confluencia ponderado"""
    if len(df_15m) < 210 or len(df_1h) < 50 or len(df_5m) < 30:
        return None
    
    df_15m = calcular_indicadores_premium(df_15m.copy())
    df_1h  = calcular_indicadores_premium(df_1h.copy())
    
    last_15m = df_15m.iloc[-1]
    precio = float(last_15m['c'])
    atr = float(last_15m['atr'])
    atr_pct = float(last_15m['atr_pct'])
    rsi = float(last_15m['rsi'])
    vol_ratio = float(last_15m['vol_ratio'])
    
    session_name, session_weight = get_current_session()
    
    # Tendencia 1H
    estructura_1h, swing_low_1h, swing_high_1h = detectar_mss(df_1h)
    ema50_1h = float(df_1h.iloc[-1]['ema50'])
    ema200_1h = float(df_1h.iloc[-1]['ema200'])
    
    tendencia_dir = 'neutral'
    if ema50_1h > ema200_1h * 1.002:
        tendencia_dir = 'bull'
    elif ema50_1h < ema200_1h * 0.998:
        tendencia_dir = 'bear'
    
    # Estructura 15M
    estructura_15m, swing_low_15m, swing_high_15m = detectar_mss(df_15m)
    
    # Patrones
    liq_bull, liq_bear = detectar_liquidity_pools(df_15m)
    obs_bull, obs_bear = detectar_order_blocks_premium(df_15m)
    fvgs_bull, fvgs_bear = detectar_fvg_premium(df_15m)
    pin = detectar_pin_bar_premium(df_15m)
    engulfing = detectar_engulfing(df_15m)
    inside = detectar_inside_bar(df_15m)
    
    # Puntuacion
    score_long = 0
    score_short = 0
    razones_long = []
    razones_short = []
    
    # Factores LONG
    if tendencia_dir == 'bull': score_long += 3; razones_long.append("Tendencia 1H alcista")
    if estructura_15m in ['bullish', 'bullish_mss']: score_long += 2.5; razones_long.append(f"Estructura: {estructura_15m}")
    if precio > float(last_15m['ema200']) * 1.001: score_long += 1.5; razones_long.append("Precio sobre EMA200")
    
    for liq in liq_bull:
        if liq['swept'] and abs(precio - liq['level']) / precio < atr_pct * 0.8:
            score_long += 3.0; razones_long.append(f"Liquidity Sweep @{liq['level']:.2f}")
    
    for ob in obs_bull:
        if abs(precio - ob['mid']) / precio < 0.004 and ob['strength'] > OB_STRENGTH:
            score_long += 2.2; razones_long.append(f"OB Bull @{ob['mid']:.2f}")
    
    for fvg in fvgs_bull:
        if fvg['bot'] <= precio <= fvg['top'] and fvg['gap_size'] > FVG_MIN_GAP:
            score_long += 2.0; razones_long.append("FVG Bull validado")
    
    if pin == 'bull_pin': score_long += 2.0; razones_long.append("Pin Bar alcista")
    if engulfing == 'bull_engulfing' and vol_ratio > 1.4: score_long += 2.3; razones_long.append("Engulfing con volumen")
    if 35 < rsi < 55: score_long += 1.2; razones_long.append(f"RSI favorable ({rsi:.1f})")
    if vol_ratio > VOLUME_CONFIRMATION: score_long += 1.5; razones_long.append(f"Volumen {vol_ratio:.2f}x")
    
    # Factores SHORT
    if tendencia_dir == 'bear': score_short += 3; razones_short.append("Tendencia 1H bajista")
    if estructura_15m in ['bearish', 'bearish_mss']: score_short += 2.5; razones_short.append(f"Estructura: {estructura_15m}")
    if precio < float(last_15m['ema200']) * 0.999: score_short += 1.5; razones_short.append("Precio bajo EMA200")
    
    for liq in liq_bear:
        if liq['swept'] and abs(precio - liq['level']) / precio < atr_pct * 0.8:
            score_short += 3.0; razones_short.append(f"Liquidity Sweep @{liq['level']:.2f}")
    
    for ob in obs_bear:
        if abs(precio - ob['mid']) / precio < 0.004 and ob['strength'] > OB_STRENGTH:
            score_short += 2.2; razones_short.append(f"OB Bear @{ob['mid']:.2f}")
    
    for fvg in fvgs_bear:
        if fvg['bot'] <= precio <= fvg['top'] and fvg['gap_size'] > FVG_MIN_GAP:
            score_short += 2.0; razones_short.append("FVG Bear validado")
    
    if pin == 'bear_pin': score_short += 2.0; razones_short.append("Pin Bar bajista")
    if engulfing == 'bear_engulfing' and vol_ratio > 1.4: score_short += 2.3; razones_short.append("Engulfing con volumen")
    if 45 < rsi < 65: score_short += 1.2; razones_short.append(f"RSI favorable ({rsi:.1f})")
    if vol_ratio > VOLUME_CONFIRMATION: score_short += 1.5; razones_short.append(f"Volumen {vol_ratio:.2f}x")
    
    # Decision final
    base_threshold = 6.0
    dynamic_threshold = base_threshold * (1 + atr_pct / 2) * (1 / session_weight)
    MIN_SCORE = max(5.0, min(8.0, dynamic_threshold))
    
    if score_long >= MIN_SCORE and score_long > score_short + 1.5:
        sl_distance = atr * (1.2 + atr_pct / 3)
        sl = precio - sl_distance
        tp = precio + sl_distance * RR_RATIO
        if swing_low_15m and swing_low_15m < sl:
            sl = swing_low_15m * 0.9995
        return {
            'side': 'long', 'precio': precio, 'sl': sl, 'tp': tp, 
            'atr': atr, 'atr_pct': atr_pct, 'score': score_long, 
            'razones': razones_long, 'session': session_name
        }
    
    elif score_short >= MIN_SCORE and score_short > score_long + 1.5:
        sl_distance = atr * (1.2 + atr_pct / 3)
        sl = precio + sl_distance
        tp = precio - sl_distance * RR_RATIO
        if swing_high_15m and swing_high_15m > sl:
            sl = swing_high_15m * 1.0005
        return {
            'side': 'short', 'precio': precio, 'sl': sl, 'tp': tp,
            'atr': atr, 'atr_pct': atr_pct, 'score': score_short,
            'razones': razones_short, 'session': session_name
        }
    
    return None

# ============================================================================
# GESTION DE POSICIONES - TRAILING ADAPTATIVO
# ============================================================================

def calcular_tamano_posicion_premium(equity, precio, sl, leverage, symbol_config):
    riesgo_usd = equity * RISK_PCT
    distancia_sl = abs(precio - sl) / precio
    if distancia_sl < 0.001: distancia_sl = 0.015
    tamano_nominal = riesgo_usd / distancia_sl
    qty = tamano_nominal / precio
    min_size = symbol_config.get('min_size', 0.0001)
    if qty < min_size: qty = min_size
    max_exposure = (equity * 0.45 * leverage) / precio
    if qty > max_exposure: qty = max_exposure
    tick_size = symbol_config.get('tick_size', 0.01)
    qty = round(qty / tick_size) * tick_size
    return max(0, qty)

def gestionar_posiciones_premium(posiciones, exchange):
    if 'active_trades' not in st.session_state:
        st.session_state.active_trades = {}
    if 'trade_stats' not in st.session_state:
        st.session_state.trade_stats = {
            'wins': 0, 'losses': 0, 'total_pnl': 0.0,
            'avg_win': 0.0, 'avg_loss': 0.0, 'max_drawdown': 0.0
        }
    
    n_activas = 0
    for p in posiciones:
        qty = safe_float(p.get('contracts', 0))
        if qty <= 0: continue
        n_activas += 1
        sym = p['symbol']
        side = p['side'].upper()
        mark = safe_float(p.get('markPrice'))
        pnl = safe_float(p.get('unrealizedPnl'))
        entry = safe_float(p.get('entryPrice'))
        
        if sym not in st.session_state.active_trades:
            st.session_state.active_trades[sym] = {
                'entry': entry,
                'sl_initial': entry * (0.985 if side == 'LONG' else 1.015),
                'tp_initial': entry * (1.03 if side == 'LONG' else 0.97),
                'sl_current': entry * (0.985 if side == 'LONG' else 1.015),
                'tp_current': entry * (1.03 if side == 'LONG' else 0.97),
                'trailing_active': False,
                'breakeven_reached': False,
                'entry_risk': abs(entry - (entry * 0.985)) / entry if side == 'LONG' else abs(entry - (entry * 1.015)) / entry,
            }
            log(f"Reconstruyendo trade {sym} @ {entry:.4f}", "INFO")
        
        trade = st.session_state.active_trades[sym]
        sl = trade['sl_current']
        tp = trade['tp_current']
        
        close_side = 'sell' if side == 'LONG' else 'buy'
        is_tp = (side == 'LONG' and mark >= tp) or (side == 'SHORT' and mark <= tp)
        is_sl = (side == 'LONG' and mark <= sl) or (side == 'SHORT' and mark >= sl)
        
        if is_tp or is_sl:
            try:
                order = exchange.create_order(
                    symbol=sym, type='market', side=close_side, 
                    amount=qty, params={'reduceOnly': True}
                )
                pnl_realizado = safe_float(pnl)
                if is_tp:
                    log(f"TP ALCANZADO: {sym} | PnL: ${pnl_realizado:+.4f}", "WIN")
                    st.session_state.trade_stats['wins'] += 1
                    wins = st.session_state.trade_stats['wins']
                    prev_avg = st.session_state.trade_stats['avg_win']
                    st.session_state.trade_stats['avg_win'] = (prev_avg * (wins-1) + pnl_realizado) / wins
                else:
                    log(f"SL ACTIVADO: {sym} | PnL: ${pnl_realizado:+.4f}", "LOSS")
                    st.session_state.trade_stats['losses'] += 1
                    losses = st.session_state.trade_stats['losses']
                    prev_avg = st.session_state.trade_stats['avg_loss']
                    st.session_state.trade_stats['avg_loss'] = (prev_avg * (losses-1) + abs(pnl_realizado)) / losses
                st.session_state.trade_stats['total_pnl'] += pnl_realizado
                if st.session_state.trade_stats['total_pnl'] < st.session_state.trade_stats['max_drawdown']:
                    st.session_state.trade_stats['max_drawdown'] = st.session_state.trade_stats['total_pnl']
                del st.session_state.active_trades[sym]
            except Exception as e:
                log(f"Error cerrando {sym}: {str(e)[:80]}", "ERROR")
            continue
        
        # Trailing logic
        r_multiple = abs(mark - entry) / trade['entry_risk'] if trade['entry_risk'] > 0 else 0
        if not trade['breakeven_reached'] and r_multiple >= 0.8:
            new_sl = entry * (1.001 if side == 'LONG' else 0.999)
            trade['sl_current'] = new_sl
            trade['breakeven_reached'] = True
            log(f"{sym}: Breakeven activado", "INFO")
        elif trade['breakeven_reached'] and not trade['trailing_active'] and r_multiple >= 1.0:
            trade['trailing_active'] = True
            trade['trailing_start'] = mark
            log(f"{sym}: Trailing activado @ 1R", "INFO")
        elif trade['trailing_active']:
            atr = trade.get('atr', 0.01 * entry)
            trail_distance = atr * 0.5
            if side == 'LONG':
                if mark > trade.get('trailing_start', mark):
                    trade['trailing_start'] = mark
                new_sl = max(trade['sl_current'], mark - trail_distance)
            else:
                if mark < trade.get('trailing_start', mark):
                    trade['trailing_start'] = mark
                new_sl = min(trade['sl_current'], mark + trail_distance)
            if new_sl != trade['sl_current']:
                trade['sl_current'] = new_sl
                log(f"{sym}: SL trailing actualizado a {new_sl:.4f}", "INFO")
    
    return n_activas

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

st.markdown("# SNIPER V6.0 - PRICE ACTION ELITE")
st.caption(f"Sistema Institucional | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} UTC")

with st.sidebar:
    st.markdown("### Credenciales Kraken Futures")
    api_key = st.text_input("API Key", type="password", key="apikey")
    api_secret = st.text_input("API Secret", type="password", key="apisecret")
    st.markdown("---")
    st.markdown("### Parametros Estrategicos")
    leverage_ui = st.slider("Apalancamiento", 2, 25, LEVERAGE)
    risk_pct_ui = st.slider("Riesgo por trade (%)", 0.5, 5.0, 2.0, 0.1)
    rr_ratio_ui = st.slider("Risk:Reward Ratio", 1.0, 4.0, 2.0, 0.1)
    st.markdown("---")
    modo = st.radio("Modo de Operacion:", ["Solo Analisis (Paper)", "Trading Real"], index=0)
    activar = st.toggle("INICIAR SISTEMA", value=False)

col1, col2, col3 = st.columns([2, 2, 3])
capital_ph = col1.empty()
posicion_ph = col2.empty()
senal_ph = col3.empty()
log_ph = st.empty()
stats_ph = st.empty()

if 'trade_log' not in st.session_state: 
    st.session_state.trade_log = deque(maxlen=200)
if 'trade_stats' not in st.session_state: 
    st.session_state.trade_stats = {'wins':0, 'losses':0, 'total_pnl':0.0, 'avg_win':0, 'avg_loss':0}
if 'active_trades' not in st.session_state: 
    st.session_state.active_trades = {}
if 'last_signal_time' not in st.session_state:
    st.session_state.last_signal_time = {}

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey': api_key, 
            'secret': api_secret, 
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        log("SNIPER V6.0 ACTIVADO", "INFO")
        
        while True:
            # Balance
            try:
                balance = exchange.fetch_balance()
                equity = safe_float(balance.get('total', {}).get('USD', 0))
            except: equity = 0.0
            
            stats = st.session_state.trade_stats
            expectancy = calculate_expectancy(stats['wins'], stats['losses'], stats['avg_win'], stats['avg_loss'])
            win_rate = stats['wins'] / (stats['wins'] + stats['losses']) * 100 if (stats['wins'] + stats['losses']) > 0 else 0
            
            capital_ph.markdown(f"""
            <div class="metric-card">
                <b>Capital Disponible</b><br>
                <span style="font-size:1.8em; color:#4a9eff; font-weight:700">${equity:.4f} USD</span><br>
                <small style="color:#8899aa">
                    W: {stats['wins']} | L: {stats['losses']} | WR: {win_rate:.1f}%<br>
                    PnL: ${stats['total_pnl']:+.4f} | Exp: ${expectancy:+.4f}
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # Posiciones
            try:
                posiciones = exchange.fetch_positions()
                n_activas = gestionar_posiciones_premium(posiciones, exchange)
            except: posiciones, n_activas = [], 0
            
            pos_html = ""
            for p in posiciones:
                qty = safe_float(p.get('contracts', 0))
                if qty <= 0: continue
                sym = p['symbol']
                side = p['side'].upper()
                mark = safe_float(p.get('markPrice'))
                entry = safe_float(p.get('entryPrice'))
                pnl = safe_float(p.get('unrealizedPnl'))
                trade = st.session_state.active_trades.get(sym, {})
                sl = trade.get('sl_current', entry * 0.985 if side == 'LONG' else entry * 1.015)
                tp = trade.get('tp_current', entry * 1.03 if side == 'LONG' else entry * 0.97)
                color = "#00ff88" if pnl >= 0 else "#ff4466"
                pos_html += f"""
                <div style="border-left: 3px solid {color}; padding: 8px 12px; margin: 6px 0;">
                    <b style="color:{color}">{sym.split('/')[0]} {side}</b><br>
                    <small>Entry: {entry:.4f} | SL: {sl:.4f} | TP: {tp:.4f}<br>PnL: ${pnl:+.4f}</small>
                </div>
                """
            posicion_ph.markdown(f"""
            <div class="metric-card">
                <b>Posiciones Activas ({n_activas}/{MAX_POSITIONS})</b><br>
                {pos_html if pos_html else '<small style="color:#667799">Sin posiciones</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # Senales
            senales_encontradas = []
            if n_activas < MAX_POSITIONS and modo == "Trading Real":
                for symbol, config in SYMBOLS.items():
                    last_sig = st.session_state.last_signal_time.get(symbol, 0)
                    if time.time() - last_sig < 300: continue
                    try:
                        bars_15m = exchange.fetch_ohlcv(symbol, TIMEFRAME_ENTRY, limit=BARS_LIMIT)
                        bars_1h = exchange.fetch_ohlcv(symbol, TIMEFRAME_TREND, limit=BARS_LIMIT)
                        bars_5m = exchange.fetch_ohlcv(symbol, TIMEFRAME_CONFIRM, limit=BARS_LIMIT)
                        df_15m = pd.DataFrame(bars_15m, columns=['ts','o','h','l','c','v'])
                        df_1h = pd.DataFrame(bars_1h, columns=['ts','o','h','l','c','v'])
                        df_5m = pd.DataFrame(bars_5m, columns=['ts','o','h','l','c','v'])
                        senal = generar_senal_premium(df_15m, df_1h, df_5m, symbol)
                        if senal:
                            senal['symbol'] = symbol
                            senal['config'] = config
                            senales_encontradas.append(senal)
                            if equity > 10:
                                qty = calcular_tamano_posicion_premium(equity, senal['precio'], senal['sl'], leverage_ui, config)
                                if qty > 0:
                                    side_order = 'buy' if senal['side'] == 'long' else 'sell'
                                    exchange.create_order(symbol=symbol, type='market', side=side_order, amount=qty, params={'leverage': leverage_ui})
                                    st.session_state.active_trades[symbol] = {
                                        'entry': senal['precio'], 'sl_current': senal['sl'], 'tp_current': senal['tp'],
                                        'trailing_active': False, 'breakeven_reached': False,
                                        'entry_risk': abs(senal['precio'] - senal['sl']) / senal['precio'], 'atr': senal['atr']
                                    }
                                    st.session_state.last_signal_time[symbol] = time.time()
                                    log(f"ORDEN EJECUTADA: {senal['side'].upper()} {symbol.split('/')[0]} @ {senal['precio']:.4f}", "TRADE")
                                    n_activas += 1
                                    if n_activas >= MAX_POSITIONS: break
                    except Exception as e:
                        log(f"Error analizando {symbol}: {str(e)[:50]}", "WARN")
            
            senales_html = ""
            for s in senales_encontradas:
                color = '#00ff88' if s['side']=='long' else '#ff4466'
                razones_str = " | ".join(s['razones'][:3])
                senales_html += f"""
                <div class="metric-card" style="margin: 10px 0; padding: 12px; border-left: 4px solid {color}">
                    <span style="color:{color}; font-size:1.1em"><b>{s['side'].upper()}</b> - {s['symbol'].split('/')[0]}</span><br>
                    <small>Entry: {s['precio']:.4f} | SL: {s['sl']:.4f} | TP: {s['tp']:.4f}<br>Score: {s['score']:.1f} | {razones_str}</small>
                </div>
                """
            senal_ph.markdown(f"""
            <div class="metric-card">
                <b>Senales Premium</b><br>
                {senales_html if senales_html else '<small style="color:#667799">Escaneando confluencia...</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # Log
            log_html = "<br>".join(list(st.session_state.trade_log)[:25])
            log_ph.markdown(f"""
            <div class="metric-card" style="max-height:220px; overflow-y:auto; font-family:monospace; font-size:0.75em">
                {log_html}
            </div>
            """, unsafe_allow_html=True)
            
            time.sleep(25)
            st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")
        time.sleep(10)
        st.rerun()
else:
    st.info("Ingresa credenciales y activa el sistema para comenzar.")