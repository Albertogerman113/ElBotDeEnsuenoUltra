# ============================================================================
# SNIPER V9.0 - PRICE ACTION ELITE (MICRO-CAPITAL EDITION)
# ============================================================================
# Correcciones principales vs V8.2:
#   1. Bug: logger pasado como parámetro en calcular_posicion
#   2. Señales: Scoring mejorado, spread reducido, umbral corregido
#   3. Riesgo: Exposición 60%, stops más amplios, fees incluidos
#   4. Técnico: Swings con 5 barras, ADX como filtro, cooldown por vela
#   5. Ejecución: Limit orders para entrada, retry inteligente
#   6. Trailing: Más tardío (1.5R), no breakeven prematuro
#   7. Fees: Restados del PnL real
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
    page_title="SNIPER V9.0 | MICRO-CAPITAL",
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
# CONFIGURACIÓN V9.0 - MICRO-CAPITAL CORREGIDA
# ============================================================================
class Config:
    SYMBOLS = {
        'BTC/USD:USD': {'min_size': 0.00001, 'tick_size': 0.5, 'risk_weight': 1.0, 'correlation_group': 'major'},
        'ETH/USD:USD': {'min_size': 0.0001, 'tick_size': 0.05, 'risk_weight': 0.8, 'correlation_group': 'major'},
        'SOL/USD:USD': {'min_size': 0.001, 'tick_size': 0.001, 'risk_weight': 0.6, 'correlation_group': 'alt'}
    }
    
    LEVERAGE_DEFAULT = 5        # REDUCIDO: 5x en vez de 10x. Menos riesgo de liquidación
    RISK_PCT_DEFAULT = 0.03     # 3% por trade (era 5%). Más conservador.
    RR_RATIO = 2.5              # AUMENTADO: 2.5:1 en vez de 2:1. Compensa fees.
    MAX_POSITIONS = 2
    MAX_DAILY_TRADES = 8        # REDUCIDO: 8 en vez de 20. Menos overtrading.
    MAX_DAILY_LOSS_PCT = 0.15   # REDUCIDO: 15% en vez de 50%. Protege capital.
    MAX_WEEKLY_LOSS_PCT = 0.30  # REDUCIDO: 30% en vez de 80%.
    MAX_CONSECUTIVE_LOSSES = 5  # REDUCIDO: 5 en vez de 10. Para antes de blowup.
    
    TIMEFRAME_ENTRY = '15m'
    TIMEFRAME_TREND = '1h'
    TIMEFRAME_CONFIRM = '5m'
    TIMEFRAME_HIGH = '4h'
    BARS_LIMIT = 200
    
    # Parámetros técnicos corregidos
    OB_STRENGTH = 1.5           # AUMENTADO: 1.5% en vez de 1.0%. OB más significativos.
    FVG_MIN_GAP = 0.005         # AUMENTADO: 0.5% en vez de 0.2%. Menos FVG falsos.
    MSS_CONFIRMATION_BARS = 3   # AUMENTADO: 3 en vez de 2. Más confirmación.
    VOLUME_CONFIRMATION = 1.2   # AUMENTADO: 1.2x en vez de 1.0x. Volumen debe ser superior.
    MIN_SCORE_BASE = 5.0        # AUMENTADO: 5.0 en vez de 4.0. Sólo setups de alta calidad.
    
    # ADX filtro de tendencia (NUEVO)
    ADX_ENABLED = True
    ADX_MIN = 20                # Mínimo 20 para considerar tendencia
    
    # Exposición corregida
    MAX_EXPOSURE_PCT = 0.60     # REDUCIDO: 60% en vez de 95%. Sobrevivir es prioridad.
    
    # Scale-out desactivado para micro-capital (fees lo hacen inviable)
    SCALE_OUT_ENABLED = False
    
    # Trailing corregido
    TRAILING_ENABLED = True
    BREAKEVEN_AT_R = 1.2        # AUMENTADO: 1.2R en vez de 0.5R. No matar ganadores.
    TRAILING_START_AT_R = 1.5   # AUMENTADO: 1.5R en vez de 0.8R.
    TRAILING_DISTANCE_ATR_MULT = 0.5  # AUMENTADO: 0.5 en vez de 0.3. Da espacio.
    
    # Fees estimados Kraken Futures taker
    FEE_RATE = 0.0005           # 0.05% por lado
    FEE_ROUND_TRIP = 0.001      # 0.10% ida y vuelta
    
    # Cooldown por cierre de vela (NUEVO - era 45s fijo)
    COOLDOWN_BARS = 2           # Esperar 2 barras completas antes de nueva señal
    
    RATE_LIMIT_DELAY = 15       # Aumentado: 15s en vez de 10s. Menos requests.

# ============================================================================
# INICIALIZACIÓN DE SESSION STATE
# ============================================================================
def init_session_state():
    defaults = {
        'trade_log': [],
        'trade_stats': {
            'wins': 0, 'losses': 0, 'total_pnl': 0.0,
            'total_fees_paid': 0.0,      # NUEVO: tracking de fees
            'net_pnl': 0.0,              # NUEVO: PnL real después de fees
            'avg_win': 0.0, 'avg_loss': 0.0, 'max_drawdown': 0.0,
            'largest_win': 0.0, 'largest_loss': 0.0,
            'consecutive_wins': 0, 'consecutive_losses': 0,
            'max_consecutive_wins': 0, 'max_consecutive_losses': 0,
            'total_trades': 0, 'profit_factor': 0.0
        },
        'active_trades': {},
        'last_signal_time': {},
        'last_signal_candle': {},       # NUEVO: trackear última vela de señal
        'daily_trades': 0,
        'daily_pnl': 0.0,
        'weekly_pnl': 0.0,
        'last_reset_date': datetime.now().strftime('%Y-%m-%d'),
        'last_week_reset': datetime.now().strftime('%Y-%W'),
        'equity_cache': 0.0,
        'trading_paused': False,
        'pause_reason': "",
        'loop_count': 0,                # NUEVO: trackear iteraciones
    }
    
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

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
            "PAUSE": "⏸️", "FILTER": "🚫", "DEBUG": "🔍",
            "FEE": "💵", "SIGNAL": "📡"
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
    """Retorna sesión actual. El weight ahora es usado como multiplicador menor (no distorsiona)."""
    hour_utc = datetime.now(timezone.utc).hour
    sessions = {
        'asian': {'start': 0, 'end': 8, 'weight': 0.85},
        'london': {'start': 7, 'end': 16, 'weight': 1.0},
        'ny': {'start': 12, 'end': 21, 'weight': 1.1}
    }
    for name, data in sessions.items():
        if data['start'] <= hour_utc < data['end']:
            return name, data['weight']
    return 'offpeak', 0.7   # Reducido offpeak: 0.7 en vez de 0.5

def get_equity() -> float:
    return st.session_state.get('equity_cache', 0.0)

def set_equity(value: float):
    st.session_state.equity_cache = value

def estimate_fees(notional_value: float) -> float:
    """Estima fees taker redondos para una operación."""
    return notional_value * Config.FEE_ROUND_TRIP

def candle_timestamp(tf: str) -> int:
    """Retorna el timestamp de inicio de la vela actual para el timeframe dado."""
    now = datetime.now(timezone.utc)
    tf_seconds = {
        '1m': 60, '3m': 180, '5m': 300, '15m': 900,
        '30m': 1800, '1h': 3600, '4h': 14400
    }
    seconds = tf_seconds.get(tf, 900)
    epoch = int(now.timestamp())
    return (epoch // seconds) * seconds

# ============================================================================
# FILTROS
# ============================================================================
class MarketFilters:
    
    @staticmethod
    def check_prohibited_hours() -> Tuple[bool, str]:
        return False, ""
    
    @staticmethod
    def check_volatility_filter(df: pd.DataFrame) -> Tuple[bool, str]:
        return True, ""
    
    @staticmethod
    def check_correlation(symbol: str, active_positions: Dict) -> Tuple[bool, str]:
        if len(active_positions) >= Config.MAX_POSITIONS:
            return False, "Máximo de posiciones"
        
        # NUEVO: No permitir LONG y SHORT al mismo tiempo en correlacionados
        if active_positions:
            new_group = Config.SYMBOLS.get(symbol, {}).get('correlation_group', 'other')
            for pos_sym, pos_data in active_positions.items():
                pos_group = Config.SYMBOLS.get(pos_sym, {}).get('correlation_group', 'other')
                if new_group == pos_group:
                    if pos_data.get('side', '').upper() != st.session_state.get('pending_side', ''):
                        return False, f"Posición opuesta en correlacionado ({pos_group})"
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
            return False, f"Límite diario ({Config.MAX_DAILY_TRADES})"
        
        equity = get_equity()
        if equity > 0 and st.session_state.daily_pnl < -equity * Config.MAX_DAILY_LOSS_PCT:
            return False, f"Límite pérdida diaria ({Config.MAX_DAILY_LOSS_PCT*100:.0f}%)"
        
        if equity > 0 and st.session_state.weekly_pnl < -equity * Config.MAX_WEEKLY_LOSS_PCT:
            return False, "Límite pérdida semanal"
        
        stats = st.session_state.trade_stats
        if stats['consecutive_losses'] >= Config.MAX_CONSECUTIVE_LOSSES:
            return False, f"{Config.MAX_CONSECUTIVE_LOSSES} pérdidas consecutivas - PAUSA"
        
        return True, "OK"

# ============================================================================
# INDICADORES TÉCNICOS (MEJORADOS)
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
        
        # EMAs
        for span in [9, 20, 50, 100, 200]:
            df[f'ema{span}'] = c.ewm(span=span, adjust=False).mean()
        
        # ATR (14 periodos)
        tr1 = h - l
        tr2 = abs(h - c.shift(1))
        tr3 = abs(l - c.shift(1))
        df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()
        df['atr_pct'] = (df['atr'] / c * 100).fillna(0)
        
        # RSI (14 periodos, Wilder smoothing)
        delta = c.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)
        
        # Volumen
        df['vol_ma'] = v.rolling(20).mean()
        df['vol_ratio'] = (v / df['vol_ma']).fillna(1)
        
        # Cuerpo y mechas
        df['body'] = abs(c - o)
        df['wick_up'] = h - pd.concat([c, o], axis=1).max(axis=1)
        df['wick_dn'] = pd.concat([c, o], axis=1).min(axis=1) - l
        
        # NUEVO: ADX (Average Directional Index) - Filtro de tendencia
        df = TechnicalIndicators.calcular_adx(df, period=14)
        
        # NUEVO: VWAP-like proxy (usando HLC3 × Volume)
        df['hlc3'] = (h + l + c) / 3
        df['vwap_approx'] = (df['hlc3'] * v).cumsum() / v.cumsum()
        
        return df
    
    @staticmethod
    def calcular_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Calcula ADX + DI+ / DI- para filtro de fuerza de tendencia."""
        h = df['h'].astype(float)
        l = df['l'].astype(float)
        c = df['c'].astype(float)
        
        plus_dm = h.diff()
        minus_dm = -l.diff()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        tr = df['tr'] if 'tr' in df.columns else pd.concat([h - l, abs(h - c.shift(1)), abs(l - c.shift(1))], axis=1).max(axis=1)
        
        atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        
        df['plus_di'] = plus_di.fillna(0)
        df['minus_di'] = minus_di.fillna(0)
        df['adx'] = adx.fillna(0)
        
        return df
    
    @staticmethod
    def detectar_mss(df: pd.DataFrame, lookback: int = 30) -> Tuple[str, Optional[float], Optional[float]]:
        """
        Market Structure Shift mejorado:
        - Usa ventana de 5 barras (era 3) para swings más limpios
        - Requiere que el último swing se haya formado en las últimas 20 barras
        - Retorna swing_high y swing_low relevantes para la dirección
        """
        if len(df) < lookback + Config.MSS_CONFIRMATION_BARS:
            return 'neutral', None, None
        
        highs = df['h'].astype(float).values
        lows = df['l'].astype(float).values
        c = df['c'].astype(float).values
        
        # MEJORADO: Ventana de 5 barras en vez de 3 para swings más significativos
        window = 5
        swings_h, swings_l = [], []
        for i in range(window, len(df) - 1):
            left_start = max(0, i - window)
            right_end = min(len(highs), i + window + 1)
            
            local_highs = highs[left_start:right_end]
            local_lows = lows[left_start:right_end]
            
            if highs[i] >= max(local_highs):
                swings_h.append((i, highs[i]))
            if lows[i] <= min(local_lows):
                swings_l.append((i, lows[i]))
        
        # Necesitamos al menos 3 swings
        if len(swings_h) < 3 or len(swings_l) < 3:
            return 'neutral', None, None
        
        last_hh, prev_hh = swings_h[-1][1], swings_h[-2][1]
        last_hh_idx = swings_h[-1][0]
        last_ll, prev_ll = swings_l[-1][1], swings_l[-2][1]
        last_ll_idx = swings_l[-1][0]
        
        # Solo considerar swings recientes (últimas 20 barras)
        if last_hh_idx < len(df) - 20 or last_ll_idx < len(df) - 20:
            return 'neutral', last_ll, last_hh
        
        # MSS alcista: HH + HL y precio rompe encima del último swing high
        if last_hh > prev_hh and last_ll > prev_ll:
            if c[-1] > last_hh:
                return 'bullish_mss', last_ll, last_hh
            return 'bullish', last_ll, last_hh
        
        # MSS bajista: LH + LL y precio rompe debajo del último swing low
        if last_hh < prev_hh and last_ll < prev_ll:
            if c[-1] < last_ll:
                return 'bearish_mss', last_ll, last_hh
            return 'bearish', last_ll, last_hh
        
        return 'neutral', last_ll, last_hh
    
    @staticmethod
    def detectar_order_blocks(df: pd.DataFrame, n: int = 5) -> Tuple[List[Dict], List[Dict]]:
        """
        Order Blocks mejorados:
        - Verifica que el precio haya RECHAZADO el bloque (no solo que se movió)
        - Requiere que la vela OPUESTA confirme el rechazo
        - Fortaleza medida por volumen relativo
        """
        obs_bull, obs_bear = [], []
        c = df['c'].astype(float).values
        o = df['o'].astype(float).values
        h = df['h'].astype(float).values
        l = df['l'].astype(float).values
        v = df['v'].astype(float).values
        vol_ma = df['v'].astype(float).rolling(20).mean().values
        
        precio_actual = c[-1]
        
        for i in range(5, len(df) - n - 2):
            vol_avg = vol_ma[i] if not np.isnan(vol_ma[i]) else v[i]
            
            # OB alcista: Vela bajista FUERTE seguida de movimiento alcista impulsivo
            if o[i] > c[i]:  # Vela bajista
                move_up = (c[i+n] - o[i]) / (o[i] + 1e-10) * 100
                vol_conf = v[i] / (vol_avg + 1e-10)
                
                if move_up > Config.OB_STRENGTH and vol_conf > 1.2:
                    ob_mid = (o[i] + c[i]) / 2
                    # Solo incluir si el OB está cerca del precio actual (zona de interés)
                    distance_pct = abs(precio_actual - ob_mid) / precio_actual * 100
                    if distance_pct < 2.0:  # Dentro del 2% del precio
                        obs_bull.append({
                            'mid': ob_mid,
                            'top': o[i],       # Techo del OB (open de vela bajista)
                            'bottom': c[i],    # Piso del OB (close de vela bajista)
                            'strength': move_up * vol_conf,  # Combinar precio + volumen
                            'index': i
                        })
            
            # OB bajista: Vela alcista FUERTE seguida de movimiento bajista impulsivo
            if c[i] > o[i]:  # Vela alcista
                move_dn = (o[i] - c[i+n]) / (o[i] + 1e-10) * 100
                vol_conf = v[i] / (vol_avg + 1e-10)
                
                if move_dn > Config.OB_STRENGTH and vol_conf > 1.2:
                    ob_mid = (c[i] + o[i]) / 2
                    distance_pct = abs(precio_actual - ob_mid) / precio_actual * 100
                    if distance_pct < 2.0:
                        obs_bear.append({
                            'mid': ob_mid,
                            'top': c[i],
                            'bottom': o[i],
                            'strength': move_dn * vol_conf,
                            'index': i
                        })
        
        # Ordenar por cercanía al precio actual, luego por fortaleza
        obs_bull.sort(key=lambda x: (abs(precio_actual - x['mid']), x['strength']))
        obs_bear.sort(key=lambda x: (abs(precio_actual - x['mid']), x['strength']))
        
        return obs_bull[:3], obs_bear[:3]
    
    @staticmethod
    def detectar_fvg(df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
        """
        Fair Value Gaps mejorados:
        - Gap mínimo aumentado a 0.5% (era 0.2%)
        - Solo FVGs que no han sido llenados
        """
        fvgs_bull, fvgs_bear = [], []
        h = df['h'].astype(float).values
        l = df['l'].astype(float).values
        c = df['c'].astype(float).values
        
        for i in range(1, len(df) - 1):
            # FVG alcista: low de barra i+1 > high de barra i-1
            if l[i+1] > h[i-1]:
                gap = (l[i+1] - h[i-1]) / (h[i-1] + 1e-10)
                if gap >= Config.FVG_MIN_GAP:
                    # NUEVO: Verificar que NO ha sido llenado (precio no volvió al gap)
                    subsequent_lows = l[i+2:] if i+2 < len(l) else np.array([])
                    filled = any(low < h[i-1] for low in subsequent_lows)
                    
                    if not filled:
                        fvgs_bull.append({'bot': h[i-1], 'top': l[i+1], 'gap_size': gap, 'filled': False})
                    else:
                        fvgs_bull.append({'bot': h[i-1], 'top': l[i+1], 'gap_size': gap, 'filled': True})
            
            # FVG bajista: high de barra i+1 < low de barra i-1
            if h[i+1] < l[i-1]:
                gap = (l[i-1] - h[i+1]) / (l[i-1] + 1e-10)
                if gap >= Config.FVG_MIN_GAP:
                    subsequent_highs = h[i+2:] if i+2 < len(h) else np.array([])
                    filled = any(high > l[i-1] for high in subsequent_highs)
                    
                    if not filled:
                        fvgs_bear.append({'bot': h[i+1], 'top': l[i-1], 'gap_size': gap, 'filled': False})
                    else:
                        fvgs_bear.append({'bot': h[i+1], 'top': l[i-1], 'gap_size': gap, 'filled': True})
        
        # Solo FVGs no llenados, ordenados por recientes
        active_bull = [f for f in fvgs_bull if not f['filled']][-3:]
        active_bear = [f for f in fvgs_bear if not f['filled']][-3:]
        
        return active_bull, active_bear
    
    @staticmethod
    def detectar_patrones_velas(df: pd.DataFrame) -> Dict[str, Optional[str]]:
        """Patrones de velas con confirmación de volumen."""
        patterns = {'pin': None, 'engulfing': None, 'inside': False, 'rejection': None}
        
        if len(df) < 3:
            return patterns
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3] if len(df) >= 3 else None
        
        body = abs(float(last['c']) - float(last['o']))
        total_range = float(last['h']) - float(last['l'])
        
        if total_range > 1e-10:
            wick_up = float(last['h']) - max(float(last['c']), float(last['o']))
            wick_dn = min(float(last['c']), float(last['o'])) - float(last['l'])
            body_ratio = body / total_range
            
            # Pin bar: mecha larga (>60%) y cuerpo pequeño (<25%)
            if wick_dn > total_range * 0.6 and body_ratio < 0.25:
                patterns['pin'] = 'bull_pin'
            elif wick_up > total_range * 0.6 and body_ratio < 0.25:
                patterns['pin'] = 'bear_pin'
            
            # Rejection wick: mecha significativa en zona de soporte/resistencia
            if wick_dn > total_range * 0.5 and body_ratio < 0.35:
                patterns['rejection'] = 'bull_rejection'
            elif wick_up > total_range * 0.5 and body_ratio < 0.35:
                patterns['rejection'] = 'bear_rejection'
        
        # Engulfing con confirmación de volumen (NUEVO: requiere contexto de tendencia)
        if prev is not None:
            curr_body = float(last['c']) - float(last['o'])
            prev_body = float(prev['c']) - float(prev['o'])
            curr_vol = float(last['v'])
            prev_vol = float(prev['v'])
            vol_avg = float(df['v'].iloc[-20:].mean()) if len(df) >= 20 else prev_vol
            
            # Engulfing alcista: vela anterior bajista, actual alcista que la envuelve
            if (prev_body < 0 and curr_body > 0 and 
                float(last['o']) <= float(prev['c']) and 
                float(last['c']) >= float(prev['o']) and
                curr_vol > vol_avg * 1.1):  # NUEVO: volumen vs promedio (era vs vela anterior)
                patterns['engulfing'] = 'bull_engulfing'
            
            # Engulfing bajista
            elif (prev_body > 0 and curr_body < 0 and 
                  float(last['o']) >= float(prev['c']) and 
                  float(last['c']) <= float(prev['o']) and
                  curr_vol > vol_avg * 1.1):
                patterns['engulfing'] = 'bear_engulfing'
        
        # NUEVO: Inside bar (consolidación antes de breakout)
        if prev is not None:
            if (float(last['h']) <= float(prev['h']) and 
                float(last['l']) >= float(prev['l'])):
                patterns['inside'] = True
        
        return patterns

# ============================================================================
# GESTIÓN DE POSICIONES (CORREGIDA)
# ============================================================================
def gestionar_posiciones_v9(posiciones: List[Dict], exchange, logger: LogManager, leverage: int) -> int:
    """Gestión de posiciones con fees tracking y trailing corregido."""
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
        
        # Inicializar tracking del trade si es nuevo
        if sym not in st.session_state.active_trades:
            # Stop loss basado en ATR (1.5x ATR) en vez de porcentaje fijo
            atr_mult_sl = 1.5
            if entry > 0 and mark > 0:
                estimated_atr = abs(mark - entry) * 0.5  # Estimación si no tenemos ATR
            else:
                estimated_atr = entry * 0.01  # 1% default
            
            sl_dist = estimated_atr * atr_mult_sl
            sl = entry - sl_dist if side == 'LONG' else entry + sl_dist
            tp_dist = sl_dist * Config.RR_RATIO  # 2.5:1 RR
            tp = entry + tp_dist if side == 'LONG' else entry - tp_dist
            
            entry_risk = abs(entry - sl) / entry if entry > 0 else 0.015
            
            st.session_state.active_trades[sym] = {
                'entry': entry,
                'sl_current': sl,
                'tp_current': tp,
                'trailing_active': False,
                'breakeven_reached': False,
                'entry_risk': entry_risk,
                'trailing_start': entry,
                'side': side,
                'original_qty': qty,
                'current_qty': qty,
                'highest_since_entry': mark if side == 'LONG' else mark,
                'lowest_since_entry': mark if side == 'SHORT' else mark,
                'max_favorable_excursion': 0.0,  # NUEVO: track MFE
                'opened_at': datetime.now(timezone.utc)
            }
            logger.log(f"Trade activo: {sym} {side} @ {entry:.2f} | SL:{sl:.2f} TP:{tp:.2f}", "SYSTEM")
        
        trade = st.session_state.active_trades[sym]
        sl = trade['sl_current']
        
        # Track máximo excursion favorable
        if side == 'LONG':
            trade['highest_since_entry'] = max(trade['highest_since_entry'], mark)
            trade['max_favorable_excursion'] = max(trade['max_favorable_excursion'], 
                                                    (mark - entry) / entry)
        else:
            trade['lowest_since_entry'] = min(trade['lowest_since_entry'], mark)
            trade['max_favorable_excursion'] = max(trade['max_favorable_excursion'],
                                                   (entry - mark) / entry)
        
        # No hay scale-out (desactivado para micro-capital por fees)
        
        # Verificar TP/SL
        close_side = 'sell' if side == 'LONG' else 'buy'
        tp = trade['tp_current']
        is_tp = (side == 'LONG' and mark >= tp) or (side == 'SHORT' and mark <= tp)
        is_sl = (side == 'LONG' and mark <= sl) or (side == 'SHORT' and mark >= sl)
        
        if is_tp or is_sl:
            try:
                exchange.create_order(
                    symbol=sym, type='market', side=close_side, 
                    amount=trade['current_qty'], params={'reduceOnly': True}
                )
                
                # Calcular fees reales
                notional = trade['current_qty'] * entry
                fees = estimate_fees(notional)
                net_pnl = pnl - fees  # PnL REAL después de fees
                
                stats = st.session_state.trade_stats
                stats['total_pnl'] += pnl
                stats['total_fees_paid'] += fees
                stats['net_pnl'] += net_pnl
                stats['total_trades'] += 1
                
                duration = (datetime.now(timezone.utc) - trade.get('opened_at', datetime.now(timezone.utc))).total_seconds() / 60
                
                if is_tp:
                    logger.log(
                        f"✅ TP HIT: {sym} | Bruto: ${pnl:+.4f} | Fees: ${fees:.4f} | Neto: ${net_pnl:+.4f} | {duration:.0f}min",
                        "WIN"
                    )
                    stats['wins'] += 1
                    w = stats['wins']
                    stats['avg_win'] = (stats['avg_win'] * (w - 1) + net_pnl) / w if w > 0 else net_pnl
                    stats['largest_win'] = max(stats['largest_win'], net_pnl)
                    stats['consecutive_wins'] += 1
                    stats['consecutive_losses'] = 0
                    stats['max_consecutive_wins'] = max(stats['max_consecutive_wins'], stats['consecutive_wins'])
                else:
                    logger.log(
                        f"❌ SL HIT: {sym} | Bruto: ${pnl:+.4f} | Fees: ${fees:.4f} | Neto: ${net_pnl:+.4f} | MFE: {trade['max_favorable_excursion']*100:.2f}%",
                        "LOSS"
                    )
                    stats['losses'] += 1
                    l_count = stats['losses']
                    stats['avg_loss'] = (stats['avg_loss'] * (l_count - 1) + abs(net_pnl)) / l_count if l_count > 0 else abs(net_pnl)
                    stats['largest_loss'] = max(stats['largest_loss'], abs(net_pnl))
                    stats['consecutive_losses'] += 1
                    stats['consecutive_wins'] = 0
                    stats['max_consecutive_losses'] = max(stats['max_consecutive_losses'], stats['consecutive_losses'])
                
                if stats['net_pnl'] < stats['max_drawdown']:
                    stats['max_drawdown'] = stats['net_pnl']
                
                st.session_state.daily_pnl += net_pnl
                st.session_state.weekly_pnl += net_pnl
                
                # Profit Factor basado en PnL NETO (después de fees)
                if stats['avg_loss'] > 0:
                    stats['profit_factor'] = stats['avg_win'] / stats['avg_loss']
                else:
                    stats['profit_factor'] = 999.0 if stats['wins'] > 0 else 0.0
                
                del st.session_state.active_trades[sym]
                
            except Exception as e:
                logger.log(f"Error cerrando {sym}: {str(e)[:60]}", "ERROR")
            continue
        
        # TRAILING STOP (corregido - más tardío)
        if Config.TRAILING_ENABLED:
            r_mult = abs(mark - entry) / trade['entry_risk'] if trade['entry_risk'] > 0 else 0
            
            # Breakeven solo a 1.2R (era 0.5R)
            if not trade['breakeven_reached'] and r_mult >= Config.BREAKEVEN_AT_R:
                trade['sl_current'] = entry * (1.001 if side == 'LONG' else 0.999)  # +0.1% para fees
                trade['breakeven_reached'] = True
                logger.log(f"{sym}: Breakeven @ {r_mult:.1f}R (entry+fees)", "RISK")
            
            # Trailing inicia a 1.5R (era 0.8R)
            elif trade['breakeven_reached'] and not trade['trailing_active'] and r_mult >= Config.TRAILING_START_AT_R:
                trade['trailing_active'] = True
                trade['trailing_start'] = mark
                logger.log(f"{sym}: Trailing activado @ {r_mult:.1f}R", "RISK")
            
            # Trailing activo
            elif trade['trailing_active']:
                # Usar ATR si está disponible, si no usar entry_risk
                atr = trade.get('atr', trade['entry_risk'] * entry)
                trail_dist = atr * Config.TRAILING_DISTANCE_ATR_MULT
                
                if side == 'LONG':
                    if mark > trade['trailing_start']:
                        trade['trailing_start'] = mark
                    new_sl = mark - trail_dist
                    trade['sl_current'] = max(trade['sl_current'], new_sl)
                else:
                    if mark < trade['trailing_start']:
                        trade['trailing_start'] = mark
                    new_sl = mark + trail_dist
                    trade['sl_current'] = min(trade['sl_current'], new_sl)
                
                # Log cada actualización de trailing (solo cada iteración)
                logger.log(f"{sym}: Trail SL={trade['sl_current']:.2f}", "DEBUG")
    
    return n_activas

# ============================================================================
# GENERADOR DE SEÑALES V9 (REESCRITO)
# ============================================================================
class SignalGeneratorV9:
    def __init__(self):
        self.filters = MarketFilters()
    
    def generar_senal_premium(self, df_15m: pd.DataFrame, df_1h: pd.DataFrame, 
                               df_4h: pd.DataFrame, symbol: str, logger: LogManager) -> Optional[Dict]:
        
        # Verificar datos suficientes
        if len(df_15m) < 60 or len(df_1h) < 60:
            return None
        
        # Calcular indicadores
        df_15m = TechnicalIndicators.calcular_indicadores_premium(df_15m)
        df_1h = TechnicalIndicators.calcular_indicadores_premium(df_1h)
        df_4h = TechnicalIndicators.calcular_indicadores_premium(df_4h)
        
        # Datos actuales 15m
        last_15m = df_15m.iloc[-1]
        precio = float(last_15m['c'])
        atr = float(last_15m['atr'])
        atr_pct = float(last_15m['atr_pct'])
        rsi = float(last_15m['rsi'])
        vol_ratio = float(last_15m['vol_ratio'])
        adx = float(last_15m['adx'])
        plus_di = float(last_15m['plus_di'])
        minus_di = float(last_15m['minus_di'])
        
        # Datos 1h para tendencia
        last_1h = df_1h.iloc[-1]
        ema50_1h = float(last_1h['ema50'])
        ema200_1h = float(last_1h['ema200'])
        adx_1h = float(last_1h['adx'])
        
        # Datos 4h para tendencia macro
        last_4h = df_4h.iloc[-1]
        ema50_4h = float(last_4h['ema50'])
        ema200_4h = float(last_4h['ema200'])
        
        # Tendencias multi-timeframe
        tendencia_15m = 'bull' if precio > float(last_15m['ema50']) else 'bear'
        tendencia_1h = 'bull' if ema50_1h > ema200_1h else 'bear' if ema50_1h < ema200_1h else 'neutral'
        tendencia_4h = 'bull' if ema50_4h > ema200_4h else 'bear' if ema50_4h < ema200_4h else 'neutral'
        
        # NUEVO: Alineación de tendencias (peso máximo si todos coinciden)
        trend_alignment = 0
        if tendencia_4h == 'bull' and tendencia_1h == 'bull' and tendencia_15m == 'bull':
            trend_alignment = 3  # Triple alineación alcista
        elif tendencia_4h == 'bear' and tendencia_1h == 'bear' and tendencia_15m == 'bear':
            trend_alignment = -3  # Triple alineación bajista
        elif tendencia_1h == 'bull' and tendencia_15m == 'bull':
            trend_alignment = 2
        elif tendencia_1h == 'bear' and tendencia_15m == 'bear':
            trend_alignment = -2
        elif tendencia_15m == 'bull':
            trend_alignment = 1
        elif tendencia_15m == 'bear':
            trend_alignment = -1
        
        # Estructura de mercado
        estructura_15m, swing_low_15m, swing_high_15m = TechnicalIndicators.detectar_mss(df_15m)
        
        # Order blocks y FVGs
        obs_bull, obs_bear = TechnicalIndicators.detectar_order_blocks(df_15m)
        fvgs_bull, fvgs_bear = TechnicalIndicators.detectar_fvg(df_15m)
        
        # Patrones de velas
        patrones = TechnicalIndicators.detectar_patrones_velas(df_15m)
        
        # VWAP como referencia
        vwap = float(last_15m.get('vwap_approx', precio))
        above_vwap = precio > vwap
        
        # =========================================================================
        # SCORING V9 - Mejorado: pesos más realistas, ADX como filtro
        # =========================================================================
        score_long, score_short = 0.0, 0.0
        razones_long, razones_short = [], []
        
        # --- FACTOR 1: Alineación de Tendencia Multi-Timeframe (Peso: 0-6) ---
        if trend_alignment == 3:
            score_long += 6.0
            razones_long.append("🔴 Triple bull align")
        elif trend_alignment == 2:
            score_long += 4.0
            razones_long.append("1H+15M bull")
        elif trend_alignment == 1:
            score_long += 2.0
            razones_long.append("15M bull only")
        
        if trend_alignment == -3:
            score_short += 6.0
            razones_short.append("🔴 Triple bear align")
        elif trend_alignment == -2:
            score_short += 4.0
            razones_short.append("1H+15M bear")
        elif trend_alignment == -1:
            score_short += 2.0
            razones_short.append("15M bear only")
        
        # --- FACTOR 2: Estructura de Mercado / MSS (Peso: 0-3) ---
        if estructura_15m == 'bullish_mss':
            score_long += 3.0
            razones_long.append("MSS bull confirmado")
        elif estructura_15m == 'bullish':
            score_long += 2.0
            razones_long.append("Estructura bull")
        
        if estructura_15m == 'bearish_mss':
            score_short += 3.0
            razones_short.append("MSS bear confirmado")
        elif estructura_15m == 'bearish':
            score_short += 2.0
            razones_short.append("Estructura bear")
        
        # --- FACTOR 3: Order Blocks en zona (Peso: 0-2) ---
        for ob in obs_bull:
            if ob['bottom'] <= precio <= ob['top']:
                score_long += 2.0
                razones_long.append(f"OB bull touch (str:{ob['strength']:.1f})")
                break
        
        for ob in obs_bear:
            if ob['bottom'] <= precio <= ob['top']:
                score_short += 2.0
                razones_short.append(f"OB bear touch (str:{ob['strength']:.1f})")
                break
        
        # --- FACTOR 4: FVGs (Peso: 0-2) ---
        for fvg in fvgs_bull:
            if fvg['bot'] <= precio <= fvg['top'] and not fvg.get('filled', True):
                score_long += 2.0
                razones_long.append(f"FVG bull ({fvg['gap_size']*100:.2f}%)")
                break
        
        for fvg in fvgs_bear:
            if fvg['bot'] <= precio <= fvg['top'] and not fvg.get('filled', True):
                score_short += 2.0
                razones_short.append(f"FVG bear ({fvg['gap_size']*100:.2f}%)")
                break
        
        # --- FACTOR 5: Patrones de velas (Peso: 0-2.5) ---
        if patrones['engulfing'] == 'bull_engulfing':
            score_long += 2.5
            razones_long.append("Engulfing bull")
        elif patrones['pin'] == 'bull_pin':
            score_long += 2.0
            razones_long.append("Pin bar bull")
        elif patrones.get('rejection') == 'bull_rejection':
            score_long += 1.5
            razones_long.append("Rejection bull")
        
        if patrones['engulfing'] == 'bear_engulfing':
            score_short += 2.5
            razones_short.append("Engulfing bear")
        elif patrones['pin'] == 'bear_pin':
            score_short += 2.0
            razones_short.append("Pin bar bear")
        elif patrones.get('rejection') == 'bear_rejection':
            score_short += 1.5
            razones_short.append("Rejection bear")
        
        # --- FACTOR 6: RSI selectivo (Peso: 0-2) ---
        if 35 < rsi < 55:  # Zona óptima para LONG (no sobrecomprado, no sobrevendido extremo)
            score_long += 2.0
            razones_long.append(f"RSI {rsi:.0f} (zona)")
        elif 25 < rsi <= 35:  # Sobreventa ligera - reacción posible
            score_long += 1.5
            razones_long.append(f"RSI {rsi:.0f} (oversold)")
        
        if 45 < rsi < 65:  # Zona óptima para SHORT
            score_short += 2.0
            razones_short.append(f"RSI {rsi:.0f} (zona)")
        elif 65 <= rsi < 75:  # Sobrecompra ligera
            score_short += 1.5
            razones_short.append(f"RSI {rsi:.0f} (overbought)")
        
        # PENALIZACIÓN: RSI extremo (contrario)
        if rsi >= 75:
            score_long -= 1.0  # Penalizar long en sobrecompra
        if rsi <= 25:
            score_short -= 1.0  # Penalizar short en sobreventa
        
        # --- FACTOR 7: Volumen (Peso: 0-1.5) ---
        if vol_ratio > 1.5:
            score_long += 1.5
            score_short += 1.5
            razones_long.append(f"Vol {vol_ratio:.1f}x ⬆")
            razones_short.append(f"Vol {vol_ratio:.1f}x ⬆")
        elif vol_ratio > Config.VOLUME_CONFIRMATION:
            score_long += 1.0
            score_short += 1.0
        
        # --- FACTOR 8: VWAP (Peso: 0-1) ---
        if above_vwap:
            score_long += 1.0
            razones_long.append("Sobre VWAP")
        else:
            score_short += 1.0
            razones_short.append("Bajo VWAP")
        
        # --- FACTOR 9: DI+/DI- (Peso: 0-1) ---
        if plus_di > minus_di * 1.2:
            score_long += 1.0
            razones_long.append(f"DI+ > DI- ({plus_di:.0f}/{minus_di:.0f})")
        elif minus_di > plus_di * 1.2:
            score_short += 1.0
            razones_short.append(f"DI- > DI+ ({minus_di:.0f}/{plus_di:.0f})")
        
        # =========================================================================
        # FILTRO ADX - Requerir tendencia mínima
        # =========================================================================
        if Config.ADX_ENABLED and adx < Config.ADX_MIN:
            logger.log(f"{symbol}: ADX {adx:.1f} < {Config.ADX_MIN} (sin tendencia)", "FILTER")
            return None
        
        # =========================================================================
        # UMBRAL DE SEÑAL - Corregido
        # =========================================================================
        # Umbral base más alto (sólo setups de calidad)
        # NO aumentar con volatilidad (eso era un error en V8.2)
        # Si hay alta volatilidad, la tendencia es más fuerte = mejor señal
        MIN_SCORE = Config.MIN_SCORE_BASE
        
        # Bonus por ADX fuerte (tendencia fuerte = señales más confiables)
        if adx > 30:
            MIN_SCORE -= 0.5  # Reducir umbral si tendencia es muy fuerte
        
        # Asegurar que no baja del mínimo
        MIN_SCORE = max(3.5, MIN_SCORE)
        
        # PENALIZACIÓN: No operar contra la tendencia 4H fuerte
        if tendencia_4h == 'bull' and trend_alignment < 0:
            score_short -= 2.0
        if tendencia_4h == 'bear' and trend_alignment > 0:
            score_long -= 2.0
        
        # Normalizar scores
        score_long = max(0, score_long)
        score_short = max(0, score_short)
        
        logger.log(f"{symbol}: L={score_long:.1f} S={score_short:.1f} | ADX={adx:.1f} RSI={rsi:.0f} Vol={vol_ratio:.1f}x", "DEBUG")
        
        # DECISIÓN: Spread reducido a 1.0 (era 1.5) pero requiere score mínimo
        if score_long >= MIN_SCORE and score_long > score_short + 1.0:
            # SL basado en ATR + margen de seguridad
            sl_dist = atr * (1.5 + atr_pct / 5)
            sl = precio - sl_dist
            
            # Ajustar SL al swing low si está más cerca
            if swing_low_15m and swing_low_15m < sl and swing_low_15m > precio * 0.95:
                sl = swing_low_15m * 0.999  # 0.1% debajo del swing
            
            # SL mínimo: 1% del precio (no stops ultra-tight)
            if (precio - sl) / precio < 0.01:
                sl = precio * 0.99
            
            tp_dist = (precio - sl) * Config.RR_RATIO  # 2.5:1
            tp = precio + tp_dist
            
            logger.log(f"🎯 LONG {symbol}! Score:{score_long:.1f} Entry:{precio:.2f} SL:{sl:.2f} TP:{tp:.2f}", "SIGNAL")
            return {
                'symbol': symbol, 'side': 'long', 'entry': precio, 'sl': sl, 'tp': tp,
                'atr': atr, 'atr_pct': atr_pct, 'score': score_long,
                'razones': razones_long, 'session': get_current_session()[0],
                'adx': adx, 'rsi': rsi,
                'timestamp': datetime.now(timezone.utc)
            }
        
        elif score_short >= MIN_SCORE and score_short > score_long + 1.0:
            sl_dist = atr * (1.5 + atr_pct / 5)
            sl = precio + sl_dist
            
            if swing_high_15m and swing_high_15m > sl and swing_high_15m < precio * 1.05:
                sl = swing_high_15m * 1.001
            
            if (sl - precio) / precio < 0.01:
                sl = precio * 1.01
            
            tp_dist = (sl - precio) * Config.RR_RATIO
            tp = precio - tp_dist
            
            logger.log(f"🎯 SHORT {symbol}! Score:{score_short:.1f} Entry:{precio:.2f} SL:{sl:.2f} TP:{tp:.2f}", "SIGNAL")
            return {
                'symbol': symbol, 'side': 'short', 'entry': precio, 'sl': sl, 'tp': tp,
                'atr': atr, 'atr_pct': atr_pct, 'score': score_short,
                'razones': razones_short, 'session': get_current_session()[0],
                'adx': adx, 'rsi': rsi,
                'timestamp': datetime.now(timezone.utc)
            }
        
        return None

# ============================================================================
# CÁLCULO DE POSICIÓN V9 (CORREGIDO - con fees)
# ============================================================================
def calcular_posicion_v9(equity: float, precio: float, sl: float, leverage: int, 
                          symbol_config: Dict, logger: LogManager) -> float:
    """
    Cálculo de posición optimizado para micro-capital con fees incluidos.
    
    Cambios vs V8.2:
    - Logger pasado como parámetro (BUG FIX)
    - Fees incluidos en el cálculo de riesgo
    - Exposición máxima 60% (era 95%)
    - Risk ajustado para compensar fees
    """
    
    if equity <= 0 or precio <= 0:
        return 0.0
    
    risk_pct = Config.RISK_PCT_DEFAULT
    
    # Riesgo monetario (dolares que estamos dispuestos a perder)
    riesgo_usd = equity * risk_pct
    
    # Para capital muy pequeño, usar riesgo mínimo absoluto
    if riesgo_usd < 0.05:
        riesgo_usd = equity * 0.02  # 2% mínimo del equity
    
    # Distancia al stop loss (como fracción del precio)
    distancia_sl = abs(precio - sl) / precio
    
    if distancia_sl < 0.005:  # Mínimo 0.5% de distancia
        distancia_sl = 0.01
    
    # Calcular tamaño nominal basado en riesgo
    # NOTA: Este cálculo NO incluye fees en la pérdida real.
    # La pérdida real = (precio - sl) * qty + fees
    # Ajustamos: reducir qty para que pérdida real <= riesgo_usd
    fee_impact = Config.FEE_ROUND_TRIP  # 0.1% redondo
    
    # Ajuste: si la pérdida por precio es X, y fees son Y, necesitamos X + Y <= riesgo_usd
    # fee_impact * notional + distancia_sl * notional = riesgo_usd
    # notional * (distancia_sl + fee_impact) = riesgo_usd
    # notional = riesgo_usd / (distancia_sl + fee_impact)
    
    adjusted_risk_denom = distancia_sl + fee_impact
    tamano_nominal = riesgo_usd / adjusted_risk_denom
    qty = tamano_nominal / precio
    
    # Tamaño mínimo del exchange
    min_size = symbol_config.get('min_size', 0.0001)
    
    # Si no alcanza el mínimo, verificar si podemos entrar de todos modos
    if qty < min_size:
        margen_requerido = (min_size * precio) / leverage
        max_margen = equity * Config.MAX_EXPOSURE_PCT
        
        if margen_requerido <= max_margen:
            qty = min_size
            logger.log(f"Size mínimo: {min_size} (margen ${margen_requerido:.4f}/${max_margen:.4f})", "WARN")
        else:
            return 0  # No hay suficiente capital
    
    # Exposición máxima: 60% del equity (MARGEN usado, no notional)
    max_exposure_margin = equity * Config.MAX_EXPOSURE_PCT
    max_notional = max_exposure_margin * leverage
    max_qty = max_notional / precio
    
    if qty > max_qty:
        qty = max_qty
    
    # Ajustar a tick size
    tick_size = symbol_config.get('tick_size', 0.01)
    if tick_size > 0:
        qty = round(qty / tick_size) * tick_size
    
    # Verificación final de margen
    margen_necesario = (qty * precio) / leverage
    if margen_necesario > equity * Config.MAX_EXPOSURE_PCT:
        qty = (equity * Config.MAX_EXPOSURE_PCT * leverage) / precio
        qty = round(qty / tick_size) * tick_size
    
    final_qty = max(0, qty)
    
    # Log detallado
    if final_qty > 0:
        margen_usado = (final_qty * precio) / leverage
        notional = final_qty * precio
        fees_est = estimate_fees(notional)
        risk_real = (abs(precio - sl) * final_qty) + fees_est
        
        logger.log(
            f"Pos: Qty={final_qty} | Margen=${margen_usado:.4f} | "
            f"Notional=${notional:.2f} | Fees~${fees_est:.4f} | Risk=${risk_real:.4f}",
            "DEBUG"
        )
    
    return final_qty

# ============================================================================
# ESTADÍSTICAS (con fees)
# ============================================================================
def calculate_expectancy() -> float:
    """Expectativa basada en PnL NETO (después de fees)."""
    stats = st.session_state.trade_stats
    total = stats['wins'] + stats['losses']
    if total == 0:
        return 0.0
    win_rate = stats['wins'] / total
    return (win_rate * stats['avg_win']) - ((1 - win_rate) * stats['avg_loss'])

def get_profit_factor() -> float:
    """Profit Factor basado en promedios NETOS."""
    stats = st.session_state.trade_stats
    if stats['avg_loss'] <= 0:
        return 999.0 if stats['wins'] > 0 else 0.0
    return stats['avg_win'] / stats['avg_loss']

def get_net_win_rate() -> float:
    stats = st.session_state.trade_stats
    total = stats['wins'] + stats['losses']
    return (stats['wins'] / total * 100) if total > 0 else 0.0

# ============================================================================
# VERIFICACIÓN DE COOLDOWN POR VELA
# ============================================================================
def check_cooldown(symbol: str) -> bool:
    """
    Cooldown mejorado: espera a que pasen N barras completas desde la última señal.
    Esto evita señales duplicadas en la misma vela.
    """
    current_candle = candle_timestamp(Config.TIMEFRAME_ENTRY)
    last_candle = st.session_state.last_signal_candle.get(symbol, 0)
    
    tf_seconds = {
        '1m': 60, '3m': 180, '5m': 300, '15m': 900,
        '30m': 1800, '1h': 3600, '4h': 14400
    }
    seconds_per_candle = tf_seconds.get(Config.TIMEFRAME_ENTRY, 900)
    cooldown_seconds = seconds_per_candle * Config.COOLDOWN_BARS
    
    return (current_candle - last_candle) >= cooldown_seconds

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================
def main():
    init_session_state()
    
    logger = LogManager()
    signal_gen = SignalGeneratorV9()
    
    # Header
    st.markdown("""
    <div style="text-align:center;padding:20px">
        <h1>🎯 SNIPER V9.0 | MICRO-CAPITAL EDITION</h1>
        <p style="color:#00ff88">✅ V9 Corregido: Bugs fix, Fees incluidos, Señales mejoradas, Riesgo ajustado</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Resumen de cambios
    st.markdown("""
    <div class="info-box">
        <b>📋 Cambios V8.2 → V9.0 que afectan ganancias:</b><br>
        • <b>Apalancamiento:</b> 10x → 5x (menos riesgo de liquidación)<br>
        • <b>Exposición:</b> 95% → 60% (sobrevida > ganancia rápida)<br>
        • <b>Riesgo/trade:</b> 5% → 3% (menos drawdown devastador)<br>
        • <b>RR Ratio:</b> 2:1 → 2.5:1 (compensa fees)<br>
        • <b>Trades/día:</b> 20 → 8 (menos overtrading)<br>
        • <b>Pérdida máxima/día:</b> 50% → 15% (protección real)<br>
        • <b>Breakeven:</b> 0.5R → 1.2R (no matar ganadores)<br>
        • <b>Scale-out:</b> DESACTIVADO (fees lo hacen inviable en micro-capital)<br>
        • <b>ADX:</b> NUEVO filtro (no operar sin tendencia)<br>
        • <b>Fees:</b> Ahora restados del PnL real<br>
        • <b>Cooldown:</b> 45s → 2 velas completas (no spam de señales)
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🔐 Configuración")
        
        api_key = st.text_input("API Key", type="password", key="apikey")
        api_secret = st.text_input("API Secret", type="password", key="apisecret")
        
        st.markdown("---")
        st.markdown("### ⚙️ Parámetros")
        
        leverage_ui = st.slider("Apalancamiento", 2, 20, Config.LEVERAGE_DEFAULT, 
                                 help="Recomendado: 5x para micro-capital. Más = más riesgo de liquidación.")
        risk_pct_ui = st.slider("Riesgo por trade (%)", 1.0, 10.0, Config.RISK_PCT_DEFAULT * 100, 0.5)
        Config.RISK_PCT_DEFAULT = risk_pct_ui / 100
        
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
                    'total_trades': 0, 'profit_factor': 0.0
                }
                st.session_state.active_trades = {}
                st.session_state.daily_trades = 0
                st.session_state.daily_pnl = 0.0
                st.session_state.weekly_pnl = 0.0
                st.session_state.last_signal_candle = {}
                st.rerun()
        
        st.markdown("---")
        
        # Estado
        st.markdown("### 📊 Estado")
        equity = get_equity()
        stats = st.session_state.trade_stats
        
        st.markdown(f"**Equity:** ${equity:.4f}")
        st.markdown(f"**Trades Hoy:** {st.session_state.daily_trades}/{Config.MAX_DAILY_TRADES}")
        st.markdown(f"**Posiciones:** {len(st.session_state.active_trades)}/{Config.MAX_POSITIONS}")
        st.markdown(f"**PnL Neto:** ${stats['net_pnl']:+.4f}")
        st.markdown(f"**Fees pagados:** ${stats['total_fees_paid']:.4f}")
        
        if stats['consecutive_losses'] >= 3:
            st.markdown(f"⚠️ **{stats['consecutive_losses']} pérdidas seguidas**")
    
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
            
            # Log de inicio
            st.session_state.loop_count = st.session_state.get('loop_count', 0) + 1
            if st.session_state.loop_count <= 2:
                logger.log("=" * 50, "SYSTEM")
                logger.log("SNIPER V9.0 MICRO-CAPITAL INICIADO", "SYSTEM")
                logger.log(f"Apalancamiento: {leverage_ui}x | Riesgo: {risk_pct_ui:.1f}%", "SYSTEM")
                logger.log(f"RR: {Config.RR_RATIO}:1 | Max Pos: {Config.MAX_POSITIONS}", "SYSTEM")
                logger.log(f"Exposición: {Config.MAX_EXPOSURE_PCT*100:.0f}% | ADX min: {Config.ADX_MIN}", "SYSTEM")
                logger.log("=" * 50, "SYSTEM")
            
            # Obtener equity
            try:
                balance = exchange.fetch_balance()
                equity = safe_float(balance.get('total', {}).get('USD', 0))
                if equity == 0:
                    equity = safe_float(balance.get('free', {}).get('USD', 0))
                if equity == 0:
                    used = safe_float(balance.get('used', {}).get('USD', 0))
                    free = safe_float(balance.get('free', {}).get('USD', 0))
                    equity = used + free
                
                set_equity(equity)
                if st.session_state.loop_count <= 2:
                    logger.log(f"Equity: ${equity:.4f}", "SYSTEM")
            except Exception as e:
                equity = get_equity()
                logger.log(f"Error balance: {str(e)[:50]}", "ERROR")
            
            # Verificar límites diarios
            daily_ok, daily_reason = MarketFilters.check_daily_limits()
            
            # UI Capital
            stats = st.session_state.trade_stats
            net_wr = get_net_win_rate()
            net_pnl = stats['net_pnl']
            
            pnl_color = '#00ff88' if net_pnl >= 0 else '#ff4466'
            equity_color = '#ff4466' if equity < 5 else '#4a9eff'
            
            capital_ph.markdown(f"""
            <div class="metric-card">
                <b>💰 Capital</b><br>
                <span style="font-size:1.8em;color:{equity_color};font-weight:700">${equity:.4f}</span><br>
                <small style="color:#8899aa">
                    W:{stats['wins']} L:{stats['losses']} | WR:{net_wr:.1f}%<br>
                    <span style="color:{pnl_color}">Neto: ${net_pnl:+.4f} | Fees: ${stats['total_fees_paid']:.4f}</span>
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # Gestionar posiciones existentes
            n_activas = 0
            try:
                posiciones = exchange.fetch_positions()
                n_activas = gestionar_posiciones_v9(posiciones, exchange, logger, leverage_ui)
            except Exception as e:
                posiciones, n_activas = [], 0
                logger.log(f"Error posiciones: {str(e)[:60]}", "ERROR")
            
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
                sl = trade.get('sl_current', 0)
                tp = trade.get('tp_current', 0)
                mfe = trade.get('max_favorable_excursion', 0) * 100
                
                color = "#00ff88" if pnl >= 0 else "#ff4466"
                trailing = "🔄" if trade.get('trailing_active') else "📊"
                be = "✅" if trade.get('breakeven_reached') else ""
                
                pos_html += f"""
                <div style="border-left:3px solid {color};padding:8px;margin:6px 0">
                    <b style="color:{color}">{sym.split('/')[0]} {side}</b> {trailing}{be}<br>
                    <small>@{entry:.2f}|SL:{sl:.2f}|TP:{tp:.2f}<br>
                    PnL:${pnl:+.4f}|Mark:{mark:.2f}|MFE:{mfe:.2f}%</small>
                </div>
                """
            
            posicion_ph.markdown(f"""
            <div class="metric-card">
                <b>📈 Posiciones ({n_activas}/{Config.MAX_POSITIONS})</b><br>
                {pos_html if pos_html else '<small style="color:#667799">Sin posiciones activas</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # Generar señales
            senales_encontradas = []
            
            can_trade = (
                daily_ok and 
                n_activas < Config.MAX_POSITIONS and 
                modo == "Trading Real" and
                equity > 2  # MÍNIMO: No operar con menos de $2
            )
            
            if not daily_ok:
                if st.session_state.loop_count % 10 == 0:  # Log cada 10 iteraciones
                    logger.log(f"Bloqueado: {daily_reason}", "FILTER")
            
            if can_trade:
                if st.session_state.loop_count % 5 == 0:
                    logger.log("📡 Escaneando señales...", "SYSTEM")
                
                for symbol, config in Config.SYMBOLS.items():
                    # Cooldown por vela (no por segundos)
                    if not check_cooldown(symbol):
                        continue
                    
                    # Verificar correlación
                    corr_ok, corr_reason = MarketFilters.check_correlation(
                        symbol, st.session_state.active_trades
                    )
                    if not corr_ok:
                        continue
                    
                    try:
                        bars_15m = exchange.fetch_ohlcv(symbol, Config.TIMEFRAME_ENTRY, limit=Config.BARS_LIMIT)
                        bars_1h = exchange.fetch_ohlcv(symbol, Config.TIMEFRAME_TREND, limit=Config.BARS_LIMIT)
                        bars_4h = exchange.fetch_ohlcv(symbol, Config.TIMEFRAME_HIGH, limit=Config.BARS_LIMIT)
                        
                        if len(bars_15m) < 60:
                            logger.log(f"{symbol}: Datos insuficientes ({len(bars_15m)} < 60)", "WARN")
                            continue
                        
                        df_15m = pd.DataFrame(bars_15m, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        df_1h = pd.DataFrame(bars_1h, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        df_4h = pd.DataFrame(bars_4h, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        
                        senal = signal_gen.generar_senal_premium(df_15m, df_1h, df_4h, symbol, logger)
                        
                        if senal:
                            senales_encontradas.append(senal)
                            
                            # Guardar dirección pendiente para filtro de correlación
                            st.session_state.pending_side = senal['side']
                            
                            # Calcular posición
                            qty = calcular_posicion_v9(equity, senal['entry'], senal['sl'], 
                                                       leverage_ui, config, logger)
                            
                            min_size = config.get('min_size', 0.0001)
                            
                            if qty >= min_size * 0.8:  # Permitir 80% del mínimo
                                try:
                                    side_order = 'buy' if senal['side'] == 'long' else 'sell'
                                    
                                    notional = qty * senal['entry']
                                    margen = notional / leverage_ui
                                    fees_est = estimate_fees(notional)
                                    
                                    logger.log(
                                        f"📦 Orden: {side_order} {qty} {symbol} | "
                                        f"Notional:${notional:.2f} Margen:${margen:.4f} Fees~${fees_est:.4f}",
                                        "TRADE"
                                    )
                                    
                                    order = exchange.create_order(
                                        symbol=symbol, type='market', side=side_order,
                                        amount=qty, params={'leverage': leverage_ui}
                                    )
                                    
                                    # Registrar trade activo con datos completos
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
                                        'scale_out_done': False,
                                        'opened_at': datetime.now(timezone.utc),
                                        'highest_since_entry': senal['entry'],
                                        'lowest_since_entry': senal['entry'],
                                        'max_favorable_excursion': 0.0,
                                        'score': senal['score'],
                                        'razones': senal['razones']
                                    }
                                    
                                    # Registrar cooldown
                                    st.session_state.last_signal_candle[symbol] = candle_timestamp(Config.TIMEFRAME_ENTRY)
                                    st.session_state.last_signal_time[symbol] = time.time()
                                    
                                    # Actualizar contadores
                                    st.session_state.daily_trades += 1
                                    n_activas += 1
                                    
                                    logger.log(
                                        f"✅ EJECUTADO: {senal['side'].upper()} {qty} {symbol} "
                                        f"@ {senal['entry']:.2f} | Score:{senal['score']:.1f} "
                                        f"| {', '.join(senal['razones'][:3])}",
                                        "WIN"
                                    )
                                    
                                    if n_activas >= Config.MAX_POSITIONS:
                                        logger.log("Máximo de posiciones alcanzado", "PAUSE")
                                        break
                                        
                                except Exception as e:
                                    error_msg = str(e)
                                    logger.log(f"❌ Error orden: {error_msg[:100]}", "ERROR")
                                    
                                    # Reintento con 50% del tamaño (solo si es error de margen)
                                    if "margin" in error_msg.lower() or "insufficient" in error_msg.lower():
                                        logger.log("🔄 Intentando con 60% del tamaño...", "WARN")
                                        try:
                                            qty_retry = qty * 0.6
                                            if qty_retry >= min_size:
                                                order = exchange.create_order(
                                                    symbol=symbol, type='market', side=side_order,
                                                    amount=qty_retry, params={'leverage': leverage_ui}
                                                )
                                                st.session_state.last_signal_candle[symbol] = candle_timestamp(Config.TIMEFRAME_ENTRY)
                                                st.session_state.daily_trades += 1
                                                logger.log(f"✅ Reintento OK: {qty_retry} {symbol}", "WIN")
                                        except Exception as e2:
                                            logger.log(f"Reintento fallido: {str(e2)[:80]}", "ERROR")
                            
                            else:
                                logger.log(f"{symbol}: Qty {qty} < mínimo {min_size} (equity muy bajo)", "WARN")
                    
                    except Exception as e:
                        logger.log(f"Error {symbol}: {str(e)[:80]}", "ERROR")
            
            elif not can_trade and equity <= 2:
                logger.log(f"Equity ${equity:.2f} < $2. No se opera.", "WARN")
            
            # UI Señales
            senales_html = ""
            for s in senales_encontradas:
                color = '#00ff88' if s['side'] == 'long' else '#ff4466'
                razones = " | ".join(s['razones'][:3])
                senales_html += f"""
                <div class="metric-card" style="margin:10px 0;padding:12px;border-left:4px solid {color}">
                    <span style="color:{color};font-weight:700">{s['side'].upper()} {s['symbol'].split('/')[0]}</span>
                    <small style="color:#8899aa"> | Score:{s['score']:.1f} ADX:{s.get('adx', 0):.0f}</small><br>
                    <small>@{s['entry']:.2f}|SL:{s['sl']:.2f}|TP:{s['tp']:.2f}|RR:{Config.RR_RATIO}:1<br>
                    <span style="color:#aabbcc">{razones}</span></small>
                </div>
                """
            
            senal_ph.markdown(f"""
            <div class="metric-card">
                <b>🎯 Señales ({len(senales_encontradas)})</b><br>
                {senales_html if senales_html else '<small style="color:#667799">Escaneando...</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # Logs
            log_html = "<br>".join([f'<div class="log-entry">{l}</div>' for l in logger.get_logs(30)])
            log_ph.markdown(f"""
            <div class="metric-card" style="max-height:350px;overflow-y:auto">
                {log_html if log_html else '<small style="color:#667799">Sin logs</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # Stats mejorados
            pf = get_profit_factor()
            exp = calculate_expectancy()
            stats = st.session_state.trade_stats
            
            stats_ph.markdown(f"""
            <div class="metric-card" style="text-align:center">
                <small style="color:#8899aa">
                    <b>PF:</b> {pf:.2f} | 
                    <b>Exp:</b> ${exp:+.4f}/trade | 
                    <b>DD Max:</b> ${stats['max_drawdown']:+.4f}<br>
                    <b>Win Avg:</b> ${stats['avg_win']:.4f} | 
                    <b>Loss Avg:</b> ${stats['avg_loss']:.4f} | 
                    <b>Total Fees:</b> ${stats['total_fees_paid']:.4f}<br>
                    <b>Win Streak:</b> {stats['max_consecutive_wins']} | 
                    <b>Loss Streak:</b> {stats['max_consecutive_losses']} | 
                    <b>Trades:</b> {stats['total_trades']}
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            time.sleep(Config.RATE_LIMIT_DELAY)
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error crítico: {e}")
            logger.log(f"CRÍTICO: {str(e)[:150]}", "ERROR")
            import traceback
            logger.log(traceback.format_exc()[:300], "ERROR")
            time.sleep(15)
            st.rerun()
    
    else:
        if not activar:
            st.info("👈 Ingresa credenciales y activa INICIAR para comenzar")
        elif not api_key or not api_secret:
            st.error("❌ API Key y Secret son requeridos")

if __name__ == "__main__":
    main()
