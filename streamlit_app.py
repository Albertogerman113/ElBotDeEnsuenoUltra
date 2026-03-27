import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, date
import json

# ══════════════════════════════════════════
# SNIPER V6.0 - ULTIMATE PRICE ACTION WARRIOR
# ══════════════════════════════════════════

st.set_page_config(page_title="SNIPER V6.0", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0a0e1a; color: #e0e6f0; }
    .metric-card { 
        background: linear-gradient(135deg, #0f1629 0%, #1a2040 100%); 
        border: 2px solid #4a9eff; 
        border-radius: 15px; 
        padding: 20px; 
        margin: 10px 0; 
        box-shadow: 0 0 20px rgba(74,158,255,0.4); 
    }
    .signal-long { color: #00ff88; font-weight: bold; font-size: 1.3em; }
    .signal-short { color: #ff4466; font-weight: bold; font-size: 1.3em; }
    h1 { color: #4a9eff !important; text-shadow: 0 0 10px #4a9eff; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════
# PARÁMETROS OPTIMIZADOS
# ══════════════════════════════════════════
SYMBOLS = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD']
LEVERAGE = 10
RISK_PCT = 0.02          # 2% riesgo por trade
RR_RATIO = 2.5
MAX_POSITIONS = 2
MAX_DAILY_LOSS_PCT = 0.04
PARTIAL_PCT = 0.5        # Cerrar 50% en +1R
TIMEFRAME_ENTRY = '15m'
TIMEFRAME_TREND = '1h'
BARS_LIMIT = 400

# ══════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════
def safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except:
        return default

def log(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "ℹ️", "TRADE": "🚀", "WIN": "💰", "LOSS": "🛡️", "WARN": "⚠️", "ERROR": "❌"}
    icon = icons.get(level, "•")
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = []
    st.session_state.trade_log.insert(0, f"[{now}] {icon} {msg}")
    st.session_state.trade_log = st.session_state.trade_log[:150]

# ══════════════════════════════════════════
# PRICE ACTION ENGINE V6.0
# ══════════════════════════════════════════
def calcular_indicadores(df):
    c = df['c'].astype(float)
    h = df['h'].astype(float)
    l = df['l'].astype(float)
    o = df['o'].astype(float)
    v = df['v'].astype(float)
    
    df['ema20'] = c.ewm(span=20, adjust=False).mean()
    df['ema50'] = c.ewm(span=50, adjust=False).mean()
    df['ema200'] = c.ewm(span=200, adjust=False).mean()
    
    tr = pd.concat([h-l, abs(h - c.shift()), abs(l - c.shift())], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['vol_ma'] = v.rolling(20).mean()
    df['vol_ratio'] = v / df['vol_ma'].replace(0, np.nan)
    df['body'] = abs(c - o)
    df['is_bullish'] = c > o
    return df

def detectar_estructura_mercado(df):
    highs = df['h'].astype(float).values
    lows = df['l'].astype(float).values
    swings_h, swings_l = [], []
    for i in range(5, len(df)-5):
        if highs[i] == max(highs[i-5:i+6]):
            swings_h.append((i, highs[i]))
        if lows[i] == min(lows[i-5:i+6]):
            swings_l.append((i, lows[i]))
    if len(swings_h) < 3 or len(swings_l) < 3:
        return 'neutral', None, None
    if swings_h[-1][1] > swings_h[-2][1] and swings_l[-1][1] > swings_l[-2][1]:
        return 'bullish', swings_l[-1][1], swings_h[-1][1]
    if swings_h[-1][1] < swings_h[-2][1] and swings_l[-1][1] < swings_l[-2][1]:
        return 'bearish', swings_l[-1][1], swings_h[-1][1]
    return 'neutral', swings_l[-1][1], swings_h[-1][1]

def detectar_liquidity_sweep(df):
    if len(df) < 30: return None
    prev_low = df['l'].rolling(15).min().iloc[-6]
    prev_high = df['h'].rolling(15).max().iloc[-6]
    last = df.iloc[-1]
    if float(last['l']) < prev_low * 0.999 and last['is_bullish']:
        return 'bull_sweep'
    if float(last['h']) > prev_high * 1.001 and not last['is_bullish']:
        return 'bear_sweep'
    return None

def detectar_order_blocks(df, n=6):
    obs_bull, obs_bear = [], []
    c = df['c'].astype(float).values
    o = df['o'].astype(float).values
    for i in range(2, len(df)-n):
        move = (c[i+n] - c[i]) / c[i] * 100
        mid = (o[i] + c[i]) / 2
        if o[i] > c[i] and move > 2.0:
            obs_bull.append({'mid': mid})
        if c[i] > o[i] and move < -2.0:
            obs_bear.append({'mid': mid})
    return obs_bull[-4:], obs_bear[-4:]

def detectar_fvg(df):
    fvgs_bull, fvgs_bear = [], []
    h = df['h'].astype(float).values
    l = df['l'].astype(float).values
    for i in range(1, len(df)-1):
        if l[i+1] > h[i-1]:
            fvgs_bull.append({'bot': h[i-1], 'top': l[i+1]})
        if h[i+1] < l[i-1]:
            fvgs_bear.append({'bot': h[i+1], 'top': l[i-1]})
    return fvgs_bull[-4:], fvgs_bear[-4:]

def detectar_displacement(df):
    if len(df) < 3: return None
    last = df.iloc[-1]
    total_range = float(last['h']) - float(last['l'])
    if total_range == 0: return None
    body_ratio = abs(float(last['c']) - float(last['o'])) / total_range
    if body_ratio > 0.7 and float(last['vol_ratio']) > 1.8:
        return 'bull' if last['is_bullish'] else 'bear'
    return None

# ══════════════════════════════════════════
# GENERADOR DE SEÑALES
# ══════════════════════════════════════════
def generar_senal(df_15m, df_1h, symbol):
    if len(df_15m) < 250 or len(df_1h) < 80: return None
    
    df_15m = calcular_indicadores(df_15m.copy())
    df_1h = calcular_indicadores(df_1h.copy())
    
    last = df_15m.iloc[-1]
    precio = float(last['c'])
    atr = float(last['atr'])
    
    estructura_1h, _, _ = detectar_estructura_mercado(df_1h)
    tendencia_1h = 'bull' if (float(df_1h.iloc[-1]['ema50']) > float(df_1h.iloc[-1]['ema200']) and estructura_1h == 'bullish') else \
                   'bear' if (float(df_1h.iloc[-1]['ema50']) < float(df_1h.iloc[-1]['ema200']) and estructura_1h == 'bearish') else 'neutral'
    
    estructura_15m, _, _ = detectar_estructura_mercado(df_15m)
    obs_bull, obs_bear = detectar_order_blocks(df_15m)
    fvgs_bull, fvgs_bear = detectar_fvg(df_15m)
    sweep = detectar_liquidity_sweep(df_15m)
    displacement = detectar_displacement(df_15m)
    vol_ok = float(last['vol_ratio']) > 1.6
    
    score_long = score_short = 0
    
    if tendencia_1h == 'bull': score_long += 3
    if estructura_15m == 'bullish': score_long += 2
    if precio > float(last['ema200']): score_long += 1
    for ob in obs_bull:
        if abs(precio - ob['mid']) / precio < 0.006: score_long += 2
    for fvg in fvgs_bull:
        if fvg['bot'] <= precio <= fvg['top']: score_long += 2
    if sweep == 'bull_sweep': score_long += 3
    if displacement == 'bull': score_long += 2
    if vol_ok: score_long += 1
    
    if tendencia_1h == 'bear': score_short += 3
    if estructura_15m == 'bearish': score_short += 2
    if precio < float(last['ema200']): score_short += 1
    for ob in obs_bear:
        if abs(precio - ob['mid']) / precio < 0.006: score_short += 2
    for fvg in fvgs_bear:
        if fvg['bot'] <= precio <= fvg['top']: score_short += 2
    if sweep == 'bear_sweep': score_short += 3
    if displacement == 'bear': score_short += 2
    if vol_ok: score_short += 1
    
    if score_long >= 7 and score_long > score_short:
        sl = precio - atr * 1.8
        tp = precio + (precio - sl) * RR_RATIO
        return {'side': 'long', 'precio': precio, 'sl': sl, 'tp': tp, 'score': score_long}
    
    if score_short >= 7 and score_short > score_long:
        sl = precio + atr * 1.8
        tp = precio - (sl - precio) * RR_RATIO
        return {'side': 'short', 'precio': precio, 'sl': sl, 'tp': tp, 'score': score_short}
    
    return None

# ══════════════════════════════════════════
# GESTIÓN DE POSICIONES
# ══════════════════════════════════════════
def calcular_tamano_posicion(equity, precio, sl):
    riesgo_usd = equity * RISK_PCT
    distancia = abs(precio - sl) / precio
    if distancia <= 0: return 0
    qty = (riesgo_usd / distancia) / precio
    max_qty = (equity * 0.45 * LEVERAGE) / precio
    return min(qty, max_qty)

def gestionar_posiciones(posiciones, exchange):
    if 'active_trades' not in st.session_state:
        st.session_state.active_trades = {}
    
    n_activas = 0
    for p in posiciones:
        qty = safe_float(p.get('contracts', 0))
        if qty <= 0: continue
        n_activas += 1
        sym = p['symbol']
        side = p['side'].upper()
        mark = safe_float(p.get('markPrice'))
        pnl = safe_float(p.get('unrealizedPnl'))
        
        if sym not in st.session_state.active_trades:
            entry = safe_float(p.get('entryPrice'))
            st.session_state.active_trades[sym] = {
                'entry': entry, 'sl': entry * 0.985 if side == 'LONG' else entry * 1.015,
                'tp': entry * 1.04 if side == 'LONG' else entry * 0.96,
                'partial': False
            }
        
        trade = st.session_state.active_trades[sym]
        sl = trade['sl']
        tp = trade['tp']
        close_side = 'sell' if side == 'LONG' else 'buy'
        
        # Partial TP + Breakeven
        if not trade['partial']:
            r_distance = abs(trade['entry'] - sl)
            tp1 = trade['entry'] + r_distance if side == 'LONG' else trade['entry'] - r_distance
            if (side == 'LONG' and mark >= tp1) or (side == 'SHORT' and mark <= tp1):
                partial_qty = qty * PARTIAL_PCT
                try:
                    exchange.create_market_order(sym, close_side, partial_qty, params={'reduceOnly': True})
                    st.session_state.active_trades[sym]['partial'] = True
                    st.session_state.active_trades[sym]['sl'] = trade['entry']  # Breakeven
                    log(f"✅ PARTIAL TP + Breakeven en {sym}", "WIN")
                except Exception as e:
                    log(f"Error partial {sym}: {e}", "ERROR")
        
        # Cierre total
        if (side == 'LONG' and mark >= tp) or (side == 'SHORT' and mark <= tp):
            try:
                exchange.create_market_order(sym, close_side, qty, params={'reduceOnly': True})
                log(f"💰 TP TOTAL {sym} | PnL: ${pnl:.4f}", "WIN")
                st.session_state.stats['wins'] += 1
                st.session_state.stats['total_pnl'] += pnl
                del st.session_state.active_trades[sym]
            except Exception as e: log(f"Error TP {sym}: {e}", "ERROR")
        
        elif (side == 'LONG' and mark <= sl) or (side == 'SHORT' and mark >= sl):
            try:
                exchange.create_market_order(sym, close_side, qty, params={'reduceOnly': True})
                log(f"🛡️ SL {sym} | PnL: ${pnl:.4f}", "LOSS")
                st.session_state.stats['losses'] += 1
                st.session_state.stats['total_pnl'] += pnl
                del st.session_state.active_trades[sym]
            except Exception as e: log(f"Error SL {sym}: {e}", "ERROR")
    
    return n_activas

# ══════════════════════════════════════════
# INTERFAZ Y LOOP
# ══════════════════════════════════════════
st.title("🎯 SNIPER V6.0 — ULTIMATE PRICE ACTION WARRIOR")
st.caption("Versión optimizada para ganancias diarias consistentes")

with st.sidebar:
    st.markdown("### 🔐 Kraken Futures")
    api_key = st.text_input("API Key", type="password", key="api_key")
    api_secret = st.text_input("API Secret", type="password", key="api_secret")
    modo = st.radio("Modo de operación", ["⚡ Trading REAL", "🔍 Solo Análisis"])
    activar = st.toggle("INICIAR BOT", value=False)

col1, col2, col3 = st.columns([2, 2, 3])
capital_ph = col1.empty()
posicion_ph = col2.empty()
senal_ph = col3.empty()
log_ph = st.empty()

# Inicializar session_state
for key in ['trade_log', 'stats', 'active_trades', 'daily_pnl', 'last_date']:
    if key not in st.session_state:
        if key == 'stats':
            st.session_state.stats = {'wins': 0, 'losses': 0, 'total_pnl': 0.0}
        elif key == 'daily_pnl':
            st.session_state.daily_pnl = 0.0
        elif key == 'last_date':
            st.session_state.last_date = date.today()
        else:
            st.session_state[key] = [] if key == 'trade_log' else {}

if activar and api_key and api_secret:
    try:
        exchange = ccxt.krakenfutures({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })
        log("🚀 SNIPER V6.0 INICIADO - Vamos por ganancias diarias", "INFO")
        
        while True:
            # Reset diario
            if date.today() != st.session_state.last_date:
                st.session_state.last_date = date.today()
                st.session_state.daily_pnl = 0.0
            
            # Balance
            try:
                balance = exchange.fetch_balance()
                equity = safe_float(balance.get('USD', {}).get('total', 0))
            except:
                equity = 0.0
            
            capital_ph.markdown(f"""
                <div class="metric-card">
                    <b>💼 EQUITY</b><br>
                    <span style="font-size:2em;color:#4a9eff">${equity:.4f}</span><br>
                    <small>W: {st.session_state.stats['wins']} | L: {st.session_state.stats['losses']} | 
                    PnL Total: ${st.session_state.stats['total_pnl']:.4f}<br>
                    Hoy: ${st.session_state.daily_pnl:.4f}</small>
                </div>
            """, unsafe_allow_html=True)
            
            # Gestionar posiciones
            posiciones = exchange.fetch_positions()
            n_activas = gestionar_posiciones(posiciones, exchange)
            
            # Buscar señales
            senales = []
            if n_activas < MAX_POSITIONS:
                for sym in SYMBOLS:
                    try:
                        bars15 = exchange.fetch_ohlcv(sym, TIMEFRAME_ENTRY, limit=BARS_LIMIT)
                        bars1h = exchange.fetch_ohlcv(sym, TIMEFRAME_TREND, limit=BARS_LIMIT)
                        df15 = pd.DataFrame(bars15, columns=['ts','o','h','l','c','v'])
                        df1h = pd.DataFrame(bars1h, columns=['ts','o','h','l','c','v'])
                        
                        senal = generar_senal(df15, df1h, sym)
                        if senal:
                            senal['symbol'] = sym
                            senales.append(senal)
                            
                            if modo == "⚡ Trading REAL":
                                qty = calcular_tamano_posicion(equity, senal['precio'], senal['sl'])
                                if qty > 0:
                                    side_order = 'buy' if senal['side'] == 'long' else 'sell'
                                    exchange.create_market_order(sym, side_order, qty)
                                    st.session_state.active_trades[sym] = {
                                        'entry': senal['precio'], 'sl': senal['sl'], 'tp': senal['tp'], 'partial': False
                                    }
                                    log(f"🚀 ENTRADA {senal['side'].upper()} {qty:.6f} {sym} | Score: {senal['score']}", "TRADE")
                    except Exception as e:
                        log(f"Error en {sym}: {str(e)[:80]}", "ERROR")
            
            # Mostrar posiciones y señales (código simplificado para evitar errores)
            # ... (puedes agregar la visualización como en la versión anterior si quieres)
            
            log_ph.markdown(f"""
                <div class="metric-card" style="max-height:300px; overflow-y:auto; font-family:monospace; font-size:0.85em">
                    {"<br>".join(st.session_state.trade_log[:30])}
                </div>
            """, unsafe_allow_html=True)
            
            time.sleep(30)
            st.rerun()
            
    except Exception as e:
        st.error(f"Error general: {e}")
        time.sleep(10)
        st.rerun()
else:
    st.info("Ingresa tus credenciales de Kraken y activa el bot para comenzar.")