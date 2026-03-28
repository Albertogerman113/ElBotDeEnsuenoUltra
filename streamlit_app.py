# ============================================================================
# SNIPER V8.1 - PRICE ACTION ELITE (CORREGIDO)
# ============================================================================
# Cambios: Filtros relajados, debugging detallado, NewsFilter desactivado
# ============================================================================

import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import json

# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================
st.set_page_config(
    page_title="SNIPER V8.1 | CORREGIDO",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# ESTILOS PROFESIONALES
# ============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
    
    .stApp { 
        background: linear-gradient(135deg, #0a0e1a 0%, #0f1426 50%, #0a0e1a 100%); 
        color: #e0e6f0;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .metric-card { 
        background: linear-gradient(135deg, #1a2040 0%, #0f1629 100%);
        border: 1px solid #3a4a7a; 
        border-radius: 16px; 
        padding: 20px; 
        margin: 10px 0;
        box-shadow: 0 4px 15px rgba(74, 158, 255, 0.1);
    }
    
    .metric-card:hover {
        border-color: #4a9eff;
        box-shadow: 0 6px 25px rgba(74, 158, 255, 0.2);
    }
    
    .signal-long { color: #00ff88; font-weight: 700; text-shadow: 0 0 10px rgba(0, 255, 136, 0.3); }
    .signal-short { color: #ff4466; font-weight: 700; text-shadow: 0 0 10px rgba(255, 68, 102, 0.3); }
    h1 { color: #4a9eff !important; }
    
    .warning-box {
        background: linear-gradient(135deg, #2a1a1a 0%, #1a0f0f 100%);
        border: 1px solid #ff4466;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    
    .success-box {
        background: linear-gradient(135deg, #1a2a1a 0%, #0f1a0f 100%);
        border: 1px solid #00ff88;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    
    .info-box {
        background: linear-gradient(135deg, #1a2a3a 0%, #0f1a2a 100%);
        border: 1px solid #4a9eff;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    
    .log-entry { font-family: 'JetBrains Mono', monospace; font-size: 0.75em; }
    
    .stButton>button {
        background: linear-gradient(135deg, #4a9eff 0%, #2d7dd2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CONFIGURACIÓN V8.1 - CORREGIDA
# ============================================================================
class Config:
    SYMBOLS = {
        'BTC/USD:USD': {'min_size': 0.0001, 'tick_size': 0.5, 'risk_weight': 1.0, 'correlation_group': 'major'},
        'ETH/USD:USD': {'min_size': 0.001, 'tick_size': 0.05, 'risk_weight': 0.8, 'correlation_group': 'major'},
        'SOL/USD:USD': {'min_size': 0.01, 'tick_size': 0.001, 'risk_weight': 0.6, 'correlation_group': 'alt'}
    }
    
    LEVERAGE_DEFAULT = 10
    RISK_PCT_DEFAULT = 0.01
    RR_RATIO = 2.0
    MAX_POSITIONS = 3
    MAX_DAILY_TRADES = 10
    MAX_DAILY_LOSS_PCT = 0.05
    MAX_WEEKLY_LOSS_PCT = 0.15
    MAX_CONSECUTIVE_LOSSES = 5
    
    TIMEFRAME_ENTRY = '15m'
    TIMEFRAME_TREND = '1h'
    TIMEFRAME_CONFIRM = '5m'
    TIMEFRAME_HIGH = '4h'
    BARS_LIMIT = 200
    
    # PARÁMETROS RELAJADOS
    OB_STRENGTH = 1.0
    FVG_MIN_GAP = 0.002
    MSS_CONFIRMATION_BARS = 2
    VOLUME_CONFIRMATION = 1.0
    MIN_SCORE_BASE = 4.0
    
    # FILTROS DESACTIVADOS PARA PRUEBA
    VOLATILITY_FILTER_ENABLED = False
    MAX_ATR_PCT = 5.0
    MIN_ATR_PCT = 0.05
    
    # HORARIOS DESACTIVADOS
    NEWS_FILTER_ENABLED = False
    PROHIBITED_HOURS = []
    
    SCALE_OUT_ENABLED = True
    SCALE_OUT_TP1_PCT = 0.02
    SCALE_OUT_TP1_PERCENT = 0.5
    TRAILING_AFTER_SCALE = True
    
    TRAILING_ENABLED = True
    BREAKEVEN_AT_R = 0.8
    TRAILING_START_AT_R = 1.0
    TRAILING_DISTANCE_ATR_MULT = 0.5
    
    RATE_LIMIT_DELAY = 10

# ============================================================================
# INICIALIZACIÓN DE SESSION STATE
# ============================================================================
def init_session_state():
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = []
    
    if 'trade_stats' not in st.session_state:
        st.session_state.trade_stats = {
            'wins': 0, 'losses': 0, 'total_pnl': 0.0,
            'avg_win': 0.0, 'avg_loss': 0.0, 'max_drawdown': 0.0,
            'largest_win': 0.0, 'largest_loss': 0.0,
            'consecutive_wins': 0, 'consecutive_losses': 0,
            'max_consecutive_wins': 0, 'max_consecutive_losses': 0,
            'total_trades': 0, 'profit_factor': 0.0
        }
    
    if 'active_trades' not in st.session_state:
        st.session_state.active_trades = {}
    
    if 'last_signal_time' not in st.session_state:
        st.session_state.last_signal_time = {}
    
    if 'daily_trades' not in st.session_state:
        st.session_state.daily_trades = 0
    
    if 'daily_pnl' not in st.session_state:
        st.session_state.daily_pnl = 0.0
    
    if 'weekly_pnl' not in st.session_state:
        st.session_state.weekly_pnl = 0.0
    
    if 'last_reset_date' not in st.session_state:
        st.session_state.last_reset_date = datetime.now().strftime('%Y-%m-%d')
    
    if 'last_week_reset' not in st.session_state:
        st.session_state.last_week_reset = datetime.now().strftime('%Y-%W')
    
    if 'equity_cache' not in st.session_state:
        st.session_state.equity_cache = 0.0
    
    if 'trading_paused' not in st.session_state:
        st.session_state.trading_paused = False
    
    if 'pause_reason' not in st.session_state:
        st.session_state.pause_reason = ""

# ============================================================================
# GESTOR DE LOGS
# ============================================================================
class LogManager:
    def __init__(self, max_entries: int = 500):
        self.max_entries = max_entries
    
    def log(self, msg: str, level: str = "INFO"):
        now = datetime.now().strftime("%H:%M:%S")
        icons = {
            "INFO": "📊", "TRADE": "🎯", "WIN": "💰", 
            "LOSS": "⚠️", "WARN": "⚡", "ERROR": "❌",
            "SYSTEM": "🔧", "RISK": "🛡️", "SCALE": "📊",
            "PAUSE": "⏸️", "FILTER": "🚫", "DEBUG": "🔍"
        }
        icon = icons.get(level, "•")
        entry = f"[{now}] {icon} [{level}] {msg}"
        
        if 'trade_log' not in st.session_state:
            st.session_state.trade_log = []
        
        st.session_state.trade_log.insert(0, entry)
        st.session_state.trade_log = st.session_state.trade_log[:self.max_entries]
    
    def get_logs(self, limit: int = 50) -> List[str]:
        return st.session_state.trade_log[:limit] if 'trade_log' in st.session_state else []
    
    def clear_logs(self):
        st.session_state.trade_log = []

# ============================================================================
# UTILIDADES
# ============================================================================
def safe_float(val, default=0.0):
    try: 
        if val is None: return default
        f = float(val)
        return f if not np.isnan(f) else default
    except: 
        return default

def get_current_session() -> Tuple[str, float]:
    hour_utc = datetime.now(timezone.utc).hour
    sessions = {
        'asian': {'start': 0, 'end': 8, 'weight': 0.7},
        'london': {'start': 7, 'end': 16, 'weight': 1.2},
        'ny': {'start': 12, 'end': 21, 'weight': 1.5}
    }
    for name, data in sessions.items():
        if data['start'] <= hour_utc < data['end']:
            return name, data['weight']
    return 'offpeak', 0.5

def get_equity() -> float:
    return st.session_state.get('equity_cache', 0.0)

def set_equity(value: float):
    st.session_state.equity_cache = value

# ============================================================================
# FILTROS SIMPLIFICADOS
# ============================================================================
class MarketFilters:
    
    @staticmethod
    def check_prohibited_hours() -> Tuple[bool, str]:
        if not Config.NEWS_FILTER_ENABLED:
            return False, ""
        
        now_utc = datetime.now(timezone.utc).strftime('%H:%M')
        for h in Config.PROHIBITED_HOURS:
            if h['start'] <= now_utc <= h['end']:
                return True, h['reason']
        return False, ""
    
    @staticmethod
    def check_volatility_filter(df: pd.DataFrame) -> Tuple[bool, str]:
        if not Config.VOLATILITY_FILTER_ENABLED:
            return True, ""
        if len(df) < 14:
            return True, ""
        
        atr_pct = df['atr_pct'].iloc[-1]
        if atr_pct > Config.MAX_ATR_PCT:
            return False, f"Volatilidad extrema: {atr_pct:.2f}%"
        if atr_pct < Config.MIN_ATR_PCT:
            return False, f"Mercado muy quieto: {atr_pct:.2f}%"
        return True, ""
    
    @staticmethod
    def check_correlation(symbol: str, active_positions: Dict) -> Tuple[bool, str]:
        if len(active_positions) >= Config.MAX_POSITIONS:
            return False, "Máximo de posiciones alcanzado"
        return True, ""
    
    @staticmethod
    def check_daily_limits() -> Tuple[bool, str]:
        today = datetime.now().strftime('%Y-%m-%d')
        if st.session_state.get('last_reset_date') != today:
            st.session_state.daily_trades = 0
            st.session_state.daily_pnl = 0.0
            st.session_state.last_reset_date = today
        
        current_week = datetime.now().strftime('%Y-%W')
        if st.session_state.get('last_week_reset') != current_week:
            st.session_state.weekly_pnl = 0.0
            st.session_state.last_week_reset = current_week
        
        if st.session_state.daily_trades >= Config.MAX_DAILY_TRADES:
            return False, f"Límite diario de trades ({Config.MAX_DAILY_TRADES}) alcanzado"
        
        equity = get_equity()
        if equity > 0 and st.session_state.daily_pnl < -equity * Config.MAX_DAILY_LOSS_PCT:
            return False, f"Límite de pérdida diaria ({Config.MAX_DAILY_LOSS_PCT*100:.0f}%) alcanzado"
        
        if equity > 0 and st.session_state.weekly_pnl < -equity * Config.MAX_WEEKLY_LOSS_PCT:
            return False, f"Límite de pérdida semanal ({Config.MAX_WEEKLY_LOSS_PCT*100:.0f}%) alcanzado"
        
        stats = st.session_state.trade_stats
        if stats['consecutive_losses'] >= Config.MAX_CONSECUTIVE_LOSSES:
            return False, f"{Config.MAX_CONSECUTIVE_LOSSES} pérdidas consecutivas - PAUSA"
        
        return True, "OK"
    
    @staticmethod
    def check_multi_timeframe_alignment(df_15m: pd.DataFrame, df_1h: pd.DataFrame, 
                                        df_4h: pd.DataFrame) -> Tuple[bool, str]:
        if len(df_15m) < 50 or len(df_1h) < 50:
            return False, "Datos insuficientes"
        return True, "OK"

# ============================================================================
# INDICADORES TÉCNICOS
# ============================================================================
class TechnicalIndicators:
    @staticmethod
    def calcular_indicadores_premium(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        c = df['c'].astype(float)
        h = df['h'].astype(float)
        l = df['l'].astype(float)
        o = df['o'].astype(float)
        v = df['v'].astype(float)
        
        for span in [9, 20, 50, 100, 200]:
            df[f'ema{span}'] = c.ewm(span=span, adjust=False).mean()
        
        tr1 = h - l
        tr2 = abs(h - c.shift(1))
        tr3 = abs(l - c.shift(1))
        df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()
        df['atr_pct'] = (df['atr'] / c * 100).fillna(0)
        
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)
        
        df['vol_ma'] = v.rolling(20).mean()
        df['vol_ratio'] = (v / df['vol_ma']).fillna(1)
        
        df['body'] = abs(c - o)
        df['wick_up'] = h - pd.concat([c, o], axis=1).max(axis=1)
        df['wick_dn'] = pd.concat([c, o], axis=1).min(axis=1) - l
        
        return df
    
    @staticmethod
    def detectar_mss(df: pd.DataFrame, lookback: int = 20) -> Tuple[str, Optional[float], Optional[float]]:
        if len(df) < lookback + Config.MSS_CONFIRMATION_BARS:
            return 'neutral', None, None
        
        highs = df['h'].astype(float).values
        lows = df['l'].astype(float).values
        c = df['c'].astype(float).values
        
        swings_h, swings_l = [], []
        for i in range(3, len(df) - 1):
            if highs[i] == max(highs[max(0, i-3):min(len(highs), i+2)]):
                swings_h.append((i, highs[i]))
            if lows[i] == min(lows[max(0, i-3):min(len(lows), i+2)]):
                swings_l.append((i, lows[i]))
        
        if len(swings_h) < 3 or len(swings_l) < 3:
            return 'neutral', None, None
        
        last_hh, prev_hh = swings_h[-1][1], swings_h[-2][1]
        last_ll, prev_ll = swings_l[-1][1], swings_l[-2][1]
        
        if last_hh > prev_hh and last_ll > prev_ll and c[-1] > last_hh:
            return 'bullish_mss', last_ll, last_hh
        if last_hh < prev_hh and last_ll < prev_ll and c[-1] < last_ll:
            return 'bearish_mss', last_ll, last_hh
        if last_hh > prev_hh and last_ll > prev_ll:
            return 'bullish', last_ll, last_hh
        if last_hh < prev_hh and last_ll < prev_ll:
            return 'bearish', last_ll, last_hh
        
        return 'neutral', last_ll, last_hh
    
    @staticmethod
    def detectar_order_blocks(df: pd.DataFrame, n: int = 5) -> Tuple[List[Dict], List[Dict]]:
        obs_bull, obs_bear = [], []
        c = df['c'].astype(float).values
        o = df['o'].astype(float).values
        
        for i in range(3, len(df) - n - 2):
            if o[i] > c[i]:
                move_up = (c[i+n] - o[i]) / (o[i] + 1e-10) * 100
                if move_up > Config.OB_STRENGTH:
                    obs_bull.append({'mid': (o[i] + c[i]) / 2, 'strength': move_up})
            if c[i] > o[i]:
                move_dn = (o[i] - c[i+n]) / (o[i] + 1e-10) * 100
                if move_dn > Config.OB_STRENGTH:
                    obs_bear.append({'mid': (c[i] + o[i]) / 2, 'strength': move_dn})
        
        return sorted(obs_bull, key=lambda x: x['strength'], reverse=True)[:3], \
               sorted(obs_bear, key=lambda x: x['strength'], reverse=True)[:3]
    
    @staticmethod
    def detectar_fvg(df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
        fvgs_bull, fvgs_bear = [], []
        h = df['h'].astype(float).values
        l = df['l'].astype(float).values
        
        for i in range(1, len(df) - 1):
            if l[i+1] > h[i-1]:
                gap = (l[i+1] - h[i-1]) / (h[i-1] + 1e-10)
                if gap >= Config.FVG_MIN_GAP:
                    fvgs_bull.append({'bot': h[i-1], 'top': l[i+1], 'gap_size': gap})
            if h[i+1] < l[i-1]:
                gap = (l[i-1] - h[i+1]) / (l[i-1] + 1e-10)
                if gap >= Config.FVG_MIN_GAP:
                    fvgs_bear.append({'bot': h[i+1], 'top': l[i-1], 'gap_size': gap})
        
        return fvgs_bull[-3:], fvgs_bear[-3:]
    
    @staticmethod
    def detectar_patrones_velas(df: pd.DataFrame) -> Dict[str, Optional[str]]:
        patterns = {'pin': None, 'engulfing': None, 'inside': False}
        
        if len(df) < 2:
            return patterns
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        body = abs(float(last['c']) - float(last['o']))
        total_range = float(last['h']) - float(last['l'])
        
        if total_range > 1e-10:
            wick_up = float(last['h']) - max(float(last['c']), float(last['o']))
            wick_dn = min(float(last['c']), float(last['o'])) - float(last['l'])
            
            if wick_dn > total_range * 0.65 and body < total_range * 0.25:
                patterns['pin'] = 'bull_pin'
            elif wick_up > total_range * 0.65 and body < total_range * 0.25:
                patterns['pin'] = 'bear_pin'
        
        if prev is not None:
            curr_body = float(last['c']) - float(last['o'])
            prev_body = float(prev['c']) - float(prev['o'])
            curr_vol = float(last['v'])
            prev_vol = float(prev['v'])
            
            if (prev_body < 0 and curr_body > 0 and 
                float(last['o']) < float(prev['c']) and 
                float(last['c']) > float(prev['o']) and
                curr_vol > prev_vol * 1.3):
                patterns['engulfing'] = 'bull_engulfing'
            elif (prev_body > 0 and curr_body < 0 and 
                  float(last['o']) > float(prev['c']) and 
                  float(last['c']) < float(prev['o']) and
                  curr_vol > prev_vol * 1.3):
                patterns['engulfing'] = 'bear_engulfing'
        
        return patterns

# ============================================================================
# GESTIÓN DE POSICIONES CON SCALE-OUT Y TRAILING
# ============================================================================
def gestionar_posiciones_v8(posiciones: List[Dict], exchange, logger: LogManager) -> int:
    n_activas = 0
    
    for p in posiciones:
        qty = safe_float(p.get('contracts', 0))
        if qty <= 0:
            continue
        
        n_activas += 1
        sym = p['symbol']
        side = p['side'].upper()
        mark = safe_float(p.get('markPrice'))
        pnl = safe_float(p.get('unrealizedPnl'))
        entry = safe_float(p.get('entryPrice'))
        
        if sym not in st.session_state.active_trades:
            sl_mult = 0.985 if side == 'LONG' else 1.015
            tp_mult = 1.03 if side == 'LONG' else 0.97
            entry_risk = abs(entry - entry * sl_mult) / entry if entry > 0 else 0.015
            
            st.session_state.active_trades[sym] = {
                'entry': entry,
                'sl_current': entry * sl_mult,
                'tp_current': entry * tp_mult,
                'trailing_active': False,
                'breakeven_reached': False,
                'entry_risk': entry_risk,
                'trailing_start': entry,
                'side': side,
                'original_qty': qty,
                'current_qty': qty,
                'scale_out_done': False
            }
            logger.log(f"Trade reconstruido: {sym}", "SYSTEM")
        
        trade = st.session_state.active_trades[sym]
        sl, tp = trade['sl_current'], trade['tp_current']
        
        # SCALE-OUT
        if Config.SCALE_OUT_ENABLED and not trade.get('scale_out_done', False):
            profit_pct = abs(mark - entry) / entry if entry > 0 else 0
            
            if profit_pct >= Config.SCALE_OUT_TP1_PCT:
                try:
                    half_qty = trade['current_qty'] * Config.SCALE_OUT_TP1_PERCENT
                    close_side = 'sell' if side == 'LONG' else 'buy'
                    
                    exchange.create_order(
                        symbol=sym, type='market', side=close_side,
                        amount=half_qty, params={'reduceOnly': True}
                    )
                    
                    trade['current_qty'] -= half_qty
                    trade['scale_out_done'] = True
                    trade['sl_current'] = entry * (1.002 if side == 'LONG' else 0.998)
                    trade['breakeven_reached'] = True
                    
                    logger.log(f"SCALE OUT: 50% cerrado en {sym} | Profit: {profit_pct*100:.2f}%", "SCALE")
                    
                except Exception as e:
                    logger.log(f"Error en scale-out {sym}: {str(e)[:50]}", "ERROR")
        
        # Verificar TP/SL
        close_side = 'sell' if side == 'LONG' else 'buy'
        is_tp = (side == 'LONG' and mark >= tp) or (side == 'SHORT' and mark <= tp)
        is_sl = (side == 'LONG' and mark <= sl) or (side == 'SHORT' and mark >= sl)
        
        if is_tp or is_sl:
            try:
                exchange.create_order(symbol=sym, type='market', side=close_side, 
                                     amount=trade['current_qty'], params={'reduceOnly': True})
                
                stats = st.session_state.trade_stats
                stats['total_pnl'] += pnl
                stats['total_trades'] += 1
                
                if is_tp:
                    logger.log(f"TP ALCANZADO: {sym} | PnL: ${pnl:+.4f}", "WIN")
                    stats['wins'] += 1
                    w = stats['wins']
                    stats['avg_win'] = (stats['avg_win'] * (w - 1) + pnl) / w if w > 0 else pnl
                    stats['largest_win'] = max(stats['largest_win'], pnl)
                    stats['consecutive_wins'] += 1
                    stats['consecutive_losses'] = 0
                    stats['max_consecutive_wins'] = max(stats['max_consecutive_wins'], stats['consecutive_wins'])
                else:
                    logger.log(f"SL ACTIVADO: {sym} | PnL: ${pnl:+.4f}", "LOSS")
                    stats['losses'] += 1
                    l = stats['losses']
                    stats['avg_loss'] = (stats['avg_loss'] * (l - 1) + abs(pnl)) / l if l > 0 else abs(pnl)
                    stats['largest_loss'] = max(stats['largest_loss'], abs(pnl))
                    stats['consecutive_losses'] += 1
                    stats['consecutive_wins'] = 0
                    stats['max_consecutive_losses'] = max(stats['max_consecutive_losses'], stats['consecutive_losses'])
                
                if stats['total_pnl'] < stats['max_drawdown']:
                    stats['max_drawdown'] = stats['total_pnl']
                
                st.session_state.daily_pnl += pnl
                st.session_state.weekly_pnl += pnl
                
                if stats['avg_loss'] > 0:
                    stats['profit_factor'] = stats['avg_win'] / stats['avg_loss']
                else:
                    stats['profit_factor'] = 999.0 if stats['wins'] > 0 else 0.0
                
                del st.session_state.active_trades[sym]
                
            except Exception as e:
                logger.log(f"Error cerrando {sym}: {str(e)[:60]}", "ERROR")
            continue
        
        # TRAILING STOP
        if Config.TRAILING_ENABLED:
            r_mult = abs(mark - entry) / trade['entry_risk'] if trade['entry_risk'] > 0 else 0
            
            if not trade['breakeven_reached'] and r_mult >= Config.BREAKEVEN_AT_R:
                trade['sl_current'] = entry * (1.002 if side == 'LONG' else 0.998)
                trade['breakeven_reached'] = True
                logger.log(f"{sym}: Breakeven activado @ {Config.BREAKEVEN_AT_R}R", "RISK")
            
            elif trade['breakeven_reached'] and not trade['trailing_active'] and r_mult >= Config.TRAILING_START_AT_R:
                trade['trailing_active'] = True
                trade['trailing_start'] = mark
                logger.log(f"{sym}: Trailing activado @ {Config.TRAILING_START_AT_R}R", "RISK")
            
            elif trade['trailing_active']:
                atr = trade.get('atr', 0.01 * entry)
                trail_dist = atr * Config.TRAILING_DISTANCE_ATR_MULT
                
                if side == 'LONG':
                    if mark > trade['trailing_start']:
                        trade['trailing_start'] = mark
                    trade['sl_current'] = max(trade['sl_current'], mark - trail_dist)
                else:
                    if mark < trade['trailing_start']:
                        trade['trailing_start'] = mark
                    trade['sl_current'] = min(trade['sl_current'], mark + trail_dist)
    
    return n_activas

# ============================================================================
# GENERADOR DE SEÑALES V8.1 - CON DEBUGGING
# ============================================================================
class SignalGeneratorV8:
    def __init__(self):
        self.filters = MarketFilters()
    
    def generar_senal_premium(self, df_15m: pd.DataFrame, df_1h: pd.DataFrame, 
                              df_4h: pd.DataFrame, symbol: str, logger: LogManager) -> Optional[Dict]:
        """Genera señal con logging detallado"""
        
        logger.log(f"Analizando {symbol}...", "DEBUG")
        
        if len(df_15m) < 50 or len(df_1h) < 50:
            logger.log(f"{symbol}: Datos insuficientes (15m:{len(df_15m)}, 1h:{len(df_1h)})", "WARN")
            return None
        
        # Calcular indicadores
        df_15m = TechnicalIndicators.calcular_indicadores_premium(df_15m)
        df_1h = TechnicalIndicators.calcular_indicadores_premium(df_1h)
        
        last_15m = df_15m.iloc[-1]
        precio = float(last_15m['c'])
        atr = float(last_15m['atr'])
        atr_pct = float(last_15m['atr_pct'])
        rsi = float(last_15m['rsi'])
        vol_ratio = float(last_15m['vol_ratio'])
        
        session_name, session_weight = get_current_session()
        
        # Estructura de mercado simplificada
        ema50_15m = float(last_15m['ema50'])
        ema200_15m = float(last_15m['ema200'])
        ema50_1h = float(df_1h.iloc[-1]['ema50'])
        ema200_1h = float(df_1h.iloc[-1]['ema200'])
        
        tendencia_15m = 'bull' if ema50_15m > ema200_15m * 1.001 else 'bear' if ema50_15m < ema200_15m * 0.999 else 'neutral'
        tendencia_1h = 'bull' if ema50_1h > ema200_1h * 1.001 else 'bear' if ema50_1h < ema200_1h * 0.999 else 'neutral'
        
        estructura_15m, swing_low_15m, swing_high_15m = TechnicalIndicators.detectar_mss(df_15m)
        obs_bull, obs_bear = TechnicalIndicators.detectar_order_blocks(df_15m)
        fvgs_bull, fvgs_bear = TechnicalIndicators.detectar_fvg(df_15m)
        patrones = TechnicalIndicators.detectar_patrones_velas(df_15m)
        
        logger.log(f"{symbol}: Precio={precio:.2f}, RSI={rsi:.1f}, Vol={vol_ratio:.2f}x, Tend15m={tendencia_15m}, Tend1h={tendencia_1h}", "DEBUG")
        
        # Scoring
        score_long, score_short = 0, 0
        razones_long, razones_short = [], []
        
        # LONG scoring
        if tendencia_1h == 'bull':
            score_long += 3.5
            razones_long.append("Tendencia 1H alcista")
        if tendencia_15m == 'bull':
            score_long += 2.0
            razones_long.append("Tendencia 15m alcista")
        if estructura_15m in ['bullish', 'bullish_mss']:
            score_long += 2.0
            razones_long.append(f"Estructura: {estructura_15m}")
        if precio > ema200_15m * 1.001:
            score_long += 1.5
            razones_long.append("Precio sobre EMA200")
        
        for ob in obs_bull:
            if abs(precio - ob['mid']) / precio < 0.005:
                score_long += 2.0
                razones_long.append(f"OB Bull ({ob['strength']:.1f}%)")
                break
        
        for fvg in fvgs_bull:
            if fvg['bot'] <= precio <= fvg['top']:
                score_long += 2.0
                razones_long.append(f"FVG Bull")
                break
        
        if patrones['pin'] == 'bull_pin':
            score_long += 2.0
            razones_long.append("Pin Bar alcista")
        if patrones['engulfing'] == 'bull_engulfing':
            score_long += 2.5
            razones_long.append("Engulfing alcista")
        if 30 < rsi < 60:
            score_long += 1.5
            razones_long.append(f"RSI favorable: {rsi:.1f}")
        if vol_ratio > Config.VOLUME_CONFIRMATION:
            score_long += 1.5
            razones_long.append(f"Volumen {vol_ratio:.2f}x")
        
        score_long *= session_weight
        
        # SHORT scoring
        if tendencia_1h == 'bear':
            score_short += 3.5
            razones_short.append("Tendencia 1H bajista")
        if tendencia_15m == 'bear':
            score_short += 2.0
            razones_short.append("Tendencia 15m bajista")
        if estructura_15m in ['bearish', 'bearish_mss']:
            score_short += 2.0
            razones_short.append(f"Estructura: {estructura_15m}")
        if precio < ema200_15m * 0.999:
            score_short += 1.5
            razones_short.append("Precio bajo EMA200")
        
        for ob in obs_bear:
            if abs(precio - ob['mid']) / precio < 0.005:
                score_short += 2.0
                razones_short.append(f"OB Bear ({ob['strength']:.1f}%)")
                break
        
        for fvg in fvgs_bear:
            if fvg['bot'] <= precio <= fvg['top']:
                score_short += 2.0
                razones_short.append(f"FVG Bear")
                break
        
        if patrones['pin'] == 'bear_pin':
            score_short += 2.0
            razones_short.append("Pin Bar bajista")
        if patrones['engulfing'] == 'bear_engulfing':
            score_short += 2.5
            razones_short.append("Engulfing bajista")
        if 40 < rsi < 70:
            score_short += 1.5
            razones_short.append(f"RSI favorable: {rsi:.1f}")
        if vol_ratio > Config.VOLUME_CONFIRMATION:
            score_short += 1.5
            razones_short.append(f"Volumen {vol_ratio:.2f}x")
        
        score_short *= session_weight
        
        # Umbral dinámico
        base_threshold = Config.MIN_SCORE_BASE
        dynamic_threshold = base_threshold * (1 + atr_pct / 3) * (1 / session_weight)
        MIN_SCORE = max(4.0, min(8.0, dynamic_threshold))
        
        logger.log(f"{symbol}: Score L={score_long:.1f}, S={score_short:.1f}, Umbral={MIN_SCORE:.1f}", "INFO")
        
        if score_long >= MIN_SCORE and score_long > score_short + 1.5:
            sl_dist = atr * (1.2 + atr_pct / 4)
            sl = precio - sl_dist
            tp = precio + sl_dist * Config.RR_RATIO
            
            if swing_low_15m and swing_low_15m < sl:
                sl = swing_low_15m * 0.9995
            
            logger.log(f"🎯 SEÑAL LONG {symbol}! Score:{score_long:.1f}, Entry:{precio:.2f}", "TRADE")
            return {
                'symbol': symbol, 'side': 'long', 'entry': precio, 'sl': sl, 'tp': tp,
                'atr': atr, 'atr_pct': atr_pct, 'score': score_long,
                'razones': razones_long, 'session': session_name,
                'timestamp': datetime.now(timezone.utc)
            }
        
        elif score_short >= MIN_SCORE and score_short > score_long + 1.5:
            sl_dist = atr * (1.2 + atr_pct / 4)
            sl = precio + sl_dist
            tp = precio - sl_dist * Config.RR_RATIO
            
            if swing_high_15m and swing_high_15m > sl:
                sl = swing_high_15m * 1.0005
            
            logger.log(f"🎯 SEÑAL SHORT {symbol}! Score:{score_short:.1f}, Entry:{precio:.2f}", "TRADE")
            return {
                'symbol': symbol, 'side': 'short', 'entry': precio, 'sl': sl, 'tp': tp,
                'atr': atr, 'atr_pct': atr_pct, 'score': score_short,
                'razones': razones_short, 'session': session_name,
                'timestamp': datetime.now(timezone.utc)
            }
        
        return None

# ============================================================================
# GESTIÓN DE POSICIONES (Tamaño)
# ============================================================================
def calcular_posicion_v8(equity: float, precio: float, sl: float, leverage: int, 
                         symbol_config: Dict) -> float:
    risk_pct = Config.RISK_PCT_DEFAULT
    riesgo_usd = equity * risk_pct
    distancia_sl = abs(precio - sl) / (precio + 1e-10)
    
    if distancia_sl < 0.001:
        distancia_sl = 0.015
    
    tamano_nominal = riesgo_usd / distancia_sl
    qty = tamano_nominal / precio
    
    min_size = symbol_config.get('min_size', 0.0001)
    if qty < min_size:
        qty = min_size
    
    max_exposure = (equity * 0.4 * leverage) / precio
    if qty > max_exposure:
        qty = max_exposure
    
    tick_size = symbol_config.get('tick_size', 0.01)
    qty = round(qty / tick_size) * tick_size
    
    return max(0, qty)

# ============================================================================
# ESTADÍSTICAS
# ============================================================================
def calculate_expectancy() -> float:
    stats = st.session_state.trade_stats
    if stats['wins'] + stats['losses'] == 0:
        return 0.0
    win_rate = stats['wins'] / (stats['wins'] + stats['losses'])
    return (win_rate * stats['avg_win']) - ((1 - win_rate) * stats['avg_loss'])

def get_profit_factor() -> float:
    stats = st.session_state.trade_stats
    if stats['avg_loss'] <= 0:
        return 999.0 if stats['wins'] > 0 else 0.0
    return stats['avg_win'] / stats['avg_loss']

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================
def main():
    init_session_state()
    
    logger = LogManager()
    signal_gen = SignalGeneratorV8()
    
    # Header
    st.markdown("""
    <div style="text-align:center;padding:20px">
        <h1>🎯 SNIPER V8.1 - PRICE ACTION ELITE</h1>
        <p style="color:#8899aa">VERSIÓN CORREGIDA | Debugging Activo | Filtros Relajados</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Info box
    st.markdown(f"""
    <div class="info-box">
        <b>✅ CAMBIOS V8.1:</b> 
        NewsFilter DESACTIVADO | VolatilityFilter DESACTIVADO | Score Base 4.0 | 
        Máx 3 posiciones | 10 trades/día | Debugging detallado en logs
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="warning-box">
        ⚠️ <b>ADVERTENCIA:</b> Versión de prueba con filtros relajados. 
        Monitorea el comportamiento antes de confiar plenamente.
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🔐 Configuración")
        
        api_key = st.text_input("API Key", type="password", key="apikey")
        api_secret = st.text_input("API Secret", type="password", key="apisecret")
        
        st.markdown("---")
        
        leverage_ui = st.slider("Apalancamiento", 2, 25, Config.LEVERAGE_DEFAULT)
        risk_pct_ui = st.slider("Riesgo por trade (%)", 0.5, 5.0, 1.0, 0.5)
        Config.RISK_PCT_DEFAULT = risk_pct_ui / 100
        
        modo = st.radio("Modo:", ["Solo Análisis (Paper)", "Trading Real"], index=0)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            activar = st.toggle("INICIAR", value=False)
        with col2:
            if st.button("🧹 Reset"):
                logger.clear_logs()
                st.session_state.trade_stats = {
                    'wins': 0, 'losses': 0, 'total_pnl': 0.0,
                    'avg_win': 0.0, 'avg_loss': 0.0, 'max_drawdown': 0.0,
                    'largest_win': 0.0, 'largest_loss': 0.0,
                    'consecutive_wins': 0, 'consecutive_losses': 0,
                    'max_consecutive_wins': 0, 'max_consecutive_losses': 0,
                    'total_trades': 0, 'profit_factor': 0.0
                }
                st.session_state.active_trades = {}
                st.session_state.daily_trades = 0
                st.session_state.daily_pnl = 0.0
                st.rerun()
        
        st.markdown("---")
        
        # Estado de filtros
        st.markdown("### 🚫 Estado de Filtros")
        
        news_blocked, news_reason = MarketFilters.check_prohibited_hours()
        st.markdown(f"**Noticias:** {'🔴 BLOQUEADO' if news_blocked else '🟢 DESACTIVADO'}")
        
        equity = get_equity()
        daily_ok, daily_reason = MarketFilters.check_daily_limits()
        st.markdown(f"**Límites:** {'🟢 OK' if daily_ok else '🔴 ' + daily_reason}")
        
        st.markdown(f"**Trades Hoy:** {st.session_state.daily_trades}/{Config.MAX_DAILY_TRADES}")
    
    # Layout principal
    col1, col2, col3 = st.columns([2, 2, 3])
    capital_ph = col1.empty()
    posicion_ph = col2.empty()
    senal_ph = col3.empty()
    
    log_ph = st.empty()
    stats_ph = st.empty()
    
    # Sistema activo
    if activar and api_key and api_secret:
        try:
            exchange = ccxt.krakenfutures({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {'defaultType': 'future'}
            })
            
            logger.log("=" * 50, "SYSTEM")
            logger.log("SNIPER V8.1 INICIADO - Debugging Activo", "SYSTEM")
            logger.log("=" * 50, "SYSTEM")
            
            # Obtener equity
            try:
                balance = exchange.fetch_balance()
                equity = safe_float(balance.get('total', {}).get('USD', 0))
                if equity == 0:
                    equity = safe_float(balance.get('free', {}).get('USD', 0))
                set_equity(equity)
                logger.log(f"Equity detectado: ${equity:.2f}", "SYSTEM")
            except Exception as e:
                equity = get_equity()
                logger.log(f"Error leyendo balance: {str(e)[:50]}", "ERROR")
            
            # Verificar filtros
            news_blocked, news_reason = MarketFilters.check_prohibited_hours()
            daily_ok, daily_reason = MarketFilters.check_daily_limits()
            
            logger.log(f"Estado filtros: News={news_blocked}, Daily={daily_ok}, Equity={equity:.2f}", "DEBUG")
            
            # Actualizar UI Capital
            stats = st.session_state.trade_stats
            win_rate = stats['wins'] / (stats['wins'] + stats['losses']) * 100 if (stats['wins'] + stats['losses']) > 0 else 0
            expectancy = calculate_expectancy()
            pf = get_profit_factor()
            
            capital_ph.markdown(f"""
            <div class="metric-card">
                <b>💰 Capital</b><br>
                <span style="font-size:1.8em;color:#4a9eff;font-weight:700">${equity:.4f} USD</span><br>
                <small style="color:#8899aa">
                    W:{stats['wins']} L:{stats['losses']} | WR:{win_rate:.1f}% | PnL:${stats['total_pnl']:+.4f}
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # Gestionar posiciones
            n_activas = 0
            try:
                posiciones = exchange.fetch_positions()
                n_activas = gestionar_posiciones_v8(posiciones, exchange, logger)
                logger.log(f"Posiciones activas gestionadas: {n_activas}", "DEBUG")
            except Exception as e:
                posiciones, n_activas = [], 0
                logger.log(f"Error fetch_positions: {str(e)[:60]}", "ERROR")
            
            # UI Posiciones
            pos_html = ""
            for p in posiciones:
                qty = safe_float(p.get('contracts', 0))
                if qty <= 0:
                    continue
                sym = p['symbol']
                side = p['side'].upper()
                mark = safe_float(p.get('markPrice'))
                entry = safe_float(p.get('entryPrice'))
                pnl = safe_float(p.get('unrealizedPnl'))
                
                trade = st.session_state.active_trades.get(sym, {})
                sl = trade.get('sl_current', entry * 0.985 if side == 'LONG' else entry * 1.015)
                tp = trade.get('tp_current', entry * 1.03 if side == 'LONG' else entry * 0.97)
                scale_done = "✓" if trade.get('scale_out_done', False) else "○"
                
                color = "#00ff88" if pnl >= 0 else "#ff4466"
                pos_html += f"""
                <div style="border-left:3px solid {color};padding:8px;margin:6px 0">
                    <b style="color:{color}">{sym.split('/')[0]} {side}</b> [Scale: {scale_done}]<br>
                    <small>Entry:{entry:.4f}|SL:{sl:.4f}|TP:{tp:.4f}|PnL:${pnl:+.4f}</small>
                </div>
                """
            
            posicion_ph.markdown(f"""
            <div class="metric-card">
                <b>📈 Posiciones ({n_activas}/{Config.MAX_POSITIONS})</b><br>
                {pos_html if pos_html else '<small style="color:#667799">Sin posiciones</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # Generar señales
            senales_encontradas = []
            current_time = time.time()
            
            # DEBUG: Mostrar estado de can_trade
            can_trade = daily_ok and not news_blocked and n_activas < Config.MAX_POSITIONS and modo == "Trading Real"
            
            logger.log(f"Can trade check: daily={daily_ok}, news={not news_blocked}, pos={n_activas < Config.MAX_POSITIONS}, modo={modo == 'Trading Real'}", "DEBUG")
            logger.log(f"Resultado can_trade: {can_trade}", "DEBUG")
            
            if not daily_ok:
                logger.log(f"Bloqueado - Daily limits: {daily_reason}", "FILTER")
            if news_blocked:
                logger.log(f"Bloqueado - News: {news_reason}", "FILTER")
            if n_activas >= Config.MAX_POSITIONS:
                logger.log(f"Bloqueado - Max posiciones: {n_activas}/{Config.MAX_POSITIONS}", "FILTER")
            if modo != "Trading Real":
                logger.log(f"Modo actual: {modo} (selecciona 'Trading Real' para operar)", "WARN")
            
            if can_trade:
                logger.log("✅ CONDICIONES OK - Buscando señales...", "SYSTEM")
                
                for symbol, config in Config.SYMBOLS.items():
                    last_sig = st.session_state.last_signal_time.get(symbol, 0)
                    time_since_last = current_time - last_sig
                    
                    if time_since_last < 60:
                        logger.log(f"{symbol}: Esperando {60 - int(time_since_last)}s (cooldown)", "DEBUG")
                        continue
                    
                    # Verificar correlación
                    corr_ok, corr_msg = MarketFilters.check_correlation(symbol, st.session_state.active_trades)
                    if not corr_ok:
                        logger.log(f"{symbol}: Bloqueado por correlación - {corr_msg}", "FILTER")
                        continue
                    
                    try:
                        logger.log(f"Descargando datos {symbol}...", "DEBUG")
                        
                        bars_15m = exchange.fetch_ohlcv(symbol, Config.TIMEFRAME_ENTRY, limit=Config.BARS_LIMIT)
                        bars_1h = exchange.fetch_ohlcv(symbol, Config.TIMEFRAME_TREND, limit=Config.BARS_LIMIT)
                        bars_4h = exchange.fetch_ohlcv(symbol, Config.TIMEFRAME_HIGH, limit=Config.BARS_LIMIT)
                        
                        logger.log(f"{symbol}: Datos descargados - 15m:{len(bars_15m)}, 1h:{len(bars_1h)}, 4h:{len(bars_4h)}", "DEBUG")
                        
                        if len(bars_15m) < 50:
                            logger.log(f"{symbol}: Datos 15m insuficientes", "WARN")
                            continue
                        
                        df_15m = pd.DataFrame(bars_15m, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        df_1h = pd.DataFrame(bars_1h, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        df_4h = pd.DataFrame(bars_4h, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        
                        senal = signal_gen.generar_senal_premium(df_15m, df_1h, df_4h, symbol, logger)
                        
                        if senal and equity > 10:
                            senales_encontradas.append(senal)
                            
                            qty = calcular_posicion_v8(equity, senal['entry'], senal['sl'], leverage_ui, config)
                            logger.log(f"{symbol}: Calculado tamaño {qty} (equity:${equity:.2f})", "DEBUG")
                            
                            if qty > 0:
                                try:
                                    side_order = 'buy' if senal['side'] == 'long' else 'sell'
                                    order = exchange.create_order(
                                        symbol=symbol, type='market', side=side_order, 
                                        amount=qty, params={'leverage': leverage_ui}
                                    )
                                    
                                    st.session_state.active_trades[symbol] = {
                                        'entry': senal['entry'],
                                        'sl_current': senal['sl'],
                                        'tp_current': senal['tp'],
                                        'trailing_active': False,
                                        'breakeven_reached': False,
                                        'entry_risk': abs(senal['entry'] - senal['sl']) / senal['entry'],
                                        'atr': senal['atr'],
                                        'side': senal['side'].upper(),
                                        'original_qty': qty,
                                        'current_qty': qty,
                                        'scale_out_done': False
                                    }
                                    
                                    st.session_state.last_signal_time[symbol] = current_time
                                    logger.log(f"✅ ORDEN EJECUTADA: {senal['side'].upper()} {symbol} @ {senal['entry']:.4f} | Qty:{qty}", "TRADE")
                                    st.session_state.daily_trades += 1
                                    n_activas += 1
                                    
                                    if n_activas >= Config.MAX_POSITIONS:
                                        logger.log("Máximo de posiciones alcanzado, deteniendo búsqueda", "SYSTEM")
                                        break
                                except Exception as e:
                                    logger.log(f"❌ Error ejecutando orden {symbol}: {str(e)[:80]}", "ERROR")
                            else:
                                logger.log(f"{symbol}: Tamaño calculado = 0, saltando", "WARN")
                        elif not senal:
                            logger.log(f"{symbol}: No se generó señal", "DEBUG")
                        elif equity <= 10:
                            logger.log(f"{symbol}: Equity insuficiente (${equity:.2f})", "WARN")
                    
                    except Exception as e:
                        logger.log(f"Error procesando {symbol}: {str(e)[:80]}", "ERROR")
                        import traceback
                        logger.log(traceback.format_exc()[:150], "ERROR")
            else:
                logger.log("⏸️ No se buscan señales - condiciones no cumplidas", "PAUSE")
            
            # UI Señales
            senales_html = ""
            for s in senales_encontradas:
                color = '#00ff88' if s['side'] == 'long' else '#ff4466'
                razones = " | ".join(s['razones'][:3])
                senales_html += f"""
                <div class="metric-card" style="margin:10px 0;padding:12px;border-left:4px solid {color}">
                    <span style="color:{color};font-weight:700">{s['side'].upper()} - {s['symbol'].split('/')[0]}</span><br>
                    <small>Entry:{s['entry']:.4f}|SL:{s['sl']:.4f}|TP:{s['tp']:.4f}|Score:{s['score']:.1f}<br>{razones}</small>
                </div>
                """
            
            senal_ph.markdown(f"""
            <div class="metric-card">
                <b>🎯 Señales ({len(senales_encontradas)} encontradas)</b><br>
                {senales_html if senales_html else '<small style="color:#667799">Escaneando mercado...</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # Logs
            log_html = "<br>".join([f'<div class="log-entry">{l}</div>' for l in logger.get_logs(30)])
            log_ph.markdown(f"""
            <div class="metric-card" style="max-height:300px;overflow-y:auto">
                {log_html if log_html else '<small style="color:#667799">Sin logs</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # Stats
            stats_ph.markdown(f"""
            <div class="metric-card" style="text-align:center">
                <small style="color:#8899aa">
                    <b>Profit Factor:</b> {pf:.2f} | 
                    <b>Expectancy:</b> ${expectancy:+.4f}/trade |
                    <b>Drawdown:</b> ${stats['max_drawdown']:+.4f} |
                    <b>Trades Hoy:</b> {st.session_state.daily_trades}/{Config.MAX_DAILY_TRADES}
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            logger.log(f"Ciclo completado. Próximo en {Config.RATE_LIMIT_DELAY}s", "DEBUG")
            time.sleep(Config.RATE_LIMIT_DELAY)
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error crítico: {e}")
            logger.log(f"ERROR CRÍTICO: {str(e)[:150]}", "ERROR")
            import traceback
            logger.log(traceback.format_exc()[:300], "ERROR")
            time.sleep(10)
            st.rerun()
    
    else:
        if not activar:
            st.info("👈 Ingresa credenciales, selecciona 'Trading Real' y activa el sistema")
        elif not api_key or not api_secret:
            st.error("❌ API Key y Secret requeridos")
        else:
            st.info("Sistema listo. Activa el toggle 'INICIAR' para comenzar.")

if __name__ == "__main__":
    main()