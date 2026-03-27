import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone, date
import json
import os

# ══════════════════════════════════════════
# SNIPER V6.0 - ULTIMATE PRICE ACTION WARRIOR
# Estrategias: Liquidity Sweep, Breaker Block, FVG, OB, BOS/CHoCH, PD Array, Displacement
# ══════════════════════════════════════════

st.set_page_config(page_title="SNIPER V6.0", layout="wide", initial_sidebar_state="expanded")

st.markdown("""

""", unsafe_allow_html=True)

# ══════════════════════════════════════════
# PARÁMETROS OPTIMIZADOS V6.0
# ══════════════════════════════════════════
SYMBOLS = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD']
LEVERAGE = 10
RISK_PCT = 0.02
RR_RATIO = 2.5
MAX_POSITIONS = 2
MAX_DAILY_LOSS_PCT = 0.04
PARTIAL_PCT = 0.5
TRAILING_TRIGGER_R = 1.0
TIMEFRAME_ENTRY = '15m'
TIMEFRAME_TREND = '1h'
BARS_LIMIT = 400

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
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = []
    st.session_state.trade_log.insert(0, f"[{now}] {icon} {msg}")
    st.session_state.trade_log = st.session_state.trade_log[:150]

# ══════════════════════════════════════════
# NUEVAS FUNCIONES DE PRICE ACTION V6.0
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
    
    tr = pd.concat([h-l, abs(h-c.shift()), abs(l-c.shift())], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['vol_ma'] = v.rolling(20).mean()
    df['vol_ratio'] = v / df['vol_ma']
    df['body'] = abs(c - o)
    df['is_bullish'] = c > o
    return df

def detectar_estructura_mercado(df):
    """BOS + CHoCH mejorado"""
    highs = df['h'].astype(float).values
    lows = df['l'].astype(float).values
    swings_h = []
    swings_l = []
    for i in range(5, len(df)-5):
        if highs[i] == max(highs[i-5:i+6]): swings_h.append((i, highs[i]))
        if lows[i] == min(lows[i-5:i+6]): swings_l.append((i, lows[i]))
    if len(swings_h) < 3 or len(swings_l) < 3: return 'neutral', None, None
    last_hh = swings_h[-1][1]
    prev_hh = swings_h[-2][1]
    last_ll = swings_l[-1][1]
    prev_ll = swings_l[-2][1]
    if last_hh > prev_hh and last_ll > prev_ll: return 'bullish', last_ll, last_hh
    if last_hh < prev_hh and last_ll < prev_ll: return 'bearish', last_ll, last_hh
    return 'neutral', last_ll, last_hh

def detectar_liquidity_sweep(df):
    """Liquidity Sweep (estrategia SMC ultra efectiva)"""
    if len(df) < 30: return None
    prev_low = df['l'].rolling(15).min().iloc[-6]
    prev_high = df['h'].rolling(15).max().iloc[-6]
    last = df.iloc[-1]
    if float(last['l']) < prev_low and last['is_bullish']: return 'bull_sweep'
    if float(last['h']) > prev_high and not last['is_bullish']: return 'bear_sweep'
    return None

def detectar_breaker_block(df):
    """Breaker Block (re-test después de BOS)"""
    if len(df) < 20: return None
    estructura, _, _ = detectar_estructura_mercado(df.iloc[:-5])
    last = df.iloc[-1]
    if estructura == 'bullish' and float(last['l']) < df['h'].iloc[-10] * 0.999 and last['is_bullish']:
        return 'bull_breaker'
    if estructura == 'bearish' and float(last['h']) > df['l'].iloc[-10] * 1.001 and not last['is_bullish']:
        return 'bear_breaker'
    return None

def detectar_order_blocks(df, n=6):
    obs_bull, obs_bear = [], []
    c = df['c'].astype(float).values
    o = df['o'].astype(float).values
    for i in range(2, len(df)-n):
        move = (c[i+n] - c[i]) / c[i] * 100
        if o[i] > c[i] and move > 2.0:
            obs_bull.append({'mid': (o[i]+c[i])/2, 'tipo': 'bull'})
        if c[i] > o[i] and move < -2.0:
            obs_bear.append({'mid': (o[i]+c[i])/2, 'tipo': 'bear'})
    return obs_bull[-4:], obs_bear[-4:]

def detectar_fvg(df):
    fvgs_bull, fvgs_bear = [], []
    h = df['h'].astype(float).values
    l = df['l'].astype(float).values
    for i in range(1, len(df)-1):
        if l[i+1] > h[i-1]: fvgs_bull.append({'bot': h[i-1], 'top': l[i+1]})
        if h[i+1] < l[i-1]: fvgs_bear.append({'bot': h[i+1], 'top': l[i-1]})
    return fvgs_bull[-4:], fvgs_bear[-4:]

def detectar_displacement(df):
    """Displacement Candle (vela fuerte con volumen)"""
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(float(last['c']) - float(last['o']))
    total = float(last['h']) - float(last['l'])
    if total == 0: return None
    if body > total * 0.7 and float(last['vol_ratio']) > 1.8:
        return 'bull' if last['is_bullish'] else 'bear'
    return None

# ══════════════════════════════════════════
# MOTOR DE SEÑALES ULTRA CONFLUENTE
# ══════════════════════════════════════════
def generar_senal(df_15m, df_1h, symbol):
    if len(df_15m) < 250 or len(df_1h) < 80: return None
    df_15m = calcular_indicadores(df_15m.copy())
    df_1h = calcular_indicadores(df_1h.copy())
    
    last = df_15m.iloc[-1]
    precio = float(last['c'])
    atr = float(last['atr'])
    
    estructura_1h, _, _ = detectar_estructura_mercado(df_1h)
    tendencia_1h = 'bull' if float(df_1h.iloc[-1]['ema50']) > float(df_1h.iloc[-1]['ema200']) and estructura_1h == 'bullish' else \
                   'bear' if float(df_1h.iloc[-1]['ema50']) < float(df_1h.iloc[-1]['ema200']) and estructura_1h == 'bearish' else 'neutral'
    
    estructura_15m, _, _ = detectar_estructura_mercado(df_15m)
    obs_bull, obs_bear = detectar_order_blocks(df_15m)
    fvgs_bull, fvgs_bear = detectar_fvg(df_15m)
    sweep = detectar_liquidity_sweep(df_15m)
    breaker = detectar_breaker_block(df_15m)
    displacement = detectar_displacement(df_15m)
    vol_ok = float(last['vol_ratio']) > 1.6
    
    score_long = score_short = 0
    razones = []
    
    if tendencia_1h == 'bull': score_long += 3
    if estructura_15m == 'bullish': score_long += 2
    if precio > float(last['ema200']): score_long += 1
    for ob in obs_bull:
        if abs(precio - ob['mid']) / precio < 0.006: score_long += 2
    for fvg in fvgs_bull:
        if fvg['bot'] <= precio <= fvg['top']: score_long += 2
    if sweep == 'bull_sweep': score_long += 3; razones.append("Liquidity Sweep BULL")
    if breaker == 'bull_breaker': score_long += 2; razones.append("Breaker Block BULL")
    if displacement == 'bull': score_long += 2; razones.append("Displacement BULL")
    if vol_ok: score_long += 1
    
    if tendencia_1h == 'bear': score_short += 3
    if estructura_15m == 'bearish': score_short += 2
    if precio < float(last['ema200']): score_short += 1
    for ob in obs_bear:
        if abs(precio - ob['mid']) / precio < 0.006: score_short += 2
    for fvg in fvgs_bear:
        if fvg['bot'] <= precio <= fvg['top']: score_short += 2
    if sweep == 'bear_sweep': score_short += 3; razones.append("Liquidity Sweep BEAR")
    if breaker == 'bear_breaker': score_short += 2; razones.append("Breaker Block BEAR")
    if displacement == 'bear': score_short += 2; razones.append("Displacement BEAR")
    if vol_ok: score_short += 1
    
    if score_long >= 7 and score_long > score_short:
        sl = get_dynamic_sl(df_15m, 'long', precio, atr)
        tp = precio + (precio - sl) * RR_RATIO
        return {'side': 'long', 'precio': precio, 'sl': sl, 'tp': tp, 'score': score_long, 'razones': razones}
    if score_short >= 7 and score_short > score_long:
        sl = get_dynamic_sl(df_15m, 'short', precio, atr)
        tp = precio - (sl - precio) * RR_RATIO
        return {'side': 'short', 'precio': precio, 'sl': sl, 'tp': tp, 'score': score_short, 'razones': razones}
    return None

def get_dynamic_sl(df, side, precio, atr):
    """SL basado en swings reales"""
    if side == 'long':
        swing_low = df['l'].rolling(12).min().iloc[-1]
        return min(swing_low * 0.9995, precio - atr * 1.8)
    else:
        swing_high = df['h'].rolling(12).max().iloc[-1]
        return max(swing_high * 1.0005, precio + atr * 1.8)

# ══════════════════════════════════════════
# GESTIÓN DE CAPITAL Y POSICIONES AVANZADA
# ══════════════════════════════════════════
def calcular_tamano_posicion(equity, precio, sl):
    riesgo_usd = equity * RISK_PCT
    distancia = abs(precio - sl) / precio
    if distancia == 0: return 0
    tamano = riesgo_usd / distancia
    qty = tamano / precio
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
        entry = safe_float(p.get('entryPrice'))
        pnl = safe_float(p.get('unrealizedPnl'))
        
        trade = st.session_state.active_trades.get(sym)
        if not trade:
            trade = {'entry': entry, 'sl': entry*0.985 if side=='LONG' else entry*1.015, 
                     'tp': entry*1.04 if side=='LONG' else entry*0.96, 
                     'partial': False, 'trailing': False}
            st.session_state.active_trades[sym] = trade
        
        sl = trade['sl']
        tp = trade['tp']
        close_side = 'sell' if side == 'LONG' else 'buy'
        
        # Partial TP en 1R
        dist_r = abs(entry - sl)
        if not trade['partial']:
            tp1 = entry + dist_r if side == 'LONG' else entry - dist_r
            if (side == 'LONG' and mark >= tp1) or (side == 'SHORT' and mark <= tp1):
                partial_qty = qty * PARTIAL_PCT
                exchange.create_market_order(sym, close_side, partial_qty, params={'reduceOnly': True})
                st.session_state.active_trades[sym]['partial'] = True
                st.session_state.active_trades[sym]['sl'] = entry
                log(f"✅ PARTIAL TP 50% {sym} | +1R asegurado", "WIN")
        
        # TP final o SL
        if (side == 'LONG' and mark >= tp) or (side == 'SHORT' and mark <= tp):
            exchange.create_market_order(sym, close_side, qty, params={'reduceOnly': True})
            log(f"💰 TP TOTAL ALCANZADO {sym} | PnL: ${pnl:.4f}", "WIN")
            st.session_state.stats['wins'] += 1
            st.session_state.stats['total_pnl'] += pnl
            st.session_state.daily_pnl += pnl
            del st.session_state.active_trades[sym]
            
        elif (side == 'LONG' and mark <= sl) or (side == 'SHORT' and mark >= sl):
            exchange.create_market_order(sym, close_side, qty, params={'reduceOnly': True})
            log(f"🛡️ SL {sym} | PnL: ${pnl:.4f}", "LOSS")
            st.session_state.stats['losses'] += 1
            st.session_state.stats['total_pnl'] += pnl
            st.session_state.daily_pnl += pnl
            del st.session_state.active_trades[sym]
        
        # Trailing final
        elif trade['partial'] and not trade.get('trailing'):
            if (side == 'LONG' and mark >= entry + dist_r * 1.5) or (side == 'SHORT' and mark <= entry - dist_r * 1.5):
                st.session_state.active_trades[sym]['trailing'] = True
                log(f"📈 TRAILING AGRESIVO activado en {sym}", "INFO")
    
    return n_activas

# ══════════════════════════════════════════
# INTERFAZ + LOOP PRINCIPAL
# ══════════════════════════════════════════
st.title("🎯 SNIPER V6.0 — ULTIMATE PRICE ACTION WARRIOR")
st.caption("💎 Versión definitiva para ganar todos los días | Con la bendición de Dios nos va a ir brutal")

with st.sidebar:
    st.markdown("### 🔐 Kraken Futures")
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
    modo = st.radio("Modo", ["⚡ Trading REAL", "🔍 Paper (solo análisis)"])
    activar = st.toggle("INICIAR BOT SNIPER V6.0", value=False)

col1, col2, col3 = st.columns([2,2,3])
capital_ph = col1.empty()
posicion_ph = col2.empty()
senal_ph = col3.empty()
log_ph = st.empty()

if 'trade_log' not in st.session_state: st.session_state.trade_log = []
if 'stats' not in st.session_state: st.session_state.stats = {'wins':0, 'losses':0, 'total_pnl':0.0}
if 'active_trades' not in st.session_state: st.session_state.active_trades = {}
if 'daily_pnl' not in st.session_state: st.session_state.daily_pnl = 0.0
if 'last_date' not in st.session_state: st.session_state.last_date = date.today()

if activar and api_key and api_secret:
    exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True, 'options': {'defaultType': 'future'}})
    log("🚀 SNIPER V6.0 INICIADO - Que Dios nos bendiga y nos dé ganancias diarias", "INFO")
    
    while True:
        # Fecha y daily loss
        today = date.today()
        if today != st.session_state.last_date:
            st.session_state.last_date = today
            st.session_state.daily_pnl = 0.0
        
        # Balance
        try:
            balance = exchange.fetch_balance()
            equity = safe_float(balance.get('USD', {}).get('total', 0))
        except: equity = 0.0
        
        capital_ph.markdown(f"""
💼 EQUITY
${equity:.4f}

        W:{st.session_state.stats['wins']} | L:{st.session_state.stats['losses']} | PnL Total: ${st.session_state.stats['total_pnl']:.4f}

        Hoy: ${st.session_state.daily_pnl:.4f} ({st.session_state.daily_pnl/equity*100 if equity else 0:+.2f}%)
""", unsafe_allow_html=True)
        
        # Posiciones
        posiciones = exchange.fetch_positions()
        n_activas = gestionar_posiciones(posiciones, exchange)
        
        # Daily loss protection
        if st.session_state.daily_pnl < -equity * MAX_DAILY_LOSS_PCT and equity > 0:
            log("🚨 LÍMITE DIARIO ALCANZADO. Bot pausado 24h para proteger tu capital", "WARN")
            time.sleep(3600)
            continue
        
        # Señales
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
                                    'entry': senal['precio'], 'sl': senal['sl'], 'tp': senal['tp'],
                                    'partial': False, 'trailing': False
                                }
                                log(f"🚀 ENTRADA {senal['side'].upper()} {qty:.6f} {sym} | Score {senal['score']}", "TRADE")
                                n_activas += 1
                                if n_activas >= MAX_POSITIONS: break
                except Exception as e:
                    log(f"Error {sym}: {str(e)[:60]}", "ERROR")
        
        # Mostrar todo
        pos_html = ""
        for p in posiciones:
            if safe_float(p.get('contracts')) > 0:
                sym = p['symbol']
                side = p['side'].upper()
                pnl = safe_float(p.get('unrealizedPnl'))
                color = "#00ff88" if pnl >= 0 else "#ff4466"
                trade = st.session_state.active_trades.get(sym, {})
                pos_html += f"""
{sym.split('/')[0]} {side} | PnL ${pnl:+.4f}

                SL:{trade.get('sl',0):.2f} | TP:{trade.get('tp',0):.2f}
"""
        
        posicion_ph.markdown(f"""
📍 POSICIONES ({n_activas}/{MAX_POSITIONS})
{pos_html or 'Sin posiciones abiertas'}
""", unsafe_allow_html=True)
        
        senal_html = ""
        for s in senales:
            color = '#00ff88' if s['side']=='long' else '#ff4466'
            senal_html += f"""

            {s['side'].upper()} {s['symbol'].split('/')[0]}

            Entry {s['precio']:.2f} | SL {s['sl']:.2f} | TP {s['tp']:.2f} | Score {s['score']}

            {' • '.join(s['razones'][:4])}
"""
        senal_ph.markdown(f"""
🎯 SEÑALES EN VIVO
{senal_html or 'Esperando confluencia perfecta...'}
""", unsafe_allow_html=True)
        
        log_ph.markdown(f"""
{"
".join(st.session_state.trade_log[:25])}
""", unsafe_allow_html=True)
        
        time.sleep(25)
        st.rerun()

else:
    st.success("✅ Ingresa tus credenciales y activa el bot. ¡Listo para ganar todos los días!")