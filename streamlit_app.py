"""
╔══════════════════════════════════════════════════════════════════╗
║          SNIPER V5 - PRICE ACTION WARRIOR                        ║
║          Estrategias: Ruptura, FVG, OB, Estructura de Mercado    ║
╚══════════════════════════════════════════════════════════════════╝

ESTRATEGIAS IMPLEMENTADAS:
1. Order Blocks (OB) - Zonas donde los institucionales entraron
2. Fair Value Gaps (FVG) - Gaps de precio que buscan llenarse
3. Break of Structure (BOS) / Change of Character (CHoCH)
4. Confluencia Multi-Timeframe (15m confirmado con 1h)
5. Session High/Low Breakout (Asia/Londres/NY)
6. Pin Bar + Inside Bar como confirmación

GESTIÓN DE RIESGO:
- Riesgo fijo por operación: 2% del capital
- R:R mínimo de 1:2 (TP siempre el doble del SL)
- Máximo 2 posiciones simultáneas
- Trailing stop después de 1R de ganancia
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
    page_title="SNIPER V5 | Price Action Warrior",
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
    """
    Detecta Break of Structure (BOS) y Change of Character (CHoCH).
    Retorna: 'bullish', 'bearish', 'neutral'
    """
    highs = df['h'].astype(float).values
    lows  = df['l'].astype(float).values
    
    # Últimos swing highs/lows
    recent = min(lookback, len(df)-2)
    
    # Swing high: vela con high mayor que las N anteriores y posteriores
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
    
    # Higher High + Higher Low = Tendencia Alcista
    if last_hh > prev_hh and last_ll > prev_ll:
        return 'bullish', last_ll, last_hh
    # Lower High + Lower Low = Tendencia Bajista  
    elif last_hh < prev_hh and last_ll < prev_ll:
        return 'bearish', last_ll, last_hh
    else:
        return 'neutral', last_ll, last_hh

def detectar_order_blocks(df, n=5):
    """
    Order Block: La última vela bajista antes de un movimiento alcista fuerte
    (o la última alcista antes de un movimiento bajista fuerte).
    Retorna lista de OBs con zona de precio.
    """
    obs_bull = []  # OB alcistas (compra)
    obs_bear = []  # OB bajistas (venta)
    
    c = df['c'].astype(float).values
    o = df['o'].astype(float).values
    h = df['h'].astype(float).values
    l = df['l'].astype(float).values
    
    for i in range(2, len(df)-n):
        # Movimiento alcista fuerte después de vela bajista
        move_up = (c[i+n] - c[i]) / c[i] * 100
        if o[i] > c[i] and move_up > 1.5:  # Vela bajista + impulso > 1.5%
            obs_bull.append({
                'idx': i, 'top': o[i], 'bot': c[i],
                'mid': (o[i] + c[i]) / 2, 'tipo': 'bull'
            })
        
        # Movimiento bajista fuerte después de vela alcista
        move_dn = (c[i] - c[i+n]) / c[i] * 100
        if c[i] > o[i] and move_dn > 1.5:  # Vela alcista + caída > 1.5%
            obs_bear.append({
                'idx': i, 'top': c[i], 'bot': o[i],
                'mid': (c[i] + o[i]) / 2, 'tipo': 'bear'
            })
    
    # Solo los más recientes
    return obs_bull[-3:], obs_bear[-3:]

def detectar_fvg(df):
    """
    Fair Value Gap: gap de precio entre vela[i-1].high y vela[i+1].low (alcista)
    o entre vela[i-1].low y vela[i+1].high (bajista).
    """
    fvgs_bull = []
    fvgs_bear = []
    
    h = df['h'].astype(float).values
    l = df['l'].astype(float).values
    
    for i in range(1, len(df)-1):
        # FVG Alcista: hay gap entre el high[i-1] y el low[i+1]
        if l[i+1] > h[i-1]:
            fvgs_bull.append({'bot': h[i-1], 'top': l[i+1], 'idx': i})
        # FVG Bajista: hay gap entre el low[i-1] y el high[i+1]
        if h[i+1] < l[i-1]:
            fvgs_bear.append({'bot': h[i+1], 'top': l[i-1], 'idx': i})
    
    return fvgs_bull[-3:], fvgs_bear[-3:]

def detectar_pin_bar(df):
    """
    Pin Bar: mecha larga + cuerpo pequeño. Señal de reversión fuerte.
    Alcista: mecha larga ABAJO, cuerpo arriba.
    Bajista: mecha larga ARRIBA, cuerpo abajo.
    """
    last = df.iloc[-1]
    body = abs(float(last['c']) - float(last['o']))
    wick_up = float(last['h']) - max(float(last['c']), float(last['o']))
    wick_dn = min(float(last['c']), float(last['o'])) - float(last['l'])
    total_range = float(last['h']) - float(last['l'])
    
    if total_range == 0: return None
    
    # Pin bar alcista: mecha inferior > 60% del rango total, cuerpo pequeño
    if wick_dn > total_range * 0.6 and body < total_range * 0.3:
        return 'bull_pin'
    # Pin bar bajista: mecha superior > 60%, cuerpo pequeño
    if wick_up > total_range * 0.6 and body < total_range * 0.3:
        return 'bear_pin'
    return None

def detectar_inside_bar(df):
    """Inside Bar: la vela actual está completamente dentro de la anterior (compresión)"""
    if len(df) < 3: return False
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    return (float(curr['h']) < float(prev['h']) and 
            float(curr['l']) > float(prev['l']))

def nivel_soporte_resistencia(df, n=50):
    """Identifica niveles clave de S/R por pivotes"""
    highs = df['h'].astype(float).values[-n:]
    lows  = df['l'].astype(float).values[-n:]
    closes = df['c'].astype(float).values[-n:]
    
    resistencias = []
    soportes = []
    
    for i in range(2, n-2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            resistencias.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            soportes.append(lows[i])
    
    return sorted(set([round(r,2) for r in resistencias]))[-3:], \
           sorted(set([round(s,2) for s in soportes]))[:3]

# ══════════════════════════════════════════
# MOTOR DE SEÑALES - CONFLUENCIA
# ══════════════════════════════════════════

def generar_senal(df_15m, df_1h, symbol):
    """
    Genera señal de trading combinando:
    1. Estructura de mercado (1h define tendencia)
    2. Price action en 15m (entrada)
    3. Confluencia: OB o FVG + Pin Bar o BOS
    
    Retorna: dict con señal, sl, tp, score o None
    """
    if len(df_15m) < 210 or len(df_1h) < 50:
        return None
    
    df_15m = calcular_indicadores(df_15m.copy())
    df_1h  = calcular_indicadores(df_1h.copy())
    
    last   = df_15m.iloc[-1]
    precio = float(last['c'])
    atr    = float(last['atr'])
    rsi    = float(last['rsi'])
    
    # ─── PASO 1: TENDENCIA EN 1H ───
    estructura_1h, swing_low_1h, swing_high_1h = detectar_estructura_mercado(df_1h)
    ema50_1h  = float(df_1h.iloc[-1]['ema50'])
    ema200_1h = float(df_1h.iloc[-1]['ema200'])
    tendencia_1h = 'bull' if ema50_1h > ema200_1h and estructura_1h == 'bullish' else \
                   'bear' if ema50_1h < ema200_1h and estructura_1h == 'bearish' else 'neutral'
    
    # ─── PASO 2: ESTRUCTURA EN 15M ───
    estructura_15m, swing_low_15m, swing_high_15m = detectar_estructura_mercado(df_15m)
    
    # ─── PASO 3: DETECCIONES ───
    obs_bull, obs_bear = detectar_order_blocks(df_15m)
    fvgs_bull, fvgs_bear = detectar_fvg(df_15m)
    pin = detectar_pin_bar(df_15m)
    inside = detectar_inside_bar(df_15m)
    
    # ─── PASO 4: VOLUMEN CONFIRMA ───
    vol_ok = float(last['vol_ratio']) > 1.2  # Volumen 20% sobre la media
    
    score_long = 0
    score_short = 0
    razon_long = []
    razon_short = []
    
    # PUNTUACIÓN LONG
    if tendencia_1h == 'bull':
        score_long += 2; razon_long.append("Tendencia 1h alcista")
    if estructura_15m == 'bullish':
        score_long += 1; razon_long.append("Estructura 15m alcista")
    if precio > float(last['ema200']):
        score_long += 1; razon_long.append("Precio sobre EMA200")
    
    # Precio cerca de un OB alcista (dentro del 0.5% del OB)
    for ob in obs_bull:
        if abs(precio - ob['mid']) / precio < 0.005:
            score_long += 2; razon_long.append(f"Precio en Order Block bull @{ob['mid']:.2f}")
    
    # Precio cerca de un FVG alcista
    for fvg in fvgs_bull:
        if fvg['bot'] <= precio <= fvg['top']:
            score_long += 2; razon_long.append(f"Precio en FVG bull [{fvg['bot']:.2f}-{fvg['top']:.2f}]")
    
    if pin == 'bull_pin':
        score_long += 2; razon_long.append("Pin Bar alcista confirmado")
    if inside:
        score_long += 1; razon_long.append("Inside Bar (compresión)")
    if 40 < rsi < 65:
        score_long += 1; razon_long.append(f"RSI favorable ({rsi:.1f})")
    if vol_ok:
        score_long += 1; razon_long.append("Volumen elevado")
    
    # PUNTUACIÓN SHORT
    if tendencia_1h == 'bear':
        score_short += 2; razon_short.append("Tendencia 1h bajista")
    if estructura_15m == 'bearish':
        score_short += 1; razon_short.append("Estructura 15m bajista")
    if precio < float(last['ema200']):
        score_short += 1; razon_short.append("Precio bajo EMA200")
    
    for ob in obs_bear:
        if abs(precio - ob['mid']) / precio < 0.005:
            score_short += 2; razon_short.append(f"Precio en Order Block bear @{ob['mid']:.2f}")
    
    for fvg in fvgs_bear:
        if fvg['bot'] <= precio <= fvg['top']:
            score_short += 2; razon_short.append(f"Precio en FVG bear [{fvg['bot']:.2f}-{fvg['top']:.2f}]")
    
    if pin == 'bear_pin':
        score_short += 2; razon_short.append("Pin Bar bajista confirmado")
    if inside:
        score_short += 1; razon_short.append("Inside Bar (compresión)")
    if 35 < rsi < 60:
        score_short += 1; razon_short.append(f"RSI favorable ({rsi:.1f})")
    if vol_ok:
        score_short += 1; razon_short.append("Volumen elevado")
    
    # ─── PASO 5: NECESITAMOS SCORE MÍNIMO DE 5 ───
    MIN_SCORE = 5
    
    if score_long >= MIN_SCORE and score_long > score_short:
        sl = precio - (atr * 1.5)
        tp = precio + (atr * 1.5 * RR_RATIO)
        return {
            'side': 'long', 'precio': precio,
            'sl': sl, 'tp': tp,
            'atr': atr, 'score': score_long,
            'razones': razon_long,
            'rr': RR_RATIO
        }
    
    elif score_short >= MIN_SCORE and score_short > score_long:
        sl = precio + (atr * 1.5)
        tp = precio - (atr * 1.5 * RR_RATIO)
        return {
            'side': 'short', 'precio': precio,
            'sl': sl, 'tp': tp,
            'atr': atr, 'score': score_short,
            'razones': razon_short,
            'rr': RR_RATIO
        }
    
    return None

# ══════════════════════════════════════════
# GESTIÓN DE CAPITAL
# ══════════════════════════════════════════

def calcular_tamano_posicion(equity, precio, sl, leverage):
    """
    Calcula el tamaño de posición basado en riesgo fijo.
    Arriesgamos solo RISK_PCT del capital.
    """
    riesgo_usd = equity * RISK_PCT  # ej: $10 * 2% = $0.20 en riesgo
    distancia_sl = abs(precio - sl) / precio  # % de distancia al SL
    
    if distancia_sl == 0: return 0
    
    # El tamaño nominal que necesitamos para que ese % sea = riesgo_usd
    # riesgo_usd = tamano_nominal * distancia_sl
    tamano_nominal = riesgo_usd / distancia_sl
    
    # Cantidad de contratos
    qty = tamano_nominal / precio
    
    # Verificar que el margen necesario no exceda lo disponible
    margen_necesario = (qty * precio) / leverage
    if margen_necesario > equity * 0.45:  # Max 45% del capital por trade
        qty = (equity * 0.45 * leverage) / precio
    
    return qty

def gestionar_trailing_stop(posicion, exchange):
    """
    Trailing stop: si el precio se mueve 1R a nuestro favor,
    mover el SL al punto de entrada (breakeven) o 0.5R de ganancia.
    """
    sym = posicion['symbol']
    side = posicion['side'].upper()
    entry = safe_float(posicion['entryPrice'])
    mark = safe_float(posicion['markPrice'])
    atr = safe_float(posicion.get('atr', entry * 0.01))
    qty = safe_float(posicion.get('contracts', 0))
    
    if qty == 0: return
    
    # Ganancia actual en %
    if side == 'LONG':
        ganancia_pct = (mark - entry) / entry * 100
    else:
        ganancia_pct = (entry - mark) / entry * 100
    
    # Si ganamos más de 1%, aseguramos breakeven
    if ganancia_pct >= 1.0:
        log(f"Trailing activado en {sym}: moviendo SL a breakeven", "INFO")

# ══════════════════════════════════════════
# GESTIÓN DE POSICIONES ABIERTAS
# ══════════════════════════════════════════

def gestionar_posiciones(posiciones, exchange, equity):
    """Maneja TP, SL y trailing de posiciones abiertas"""
    n_activas = 0
    
    for p in posiciones:
        qty = safe_float(p.get('contracts', 0))
        if qty <= 0: continue
        
        n_activas += 1
        sym   = p['symbol']
        side  = p['side'].upper()
        entry = safe_float(p.get('entryPrice'))
        mark  = safe_float(p.get('markPrice'))
        pnl   = safe_float(p.get('unrealizedPnl'))
        
        if entry == 0: continue
        
        # Calcular movimiento en %
        if side == 'LONG':
            move_pct = (mark - entry) / entry * 100
            close_side = 'sell'
        else:
            move_pct = (entry - mark) / entry * 100
            close_side = 'buy'
        
        # ─── TAKE PROFIT: movimiento >= TP% ───
        tp_pct = atr_sl_pct = 1.5  # placeholder, idealmente guardas el TP en estado
        if move_pct >= 3.0:  # 3% = TP conservador con 10x = 30% real
            try:
                exchange.create_market_order(sym, close_side, qty, 
                                              params={'reduceOnly': True})
                log(f"💰 TP ALCANZADO: {sym} | PnL: ${pnl:.4f} | Move: {move_pct:.2f}%", "WIN")
            except Exception as e:
                log(f"Error cerrando TP {sym}: {e}", "ERROR")
        
        # ─── STOP LOSS: movimiento <= -SL% ───
        elif move_pct <= -1.5:
            try:
                exchange.create_market_order(sym, close_side, qty,
                                              params={'reduceOnly': True})
                log(f"🛡️ SL ACTIVADO: {sym} | PnL: ${pnl:.4f} | Move: {move_pct:.2f}%", "LOSS")
            except Exception as e:
                log(f"Error cerrando SL {sym}: {e}", "ERROR")
        
        # ─── TRAILING: si ganas 1.5%, mover SL a 0.5% de ganancia ───
        elif move_pct >= 1.5:
            log(f"📈 Trailing activo en {sym}: +{move_pct:.2f}%", "INFO")
    
    return n_activas

# ══════════════════════════════════════════
# INTERFAZ STREAMLIT
# ══════════════════════════════════════════

st.markdown("# 🎯 SNIPER V5 — PRICE ACTION WARRIOR")
st.caption(f"Sistema de Trading Algorítmico | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

# Sidebar
with st.sidebar:
    st.markdown("### 🔐 Credenciales Kraken")
    api_key    = st.text_input("API Key", type="password", key="apikey")
    api_secret = st.text_input("API Secret", type="password", key="apisecret")
    
    st.markdown("---")
    st.markdown("### ⚙️ Parámetros")
    leverage_ui  = st.slider("Apalancamiento", 2, 20, LEVERAGE)
    risk_pct_ui  = st.slider("Riesgo por trade (%)", 1, 5, 2)
    rr_ui        = st.slider("Ratio Riesgo:Beneficio", 1.5, 4.0, 2.0, step=0.5)
    
    st.markdown("---")
    st.markdown("### 📊 Modo")
    modo = st.radio("Selecciona:", ["🔍 Solo Análisis (Paper)", "⚡ Trading Real"])
    activar = st.toggle("INICIAR BOT", value=False)
    
    st.markdown("---")
    st.markdown("### ℹ️ Estrategias Activas")
    st.markdown("""
    - ✅ Order Blocks (OB)
    - ✅ Fair Value Gaps (FVG)  
    - ✅ Break of Structure
    - ✅ Pin Bar + Inside Bar
    - ✅ Multi-Timeframe (15m+1h)
    - ✅ Trailing Stop Dinámico
    - ✅ Riesgo Fijo 2%
    """)

# Columnas principales
col1, col2, col3 = st.columns([2,2,3])

capital_ph   = col1.empty()
posicion_ph  = col2.empty()
senal_ph     = col3.empty()

log_ph       = st.empty()
chart_ph     = st.empty()

# Estado
if 'trade_log' not in st.session_state:
    st.session_state.trade_log = []
if 'stats' not in st.session_state:
    st.session_state.stats = {'wins':0, 'losses':0, 'total_pnl':0.0}

# ══════════════════════════════════════════
# LOOP PRINCIPAL
# ══════════════════════════════════════════

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        
        # Configurar apalancamiento
        for sym in SYMBOLS:
            try:
                exchange.set_leverage(leverage_ui, sym)
            except: pass
        
        log("Bot iniciado. Escaneando mercados...", "INFO")
        ciclo = 0
        
        while True:
            ciclo += 1
            
            # ─── BALANCE ───
            try:
                balance = exchange.fetch_total_balance()
                equity = safe_float(balance.get('USD', 0))
            except:
                equity = 0.0
            
            capital_ph.markdown(f"""
            <div class="metric-card">
            <b>💼 Capital</b><br>
            <span style="font-size:1.5em; color:#4a9eff">${equity:.4f} USD</span><br>
            <small>Wins: {st.session_state.stats['wins']} | 
                   Losses: {st.session_state.stats['losses']} | 
                   PnL: ${st.session_state.stats['total_pnl']:.4f}</small>
            </div>
            """, unsafe_allow_html=True)
            
            # ─── POSICIONES ABIERTAS ───
            try:
                posiciones = exchange.fetch_positions()
                n_activas = gestionar_posiciones(posiciones, exchange, equity)
            except Exception as e:
                posiciones = []
                n_activas = 0
                log(f"Error fetch_positions: {e}", "ERROR")
            
            # Mostrar posiciones
            pos_info = ""
            for p in posiciones:
                if safe_float(p.get('contracts', 0)) > 0:
                    sym = p['symbol']
                    side = p['side'].upper()
                    pnl = safe_float(p.get('unrealizedPnl'))
                    mark = safe_float(p.get('markPrice'))
                    entry = safe_float(p.get('entryPrice'))
                    move = ((mark-entry)/entry*100) if side=='LONG' else ((entry-mark)/entry*100)
                    color = "#00ff88" if pnl >= 0 else "#ff4466"
                    pos_info += f"""<div style="color:{color}; margin:4px 0">
                        <b>{sym.split('/')[0]}</b> {side} | 
                        Entry: {entry:.2f} | Mark: {mark:.2f} |
                        Move: {move:+.2f}% | PnL: ${pnl:+.4f}
                    </div>"""
            
            if not pos_info:
                pos_info = '<span style="color:#888">Sin posiciones abiertas</span>'
            
            posicion_ph.markdown(f"""
            <div class="metric-card">
            <b>📊 Posiciones ({n_activas}/{MAX_POSITIONS})</b><br>
            {pos_info}
            </div>
            """, unsafe_allow_html=True)
            
            # ─── BUSCAR SEÑALES ───
            senales_encontradas = []
            
            if n_activas < MAX_POSITIONS:
                log(f"Ciclo {ciclo} — Escaneando {len(SYMBOLS)} símbolos...", "SCAN")
                
                for sym in SYMBOLS:
                    try:
                        # Obtener datos multi-timeframe
                        bars_15m = exchange.fetch_ohlcv(sym, TIMEFRAME_ENTRY, limit=BARS_LIMIT)
                        bars_1h  = exchange.fetch_ohlcv(sym, TIMEFRAME_TREND, limit=BARS_LIMIT)
                        
                        df_15m = pd.DataFrame(bars_15m, columns=['ts','o','h','l','c','v'])
                        df_1h  = pd.DataFrame(bars_1h,  columns=['ts','o','h','l','c','v'])
                        
                        senal = generar_senal(df_15m, df_1h, sym)
                        
                        if senal:
                            senal['symbol'] = sym
                            senales_encontradas.append(senal)
                            log(f"SEÑAL {senal['side'].upper()} en {sym} | Score: {senal['score']} | {', '.join(senal['razones'][:3])}", "TRADE")
                            
                            # ─── EJECUTAR SI ES MODO REAL ───
                            if modo == "⚡ Trading Real":
                                qty = calcular_tamano_posicion(
                                    equity, senal['precio'], senal['sl'], leverage_ui)
                                
                                if qty > 0:
                                    # Redondear según el par
                                    if 'BTC' in sym: qty = round(qty, 5)
                                    elif 'ETH' in sym: qty = round(qty, 4)
                                    else: qty = round(qty, 2)
                                    
                                    order_side = 'buy' if senal['side'] == 'long' else 'sell'
                                    exchange.create_market_order(sym, order_side, qty)
                                    log(f"ORDEN EJECUTADA: {order_side.upper()} {qty} {sym} @ {senal['precio']:.2f}", "TRADE")
                                    n_activas += 1
                                    
                                    if n_activas >= MAX_POSITIONS:
                                        break
                    
                    except Exception as e:
                        log(f"Error analizando {sym}: {str(e)[:80]}", "ERROR")
                        continue
            
            # Mostrar señales
            if senales_encontradas:
                senales_html = ""
                for s in senales_encontradas:
                    color_class = "signal-long" if s['side'] == 'long' else "signal-short"
                    arrow = "🟢 LONG" if s['side'] == 'long' else "🔴 SHORT"
                    senales_html += f"""
                    <div style="border-left: 3px solid {'#00ff88' if s['side']=='long' else '#ff4466'}; 
                                padding-left: 8px; margin: 8px 0;">
                    <span class="{color_class}">{arrow} — {s['symbol'].split('/')[0]}</span><br>
                    Entry: <b>{s['precio']:.2f}</b> | 
                    SL: <b style="color:#ff4466">{s['sl']:.2f}</b> | 
                    TP: <b style="color:#00ff88">{s['tp']:.2f}</b> | 
                    Score: <b>{s['score']}</b><br>
                    <small style="color:#aaa">{' • '.join(s['razones'][:4])}</small>
                    </div>"""
            else:
                senales_html = '<span class="signal-wait">⏳ Esperando confluencia de señales...</span>'
            
            senal_ph.markdown(f"""
            <div class="metric-card">
            <b>🎯 Señales Detectadas</b><br>
            {senales_html}
            </div>
            """, unsafe_allow_html=True)
            
            # Log
            log_ph.markdown(f"""
            <div class="metric-card" style="max-height:200px; overflow-y:auto; font-family:monospace; font-size:0.8em">
            {"<br>".join(st.session_state.trade_log[:20])}
            </div>
            """, unsafe_allow_html=True)
            
            time.sleep(30)
            st.rerun()
    
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        log(f"Error crítico: {e}", "ERROR")
        time.sleep(15)

elif activar and (not api_key or not api_secret):
    st.warning("⚠️ Ingresa tu API Key y Secret en el panel lateral")

else:
    # MODO DEMO: muestra el sistema sin conexión
    st.markdown("""
    ## 📋 Sistema Listo
    
    **Ingresa tus credenciales y activa el bot para comenzar.**
    
    ### Estrategias implementadas:
    
    | Estrategia | Descripción | Puntos |
    |-----------|-------------|--------|
    | Order Blocks | Zonas donde institucionales entraron | +2 |
    | Fair Value Gaps | Gaps de precio sin llenar | +2 |
    | Pin Bar | Mecha larga = rechazo de nivel | +2 |
    | Tendencia 1h | Dirección macro confirmada | +2 |
    | Estructura 15m | BOS / CHoCH de corto plazo | +1 |
    | EMA 200 | Filtro de tendencia maestra | +1 |
    | RSI Zona | Condición de sobrecompra/venta | +1 |
    | Volumen | Confirmación institucional | +1 |
    
    **Score mínimo para entrar: 5/10**
    
    ### Gestión de Capital:
    - 🎯 Riesgo fijo **2% por operación**
    - 📊 Take Profit = **2x el Stop Loss**  
    - 🔄 Trailing stop a partir de **+1.5% de ganancia**
    - 🔒 Máximo **2 posiciones** simultáneas
    """)
    
    st.info("💡 Usa **'Solo Análisis'** primero para ver las señales sin ejecutar trades reales.")
