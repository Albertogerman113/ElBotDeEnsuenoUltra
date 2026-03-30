# ============================================================================
# SNIPER V10 - COMPOUND MODE (ULTIMATE MICRO-CAPITAL)
# ============================================================================
# Objetivo: $3.50 → $60 mediante compounding agresivo inteligente
# 
# MATEMÁTICA: Necesitas ~55 trades ganadores a 2:1 RR con 50% win rate
# para pasar de $3.50 a $60. Con compounding, cada win AMPLIFICA el siguiente.
#
# 3 FASES automáticas:
#   FASE 1 ($3.50-$10):  Supervivencia + semilla     → 10x lev, 4% riesgo
#   FASE 2 ($10-$30):    Crecimiento acelerado       → 7x lev, 3.5% riesgo  
#   FASE 3 ($30-$60):    Consolidación del objetivo  → 5x lev, 3% riesgo
#   META ALCANZADA ($60+): STOP automático
#
# Cambios vs V9.0:
#   - Auto-compounding: tamaño de posición escala con equity actual
#   - 3 fases con parámetros distintos según equity
#   - BTC-only en Fase 1 (menos slippage, más líquido)
#   - Stop automático al alcanzar meta
#   - Progress tracker visual con milestones
#   - Todos los bug fixes de V9 (no nested divs, session migration, fees)
#   - Señales más selectivas (solo setups A+)
# ============================================================================

import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import json
import math

# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================
st.set_page_config(
    page_title="SNIPER V10 | COMPOUND → $60",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# ESTILOS
# ============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
    
    .stApp { 
        background: linear-gradient(135deg, #0a0a1a 0%, #0d0d2b 50%, #0a0a1a 100%); 
        color: #e0e6f0;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .mc { 
        background: linear-gradient(135deg, #1a1a3a 0%, #0f0f25 100%);
        border: 1px solid #3a3a7a; 
        border-radius: 12px; 
        padding: 16px; 
        margin: 8px 0;
        box-shadow: 0 4px 15px rgba(100, 100, 255, 0.08);
    }
    
    .mc-gold {
        background: linear-gradient(135deg, #2a2a1a 0%, #1a1a0f 100%);
        border: 1px solid #ffaa00; 
        border-radius: 12px; 
        padding: 16px; 
        margin: 8px 0;
        box-shadow: 0 4px 20px rgba(255, 170, 0, 0.15);
    }
    
    h1 { color: #ffaa00 !important; text-shadow: 0 0 20px rgba(255,170,0,0.3); }
    h2, h3 { color: #8888cc !important; }
    
    .phase-1 { color: #ff4466; }
    .phase-2 { color: #ffaa00; }
    .phase-3 { color: #00ff88; }
    .phase-done { color: #00ffff; }
    
    .progress-bar-bg {
        background: #1a1a3a;
        border-radius: 10px;
        height: 28px;
        border: 1px solid #3a3a7a;
        overflow: hidden;
        position: relative;
    }
    
    .progress-bar-fill {
        height: 100%;
        border-radius: 10px;
        transition: width 0.5s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75em;
        font-weight: 700;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #ffaa00 0%, #cc8800 100%);
        color: #000;
        border: none;
        border-radius: 8px;
        font-weight: 700;
    }
    
    .warning-box {
        background: linear-gradient(135deg, #2a1a1a 0%, #1a0f0f 100%);
        border: 1px solid #ff4466;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# FASES DE COMPOUNDING
# ============================================================================
class CompoundPhases:
    """
    3 fases automáticas basadas en equity actual.
    Cada fase tiene parámetros optimizados para ese rango de capital.
    """
    TARGET = 60.0
    
    PHASES = {
        1: {
            'name': 'SEMILLA',
            'emoji': '🌱',
            'equity_min': 0,
            'equity_max': 10,
            'color': '#ff4466',
            'leverage': 10,
            'risk_pct': 0.04,        # 4% por trade
            'rr_ratio': 2.0,         # 2:1 (más alcanzable)
            'max_positions': 1,      # 1 sola posición (enfoque total)
            'max_daily_trades': 6,
            'max_daily_loss_pct': 0.20,   # 20%
            'max_consecutive_losses': 4,
            'symbols': ['BTC/USD:USD'],   # Solo BTC (más líquido)
            'exposure_pct': 0.80,         # 80% exposición
            'min_score': 4.5,             # Umbral más bajo = más oportunidades
            'adx_min': 18,                # Más permisivo
            'description': 'Supervivencia + primera semilla. Solo BTC, máximo enfoque.'
        },
        2: {
            'name': 'CRECIMIENTO',
            'emoji': '🚀',
            'equity_min': 10,
            'equity_max': 30,
            'color': '#ffaa00',
            'leverage': 7,
            'risk_pct': 0.035,       # 3.5%
            'rr_ratio': 2.5,
            'max_positions': 2,
            'max_daily_trades': 8,
            'max_daily_loss_pct': 0.15,
            'max_consecutive_losses': 5,
            'symbols': ['BTC/USD:USD', 'ETH/USD:USD'],
            'exposure_pct': 0.70,
            'min_score': 5.0,
            'adx_min': 20,
            'description': 'Crecimiento acelerado. Agregar ETH para más oportunidades.'
        },
        3: {
            'name': 'CONSOLIDACIÓN',
            'emoji': '💎',
            'equity_min': 30,
            'equity_max': 60,
            'color': '#00ff88',
            'leverage': 5,
            'risk_pct': 0.03,        # 3%
            'rr_ratio': 2.5,
            'max_positions': 2,
            'max_daily_trades': 8,
            'max_daily_loss_pct': 0.12,
            'max_consecutive_losses': 5,
            'symbols': ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD'],
            'exposure_pct': 0.60,
            'min_score': 5.0,
            'adx_min': 20,
            'description': 'Consolidar ganancias hacia meta. Proteger capital.'
        }
    }
    
    @staticmethod
    def get_current_phase(equity: float) -> int:
        if equity >= CompoundPhases.TARGET:
            return 0  # META
        if equity >= 30:
            return 3
        if equity >= 10:
            return 2
        return 1
    
    @staticmethod
    def get_phase_config(equity: float) -> Dict:
        phase = CompoundPhases.get_current_phase(equity)
        if phase == 0:
            return {'name': 'META', 'emoji': '🏆', 'color': '#00ffff', 
                    'leverage': 0, 'risk_pct': 0, 'max_positions': 0,
                    'symbols': [], 'description': '¡OBJETIVO ALCANZADO! Bot detenido.'}
        return CompoundPhases.PHASES[phase]


# ============================================================================
# CONFIGURACIÓN DE SÍMBOLOS
# ============================================================================
SYMBOLS_CONFIG = {
    'BTC/USD:USD': {'min_size': 0.00001, 'tick_size': 0.5, 'correlation_group': 'major'},
    'ETH/USD:USD': {'min_size': 0.0001, 'tick_size': 0.05, 'correlation_group': 'major'},
    'SOL/USD:USD': {'min_size': 0.001, 'tick_size': 0.001, 'correlation_group': 'alt'}
}

# ============================================================================
# INICIALIZACIÓN DE SESSION STATE (con migración)
# ============================================================================
def init_session_state():
    defaults = {
        'trade_log': [],
        'trade_stats': {
            'wins': 0, 'losses': 0, 'total_pnl': 0.0,
            'total_fees_paid': 0.0, 'net_pnl': 0.0,
            'avg_win': 0.0, 'avg_loss': 0.0, 'max_drawdown': 0.0,
            'largest_win': 0.0, 'largest_loss': 0.0,
            'consecutive_wins': 0, 'consecutive_losses': 0,
            'max_consecutive_wins': 0, 'max_consecutive_losses': 0,
            'total_trades': 0, 'profit_factor': 0.0,
            'peak_equity': 0.0,           # NUEVO: para calc drawdown
            'starting_equity': 0.0,       # NUEVO: equity al inicio
        },
        'active_trades': {},
        'last_signal_time': {},
        'last_signal_candle': {},
        'daily_trades': 0,
        'daily_pnl': 0.0,
        'weekly_pnl': 0.0,
        'last_reset_date': datetime.now().strftime('%Y-%m-%d'),
        'last_week_reset': datetime.now().strftime('%Y-%W'),
        'equity_cache': 0.0,
        'loop_count': 0,
    }
    
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default
        elif isinstance(default, dict) and isinstance(st.session_state[key], dict):
            for sub_key, sub_default in default.items():
                if sub_key not in st.session_state[key]:
                    st.session_state[key][sub_key] = sub_default


# ============================================================================
# GESTOR DE LOGS
# ============================================================================
class LogManager:
    def __init__(self, max_entries=500):
        self.max_entries = max_entries
    
    def log(self, msg: str, level: str = "INFO"):
        now = datetime.now().strftime("%H:%M:%S")
        icons = {
            "INFO": "📊", "TRADE": "🎯", "WIN": "💰", "LOSS": "❌",
            "WARN": "⚡", "ERROR": "💀", "SYSTEM": "⚙️", "RISK": "🛡️",
            "PHASE": "🔄", "COMPOUND": "📈", "MILESTONE": "🏆", "DEBUG": "🔍"
        }
        icon = icons.get(level, "•")
        entry = f"[{now}] {icon} [{level}] {msg}"
        if 'trade_log' not in st.session_state:
            st.session_state.trade_log = []
        st.session_state.trade_log.insert(0, entry)
        st.session_state.trade_log = st.session_state.trade_log[:self.max_entries]
    
    def get_logs(self, limit=40):
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

def get_equity() -> float:
    return st.session_state.get('equity_cache', 0.0)

def set_equity(value: float):
    old = st.session_state.get('equity_cache', 0.0)
    st.session_state.equity_cache = value
    # Track peak equity
    stats = st.session_state.trade_stats
    if value > stats.get('peak_equity', 0):
        stats['peak_equity'] = value
    if stats.get('starting_equity', 0) == 0 and value > 0:
        stats['starting_equity'] = value

def estimate_fees(notional: float) -> float:
    return notional * 0.001  # 0.1% round trip Kraken Futures

def candle_timestamp(tf='15m') -> int:
    now = datetime.now(timezone.utc)
    tf_sec = {'1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400}
    epoch = int(now.timestamp())
    return (epoch // tf_sec.get(tf, 900)) * epoch // 1

def check_cooldown(symbol: str) -> bool:
    tf_sec = {'1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400}
    current = candle_timestamp('15m')
    last = st.session_state.last_signal_candle.get(symbol, 0)
    return (current - last) >= (900 * 2)  # 2 velas de 15m

def get_progress(equity: float) -> float:
    """Progreso de $3.50 a $60 en porcentaje."""
    return max(0, min(100, (equity - 3.5) / (60 - 3.5) * 100))

def get_progress_color(pct: float) -> str:
    if pct < 15: return '#ff4466'
    if pct < 45: return '#ffaa00'
    if pct < 90: return '#00ff88'
    return '#00ffff'

def get_phase_progress(equity: float, phase: int) -> float:
    if phase == 0: return 100
    cfg = CompoundPhases.PHASES[phase]
    return max(0, min(100, (equity - cfg['equity_min']) / (cfg['equity_max'] - cfg['equity_min']) * 100))


# ============================================================================
# FILTROS
# ============================================================================
def check_daily_limits(phase_cfg: Dict) -> Tuple[bool, str]:
    today = datetime.now().strftime('%Y-%m-%d')
    if st.session_state.get('last_reset_date') != today:
        st.session_state.daily_trades = 0
        st.session_state.daily_pnl = 0.0
        st.session_state.last_reset_date = today
    
    current_week = datetime.now().strftime('%Y-%W')
    if st.session_state.get('last_week_reset') != current_week:
        st.session_state.weekly_pnl = 0.0
        st.session_state.last_week_reset = current_week
    
    if st.session_state.daily_trades >= phase_cfg['max_daily_trades']:
        return False, f"Límite diario ({phase_cfg['max_daily_trades']})"
    
    equity = get_equity()
    if equity > 0 and st.session_state.daily_pnl < -equity * phase_cfg['max_daily_loss_pct']:
        return False, f"Pérdida diaria {phase_cfg['max_daily_loss_pct']*100:.0f}%"
    
    stats = st.session_state.trade_stats
    if stats['consecutive_losses'] >= phase_cfg['max_consecutive_losses']:
        return False, f"{phase_cfg['max_consecutive_losses']} losses seguidas - PAUSA"
    
    return True, "OK"


# ============================================================================
# INDICADORES TÉCNICOS
# ============================================================================
class Indicators:
    @staticmethod
    def calc_all(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        c, h, l, o, v = (df[x].astype(float) for x in ['c','h','l','o','v'])
        
        for span in [9, 20, 50, 100, 200]:
            df[f'ema{span}'] = c.ewm(span=span, adjust=False).mean()
        
        tr = pd.concat([h-l, abs(h-c.shift(1)), abs(l-c.shift(1))], axis=1).max(axis=1)
        df['tr'] = tr
        df['atr'] = tr.rolling(14).mean()
        df['atr_pct'] = (df['atr'] / c * 100).fillna(0)
        
        delta = c.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = (100 - (100 / (1 + rs))).fillna(50)
        
        df['vol_ma'] = v.rolling(20).mean()
        df['vol_ratio'] = (v / df['vol_ma']).fillna(1)
        df['body'] = abs(c - o)
        df['wick_up'] = h - pd.concat([c, o], axis=1).max(axis=1)
        df['wick_dn'] = pd.concat([c, o], axis=1).min(axis=1) - l
        
        # ADX
        plus_dm = h.diff().where((h.diff() > (-l.diff())) & (h.diff() > 0), 0)
        minus_dm = (-l.diff()).where(((-l.diff()) > h.diff()) & ((-l.diff()) > 0), 0)
        atr_s = tr.ewm(alpha=1/14, adjust=False).mean()
        df['plus_di'] = (100 * plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_s).fillna(0)
        df['minus_di'] = (100 * minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_s).fillna(0)
        dx = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di']).replace(0, np.nan)
        df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean().fillna(0)
        
        df['hlc3'] = (h + l + c) / 3
        df['vwap_approx'] = (df['hlc3'] * v).cumsum() / v.cumsum()
        
        return df
    
    @staticmethod
    def detect_mss(df: pd.DataFrame) -> Tuple[str, Optional[float], Optional[float]]:
        if len(df) < 35: return 'neutral', None, None
        highs, lows = df['h'].astype(float).values, df['l'].astype(float).values
        c = df['c'].astype(float).values
        w = 5
        sh, sl = [], []
        for i in range(w, len(df)-1):
            ls, le = max(0, i-w), min(len(highs), i+w+1)
            if highs[i] >= max(highs[ls:le]): sh.append((i, highs[i]))
            if lows[i] <= min(lows[ls:le]): sl.append((i, lows[i]))
        if len(sh) < 3 or len(sl) < 3: return 'neutral', None, None
        lhh, phh = sh[-1][1], sh[-2][1]
        lll, pll = sl[-1][1], sl[-2][1]
        if sh[-1][0] < len(df)-20 or sl[-1][0] < len(df)-20: return 'neutral', lll, lhh
        if lhh > phh and lll > pll:
            return ('bullish_mss' if c[-1] > lhh else 'bullish'), lll, lhh
        if lhh < phh and lll < pll:
            return ('bearish_mss' if c[-1] < lll else 'bearish'), lll, lhh
        return 'neutral', lll, lhh
    
    @staticmethod
    def detect_ob(df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
        obs_bull, obs_bear = [], []
        c, o, v = df['c'].astype(float).values, df['o'].astype(float).values, df['v'].astype(float).values
        vol_ma = v.rolling(20).mean().values
        price = c[-1]
        for i in range(5, len(df)-7):
            va = vol_ma[i] if not np.isnan(vol_ma[i]) else v[i]
            if o[i] > c[i]:
                mu = (c[i+5]-o[i])/(o[i]+1e-10)*100
                if mu > 1.5 and v[i]/(va+1e-10) > 1.1 and abs(price-(o[i]+c[i])/2)/price*100 < 2:
                    obs_bull.append({'mid':(o[i]+c[i])/2, 'top':o[i], 'bot':c[i], 'str':mu*v[i]/(va+1e-10)})
            if c[i] > o[i]:
                md = (o[i]-c[i+5])/(o[i]+1e-10)*100
                if md > 1.5 and v[i]/(va+1e-10) > 1.1 and abs(price-(c[i]+o[i])/2)/price*100 < 2:
                    obs_bear.append({'mid':(c[i]+o[i])/2, 'top':c[i], 'bot':o[i], 'str':md*v[i]/(va+1e-10)})
        obs_bull.sort(key=lambda x: abs(price-x['mid']))
        obs_bear.sort(key=lambda x: abs(price-x['mid']))
        return obs_bull[:3], obs_bear[:3]
    
    @staticmethod
    def detect_fvg(df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
        fvgs_b, fvgs_s = [], []
        h, l = df['h'].astype(float).values, df['l'].astype(float).values
        for i in range(1, len(df)-1):
            if l[i+1] > h[i-1]:
                g = (l[i+1]-h[i-1])/(h[i-1]+1e-10)
                if g >= 0.004:
                    filled = any(lw < h[i-1] for lw in l[i+2:]) if i+2 < len(l) else False
                    if not filled: fvgs_b.append({'bot':h[i-1], 'top':l[i+1], 'gap':g})
            if h[i+1] < l[i-1]:
                g = (l[i-1]-h[i+1])/(l[i-1]+1e-10)
                if g >= 0.004:
                    filled = any(hh > l[i-1] for hh in h[i+2:]) if i+2 < len(h) else False
                    if not filled: fvgs_s.append({'bot':h[i+1], 'top':l[i-1], 'gap':g})
        return fvgs_b[-3:], fvgs_s[-3:]
    
    @staticmethod
    def detect_candles(df: pd.DataFrame) -> Dict:
        p = {'pin': None, 'engulfing': None}
        if len(df) < 2: return p
        last, prev = df.iloc[-1], df.iloc[-2]
        body = abs(float(last['c'])-float(last['o']))
        rng = float(last['h'])-float(last['l'])
        if rng > 1e-10:
            wu = float(last['h'])-max(float(last['c']),float(last['o']))
            wd = min(float(last['c']),float(last['o']))-float(last['l'])
            if wd > rng*0.6 and body/rng < 0.25: p['pin'] = 'bull_pin'
            elif wu > rng*0.6 and body/rng < 0.25: p['pin'] = 'bear_pin'
        cb, pb = float(last['c'])-float(last['o']), float(prev['c'])-float(prev['o'])
        cv, va = float(last['v']), float(df['v'].iloc[-20:].mean()) if len(df)>=20 else float(prev['v'])
        if pb<0 and cb>0 and float(last['o'])<=float(prev['c']) and float(last['c'])>=float(prev['o']) and cv>va*1.1:
            p['engulfing'] = 'bull_engulfing'
        elif pb>0 and cb<0 and float(last['o'])>=float(prev['c']) and float(last['c'])<=float(prev['o']) and cv>va*1.1:
            p['engulfing'] = 'bear_engulfing'
        return p


# ============================================================================
# GENERADOR DE SEÑALES
# ============================================================================
def generate_signal(df_15m: pd.DataFrame, df_1h: pd.DataFrame, df_4h: pd.DataFrame,
                    symbol: str, logger: LogManager, phase_cfg: Dict) -> Optional[Dict]:
    if len(df_15m) < 60 or len(df_1h) < 60: return None
    
    d15 = Indicators.calc_all(df_15m)
    d1h = Indicators.calc_all(df_1h)
    d4h = Indicators.calc_all(df_4h)
    
    la = d15.iloc[-1]
    price = float(la['c'])
    atr = float(la['atr'])
    atr_pct = float(la['atr_pct'])
    rsi = float(la['rsi'])
    vol_r = float(la['vol_ratio'])
    adx = float(la['adx'])
    pdi = float(la['plus_di'])
    mdi = float(la['minus_di'])
    
    # Tendencias
    t15 = 'bull' if price > float(la['ema50']) else 'bear'
    l1h = d1h.iloc[-1]
    t1h = 'bull' if float(l1h['ema50']) > float(l1h['ema200']) else 'bear' if float(l1h['ema50']) < float(l1h['ema200']) else 'neutral'
    l4h = d4h.iloc[-1]
    t4h = 'bull' if float(l4h['ema50']) > float(l4h['ema200']) else 'bear' if float(l4h['ema50']) < float(l4h['ema200']) else 'neutral'
    
    # Alineación
    align = 0
    if t4h=='bull' and t1h=='bull' and t15=='bull': align=3
    elif t4h=='bear' and t1h=='bear' and t15=='bear': align=-3
    elif t1h=='bull' and t15=='bull': align=2
    elif t1h=='bear' and t15=='bear': align=-2
    elif t15=='bull': align=1
    elif t15=='bear': align=-1
    
    struct, sw_lo, sw_hi = Indicators.detect_mss(d15)
    ob_b, ob_s = Indicators.detect_ob(d15)
    fvg_b, fvg_s = Indicators.detect_fvg(d15)
    pats = Indicators.detect_candles(d15)
    vwap = float(la.get('vwap_approx', price))
    
    # Filtro ADX
    if adx < phase_cfg['adx_min']:
        return None
    
    # ====== SCORING ======
    sL, sS, rL, rS = 0.0, 0.0, [], []
    
    # Tendencia multi-TF (0-6)
    if align==3: sL+=6; rL.append("Triple bull")
    elif align==2: sL+=4; rL.append("1H+15M bull")
    elif align==1: sL+=2; rL.append("15M bull")
    if align==-3: sS+=6; rS.append("Triple bear")
    elif align==-2: sS+=4; rS.append("1H+15M bear")
    elif align==-1: sS+=2; rS.append("15M bear")
    
    # Estructura (0-3)
    if struct in ['bullish_mss']: sL+=3; rL.append("MSS bull")
    elif struct=='bullish': sL+=2; rL.append("Struct bull")
    if struct in ['bearish_mss']: sS+=3; rS.append("MSS bear")
    elif struct=='bearish': sS+=2; rS.append("Struct bear")
    
    # OB (0-2)
    for ob in ob_b:
        if ob['bot']<=price<=ob['top']: sL+=2; rL.append("OB bull"); break
    for ob in ob_s:
        if ob['bot']<=price<=ob['top']: sS+=2; rS.append("OB bear"); break
    
    # FVG (0-2)
    for f in fvg_b:
        if f['bot']<=price<=f['top']: sL+=2; rL.append("FVG bull"); break
    for f in fvg_s:
        if f['bot']<=price<=f['top']: sS+=2; rS.append("FVG bear"); break
    
    # Patrones (0-2.5)
    if pats['engulfing']=='bull_engulfing': sL+=2.5; rL.append("Engulf bull")
    elif pats['pin']=='bull_pin': sL+=2; rL.append("Pin bull")
    if pats['engulfing']=='bear_engulfing': sS+=2.5; rS.append("Engulf bear")
    elif pats['pin']=='bear_pin': sS+=2; rS.append("Pin bear")
    
    # RSI (0-2 + penalización)
    if 35<rsi<55: sL+=2; rL.append(f"RSI {rsi:.0f}")
    elif 25<rsi<=35: sL+=1.5; rL.append(f"RSI {rsi:.0f} OS")
    if 45<rsi<65: sS+=2; rS.append(f"RSI {rsi:.0f}")
    elif 65<=rsi<75: sS+=1.5; rS.append(f"RSI {rsi:.0f} OB")
    if rsi>=75: sL-=1
    if rsi<=25: sS-=1
    
    # Volumen (0-1.5)
    if vol_r>1.5: sL+=1.5; sS+=1.5; rL.append(f"Vol {vol_r:.1f}x"); rS.append(f"Vol {vol_r:.1f}x")
    elif vol_r>1.2: sL+=1; sS+=1
    
    # VWAP (0-1)
    if price>vwap: sL+=1; rL.append("VWAP+")
    else: sS+=1; rS.append("VWAP-")
    
    # DI (0-1)
    if pdi>mdi*1.2: sL+=1; rL.append("DI+>DI-")
    elif mdi>pdi*1.2: sS+=1; rS.append("DI->DI+")
    
    # Contra tendencia 4H
    if t4h=='bull' and align<0: sS-=2
    if t4h=='bear' and align>0: sL-=2
    
    sL, sS = max(0, sL), max(0, sS)
    MIN_SCORE = phase_cfg['min_score']
    if adx>30: MIN_SCORE = max(3.0, MIN_SCORE-0.5)
    
    logger.log(f"{symbol}: L={sL:.1f} S={sS:.1f} Min={MIN_SCORE:.1f} ADX={adx:.0f}", "DEBUG")
    
    rr = phase_cfg['rr_ratio']
    
    if sL >= MIN_SCORE and sL > sS + 1.0:
        sl_d = atr * 1.5
        sl = price - sl_d
        if sw_lo and sw_lo < sl and sw_lo > price*0.95: sl = sw_lo*0.999
        if (price-sl)/price < 0.008: sl = price*0.992
        tp = price + (price-sl)*rr
        return {'symbol':symbol,'side':'long','entry':price,'sl':sl,'tp':tp,
                'atr':atr,'atr_pct':atr_pct,'score':sL,'razones':rL,
                'adx':adx,'rsi':rsi,'timestamp':datetime.now(timezone.utc)}
    
    if sS >= MIN_SCORE and sS > sL + 1.0:
        sl_d = atr * 1.5
        sl = price + sl_d
        if sw_hi and sw_hi > sl and sw_hi < price*1.05: sl = sw_hi*1.001
        if (sl-price)/price < 0.008: sl = price*1.008
        tp = price - (sl-price)*rr
        return {'symbol':symbol,'side':'short','entry':price,'sl':sl,'tp':tp,
                'atr':atr,'atr_pct':atr_pct,'score':sS,'razones':rS,
                'adx':adx,'rsi':rsi,'timestamp':datetime.now(timezone.utc)}
    
    return None


# ============================================================================
# CÁLCULO DE POSICIÓN (COMPOUND)
# ============================================================================
def calc_position(equity: float, price: float, sl: float, leverage: int,
                  sym_cfg: Dict, phase_cfg: Dict, logger: LogManager) -> float:
    if equity <= 0 or price <= 0: return 0.0
    
    risk_usd = equity * phase_cfg['risk_pct']
    if risk_usd < 0.03: risk_usd = equity * 0.025  # Mínimo 2.5%
    
    dist_sl = abs(price - sl) / price
    if dist_sl < 0.005: dist_sl = 0.008
    
    # Incluir fees en cálculo de riesgo
    denom = dist_sl + 0.001  # 0.1% fee round trip
    notional = risk_usd / denom
    qty = notional / price
    
    min_size = sym_cfg.get('min_size', 0.0001)
    
    if qty < min_size:
        margin_req = (min_size * price) / leverage
        max_margin = equity * phase_cfg['exposure_pct']
        if margin_req <= max_margin:
            qty = min_size
            logger.log(f"Min size: {min_size} (margin ${margin_req:.4f})", "WARN")
        else:
            return 0
    
    # Exposición máxima de la fase
    max_notional = (equity * phase_cfg['exposure_pct']) * leverage
    max_qty = max_notional / price
    if qty > max_qty: qty = max_qty
    
    tick = sym_cfg.get('tick_size', 0.01)
    if tick > 0: qty = round(qty / tick) * tick
    
    # Verificar margen final
    margin = (qty * price) / leverage
    if margin > equity * phase_cfg['exposure_pct']:
        qty = (equity * phase_cfg['exposure_pct'] * leverage) / price
        qty = round(qty / tick) * tick
    
    qty = max(0, qty)
    if qty > 0:
        logger.log(f"Pos: {qty} | Margin ${(qty*price)/leverage:.4f} | Risk ${risk_usd:.4f}", "DEBUG")
    return qty


# ============================================================================
# GESTIÓN DE POSICIONES
# ============================================================================
def manage_positions(positions: List[Dict], exchange, logger: LogManager, 
                     phase_cfg: Dict) -> int:
    n = 0
    for p in positions:
        qty = safe_float(p.get('contracts', 0))
        if qty <= 0: continue
        n += 1
        sym = p['symbol']
        side = p['side'].upper()
        mark = safe_float(p.get('markPrice'))
        pnl = safe_float(p.get('unrealizedPnl'))
        entry = safe_float(p.get('entryPrice'))
        
        if sym not in st.session_state.active_trades:
            est_atr = abs(mark-entry)*0.5 if entry>0 and mark>0 else entry*0.01
            sl_d = est_atr * 1.5
            sl = entry - sl_d if side=='LONG' else entry + sl_d
            tp_d = sl_d * phase_cfg['rr_ratio']
            tp = entry + tp_d if side=='LONG' else entry - tp_d
            
            st.session_state.active_trades[sym] = {
                'entry': entry, 'sl_current': sl, 'tp_current': tp,
                'trailing_active': False, 'breakeven_reached': False,
                'entry_risk': abs(entry-sl)/entry if entry>0 else 0.015,
                'side': side, 'original_qty': qty, 'current_qty': qty,
                'highest': mark, 'lowest': mark, 'mfe': 0.0,
                'opened_at': datetime.now(timezone.utc)
            }
            logger.log(f"Tracking: {sym} {side} @ {entry:.2f}", "SYSTEM")
        
        tr = st.session_state.active_trades[sym]
        if side=='LONG':
            tr['highest'] = max(tr['highest'], mark)
            tr['mfe'] = max(tr['mfe'], (mark-entry)/entry)
        else:
            tr['lowest'] = min(tr['lowest'], mark)
            tr['mfe'] = max(tr['mfe'], (entry-mark)/entry)
        
        close_s = 'sell' if side=='LONG' else 'buy'
        is_tp = (side=='LONG' and mark>=tr['tp_current']) or (side=='SHORT' and mark<=tr['tp_current'])
        is_sl = (side=='LONG' and mark<=tr['sl_current']) or (side=='SHORT' and mark>=tr['sl_current'])
        
        if is_tp or is_sl:
            try:
                exchange.create_order(symbol=sym, type='market', side=close_s,
                                     amount=tr['current_qty'], params={'reduceOnly': True})
                
                notional = tr['current_qty'] * entry
                fees = estimate_fees(notional)
                net = pnl - fees
                
                stats = st.session_state.trade_stats
                stats['total_pnl'] += pnl
                stats['total_fees_paid'] += fees
                stats['net_pnl'] += net
                stats['total_trades'] += 1
                
                dur = (datetime.now(timezone.utc) - tr.get('opened_at', datetime.now(timezone.utc))).total_seconds()/60
                
                if is_tp:
                    stats['wins'] += 1; w=stats['wins']
                    stats['avg_win'] = (stats['avg_win']*(w-1)+net)/w if w>0 else net
                    stats['largest_win'] = max(stats['largest_win'], net)
                    stats['consecutive_wins'] += 1; stats['consecutive_losses'] = 0
                    stats['max_consecutive_wins'] = max(stats['max_consecutive_wins'], stats['consecutive_wins'])
                    logger.log(f"✅ TP: {sym} | Net ${net:+.4f} | Fees ${fees:.4f} | {dur:.0f}m", "WIN")
                else:
                    stats['losses'] += 1; lc=stats['losses']
                    stats['avg_loss'] = (stats['avg_loss']*(lc-1)+abs(net))/lc if lc>0 else abs(net)
                    stats['largest_loss'] = max(stats['largest_loss'], abs(net))
                    stats['consecutive_losses'] += 1; stats['consecutive_wins'] = 0
                    stats['max_consecutive_losses'] = max(stats['max_consecutive_losses'], stats['consecutive_losses'])
                    logger.log(f"❌ SL: {sym} | Net ${net:+.4f} | MFE {tr['mfe']*100:.1f}%", "LOSS")
                
                if stats.get('net_pnl', 0) < stats.get('max_drawdown', 0):
                    stats['max_drawdown'] = stats.get('net_pnl', 0)
                
                st.session_state.daily_pnl += net
                st.session_state.weekly_pnl += net
                
                if stats['avg_loss'] > 0: stats['profit_factor'] = stats['avg_win'] / stats['avg_loss']
                else: stats['profit_factor'] = 999.0 if stats['wins'] > 0 else 0.0
                
                del st.session_state.active_trades[sym]
            except Exception as e:
                logger.log(f"Error closing {sym}: {str(e)[:60]}", "ERROR")
            continue
        
        # Trailing (breakeven tardío)
        if tr['entry_risk'] > 0:
            rm = abs(mark - entry) / tr['entry_risk']
            if not tr['breakeven_reached'] and rm >= 1.2:
                tr['sl_current'] = entry * (1.001 if side=='LONG' else 0.999)
                tr['breakeven_reached'] = True
                logger.log(f"{sym}: BE @ {rm:.1f}R", "RISK")
            elif tr['breakeven_reached'] and not tr['trailing_active'] and rm >= 1.5:
                tr['trailing_active'] = True
                tr['trail_start'] = mark
                logger.log(f"{sym}: Trail @ {rm:.1f}R", "RISK")
            elif tr.get('trailing_active'):
                atr_t = tr.get('atr', tr['entry_risk']*entry)
                td = atr_t * 0.5
                if side=='LONG':
                    if mark > tr.get('trail_start', mark): tr['trail_start'] = mark
                    tr['sl_current'] = max(tr['sl_current'], mark - td)
                else:
                    if mark < tr.get('trail_start', mark): tr['trail_start'] = mark
                    tr['sl_current'] = min(tr['sl_current'], mark + td)
    
    return n


# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================
def main():
    init_session_state()
    logger = LogManager()
    
    # Header
    st.markdown("""
    <div style="text-align:center;padding:15px">
        <h1>💎 SNIPER V10 | COMPOUND MODE</h1>
        <p style="color:#ffaa00;font-size:1.1em">$3.50 → $60 | Auto-Scaling por Fases</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🔐 Conexión")
        api_key = st.text_input("API Key", type="password", key="apikey")
        api_secret = st.text_input("API Secret", type="password", key="apisecret")
        
        st.markdown("---")
        st.markdown("### 🎯 Objetivo")
        target = st.number_input("Meta ($)", value=60.0, min_value=10.0, max_value=1000.0, step=10.0)
        CompoundPhases.TARGET = target
        
        st.markdown("---")
        modo = st.radio("Modo:", ["Solo Análisis (Paper)", "Trading Real"], index=1)
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            activar = st.toggle("INICIAR", value=False)
        with col2:
            if st.button("🧹 Reset"):
                logger.clear_logs()
                st.session_state.trade_stats = {
                    'wins': 0, 'losses': 0, 'total_pnl': 0.0,
                    'total_fees_paid': 0.0, 'net_pnl': 0.0,
                    'avg_win': 0.0, 'avg_loss': 0.0, 'max_drawdown': 0.0,
                    'largest_win': 0.0, 'largest_loss': 0.0,
                    'consecutive_wins': 0, 'consecutive_losses': 0,
                    'max_consecutive_wins': 0, 'max_consecutive_losses': 0,
                    'total_trades': 0, 'profit_factor': 0.0,
                    'peak_equity': 0.0, 'starting_equity': 0.0
                }
                st.session_state.active_trades = {}
                st.session_state.daily_trades = 0
                st.session_state.daily_pnl = 0.0
                st.session_state.weekly_pnl = 0.0
                st.session_state.last_signal_candle = {}
                st.rerun()
        
        # Estado en sidebar
        st.markdown("---")
        equity = get_equity()
        phase = CompoundPhases.get_current_phase(equity)
        pcfg = CompoundPhases.get_phase_config(equity)
        
        st.markdown(f"**Fase:** {pcfg.get('emoji','')} {pcfg.get('name','N/A')}")
        st.markdown(f"**Equity:** ${equity:.4f}")
        st.markdown(f"**Trades:** {st.session_state.daily_trades}/{pcfg.get('max_daily_trades',0)}")
        st.markdown(f"**Neto:** ${st.session_state.trade_stats.get('net_pnl',0):+.4f}")
        st.markdown(f"**Fees:** ${st.session_state.trade_stats.get('total_fees_paid',0):.4f}")
        
        if st.session_state.trade_stats.get('consecutive_losses', 0) >= 3:
            st.markdown(f"⚠️ **{st.session_state.trade_stats['consecutive_losses']} losses seguidos**")
    
    # Layout
    col_top1, col_top2 = st.columns([3, 2])
    progress_ph = col_top1.empty()
    phase_ph = col_top2.empty()
    
    col_mid1, col_mid2, col_mid3 = st.columns([2, 2, 3])
    capital_ph = col_mid1.empty()
    posicion_ph = col_mid2.empty()
    senal_ph = col_mid3.empty()
    
    log_ph = st.empty()
    stats_ph = st.empty()
    
    # ============================================================
    # SISTEMA ACTIVO
    # ============================================================
    if activar and api_key and api_secret:
        try:
            exchange = ccxt.krakenfutures({
                'apiKey': api_key, 'secret': api_secret,
                'enableRateLimit': True, 'options': {'defaultType': 'future'}
            })
            
            st.session_state.loop_count = st.session_state.get('loop_count', 0) + 1
            lc = st.session_state.loop_count
            
            # Obtener equity
            try:
                bal = exchange.fetch_balance()
                eq = safe_float(bal.get('total', {}).get('USD', 0))
                if eq == 0: eq = safe_float(bal.get('free', {}).get('USD', 0))
                if eq == 0:
                    eq = safe_float(bal.get('used', {}).get('USD', 0)) + safe_float(bal.get('free', {}).get('USD', 0))
                set_equity(eq)
            except Exception as e:
                eq = get_equity()
                if lc <= 2: logger.log(f"Balance err: {str(e)[:50]}", "ERROR")
            
            equity = get_equity()
            phase = CompoundPhases.get_current_phase(equity)
            pcfg = CompoundPhases.get_phase_config(equity)
            
            # Log inicio
            if lc <= 2:
                logger.log("=" * 50, "SYSTEM")
                logger.log(f"V10 COMPOUND | Equity: ${equity:.4f}", "SYSTEM")
                logger.log(f"Fase {phase}: {pcfg.get('name','')} | {pcfg.get('description','')}", "PHASE")
                logger.log(f"Lev:{pcfg.get('leverage',0)}x Risk:{pcfg.get('risk_pct',0)*100:.1f}% RR:{pcfg.get('rr_ratio',0)}:1", "PHASE")
                logger.log(f"Símbolos: {pcfg.get('symbols',[])}", "PHASE")
                logger.log(f"Target: ${CompoundPhases.TARGET}", "SYSTEM")
                logger.log("=" * 50, "SYSTEM")
            
            # ===== MILESTONE CHECK =====
            old_phase = st.session_state.get('last_phase', phase)
            if 'last_phase' not in st.session_state:
                st.session_state.last_phase = phase
            
            milestones = {10: ('$10', '🔥'), 20: ('$20', '⚡'), 30: ('$30', '🚀'), 
                         40: ('$40', '💫'), 50: ('$50', '⭐'), 60: ('$60', '🏆')}
            for m_val, (m_name, m_emoji) in milestones.items():
                if equity >= m_val and not st.session_state.get(f'milestone_{m_val}', False):
                    st.session_state[f'milestone_{m_val}'] = True
                    logger.log(f"{m_emoji} MILESTONE: {m_name} ALCANZADO!", "MILESTONE")
            
            if phase != old_phase and phase > 0:
                logger.log(f"🔄 FASE CAMBIADA: {old_phase} → {phase} ({pcfg['name']})", "PHASE")
                st.session_state.last_phase = phase
            
            # ===== PROGRESS BAR =====
            progress = get_progress(equity)
            p_color = get_progress_color(progress)
            
            # Check milestones reached
            ms_html = ""
            for m_val in [10, 20, 30, 40, 50, 60]:
                if st.session_state.get(f'milestone_{m_val}', False):
                    ms_html += f" <span style='color:#00ff88'>✓${m_val}</span>"
                else:
                    ms_html += f" <span style='color:#444'>○${m_val}</span>"
            
            progress_ph.markdown(f"""
            <div class="mc-gold">
                <b>📈 PROGRESO: $3.50 → ${CompoundPhases.TARGET:.0f}</b><br>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width:{progress:.1f}%;background:linear-gradient(90deg, {p_color}, {p_color}88)">
                        ${equity:.2f} ({progress:.1f}%)
                    </div>
                </div>
                <span style="font-size:0.8em">Milestones:{ms_html}</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Phase info
            pp = get_phase_progress(equity, phase) if phase > 0 else 100
            phase_ph.markdown(f"""
            <div class="mc">
                <b>{pcfg.get('emoji','')} FASE {phase}: {pcfg.get('name','N/A')}</b><br>
                <span style="color:{pcfg.get('color','#fff')}">{pp:.0f}% completada</span><br>
                <small style="color:#8888aa">
                    Lev:{pcfg.get('leverage',0)}x | Risk:{pcfg.get('risk_pct',0)*100:.1f}% | 
                    RR:{pcfg.get('rr_ratio',0)}:1<br>
                    {pcfg.get('description','')}
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # ===== META ALCANZADA - PARAR =====
            if phase == 0:
                logger.log("🏆 ¡OBJETIVO ALCANZADO! Bot detenido. Retira tus fondos.", "MILESTONE")
                capital_ph.markdown(f"""
                <div class="mc" style="border-color:#00ffff;text-align:center">
                    <b style="color:#00ffff;font-size:1.3em">🏆 ¡META ALCANZADA! 🏆</b><br>
                    <span style="font-size:2em;color:#00ff88;font-weight:700">${equity:.2f}</span><br>
                    <small style="color:#aaa">Retira tus fondos a tu wallet. ¡Buen trabajo!</small>
                </div>
                """, unsafe_allow_html=True)
                
                # Mostrar stats finales
                stats = st.session_state.trade_stats
                wr = stats['wins']/(stats['wins']+stats['losses'])*100 if (stats['wins']+stats['losses'])>0 else 0
                stats_ph.markdown(f"""
                <div class="mc" style="text-align:center">
                    <b>📊 Resumen Final</b><br>
                    <small>
                    Trades: {stats['total_trades']} | WR: {wr:.1f}% | 
                    PF: {stats.get('profit_factor',0):.2f}<br>
                    Neto: ${stats.get('net_pnl',0):+.2f} | Fees: ${stats.get('total_fees_paid',0):.2f}<br>
                    Inicio: ${stats.get('starting_equity',0):.2f} → Final: ${equity:.2f}
                    </small>
                </div>
                """, unsafe_allow_html=True)
                time.sleep(60)
                st.rerun()
                return
            
            # ===== VERIFICAR LÍMITES =====
            daily_ok, daily_reason = check_daily_limits(pcfg)
            
            # ===== UI CAPITAL =====
            stats = st.session_state.trade_stats
            wr = stats['wins']/(stats['wins']+stats['losses'])*100 if (stats['wins']+stats['losses'])>0 else 0
            net = stats.get('net_pnl', stats.get('total_pnl', 0))
            nc = '#00ff88' if net>=0 else '#ff4466'
            ec = pcfg.get('color', '#4a9eff')
            
            capital_ph.markdown(f"""
            <div class="mc">
                <b>💰 Capital</b><br>
                <span style="font-size:1.6em;color:{ec};font-weight:700">${equity:.4f}</span><br>
                <small style="color:#8899aa">
                    W:{stats['wins']} L:{stats['losses']} | WR:{wr:.0f}%<br>
                    <span style="color:{nc}">Neto: ${net:+.4f}</span>
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # ===== GESTIONAR POSICIONES =====
            n_act = 0
            try:
                positions = exchange.fetch_positions()
                n_act = manage_positions(positions, exchange, logger, pcfg)
            except Exception as e:
                positions, n_act = [], 0
                logger.log(f"Pos err: {str(e)[:50]}", "ERROR")
            
            # UI Posiciones (sin nested divs)
            pos_html = ""
            for p in positions:
                qty = safe_float(p.get('contracts', 0))
                if qty <= 0: continue
                sym = p['symbol']
                side = p['side'].upper()
                mark = safe_float(p.get('markPrice'))
                entry = safe_float(p.get('entryPrice'))
                pnl = safe_float(p.get('unrealizedPnl'))
                tr = st.session_state.active_trades.get(sym, {})
                sl = tr.get('sl_current', 0)
                tp = tr.get('tp_current', 0)
                mfe = tr.get('mfe', 0) * 100
                clr = "#00ff88" if pnl >= 0 else "#ff4466"
                trail = "🔄" if tr.get('trailing_active') else ""
                be = "✅" if tr.get('breakeven_reached') else ""
                pos_html += (
                    f'<hr style="border-color:{clr};opacity:0.3;margin:5px 0">'
                    f'<b style="color:{clr}">{sym.split("/")[0]} {side}</b> {trail}{be}<br>'
                    f'<span style="color:#aaa;font-size:0.85em">'
                    f'@{entry:.2f} | SL:{sl:.2f} | TP:{tp:.2f}<br>'
                    f'PnL: ${pnl:+.4f} | MFE: {mfe:.1f}%</span>'
                )
            
            if pos_html:
                pos_full = f'<b>📈 Posiciones ({n_act}/{pcfg["max_positions"]})</b><br>{pos_html}'
            else:
                pos_full = f'<b>📈 Posiciones (0/{pcfg["max_positions"]})</b><br><span style="color:#667799">Sin posiciones</span>'
            
            posicion_ph.markdown(f'<div class="mc">{pos_full}</div>', unsafe_allow_html=True)
            
            # ===== GENERAR SEÑALES =====
            signals = []
            can_trade = (daily_ok and n_act < pcfg['max_positions'] and 
                        modo == "Trading Real" and equity > 1.5)
            
            if can_trade:
                if lc % 5 == 0:
                    logger.log("📡 Scanning...", "SYSTEM")
                
                active_symbols = pcfg['symbols']
                
                for symbol in active_symbols:
                    if symbol not in SYMBOLS_CONFIG: continue
                    if not check_cooldown(symbol): continue
                    if n_act >= pcfg['max_positions']: break
                    
                    try:
                        b15 = exchange.fetch_ohlcv(symbol, '15m', limit=200)
                        b1h = exchange.fetch_ohlcv(symbol, '1h', limit=200)
                        b4h = exchange.fetch_ohlcv(symbol, '4h', limit=200)
                        if len(b15) < 60: continue
                        
                        d15 = pd.DataFrame(b15, columns=['ts','o','h','l','c','v'])
                        d1h = pd.DataFrame(b1h, columns=['ts','o','h','l','c','v'])
                        d4h = pd.DataFrame(b4h, columns=['ts','o','h','l','c','v'])
                        
                        sig = generate_signal(d15, d1h, d4h, symbol, logger, pcfg)
                        if not sig: continue
                        
                        signals.append(sig)
                        
                        # Calcular posición
                        sym_cfg = SYMBOLS_CONFIG[symbol]
                        qty = calc_position(equity, sig['entry'], sig['sl'], 
                                          pcfg['leverage'], sym_cfg, pcfg, logger)
                        min_sz = sym_cfg['min_size']
                        
                        if qty >= min_sz * 0.8:
                            try:
                                side_o = 'buy' if sig['side']=='long' else 'sell'
                                notional = qty * sig['entry']
                                fees = estimate_fees(notional)
                                
                                logger.log(
                                    f"📦 {side_o} {qty} {symbol} | "
                                    f"N:${notional:.2f} Fees:${fees:.4f}", "TRADE"
                                )
                                
                                exchange.create_order(
                                    symbol=symbol, type='market', side=side_o,
                                    amount=qty, params={'leverage': pcfg['leverage']}
                                )
                                
                                st.session_state.active_trades[symbol] = {
                                    'entry': sig['entry'], 'sl_current': sig['sl'],
                                    'tp_current': sig['tp'], 'trailing_active': False,
                                    'breakeven_reached': False,
                                    'entry_risk': abs(sig['entry']-sig['sl'])/sig['entry'],
                                    'atr': sig['atr'], 'side': sig['side'].upper(),
                                    'original_qty': qty, 'current_qty': qty,
                                    'highest': sig['entry'], 'lowest': sig['entry'],
                                    'mfe': 0.0, 'opened_at': datetime.now(timezone.utc),
                                    'score': sig['score'], 'razones': sig['razones']
                                }
                                
                                st.session_state.last_signal_candle[symbol] = candle_timestamp('15m')
                                st.session_state.daily_trades += 1
                                n_act += 1
                                
                                logger.log(
                                    f"✅ {sig['side'].upper()} {qty} {symbol} "
                                    f"@ {sig['entry']:.2f} S:{sig['score']:.1f} "
                                    f"| {', '.join(sig['razones'][:3])}", "WIN"
                                )
                                
                                if n_act >= pcfg['max_positions']: break
                                
                            except Exception as e:
                                em = str(e)
                                logger.log(f"❌ Order err: {em[:100]}", "ERROR")
                                if "margin" in em.lower() or "insufficient" in em.lower():
                                    try:
                                        qr = qty * 0.5
                                        if qr >= min_sz:
                                            exchange.create_order(
                                                symbol=symbol, type='market', side=side_o,
                                                amount=qr, params={'leverage': pcfg['leverage']}
                                            )
                                            st.session_state.last_signal_candle[symbol] = candle_timestamp('15m')
                                            st.session_state.daily_trades += 1
                                            logger.log(f"✅ Retry: {qr} {symbol}", "WIN")
                                    except Exception as e2:
                                        logger.log(f"Retry fail: {str(e2)[:60]}", "ERROR")
                        else:
                            logger.log(f"{symbol}: Qty too small ({qty} < {min_sz})", "WARN")
                    
                    except Exception as e:
                        logger.log(f"{symbol}: {str(e)[:70]}", "ERROR")
            
            # UI Señales (sin nested divs)
            sig_html = ""
            for s in signals:
                clr = '#00ff88' if s['side']=='long' else '#ff4466'
                rz = " | ".join(s['razones'][:3])
                sig_html += (
                    f'<hr style="border-color:{clr};opacity:0.4;margin:6px 0">'
                    f'<span style="color:{clr};font-weight:700;font-size:1.05em">'
                    f'{s["side"].upper()} {s["symbol"].split("/")[0]}</span>'
                    f' <span style="color:#8899aa">S:{s["score"]:.1f} ADX:{s.get("adx",0):.0f}</span><br>'
                    f'<span style="color:#ccc;font-size:0.88em">'
                    f'@{s["entry"]:.2f} | SL:{s["sl"]:.2f} | TP:{s["tp"]:.2f} | RR:{pcfg["rr_ratio"]}:1</span><br>'
                    f'<span style="color:#8899bb;font-size:0.8em">{rz}</span>'
                )
            
            if sig_html:
                sig_full = f'<b>🎯 Señales ({len(signals)})</b><br>{sig_html}'
            else:
                sig_full = '<b>🎯 Señales (0)</b><br><span style="color:#667799">Escaneando...</span>'
            
            senal_ph.markdown(f'<div class="mc">{sig_full}</div>', unsafe_allow_html=True)
            
            # Logs (sin nested divs)
            logs = logger.get_logs(30)
            if logs:
                log_html = "<br>".join([f'<span style="font-family:monospace;font-size:0.75em;color:#99aabb">{l}</span>' for l in logs])
            else:
                log_html = '<span style="color:#667">Sin logs</span>'
            log_ph.markdown(f'<div class="mc" style="max-height:300px;overflow-y:auto">{log_html}</div>', unsafe_allow_html=True)
            
            # Stats
            pf = stats.get('profit_factor', 0)
            exp_val = (wr/100 * stats['avg_win']) - ((1-wr/100) * stats['avg_loss']) if (stats['wins']+stats['losses'])>0 else 0
            
            stats_ph.markdown(f"""
            <div class="mc" style="text-align:center">
                <small style="color:#8899aa">
                    <b>PF:</b> {pf:.2f} | <b>Exp:</b> ${exp_val:+.4f}/t | 
                    <b>DD:</b> ${stats.get('max_drawdown',0):+.4f}<br>
                    <b>Win:</b> ${stats.get('avg_win',0):.4f} | <b>Loss:</b> ${stats.get('avg_loss',0):.4f} | 
                    <b>Fees:</b> ${stats.get('total_fees_paid',0):.4f}<br>
                    <b>Streak W:</b> {stats.get('max_consecutive_wins',0)} | 
                    <b>Streak L:</b> {stats.get('max_consecutive_losses',0)} | 
                    <b>Total:</b> {stats['total_trades']}
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            time.sleep(15)
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ Error: {e}")
            logger.log(f"CRITICAL: {str(e)[:150]}", "ERROR")
            import traceback
            logger.log(traceback.format_exc()[:300], "ERROR")
            time.sleep(15)
            st.rerun()
    
    else:
        if not activar:
            st.info("👈 Ingresa API credentials y activa INICIAR")
        elif not api_key or not api_secret:
            st.error("❌ API Key y Secret requeridos")


if __name__ == "__main__":
    main()
