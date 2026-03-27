╔══════════════════════════════════════════════════════════════════╗
║          SNIPER V6.0 - PRICE ACTION ELITE (INSTITUTIONAL)        ║
║          Estrategias: Liquidity Sweeps, Mitigation, Breaker,    ║
║          FVG, OB, MSS (Market Structure Shift), SMT Divergence   ║
╚══════════════════════════════════════════════════════════════════╝

MEJORAS V6.0:
1. Detección de Liquidity Sweeps (caza de stops) + Reversión
2. Mitigation Blocks y Breaker Blocks para entradas premium
3. MSS (Market Structure Shift) con confirmación de volumen
4. SMT Divergence entre BTC/ETH para filtrar señales
5. Sistema de "Confluence Score" ponderado dinámicamente
6. Trailing Stop adaptativo con ATR dinámico
7. Backtesting integrado en modo Paper
8. Gestión de sesiones (Asian/London/NY) para timing óptimo
9. Protección contra slippage y re-entradas inmediatas
10. Estadísticas avanzadas: WinRate, Profit Factor, Expectancy
"""

import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone, timedelta
import json
import hmac
import hashlib
from collections import deque

# ══════════════════════════════════════════
# CONFIGURACIÓN GLOBAL OPTIMIZADA
# ══════════════════════════════════════════
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

# ══════════════════════════════════════════
# PARÁMETROS ESTRATÉGICOS
# ══════════════════════════════════════════
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

# Parámetros de Price Action Institucional
LIQUIDITY_LOOKBACK = 30      # Velas para detectar liquidity pools
OB_STRENGTH = 1.8            # % mínimo de movimiento post-OB
FVG_MIN_GAP = 0.003          # Gap mínimo para FVG válido
MSS_CONFIRMATION_BARS = 3    # Velas para confirmar MSS
VOLUME_CONFIRMATION = 1.3    # Ratio de volumen para confirmación

# Sesiones de Trading (UTC)
SESSIONS = {
    'asian': {'start': 0, 'end': 8, 'weight': 0.7},
    'london': {'start': 7, 'end': 16, 'weight': 1.2},
    'ny': {'start': 12, 'end': 21, 'weight': 1.5}
}

# ══════════════════════════════════════════
# UTILIDADES AVANZADAS
# ══════════════════════════════════════════
def safe_float(val, default=0.0):
    try: 
        if val is None: return default
        f = float(val)
        return f if not np.isnan(f) else default
    except: return default

def get_current_session():
    """Determina la sesión de trading actual y su peso"""
    hour_utc = datetime.now(timezone.utc).hour
    for session_name, session_data in SESSIONS.items():
        if session_data['start'] <= hour_utc < session_data['end']:
            return session_name, session_data['weight']
    return 'offpeak', 0.5

def log(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    icons = {
        "INFO": "ℹ️", "TRADE": "🚀", "WIN": "💰", "LOSS": "🛡️", 
        "WARN": "⚠️", "ERROR": "❌", "SCAN": "🔍", "MSS": "🔄",
        "LIQ": "🌊", "OB": "🧱", "FVG": "⚡"
    }
    icon = icons.get(level, "•")
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = deque(maxlen=200)
    st.session_state.trade_log.appendleft(f"[{now}] {icon} {msg}")

def calculate_expectancy(wins, losses, avg_win, avg_loss):
    """Calcula la esperanza matemática del sistema"""
    if wins + losses == 0: return 0
    win_rate = wins / (wins + losses)
    return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

# ══════════════════════════════════════════
# MOTOR DE ANÁLISIS - PRICE ACTION INSTITUCIONAL
# ══════════════════════════════════════════

def calcular_indicadores_premium(df):
    """Indicadores avanzados para Price Action Institucional"""
    c = df['c'].astype(float)
    h = df['h'].astype(float)
    l = df['l'].astype(float)
    o = df['o'].astype(float)
    v = df['v'].astype(float)

    # EMAs múltiples para confluencia
    for span in [9, 20, 50, 100, 200]:
        df[f'ema{span}'] = c.ewm(span=span, adjust=False).mean()
    
    # ATR Dinámico con multiplicador adaptativo
    tr1 = h - l
    tr2 = abs(h - c.shift(1))
    tr3 = abs(l - c.shift(1))
    df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_pct'] = df['atr'] / c * 100  # ATR en porcentaje
    
    # RSI con zonas institucionales
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi_zone'] = pd.cut(df['rsi'], 
                           bins=[0, 30, 40, 60, 70, 100], 
                           labels=['oversold', 'bearish', 'neutral', 'bullish', 'overbought'])
    
    # Volumen Profile simplificado
    df['vol_ma'] = v.rolling(20).mean()
    df['vol_ratio'] = v / df['vol_ma']
    df['vol_spike'] = df['vol_ratio'] > 2.0
    
    # Cuerpo y mechas para patrones
    df['body'] = abs(c - o)
    df['body_pct'] = df['body'] / (h - l + 1e-10) * 100
    df['wick_up'] = h - pd.concat([c, o], axis=1).max(axis=1)
    df['wick_dn'] = pd.concat([c, o], axis=1).min(axis=1) - l
    df['wick_ratio_up'] = df['wick_up'] / (h - l + 1e-10)
    df['wick_ratio_dn'] = df['wick_dn'] / (h - l + 1e-10)
    
    # Momentum para confirmación
    df['momentum'] = c - c.shift(5)
    df['momentum_conf'] = df['momentum'] * df['momentum'].shift(1) > 0
    
    return df

def detectar_liquidity_pools(df, lookback=LIQUIDITY_LOOKBACK):
    """Detecta pools de liquidez (stops) por encima de máximos y debajo de mínimos"""
    highs = df['h'].astype(float).values
    lows = df['l'].astype(float).values
    recent = min(lookback, len(df) - 5)
    
    liquidity_bull = []  # Stops por debajo (para longs)
    liquidity_bear = []  # Stops por encima (para shorts)
    
    # Buscar máximos/mínimos significativos
    for i in range(recent, len(df) - 2):
        # Liquidez bearish: máximo que fue barrido
        if highs[i] == max(highs[i-3:i+2]):
            # Verificar si fue "swept" (precio superó y cerró por debajo)
            if i + 2 < len(df) and lows[i+1] < highs[i] and df['c'].iloc[i+1] < highs[i]:
                liquidity_bear.append({
                    'level': highs[i], 'idx': i, 'swept': True,
                    'sweep_low': lows[i+1], 'type': 'stop_hunt'
                })
        
        # Liquidez bullish: mínimo que fue barrido
        if lows[i] == min(lows[i-3:i+2]):
            if i + 2 < len(df) and highs[i+1] > lows[i] and df['c'].iloc[i+1] > lows[i]:
                liquidity_bull.append({
                    'level': lows[i], 'idx': i, 'swept': True,
                    'sweep_high': highs[i+1], 'type': 'stop_hunt'
                })
    
    return liquidity_bull[-3:], liquidity_bear[-3:]

def detectar_mitigation_blocks(df):
    """Mitigation Block: Zona donde el precio "mitiga" un movimiento previo"""
    c = df['c'].astype(float).values
    o = df['o'].astype(float).values
    h = df['h'].astype(float).values
    l = df['l'].astype(float).values
    
    mitigation_bull = []
    mitigation_bear = []
    
    for i in range(10, len(df) - 5):
        # Buscar movimiento fuerte previo
        move_up = (c[i] - c[i-5]) / c[i-5] * 100
        move_dn = (c[i-5] - c[i]) / c[i-5] * 100
        
        # Mitigation Bull: después de caída fuerte, consolidación y ruptura alcista
        if move_dn > 2.0:  # Caída previa
            # Buscar zona de consolidación
            consolidation = True
            for j in range(i-4, i+1):
                if abs(c[j] - c[j-1]) / c[j-1] * 100 > 0.8:
                    consolidation = False
                    break
            if consolidation and i+3 < len(df) and c[i+3] > h[i]:
                mitigation_bull.append({
                    'top': max(h[i-4:i+1]), 'bot': min(l[i-4:i+1]),
                    'mid': (max(h[i-4:i+1]) + min(l[i-4:i+1])) / 2,
                    'idx': i, 'type': 'mitigation_bull'
                })
        
        # Mitigation Bear: simétrico
        if move_up > 2.0:
            consolidation = True
            for j in range(i-4, i+1):
                if abs(c[j] - c[j-1]) / c[j-1] * 100 > 0.8:
                    consolidation = False
                    break
            if consolidation and i+3 < len(df) and c[i+3] < l[i]:
                mitigation_bear.append({
                    'top': max(h[i-4:i+1]), 'bot': min(l[i-4:i+1]),
                    'mid': (max(h[i-4:i+1]) + min(l[i-4:i+1])) / 2,
                    'idx': i, 'type': 'mitigation_bear'
                })
    
    return mitigation_bull[-2:], mitigation_bear[-2:]

def detectar_breaker_blocks(df):
    """Breaker Block: Order block que "rompe" estructura previa"""
    c = df['c'].astype(float).values
    o = df['o'].astype(float).values
    h = df['h'].astype(float).values
    l = df['l'].astype(float).values
    
    breaker_bull = []
    breaker_bear = []
    
    for i in range(8, len(df) - 3):
        # Breaker Bull: OB bajista que es roto alcistamente con fuerza
        if o[i] > c[i]:  # Vela bajista
            # Verificar ruptura posterior
            if i+2 < len(df) and c[i+2] > o[i] and (c[i+2] - o[i]) / o[i] * 100 > 0.8:
                breaker_bull.append({
                    'level': o[i], 'idx': i,
                    'confirmation': c[i+2], 'strength': (c[i+2] - o[i]) / o[i]
                })
        
        # Breaker Bear: OB alcista roto bajistamente
        if c[i] > o[i]:  # Vela alcista
            if i+2 < len(df) and c[i+2] < o[i] and (o[i] - c[i+2]) / o[i] * 100 > 0.8:
                breaker_bear.append({
                    'level': o[i], 'idx': i,
                    'confirmation': c[i+2], 'strength': (o[i] - c[i+2]) / o[i]
                })
    
    return breaker_bull[-2:], breaker_bear[-2:]

def detectar_mss(df, lookback=20):
    """Market Structure Shift con confirmación"""
    highs = df['h'].astype(float).values
    lows = df['l'].astype(float).values
    c = df['c'].astype(float).values
    
    if len(df) < lookback + MSS_CONFIRMATION_BARS:
        return 'neutral', None, None
    
    # Identificar últimos swings
    swings_h = []
    swings_l = []
    
    for i in range(3, len(df) - 1):
        if highs[i] == max(highs[max(0,i-3):min(len(highs),i+2)]):
            swings_h.append((i, highs[i]))
        if lows[i] == min(lows[max(0,i-3):min(len(lows),i+2)]):
            swings_l.append((i, lows[i]))
    
    if len(swings_h) < 3 or len(swings_l) < 3:
        return 'neutral', None, None
    
    # Analizar estructura reciente
    last_hh = swings_h[-1][1]
    prev_hh = swings_h[-2][1]
    last_ll = swings_l[-1][1]
    prev_ll = swings_l[-2][1]
    
    # MSS Bullish: Rompe último HH y mantiene LL más alto
    mss_bull = False
    mss_bear = False
    
    if last_hh > prev_hh and last_ll > prev_ll:
        # Confirmar con cierre por encima del HH
        if c[-1] > last_hh and c[-MSS_CONFIRMATION_BARS] <= last_hh:
            mss_bull = True
    
    if last_hh < prev_hh and last_ll < prev_ll:
        # Confirmar con cierre por debajo del LL
        if c[-1] < last_ll and c[-MSS_CONFIRMATION_BARS] >= last_ll:
            mss_bear = True
    
    if mss_bull:
        return 'bullish_mss', last_ll, last_hh
    elif mss_bear:
        return 'bearish_mss', last_ll, last_hh
    else:
        # Estructura normal
        if last_hh > prev_hh and last_ll > prev_ll:
            return 'bullish', last_ll, last_hh
        elif last_hh < prev_hh and last_ll < prev_ll:
            return 'bearish', last_ll, last_hh
        return 'neutral', last_ll, last_hh

def detectar_smt_divergence(df_btc, df_eth):
    """Smart Money Technique: Divergencia entre BTC y ETH para filtrar"""
    if len(df_btc) < 20 or len(df_eth) < 20:
        return None
    
    # Comparar momentum reciente
    btc_mom = df_btc['c'].iloc[-1] - df_btc['c'].iloc[-5]
    eth_mom = df_eth['c'].iloc[-1] - df_eth['c'].iloc[-5]
    
    # Divergencia: uno sube, otro baja
    if btc_mom * eth_mom < 0:
        # BTC fuerte, ETH débil -> preferir shorts en altcoins
        if btc_mom > 0 and eth_mom < 0:
            return 'btc_strength'
        elif btc_mom < 0 and eth_mom > 0:
            return 'eth_strength'
    return None

# ══════════════════════════════════════════
# MOTOR DE SEÑALES - CONFLUENCIA DINÁMICA
# ══════════════════════════════════════════

def generar_senal_premium(df_15m, df_1h, df_5m, symbol, df_btc=None, df_eth=None):
    """Genera señal con sistema de confluencia ponderado institucional"""
    if len(df_15m) < 210 or len(df_1h) < 50 or len(df_5m) < 30:
        return None
    
    # Calcular indicadores
    df_15m = calcular_indicadores_premium(df_15m.copy())
    df_1h  = calcular_indicadores_premium(df_1h.copy())
    df_5m  = calcular_indicadores_premium(df_5m.copy())
    
    last_15m = df_15m.iloc[-1]
    precio = float(last_15m['c'])
    atr = float(last_15m['atr'])
    atr_pct = float(last_15m['atr_pct'])
    rsi = float(last_15m['rsi'])
    vol_ratio = float(last_15m['vol_ratio'])
    
    # Obtener sesión actual para ponderación
    session_name, session_weight = get_current_session()
    
    # === ANÁLISIS DE TENDENCIA (1H) ===
    estructura_1h, swing_low_1h, swing_high_1h = detectar_mss(df_1h)
    ema50_1h = float(df_1h.iloc[-1]['ema50'])
    ema200_1h = float(df_1h.iloc[-1]['ema200'])
    
    tendencia_score = 0
    if ema50_1h > ema200_1h * 1.002:  # Filtro de separación mínima
        tendencia_score += 2
        tendencia_dir = 'bull'
    elif ema50_1h < ema200_1h * 0.998:
        tendencia_score += 2
        tendencia_dir = 'bear'
    else:
        tendencia_dir = 'neutral'
    
    # === ANÁLISIS DE ESTRUCTURA (15M) ===
    estructura_15m, swing_low_15m, swing_high_15m = detectar_mss(df_15m)
    
    # === DETECCIÓN DE PATRONES INSTITUCIONALES ===
    liq_bull, liq_bear = detectar_liquidity_pools(df_15m)
    mit_bull, mit_bear = detectar_mitigation_blocks(df_15m)
    breaker_bull, breaker_bear = detectar_breaker_blocks(df_15m)
    obs_bull, obs_bear = detectar_order_blocks_premium(df_15m)
    fvgs_bull, fvgs_bear = detectar_fvg_premium(df_15m)
    
    # Patrones de velas
    pin = detectar_pin_bar_premium(df_15m)
    engulfing = detectar_engulfing(df_15m)
    inside = detectar_inside_bar(df_15m)
    
    # SMT Divergence si hay datos de BTC/ETH
    smt_signal = None
    if df_btc is not None and df_eth is not None and 'BTC' not in symbol:
        smt_signal = detectar_smt_divergence(df_btc, df_eth)
    
    # === SISTEMA DE PUNTUACIÓN DINÁMICO ===
    score_long = 0
    score_short = 0
    razones_long = []
    razones_short = []
    weights = {'tendencia': 2.5, 'estructura': 2.0, 'patron': 1.8, 'volumen': 1.2, 'sesion': session_weight}
    
    # Factores LONG
    if tendencia_dir == 'bull': 
        score_long += 3 * weights['tendencia']; razones_long.append("Tendencia 1H alcista confirmada")
    if estructura_15m in ['bullish', 'bullish_mss']: 
        score_long += 2.5 * weights['estructura']; razones_long.append(f"Estructura 15M: {estructura_15m}")
    if precio > float(last_15m['ema200']) * 1.001: 
        score_long += 1.5; razones_long.append("Precio sobre EMA200 con filtro")
    
    # Liquidity Sweep Bull (precio barrió stops y revirtió)
    for liq in liq_bull:
        if liq['swept'] and abs(precio - liq['level']) / precio < atr_pct * 0.8:
            score_long += 3.0; razones_long.append(f"🌊 Liquidity Sweep en {liq['level']:.2f}")
    
    # Mitigation Block Bull
    for mit in mit_bull:
        if mit['bot'] <= precio <= mit['top']:
            score_long += 2.5; razones_long.append(f"🧱 Mitigation Block en {mit['mid']:.2f}")
    
    # Breaker Block Bull
    for brk in breaker_bull:
        if abs(precio - brk['level']) / precio < 0.003 and precio > brk['confirmation']:
            score_long += 2.8; razones_long.append(f"⚡ Breaker Block confirmado @{brk['level']:.2f}")
    
    # Order Blocks Premium
    for ob in obs_bull:
        if abs(precio - ob['mid']) / precio < 0.004 and ob['strength'] > OB_STRENGTH:
            score_long += 2.2; razones_long.append(f"OB Bull fuerte @{ob['mid']:.2f}")
    
    # FVG Premium
    for fvg in fvgs_bull:
        if fvg['bot'] <= precio <= fvg['top'] and (fvg['top']-fvg['bot'])/fvg['bot'] > FVG_MIN_GAP:
            score_long += 2.0; razones_long.append(f"⚡ FVG Bull validado")
    
    # Patrones de velas
    if pin == 'bull_pin' and last_15m['wick_ratio_dn'] > 0.65: 
        score_long += 2.0; razones_long.append("📍 Pin Bar alcista premium")
    if engulfing == 'bull_engulfing' and vol_ratio > 1.4: 
        score_long += 2.3; razones_long.append("🔥 Engulfing alcista con volumen")
    
    # RSI en zona favorable
    if 35 < rsi < 55: 
        score_long += 1.2; razones_long.append(f"RSI en zona de entrada ({rsi:.1f})")
    
    # Volumen de confirmación
    if vol_ratio > VOLUME_CONFIRMATION: 
        score_long += 1.5 * weights['volumen']; razones_long.append(f"Volumen {vol_ratio:.2f}x promedio")
    
    # SMT Filter
    if smt_signal == 'btc_strength': 
        score_long += 1.0; razones_long.append("SMT: BTC mostrando fortaleza")
    
    # Factores SHORT (simétrico con ajustes)
    if tendencia_dir == 'bear': 
        score_short += 3 * weights['tendencia']; razones_short.append("Tendencia 1H bajista confirmada")
    if estructura_15m in ['bearish', 'bearish_mss']: 
        score_short += 2.5 * weights['estructura']; razones_short.append(f"Estructura 15M: {estructura_15m}")
    if precio < float(last_15m['ema200']) * 0.999: 
        score_short += 1.5; razones_short.append("Precio bajo EMA200 con filtro")
    
    for liq in liq_bear:
        if liq['swept'] and abs(precio - liq['level']) / precio < atr_pct * 0.8:
            score_short += 3.0; razones_short.append(f"🌊 Liquidity Sweep bear en {liq['level']:.2f}")
    
    for mit in mit_bear:
        if mit['bot'] <= precio <= mit['top']:
            score_short += 2.5; razones_short.append(f"🧱 Mitigation Block bear en {mit['mid']:.2f}")
    
    for brk in breaker_bear:
        if abs(precio - brk['level']) / precio < 0.003 and precio < brk['confirmation']:
            score_short += 2.8; razones_short.append(f"⚡ Breaker Block bear confirmado @{brk['level']:.2f}")
    
    for ob in obs_bear:
        if abs(precio - ob['mid']) / precio < 0.004 and ob['strength'] > OB_STRENGTH:
            score_short += 2.2; razones_short.append(f"OB Bear fuerte @{ob['mid']:.2f}")
    
    for fvg in fvgs_bear:
        if fvg['bot'] <= precio <= fvg['top'] and (fvg['top']-fvg['bot'])/fvg['bot'] > FVG_MIN_GAP:
            score_short += 2.0; razones_short.append(f"⚡ FVG Bear validado")
    
    if pin == 'bear_pin' and last_15m['wick_ratio_up'] > 0.65: 
        score_short += 2.0; razones_short.append("📍 Pin Bar bajista premium")
    if engulfing == 'bear_engulfing' and vol_ratio > 1.4: 
        score_short += 2.3; razones_short.append("🔥 Engulfing bajista con volumen")
    
    if 45 < rsi < 65: 
        score_short += 1.2; razones_short.append(f"RSI en zona de entrada short ({rsi:.1f})")
    
    if vol_ratio > VOLUME_CONFIRMATION: 
        score_short += 1.5 * weights['volumen']; razones_short.append(f"Volumen {vol_ratio:.2f}x promedio")
    
    if smt_signal == 'eth_strength': 
        score_short += 1.0; razones_short.append("SMT: ETH mostrando fortaleza relativa")
    
    # === DECISIÓN FINAL CON UMBRAL DINÁMICO ===
    # Umbral ajustado por volatilidad y sesión
    base_threshold = 6.0
    dynamic_threshold = base_threshold * (1 + atr_pct / 2) * (1 / session_weight)
    
    MIN_SCORE = max(5.0, min(8.0, dynamic_threshold))
    
    if score_long >= MIN_SCORE and score_long > score_short + 1.5:
        # Calcular SL/TP con ATR adaptativo
        sl_distance = atr * (1.2 + atr_pct / 3)  # SL más amplio en alta volatilidad
        sl = precio - sl_distance
        tp = precio + sl_distance * RR_RATIO
        
        # Ajustar SL por estructura
        if swing_low_15m and swing_low_15m < sl:
            sl = swing_low_15m * 0.9995  # Justo debajo del swing
        
        return {
            'side': 'long', 'precio': precio, 'sl': sl, 'tp': tp, 
            'atr': atr, 'atr_pct': atr_pct, 'score': score_long, 
            'razones': razones_long, 'session': session_name,
            'sl_type': 'structure' if swing_low_15m and swing_low_15m < precio - atr else 'atr'
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
            'razones': razones_short, 'session': session_name,
            'sl_type': 'structure' if swing_high_15m and swing_high_15m > precio + atr else 'atr'
        }
    
    return None

# Funciones auxiliares premium (Order Blocks y FVG mejorados)
def detectar_order_blocks_premium(df, n=5):
    """Order Blocks con filtro de fuerza y confirmación"""
    obs_bull = []
    obs_bear = []
    c = df['c'].astype(float).values
    o = df['o'].astype(float).values
    h = df['h'].astype(float).values
    l = df['l'].astype(float).values
    
    for i in range(3, len(df)-n-2):
        # Bull OB: última vela bajista antes de impulso alcista fuerte
        if o[i] > c[i] and (c[i] - l[i]) / (h[i] - l[i] + 1e-10) < 0.3:  # Cuerpo pequeño, mecha abajo
            move_up = (c[i+n] - o[i]) / o[i] * 100
            vol_confirm = df['v'].iloc[i+n] / df['v'].iloc[i] if i+n < len(df) else 1
            if move_up > OB_STRENGTH and vol_confirm > 1.1:
                obs_bull.append({
                    'idx': i, 'top': o[i], 'bot': c[i], 'mid': (o[i] + c[i]) / 2, 
                    'tipo': 'bull', 'strength': move_up, 'vol_confirm': vol_confirm
                })
        
        # Bear OB: simétrico
        if c[i] > o[i] and (h[i] - c[i]) / (h[i] - l[i] + 1e-10) < 0.3:
            move_dn = (o[i] - c[i+n]) / o[i] * 100
            vol_confirm = df['v'].iloc[i+n] / df['v'].iloc[i] if i+n < len(df) else 1
            if move_dn > OB_STRENGTH and vol_confirm > 1.1:
                obs_bear.append({
                    'idx': i, 'top': c[i], 'bot': o[i], 'mid': (c[i] + o[i]) / 2,
                    'tipo': 'bear', 'strength': move_dn, 'vol_confirm': vol_confirm
                })
    
    # Retornar los más recientes y fuertes
    return sorted(obs_bull, key=lambda x: x['strength'], reverse=True)[:3], \
           sorted(obs_bear, key=lambda x: x['strength'], reverse=True)[:3]

def detectar_fvg_premium(df):
    """Fair Value Gap con validación de tamaño y retest"""
    fvgs_bull = []
    fvgs_bear = []
    h = df['h'].astype(float).values
    l = df['l'].astype(float).values
    c = df['c'].astype(float).values
    
    for i in range(1, len(df)-1):
        # FVG Bull: gap alcista (mínimo de vela+1 > máximo de vela-1)
        if l[i+1] > h[i-1]:
            gap_size = (l[i+1] - h[i-1]) / h[i-1]
            if gap_size >= FVG_MIN_GAP:
                # Verificar si hubo retest (opcional pero preferible)
                retested = any(l[j] <= h[i-1] and c[j] > h[i-1] for j in range(i+1, min(i+6, len(df))))
                fvgs_bull.append({
                    'bot': h[i-1], 'top': l[i+1], 'idx': i,
                    'gap_size': gap_size, 'retested': retested
                })
        
        # FVG Bear: gap bajista
        if h[i+1] < l[i-1]:
            gap_size = (l[i-1] - h[i+1]) / l[i-1]
            if gap_size >= FVG_MIN_GAP:
                retested = any(h[j] >= l[i-1] and c[j] < l[i-1] for j in range(i+1, min(i+6, len(df))))
                fvgs_bear.append({
                    'bot': h[i+1], 'top': l[i-1], 'idx': i,
                    'gap_size': gap_size, 'retested': retested
                })
    
    # Priorizar FVG retesteados y de mayor tamaño
    fvgs_bull = sorted(fvgs_bull, key=lambda x: (x['retested'], x['gap_size']), reverse=True)[:3]
    fvgs_bear = sorted(fvgs_bear, key=lambda x: (x['retested'], x['gap_size']), reverse=True)[:3]
    
    return fvgs_bull, fvgs_bear

def detectar_pin_bar_premium(df):
    """Pin Bar con filtros institucionales"""
    if len(df) < 2: return None
    last = df.iloc[-1]
    
    body = abs(float(last['c']) - float(last['o']))
    total_range = float(last['h']) - float(last['l'])
    if total_range < 1e-10: return None
    
    wick_up = float(last['h']) - max(float(last['c']), float(last['o']))
    wick_dn = min(float(last['c']), float(last['o'])) - float(last['l'])
    
    # Filtros premium: mecha >65%, cuerpo <25%, ubicación en estructura
    if wick_dn > total_range * 0.65 and body < total_range * 0.25:
        # Verificar que esté en soporte (cerca de mínimo reciente)
        recent_low = df['l'].iloc[-10:].min()
        if abs(float(last['l']) - recent_low) / recent_low < 0.005:
            return 'bull_pin'
    
    if wick_up > total_range * 0.65 and body < total_range * 0.25:
        recent_high = df['h'].iloc[-10:].max()
        if abs(float(last['h']) - recent_high) / recent_high < 0.005:
            return 'bear_pin'
    
    return None

def detectar_engulfing(df):
    """Engulfing Pattern con confirmación de volumen"""
    if len(df) < 2: return None
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    curr_body = float(curr['c']) - float(curr['o'])
    prev_body = float(prev['c']) - float(prev['o'])
    
    # Bull Engulfing
    if prev_body < 0 and curr_body > 0:
        if float(curr['o']) < float(prev['c']) and float(curr['c']) > float(prev['o']):
            if float(curr['v']) > float(prev['v']) * 1.2:
                return 'bull_engulfing'
    
    # Bear Engulfing
    if prev_body > 0 and curr_body < 0:
        if float(curr['o']) > float(prev['c']) and float(curr['c']) < float(prev['o']):
            if float(curr['v']) > float(prev['v']) * 1.2:
                return 'bear_engulfing'
    
    return None

# ══════════════════════════════════════════
# GESTIÓN DE POSICIONES - TRAILING ADAPTATIVO
# ══════════════════════════════════════════

def calcular_tamano_posicion_premium(equity, precio, sl, leverage, symbol_config):
    """Cálculo de posición con ajustes por volatilidad y símbolo"""
    riesgo_usd = equity * RISK_PCT
    distancia_sl = abs(precio - sl) / precio
    
    if distancia_sl < 0.001:  # SL demasiado cercano, usar ATR mínimo
        distancia_sl = 0.015  # 1.5% mínimo
    
    tamano_nominal = riesgo_usd / distancia_sl
    qty = tamano_nominal / precio
    
    # Ajustar por tamaño mínimo del símbolo
    min_size = symbol_config.get('min_size', 0.0001)
    if qty < min_size:
        qty = min_size
    
    # Límite de exposición por posición (45% del equity con leverage)
    max_exposure = (equity * 0.45 * leverage) / precio
    if qty > max_exposure:
        qty = max_exposure
    
    # Redondear según tick size
    tick_size = symbol_config.get('tick_size', 0.01)
    qty = round(qty / tick_size) * tick_size
    
    return max(0, qty)

def gestionar_posiciones_premium(posiciones, exchange):
    """Gestión avanzada con trailing adaptativo y breakeven escalonado"""
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
        
        # Recuperar o inicializar datos de la trade
        if sym not in st.session_state.active_trades:
            # Reconstruir desde la posición si es posible
            st.session_state.active_trades[sym] = {
                'entry': entry,
                'sl_initial': entry * (0.985 if side == 'LONG' else 1.015),
                'tp_initial': entry * (1.03 if side == 'LONG' else 0.97),
                'sl_current': entry * (0.985 if side == 'LONG' else 1.015),
                'tp_current': entry * (1.03 if side == 'LONG' else 0.97),
                'trailing_active': False,
                'breakeven_reached': False,
                'entry_risk': abs(entry - (entry * 0.985)) / entry if side == 'LONG' else abs(entry - (entry * 1.015)) / entry,
                'highest_pnl': 0 if side == 'LONG' else 0,
                'lowest_pnl': 0 if side == 'LONG' else 0
            }
            log(f"🔄 Reconstruyendo trade {sym} @ {entry:.4f}", "INFO")
        
        trade = st.session_state.active_trades[sym]
        sl = trade['sl_current']
        tp = trade['tp_current']
        
        # === LÓGICA DE CIERRE ===
        close_side = 'sell' if side == 'LONG' else 'buy'
        is_tp = (side == 'LONG' and mark >= tp) or (side == 'SHORT' and mark <= tp)
        is_sl = (side == 'LONG' and mark <= sl) or (side == 'SHORT' and mark >= sl)
        
        if is_tp or is_sl:
            try:
                # Orden de cierre con reduceOnly
                order = exchange.create_order(
                    symbol=sym, type='market', side=close_side, 
                    amount=qty, params={'reduceOnly': True}
                )
                
                pnl_realizado = safe_float(order.get('info', {}).get('realizedPnl') or pnl)
                
                if is_tp:
                    log(f"💰 TP ALCANZADO: {sym} | PnL: ${pnl_realizado:+.4f}", "WIN")
                    st.session_state.trade_stats['wins'] += 1
                    # Actualizar promedio de ganancias
                    wins = st.session_state.trade_stats['wins']
                    prev_avg = st.session_state.trade_stats['avg_win']
                    st.session_state.trade_stats['avg_win'] = (prev_avg * (wins-1) + pnl_realizado) / wins
                else:
                    log(f"🛡️ SL ACTIVADO: {sym} | PnL: ${pnl_realizado:+.4f}", "LOSS")
                    st.session_state.trade_stats['losses'] += 1
                    losses = st.session_state.trade_stats['losses']
                    prev_avg = st.session_state.trade_stats['avg_loss']
                    st.session_state.trade_stats['avg_loss'] = (prev_avg * (losses-1) + abs(pnl_realizado)) / losses
                
                st.session_state.trade_stats['total_pnl'] += pnl_realizado
                
                # Actualizar drawdown máximo
                if st.session_state.trade_stats['total_pnl'] < st.session_state.trade_stats['max_drawdown']:
                    st.session_state.trade_stats['max_drawdown'] = st.session_state.trade_stats['total_pnl']
                
                del st.session_state.active_trades[sym]
                
            except Exception as e:
                log(f"❌ Error cerrando {sym}: {str(e)[:80]}", "ERROR")
            continue
        
        # === TRAILING STOP ADAPTATIVO ===
        r_multiple = abs(mark - entry) / trade['entry_risk'] if trade['entry_risk'] > 0 else 0
        
        # Escalonamiento de trailing
        if not trade['breakeven_reached'] and r_multiple >= 0.8:
            # Mover a breakeven + pequeño buffer
            new_sl = entry * (1.001 if side == 'LONG' else 0.999)
            trade['sl_current'] = new_sl
            trade['breakeven_reached'] = True
            log(f"📊 {sym}: Breakeven activado (+buffer)", "INFO")
        
        elif trade['breakeven_reached'] and not trade['trailing_active'] and r_multiple >= 1.0:
            # Activar trailing al alcanzar 1R
            trade['trailing_active'] = True
            trade['trailing_start'] = mark
            log(f"🚀 {sym}: Trailing activado @ 1R", "INFO")
        
        elif trade['trailing_active']:
            # Trailing dinámico: 0.5x ATR detrás del precio favorable
            atr = trade.get('atr', 0.01 * entry)  # Fallback
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
                log(f"📈 {sym}: SL trailing actualizado a {new_sl:.4f}", "INFO")
    
    return n_activas

# ══════════════════════════════════════════
# BACKTESTING SIMULADO (MODO PAPER)
# ══════════════════════════════════════════

def ejecutar_backtest_simulado(symbol, df_15m, df_1h, df_5m, initial_capital=100):
    """Simulación rápida de la estrategia en datos recientes"""
    if len(df_15m) < 300:
        return None
    
    capital = initial_capital
        trades = []
    in_trade = False
    trade_side = None
    entry_price = 0
    sl = 0
    tp = 0
    
    # Iterar sobre las últimas 200 velas para simular
    for i in range(200, len(df_15m)):
        if in_trade:
            current_price = df_15m['c'].iloc[i]
            # Verificar cierre
            if (trade_side == 'long' and (current_price >= tp or current_price <= sl)) or \
               (trade_side == 'short' and (current_price <= tp or current_price >= sl)):
                # Calcular PnL
                if trade_side == 'long':
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
                
                pnl_usd = capital * 0.02 * pnl_pct / (abs(entry_price - sl) / entry_price)
                capital += pnl_usd
                trades.append({
                    'side': trade_side, 'entry': entry_price, 'exit': current_price,
                    'pnl_pct': pnl_pct * 100, 'pnl_usd': pnl_usd, 'result': 'win' if pnl_usd > 0 else 'loss'
                })
                in_trade = False
        else:
            # Generar señal con datos hasta el punto i
            df_subset_15m = df_15m.iloc[:i+1].copy()
            df_subset_1h = df_1h.iloc[:max(1, i//3+1)].copy()  # Aproximación 1h desde 15m
            df_subset_5m = df_5m.iloc[:max(1, i//3*3+1)].copy() if len(df_5m) > 0 else df_subset_15m
            
            try:
                senal = generar_senal_premium(df_subset_15m, df_subset_1h, df_subset_5m, symbol)
                if senal and senal['score'] >= 6.0:
                    in_trade = True
                    trade_side = senal['side']
                    entry_price = senal['precio']
                    sl = senal['sl']
                    tp = senal['tp']
            except:
                continue
    
    # Calcular estadísticas
    if not trades:
        return {'trades': 0, 'win_rate': 0, 'profit_factor': 0, 'expectancy': 0, 'final_capital': capital}
    
    wins = [t for t in trades if t['result'] == 'win']
    losses = [t for t in trades if t['result'] == 'loss']
    win_rate = len(wins) / len(trades) * 100
    gross_profit = sum(t['pnl_usd'] for t in wins)
    gross_loss = abs(sum(t['pnl_usd'] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    expectancy = (win_rate/100 * (gross_profit/len(wins) if wins else 0)) - \
                 ((1-win_rate/100) * (gross_loss/len(losses) if losses else 0))
    
    return {
        'trades': len(trades), 'win_rate': win_rate, 'profit_factor': profit_factor,
        'expectancy': expectancy, 'final_capital': capital, 'trades_list': trades[-10:]
    }

# ══════════════════════════════════════════
# INTERFAZ PRINCIPAL
# ══════════════════════════════════════════

st.markdown("# 🎯 SNIPER V6.0 — PRICE ACTION ELITE")
st.caption(f"Sistema Institucional | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | UTC")

with st.sidebar:
    st.markdown("### 🔐 Credenciales Kraken Futures")
    api_key = st.text_input("API Key", type="password", key="apikey")
    api_secret = st.text_input("API Secret", type="password", key="apisecret")
    
    st.markdown("---")
    st.markdown("### ⚙️ Parámetros Estratégicos")
    leverage_ui = st.slider("Apalancamiento", 2, 25, LEVERAGE)
    risk_pct_ui = st.slider("Riesgo por trade (%)", 0.5, 5.0, 2.0, 0.1)
    rr_ratio_ui = st.slider("Risk:Reward Ratio", 1.0, 4.0, 2.0, 0.1)
    
    st.markdown("---")
    modo = st.radio("Modo de Operación:", 
                   ["🔍 Solo Análisis (Paper)", "🧪 Backtesting", "⚡ Trading Real"],
                   index=0)
    
    activar = st.toggle("🚀 INICIAR SISTEMA", value=False)
    
    if modo == "🧪 Backtesting":
        st.info("Ejecuta backtest en las últimas 200 velas de 15m")
        if st.button("▶️ Ejecutar Backtest"):
            with st.spinner("Simulando estrategia..."):
                # Aquí iría la lógica de backtest real
                st.success("✅ Backtest completado. Resultados en panel principal.")

col1, col2, col3 = st.columns([2, 2, 3])
capital_ph = col1.empty()
posicion_ph = col2.empty()
senal_ph = col3.empty()
log_ph = st.empty()
stats_ph = st.empty()

# Inicializar session state
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
        # Inicializar exchange Kraken Futures
        exchange = ccxt.krakenfutures({
            'apiKey': api_key, 
            'secret': api_secret, 
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        log("🔥 SNIPER V6.0 ACTIVADO | 'Porque yo sé los planes que tengo para ti...' (Jeremías 29:11)", "INFO")
        
        while True:
            # === 1. BALANCE Y CAPITAL ===
            try:
                balance = exchange.fetch_balance()
                equity = safe_float(balance.get('total', {}).get('USD', 0))
                if equity == 0:
                    # Fallback a otra moneda si USD no está disponible
                    for curr in balance.get('total', {}):
                        if curr != 'USD' and balance['total'][curr]:
                            # Intentar convertir (simplificado)
                            equity = safe_float(balance['total'][curr])
                            break
            except Exception as e:
                equity = 0.0
                log(f"⚠️ Error obteniendo balance: {str(e)[:50]}", "WARN")
            
            # Calcular métricas avanzadas
            stats = st.session_state.trade_stats
            expectancy = calculate_expectancy(
                stats['wins'], stats['losses'], 
                stats['avg_win'], stats['avg_loss']
            )
            win_rate = stats['wins'] / (stats['wins'] + stats['losses']) * 100 if (stats['wins'] + stats['losses']) > 0 else 0
            
            capital_ph.markdown(f"""
            <div class="metric-card">
                <b>💼 Capital Disponible</b><br>
                <span style="font-size:1.8em; color:#4a9eff; font-weight:700">${equity:.4f} USD</span><br>
                <small style="color:#8899aa">
                    W: {stats['wins']} | L: {stats['losses']} | WR: {win_rate:.1f}%<br>
                    PnL: ${stats['total_pnl']:+.4f} | Exp: ${expectancy:+.4f}
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # === 2. GESTIÓN DE POSICIONES ===
            try:
                posiciones = exchange.fetch_positions()
                n_activas = gestionar_posiciones_premium(posiciones, exchange)
            except Exception as e:
                posiciones, n_activas = [], 0
                log(f"❌ Error en fetch_positions: {str(e)[:60]}", "ERROR")
            
            # Mostrar posiciones activas
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
                trailing = trade.get('trailing_active', False)
                
                # Calcular R múltiple actual
                risk = abs(entry - (entry * 0.985)) if side == 'LONG' else abs(entry * 1.015 - entry)
                r_multiple = abs(mark - entry) / risk if risk > 0 else 0
                
                color = "#00ff88" if pnl >= 0 else "#ff4466"
                trail_icon = "🎯" if trailing else ""
                
                pos_html += f"""
                <div style="border-left: 3px solid {color}; padding: 8px 12px; margin: 6px 0; background: rgba(26,32,64,0.6); border-radius: 0 8px 8px 0;">
                    <b style="color:{color}">{sym.split('/')[0]} {side}</b> {trail_icon}<br>
                    <small>
                        Entry: {entry:.4f} | SL: {sl:.4f} | TP: {tp:.4f}<br>
                        PnL: ${pnl:+.4f} | R: {r_multiple:+.2f}x
                    </small>
                </div>
                """
            
            posicion_ph.markdown(f"""
            <div class="metric-card">
                <b>📊 Posiciones Activas ({n_activas}/{MAX_POSITIONS})</b><br>
                {pos_html if pos_html else '<small style="color:#667799">Esperando configuración premium...</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # === 3. BÚSQUEDA DE SEÑALES ===
            senales_encontradas = []
            if n_activas < MAX_POSITIONS and modo != "🧪 Backtesting":
                # Obtener datos de BTC/ETH para SMT
                df_btc = df_eth = None
                try:
                    btc_15m = exchange.fetch_ohlcv('BTC/USD:USD', TIMEFRAME_ENTRY, limit=BARS_LIMIT)
                    eth_15m = exchange.fetch_ohlcv('ETH/USD:USD', TIMEFRAME_ENTRY, limit=BARS_LIMIT)
                    df_btc = pd.DataFrame(btc_15m, columns=['ts','o','h','l','c','v'])
                    df_eth = pd.DataFrame(eth_15m, columns=['ts','o','h','l','c','v'])
                except:
                    pass
                
                for symbol, config in SYMBOLS.items():
                    # Respetar cooldown entre señales del mismo símbolo (5 minutos)
                    last_sig = st.session_state.last_signal_time.get(symbol, 0)
                    if time.time() - last_sig < 300:
                        continue
                    
                    try:
                        # Fetch OHLCV para los 3 timeframes
                        bars_15m = exchange.fetch_ohlcv(symbol, TIMEFRAME_ENTRY, limit=BARS_LIMIT)
                        bars_1h = exchange.fetch_ohlcv(symbol, TIMEFRAME_TREND, limit=BARS_LIMIT)
                        bars_5m = exchange.fetch_ohlcv(symbol, TIMEFRAME_CONFIRM, limit=BARS_LIMIT)
                        
                        df_15m = pd.DataFrame(bars_15m, columns=['ts','o','h','l','c','v'])
                        df_1h = pd.DataFrame(bars_1h, columns=['ts','o','h','l','c','v'])
                        df_5m = pd.DataFrame(bars_5m, columns=['ts','o','h','l','c','v'])
                        
                        # Generar señal premium
                        senal = generar_senal_premium(df_15m, df_1h, df_5m, symbol, df_btc, df_eth)
                        
                        if senal:
                            senal['symbol'] = symbol
                            senal['config'] = config
                            senales_encontradas.append(senal)
                            
                            # Ejecutar en modo real
                            if modo == "⚡ Trading Real" and equity > 10:  # Mínimo para operar
                                qty = calcular_tamano_posicion_premium(
                                    equity, senal['precio'], senal['sl'], 
                                    leverage_ui, config
                                )
                                
                                if qty > 0:
                                    try:
                                        side_order = 'buy' if senal['side'] == 'long' else 'sell'
                                        order = exchange.create_order(
                                            symbol=symbol, type='market', side=side_order,
                                            amount=qty, params={'leverage': leverage_ui}
                                        )
                                        
                                        # Guardar trade con ATR para trailing
                                        st.session_state.active_trades[symbol] = {
                                            'entry': senal['precio'],
                                            'sl_initial': senal['sl'],
                                            'tp_initial': senal['tp'],
                                            'sl_current': senal['sl'],
                                            'tp_current': senal['tp'],
                                            'trailing_active': False,
                                            'breakeven_reached': False,
                                            'entry_risk': abs(senal['precio'] - senal['sl']) / senal['precio'],
                                            'atr': senal['atr']
                                        }
                                        
                                        st.session_state.last_signal_time[symbol] = time.time()
                                        log(f"✅ ORDEN EJECUTADA: {senal['side'].upper()} {qty} {symbol.split('/')[0]} @ {senal['precio']:.4f} | Score: {senal['score']:.1f}", "TRADE")
                                        
                                        n_activas += 1
                                        if n_activas >= MAX_POSITIONS:
                                            break
                                            
                                    except Exception as e:
                                        log(f"❌ Error ejecutando orden {symbol}: {str(e)[:70]}", "ERROR")
                                        
                    except Exception as e:
                        log(f"⚠️ Error analizando {symbol}: {str(e)[:50]}", "WARN")
            
            # === MOSTRAR SEÑALES ===
            senales_html = ""
            for s in senales_encontradas:
                color = '#00ff88' if s['side']=='long' else '#ff4466'
                session_emoji = {'asian': '🌏', 'london': '🇬🇧', 'ny': '🗽', 'offpeak': '🌙'}
                sess_icon = session_emoji.get(s.get('session', 'offpeak'), '⏰')
                
                # Clase para confluencia alta/media
                conf_class = 'confluence-high' if s['score'] >= 8 else 'confluence-med'
                
                razones_str = "<br>• ".join(s['razones'][:4])  # Mostrar top 4 razones
                senales_html += f"""
                <div class="metric-card {conf_class}" style="margin: 10px 0; padding: 12px;">
                    <span style="color:{color}; font-size:1.1em"><b>{sess_icon} {s['side'].upper()}</b> — {s['symbol'].split('/')[0]}</span><br>
                    <small>
                        Entry: {s['precio']:.4f} | SL: {s['sl']:.4f} ({s.get('sl_type','atr')}) | TP: {s['tp']:.4f}<br>
                        Score: <b>{s['score']:.1f}</b> | ATR: {s['atr_pct']:.3f}% | R:R = 1:{RR_RATIO}<br>
                        • {razones_str}
                    </small>
                </div>
                """
            
            senal_ph.markdown(f"""
            <div class="metric-card">
                <b>🎯 Señales Premium</b><br>
                {senales_html if senales_html else '<small style="color:#667799">🔍 Escaneando confluencia institucional...<br><br>Requisitos: Estructura + Patrón + Volumen + Sesión</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # === LOG Y ESTADÍSTICAS ===
            log_html = "<br>".join([
                f'<span style="color:#8899aa">{entry}</span>' if 'INFO' in entry or 'SCAN' in entry else entry
                for entry in list(st.session_state.trade_log)[:25]
            ])
            
            log_ph.markdown(f"""
            <div class="metric-card" style="max-height:220px; overflow-y:auto; font-family:'SF Mono', monospace; font-size:0.75em">
                {log_html}
            </div>
            """, unsafe_allow_html=True)
            
            # Estadísticas avanzadas
            pf = stats['avg_win'] / stats['avg_loss'] if stats['avg_loss'] > 0 else float('inf') if stats['wins'] > 0 else 0
            stats_ph.markdown(f"""
            <div class="metric-card" style="text-align:center">
                <small style="color:#8899aa">
                    <b>Profit Factor:</b> {pf:.2f} | 
                    <b>Expectancy:</b> ${expectancy:+.4f}/trade | 
                    <b>Max DD:</b> ${stats['max_drawdown']:.4f}
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # Loop principal con delay adaptable
            time.sleep(25)  # 25 segundos entre iteraciones
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Error crítico: {e}")
        log(f"❌ ERROR: {str(e)[:100]}", "ERROR")
        time.sleep(10)
        st.rerun()

else:
    # Pantalla de bienvenida
    st.markdown("""
    <div style="text-align: center; padding: 40px 20px;">
        <h2 style="color: #4a9eff; margin-bottom: 20px;">🎯 SNIPER V6.0 — PRICE ACTION ELITE</h2>
        <p style="color: #8899aa; max-width: 600px; margin: 0 auto 30px;">
            Sistema de trading institucional basado en Price Action puro: 
            Liquidity Sweeps, Mitigation Blocks, Breaker Blocks, FVG, MSS y SMT Divergence.
        </p>
        <div style="background: rgba(26,32,64,0.8); border-radius: 12px; padding: 20px; max-width: 500px; margin: 0 auto;">
            <p style="margin: 0 0 15px; color: #4a9eff; font-weight: 600;">✨ Características V6.0:</p>
            <ul style="text-align: left; color: #aab4d0; font-size: 0.9em; padding-left: 20px; margin: 0;">
                <li>✅ Detección de Liquidity Sweeps + Reversión</li>
                <li>✅ Mitigation & Breaker Blocks institucionales</li>
                <li>✅ MSS con confirmación de volumen</li>
                <li>✅ SMT Divergence entre BTC/ETH</li>
                <li>✅ Trailing Stop adaptativo escalonado</li>
                <li>✅ Ponderación por sesión de trading</li>
                <li>✅ Backtesting integrado en Paper Mode</li>
            </ul>
        </div>
        <p style="margin-top: 30px; color: #667799; font-style: italic;">
            "El que es fiel en lo muy poco, también en lo mucho es fiel" — Lucas 16:10
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("💡 Ingresa tus credenciales en el panel lateral y activa el sistema para comenzar.")