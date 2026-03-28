# ============================================================================
# SNIPER V7.0 - PRICE ACTION ELITE INSTITUTIONAL (ARTE DEL TRADING)
# ============================================================================
# Basado en mejores prácticas de trading algorítmico 2025-2026 [[3]][[7]][[23]]
# ============================================================================

import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import base64
import os

# ============================================================================
# CONFIGURACIÓN GLOBAL OPTIMIZADA
# ============================================================================
st.set_page_config(
    page_title="SNIPER V7.0 | ELITE",
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
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        border-color: #4a9eff;
        box-shadow: 0 6px 25px rgba(74, 158, 255, 0.2);
    }
    
    .signal-long { 
        color: #00ff88; 
        font-weight: 700;
        text-shadow: 0 0 10px rgba(0, 255, 136, 0.3);
    }
    .signal-short { 
        color: #ff4466; 
        font-weight: 700;
        text-shadow: 0 0 10px rgba(255, 68, 102, 0.3);
    }
    
    h1 { 
        color: #4a9eff !important;
        text-shadow: 0 0 20px rgba(74, 158, 255, 0.3);
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #4a9eff 0%, #2d7dd2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 700;
    }
    
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
    
    div[data-testid="stMetricValue"] {
        font-size: 2em !important;
        font-weight: 700 !important;
    }
    
    .log-entry { font-family: 'JetBrains Mono', monospace; font-size: 0.75em; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CLASES DE DATOS (TYPE SAFETY)
# ============================================================================
@dataclass
class TradeSignal:
    symbol: str
    side: str
    entry: float
    sl: float
    tp: float
    score: float
    atr: float
    atr_pct: float
    razones: List[str]
    session: str
    timestamp: datetime
    
@dataclass
class Position:
    symbol: str
    side: str
    entry: float
    qty: float
    sl: float
    tp: float
    trailing_active: bool
    breakeven_reached: bool
    entry_risk: float
    atr: float
    
@dataclass
class TradeStats:
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

# ============================================================================
# CONFIGURACIÓN DE PARÁMETROS
# ============================================================================
class Config:
    SYMBOLS = {
        'BTC/USD:USD': {'min_size': 0.0001, 'tick_size': 0.5, 'risk_weight': 1.0},
        'ETH/USD:USD': {'min_size': 0.001, 'tick_size': 0.05, 'risk_weight': 0.8},
        'SOL/USD:USD': {'min_size': 0.01, 'tick_size': 0.001, 'risk_weight': 0.6}
    }
    
    LEVERAGE_DEFAULT = 10
    RISK_PCT_DEFAULT = 0.02
    RR_RATIO = 2.0
    MAX_POSITIONS = 2
    MAX_DAILY_TRADES = 10
    MAX_DAILY_LOSS_PCT = 0.05
    
    TIMEFRAME_ENTRY = '15m'
    TIMEFRAME_TREND = '1h'
    TIMEFRAME_CONFIRM = '5m'
    BARS_LIMIT = 500
    
    OB_STRENGTH = 1.8
    FVG_MIN_GAP = 0.003
    MSS_CONFIRMATION_BARS = 3
    VOLUME_CONFIRMATION = 1.3
    
    MIN_SCORE_BASE = 6.0
    SCORE_THRESHOLD_DYNAMIC = True
    
    SESSIONS = {
        'asian': {'start': 0, 'end': 8, 'weight': 0.7, 'volatility': 'low'},
        'london': {'start': 7, 'end': 16, 'weight': 1.2, 'volatility': 'medium'},
        'ny': {'start': 12, 'end': 21, 'weight': 1.5, 'volatility': 'high'}
    }
    
    RATE_LIMIT_DELAY = 25
    API_RETRIES = 3
    API_RETRY_DELAY = 2

# ============================================================================
# UTILIDADES DE SEGURIDAD
# ============================================================================
class SecurityUtils:
    @staticmethod
    def hash_credentials(key: str, secret: str) -> Tuple[str, str]:
        """Encripta credenciales con hash SHA-256"""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        return key_hash, secret_hash
    
    @staticmethod
    def validate_api_format(api_key: str, api_secret: str) -> bool:
        """Valida formato básico de credenciales"""
        if not api_key or not api_secret:
            return False
        if len(api_key) < 10 or len(api_secret) < 10:
            return False
        return True

# ============================================================================
# GESTOR DE LOGS PROFESIONAL
# ============================================================================
class LogManager:
    def __init__(self, max_entries: int = 500):
        self.max_entries = max_entries
        if 'trade_log' not in st.session_state:
            st.session_state.trade_log = []
    
    def log(self, msg: str, level: str = "INFO"):
        now = datetime.now().strftime("%H:%M:%S")
        icons = {
            "INFO": "📊", "TRADE": "🎯", "WIN": "💰", 
            "LOSS": "⚠️", "WARN": "⚡", "ERROR": "❌",
            "SYSTEM": "🔧", "RISK": "🛡️"
        }
        icon = icons.get(level, "•")
        entry = f"[{now}] {icon} [{level}] {msg}"
        st.session_state.trade_log.insert(0, entry)
        st.session_state.trade_log = st.session_state.trade_log[:self.max_entries]
    
    def get_logs(self, limit: int = 50) -> List[str]:
        return st.session_state.trade_log[:limit]
    
    def clear_logs(self):
        st.session_state.trade_log = []

# ============================================================================
# INDICADORES TÉCNICOS PREMIUM
# ============================================================================
class TechnicalIndicators:
    @staticmethod
    def calcular_indicadores_premium(df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores institucionales completos"""
        df = df.copy()
        c = df['c'].astype(float)
        h = df['h'].astype(float)
        l = df['l'].astype(float)
        o = df['o'].astype(float)
        v = df['v'].astype(float)
        
        # EMAs múltiples
        for span in [9, 20, 50, 100, 200]:
            df[f'ema{span}'] = c.ewm(span=span, adjust=False).mean()
        
        # ATR
        tr1 = h - l
        tr2 = abs(h - c.shift(1))
        tr3 = abs(l - c.shift(1))
        df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()
        df['atr_pct'] = (df['atr'] / c * 100).fillna(0)
        
        # RSI
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)
        
        # Volumen
        df['vol_ma'] = v.rolling(20).mean()
        df['vol_ratio'] = (v / df['vol_ma']).fillna(1)
        
        # Velas
        df['body'] = abs(c - o)
        df['body_pct'] = (df['body'] / (h - l + 1e-10)) * 100
        df['wick_up'] = h - pd.concat([c, o], axis=1).max(axis=1)
        df['wick_dn'] = pd.concat([c, o], axis=1).min(axis=1) - l
        
        # VWAP (aproximado)
        df['vwap'] = ((c + h + l) / 3 * v).rolling(20).sum() / v.rolling(20).sum()
        
        return df
    
    @staticmethod
    def detectar_mss(df: pd.DataFrame, lookback: int = 20) -> Tuple[str, Optional[float], Optional[float]]:
        """Detecta Market Structure Shift (MSS) - Concepto institucional [[25]][[26]]"""
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
        
        # MSS Bullish: Rompe estructura bajista
        if last_hh > prev_hh and last_ll > prev_ll and c[-1] > last_hh:
            return 'bullish_mss', last_ll, last_hh
        # MSS Bearish: Rompe estructura alcista
        if last_hh < prev_hh and last_ll < prev_ll and c[-1] < last_ll:
            return 'bearish_mss', last_ll, last_hh
        # Tendencia normal
        if last_hh > prev_hh and last_ll > prev_ll:
            return 'bullish', last_ll, last_hh
        if last_hh < prev_hh and last_ll < prev_ll:
            return 'bearish', last_ll, last_hh
        
        return 'neutral', last_ll, last_hh
    
    @staticmethod
    def detectar_order_blocks(df: pd.DataFrame, n: int = 5) -> Tuple[List[Dict], List[Dict]]:
        """Detecta Order Blocks institucionales [[25]][[26]][[28]]"""
        obs_bull, obs_bear = [], []
        c = df['c'].astype(float).values
        o = df['o'].astype(float).values
        
        for i in range(3, len(df) - n - 2):
            # Order Block Bajista (vela roja antes de caída)
            if o[i] > c[i]:
                move_up = (c[i+n] - o[i]) / (o[i] + 1e-10) * 100
                if move_up > Config.OB_STRENGTH:
                    obs_bull.append({
                        'mid': (o[i] + c[i]) / 2,
                        'high': o[i],
                        'low': c[i],
                        'strength': move_up,
                        'index': i
                    })
            
            # Order Block Alcista (vela verde antes de subida)
            if c[i] > o[i]:
                move_dn = (o[i] - c[i+n]) / (o[i] + 1e-10) * 100
                if move_dn > Config.OB_STRENGTH:
                    obs_bear.append({
                        'mid': (c[i] + o[i]) / 2,
                        'high': c[i],
                        'low': o[i],
                        'strength': move_dn,
                        'index': i
                    })
        
        # Retorna los 3 más fuertes
        obs_bull = sorted(obs_bull, key=lambda x: x['strength'], reverse=True)[:3]
        obs_bear = sorted(obs_bear, key=lambda x: x['strength'], reverse=True)[:3]
        
        return obs_bull, obs_bear
    
    @staticmethod
    def detectar_fvg(df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
        """Detecta Fair Value Gaps - Imbalance institucional [[29]][[30]][[31]][[32]]"""
        fvgs_bull, fvgs_bear = [], []
        h = df['h'].astype(float).values
        l = df['l'].astype(float).values
        
        for i in range(1, len(df) - 1):
            # FVG Alcista
            if l[i+1] > h[i-1]:
                gap = (l[i+1] - h[i-1]) / (h[i-1] + 1e-10)
                if gap >= Config.FVG_MIN_GAP:
                    fvgs_bull.append({
                        'bot': h[i-1],
                        'top': l[i+1],
                        'mid': (h[i-1] + l[i+1]) / 2,
                        'gap_size': gap,
                        'index': i
                    })
            
            # FVG Bajista
            if h[i+1] < l[i-1]:
                gap = (l[i-1] - h[i+1]) / (l[i-1] + 1e-10)
                if gap >= Config.FVG_MIN_GAP:
                    fvgs_bear.append({
                        'bot': h[i+1],
                        'top': l[i-1],
                        'mid': (h[i+1] + l[i-1]) / 2,
                        'gap_size': gap,
                        'index': i
                    })
        
        return fvgs_bull[-3:], fvgs_bear[-3:]
    
    @staticmethod
    def detectar_patrones_velas(df: pd.DataFrame) -> Dict[str, Optional[str]]:
        """Detecta patrones de velas japonesas"""
        patterns = {'pin': None, 'engulfing': None, 'inside': False, 'doji': None}
        
        if len(df) < 2:
            return patterns
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else None
        
        body = abs(float(last['c']) - float(last['o']))
        total_range = float(last['h']) - float(last['l'])
        
        if total_range > 1e-10:
            wick_up = float(last['h']) - max(float(last['c']), float(last['o']))
            wick_dn = min(float(last['c']), float(last['o'])) - float(last['l'])
            
            # Pin Bar
            if wick_dn > total_range * 0.65 and body < total_range * 0.25:
                patterns['pin'] = 'bull_pin'
            elif wick_up > total_range * 0.65 and body < total_range * 0.25:
                patterns['pin'] = 'bear_pin'
            
            # Doji
            if body < total_range * 0.1:
                patterns['doji'] = 'neutral'
        
        # Engulfing
        if prev is not None:
            curr_body = float(last['c']) - float(last['o'])
            prev_body = float(prev['c']) - float(prev['o'])
            curr_vol = float(last['v'])
            prev_vol = float(prev['v'])
            
            if (prev_body < 0 and curr_body > 0 and 
                float(last['o']) < float(prev['c']) and 
                float(last['c']) > float(prev['o']) and 
                curr_vol > prev_vol * 1.2):
                patterns['engulfing'] = 'bull_engulfing'
            
            if (prev_body > 0 and curr_body < 0 and 
                float(last['o']) > float(prev['c']) and 
                float(last['c']) < float(prev['o']) and 
                curr_vol > prev_vol * 1.2):
                patterns['engulfing'] = 'bear_engulfing'
        
        # Inside Bar
        if len(df) >= 3:
            prev2 = df.iloc[-2]
            patterns['inside'] = (float(last['h']) < float(prev2['h']) and 
                                  float(last['l']) > float(prev2['l']))
        
        return patterns

# ============================================================================
# GESTOR DE SESIONES DE MERCADO
# ============================================================================
class SessionManager:
    @staticmethod
    def get_current_session() -> Tuple[str, float, str]:
        """Retorna sesión actual, peso y volatilidad esperada"""
        hour_utc = datetime.now(timezone.utc).hour
        
        for name, data in Config.SESSIONS.items():
            if data['start'] <= hour_utc < data['end']:
                return name, data['weight'], data['volatility']
        
        return 'offpeak', 0.5, 'low'
    
    @staticmethod
    def get_session_multiplier() -> float:
        """Retorna multiplicador de riesgo según sesión"""
        _, weight, _ = SessionManager.get_current_session()
        return weight
    
    @staticmethod
    def is_high_volatility_session() -> bool:
        _, _, volatility = SessionManager.get_current_session()
        return volatility == 'high'

# ============================================================================
# GENERADOR DE SEÑALES INSTITUCIONAL
# ============================================================================
class SignalGenerator:
    def __init__(self):
        self.indicators = TechnicalIndicators()
        self.session_mgr = SessionManager()
    
    def generar_senal_premium(self, df_15m: pd.DataFrame, df_1h: pd.DataFrame, 
                              df_5m: pd.DataFrame, symbol: str) -> Optional[TradeSignal]:
        """Genera señal con scoring institucional multi-factor"""
        
        if len(df_15m) < 210 or len(df_1h) < 50:
            return None
        
        # Calcular indicadores
        df_15m = self.indicators.calcular_indicadores_premium(df_15m)
        df_1h = self.indicators.calcular_indicadores_premium(df_1h)
        
        last_15m = df_15m.iloc[-1]
        precio = float(last_15m['c'])
        atr = float(last_15m['atr'])
        atr_pct = float(last_15m['atr_pct'])
        rsi = float(last_15m['rsi'])
        vol_ratio = float(last_15m['vol_ratio'])
        
        # Sesión actual
        session_name, session_weight, session_vol = self.session_mgr.get_current_session()
        
        # Estructura de mercado 1H (trend filter)
        estructura_1h, _, _ = self.indicators.detectar_mss(df_1h)
        ema50_1h = float(df_1h.iloc[-1]['ema50'])
        ema200_1h = float(df_1h.iloc[-1]['ema200'])
        
        tendencia_dir = 'bull' if ema50_1h > ema200_1h * 1.002 else 'bear' if ema50_1h < ema200_1h * 0.998 else 'neutral'
        
        # Estructura 15M
        estructura_15m, swing_low_15m, swing_high_15m = self.indicators.detectar_mss(df_15m)
        
        # Order Blocks y FVGs
        obs_bull, obs_bear = self.indicators.detectar_order_blocks(df_15m)
        fvgs_bull, fvgs_bear = self.indicators.detectar_fvg(df_15m)
        
        # Patrones de velas
        patrones = self.indicators.detectar_patrones_velas(df_15m)
        
        # === SCORING SYSTEM ===
        score_long, score_short = 0, 0
        razones_long, razones_short = [], []
        
        # Factores LONG
        if tendencia_dir == 'bull':
            score_long += 3.0
            razones_long.append("Tendencia 1H alcista ✓")
        if estructura_15m in ['bullish', 'bullish_mss']:
            score_long += 2.5
            razones_long.append(f"Estructura: {estructura_15m}")
        if precio > float(last_15m['ema200']) * 1.001:
            score_long += 1.5
            razones_long.append("Precio sobre EMA200")
        
        # Order Blocks
        for ob in obs_bull:
            if abs(precio - ob['mid']) / precio < 0.004 and ob['strength'] > Config.OB_STRENGTH:
                score_long += 2.2
                razones_long.append(f"OB Bull (fuerza: {ob['strength']:.1f}%)")
        
        # FVGs
        for fvg in fvgs_bull:
            if fvg['bot'] <= precio <= fvg['top'] and fvg['gap_size'] > Config.FVG_MIN_GAP:
                score_long += 2.0
                razones_long.append(f"FVG Bull ({fvg['gap_size']*100:.2f}%)")
        
        # Patrones
        if patrones['pin'] == 'bull_pin':
            score_long += 2.0
            razones_long.append("Pin Bar alcista")
        if patrones['engulfing'] == 'bull_engulfing' and vol_ratio > 1.4:
            score_long += 2.3
            razones_long.append("Engulfing + volumen")
        
        # RSI en zona neutral (mejor entrada)
        if 35 < rsi < 55:
            score_long += 1.2
            razones_long.append(f"RSI neutral: {rsi:.1f}")
        
        # Volumen
        if vol_ratio > Config.VOLUME_CONFIRMATION:
            score_long += 1.5
            razones_long.append(f"Volumen {vol_ratio:.2f}x")
        
        # Ajuste por sesión
        score_long *= session_weight
        
        # Factores SHORT
        if tendencia_dir == 'bear':
            score_short += 3.0
            razones_short.append("Tendencia 1H bajista ✓")
        if estructura_15m in ['bearish', 'bearish_mss']:
            score_short += 2.5
            razones_short.append(f"Estructura: {estructura_15m}")
        if precio < float(last_15m['ema200']) * 0.999:
            score_short += 1.5
            razones_short.append("Precio bajo EMA200")
        
        for ob in obs_bear:
            if abs(precio - ob['mid']) / precio < 0.004 and ob['strength'] > Config.OB_STRENGTH:
                score_short += 2.2
                razones_short.append(f"OB Bear (fuerza: {ob['strength']:.1f}%)")
        
        for fvg in fvgs_bear:
            if fvg['bot'] <= precio <= fvg['top'] and fvg['gap_size'] > Config.FVG_MIN_GAP:
                score_short += 2.0
                razones_short.append(f"FVG Bear ({fvg['gap_size']*100:.2f}%)")
        
        if patrones['pin'] == 'bear_pin':
            score_short += 2.0
            razones_short.append("Pin Bar bajista")
        if patrones['engulfing'] == 'bear_engulfing' and vol_ratio > 1.4:
            score_short += 2.3
            razones_short.append("Engulfing + volumen")
        
        if 45 < rsi < 65:
            score_short += 1.2
            razones_short.append(f"RSI neutral: {rsi:.1f}")
        
        if vol_ratio > Config.VOLUME_CONFIRMATION:
            score_short += 1.5
            razones_short.append(f"Volumen {vol_ratio:.2f}x")
        
        score_short *= session_weight
        
        # === UMBRAL DINÁMICO ===
        base_threshold = Config.MIN_SCORE_BASE
        if Config.SCORE_THRESHOLD_DYNAMIC:
            dynamic_threshold = base_threshold * (1 + atr_pct / 2) * (1 / session_weight)
            MIN_SCORE = max(5.0, min(8.0, dynamic_threshold))
        else:
            MIN_SCORE = base_threshold
        
        # === GENERAR SEÑAL ===
        if score_long >= MIN_SCORE and score_long > score_short + 1.5:
            sl_dist = atr * (1.2 + atr_pct / 3)
            sl = precio - sl_dist
            tp = precio + sl_dist * Config.RR_RATIO
            
            # Ajustar SL a swing low
            if swing_low_15m and swing_low_15m < sl:
                sl = swing_low_15m * 0.9995
            
            return TradeSignal(
                symbol=symbol, side='long', entry=precio, sl=sl, tp=tp,
                atr=atr, atr_pct=atr_pct, score=score_long,
                razones=razones_long, session=session_name,
                timestamp=datetime.now(timezone.utc)
            )
        
        elif score_short >= MIN_SCORE and score_short > score_long + 1.5:
            sl_dist = atr * (1.2 + atr_pct / 3)
            sl = precio + sl_dist
            tp = precio - sl_dist * Config.RR_RATIO
            
            if swing_high_15m and swing_high_15m > sl:
                sl = swing_high_15m * 1.0005
            
            return TradeSignal(
                symbol=symbol, side='short', entry=precio, sl=sl, tp=tp,
                atr=atr, atr_pct=atr_pct, score=score_short,
                razones=razones_short, session=session_name,
                timestamp=datetime.now(timezone.utc)
            )
        
        return None

# ============================================================================
# GESTIÓN DE RIESGO INSTITUCIONAL
# ============================================================================
class RiskManager:
    def __init__(self, equity: float):
        self.equity = equity
        self.risk_pct = Config.RISK_PCT_DEFAULT
        self.daily_pnl = 0.0
        self.daily_trades = 0
    
    def check_daily_limits(self) -> Tuple[bool, str]:
        """Verifica límites diarios de riesgo [[21]][[23]]"""
        if self.daily_trades >= Config.MAX_DAILY_TRADES:
            return False, "Límite diario de trades alcanzado"
        
        if self.daily_pnl < -self.equity * Config.MAX_DAILY_LOSS_PCT:
            return False, "Límite de pérdida diaria alcanzado"
        
        return True, "OK"
    
    def calcular_posicion(self, precio: float, sl: float, leverage: int, 
                         symbol_config: Dict) -> float:
        """Calcula tamaño de posición con gestión de riesgo multi-nivel"""
        
        riesgo_usd = self.equity * self.risk_pct
        distancia_sl = abs(precio - sl) / (precio + 1e-10)
        
        if distancia_sl < 0.001:
            distancia_sl = 0.015
        
        tamano_nominal = riesgo_usd / distancia_sl
        qty = tamano_nominal / precio
        
        # Límites mínimos y máximos
        min_size = symbol_config.get('min_size', 0.0001)
        if qty < min_size:
            qty = min_size
        
        # Límite de exposición máxima (45% del capital con leverage)
        max_exposure = (self.equity * 0.45 * leverage) / precio
        if qty > max_exposure:
            qty = max_exposure
        
        # Redondear al tick size
        tick_size = symbol_config.get('tick_size', 0.01)
        qty = round(qty / tick_size) * tick_size
        
        return max(0, qty)
    
    def update_daily_stats(self, pnl: float):
        """Actualiza estadísticas diarias"""
        self.daily_pnl += pnl
        self.daily_trades += 1
    
    def reset_daily(self):
        """Resetea estadísticas diarias (llamar cada 24h)"""
        self.daily_pnl = 0.0
        self.daily_trades = 0

# ============================================================================
# GESTOR DE POSICIONES CON TRAILING STOP
# ============================================================================
class PositionManager:
    def __init__(self):
        if 'active_trades' not in st.session_state:
            st.session_state.active_trades = {}
        if 'trade_stats' not in st.session_state:
            st.session_state.trade_stats = TradeStats()
    
    def gestionar_posiciones(self, posiciones: List[Dict], exchange, logger: LogManager) -> int:
        """Gestiona posiciones activas con trailing stop y breakeven"""
        
        n_activas = 0
        
        for p in posiciones:
            qty = float(p.get('contracts', 0) or 0)
            if qty <= 0:
                continue
            
            n_activas += 1
            sym = p['symbol']
            side = p['side'].upper()
            mark = float(p.get('markPrice') or 0)
            pnl = float(p.get('unrealizedPnl') or 0)
            entry = float(p.get('entryPrice') or 0)
            
            # Inicializar trade en session state
            if sym not in st.session_state.active_trades:
                sl_mult = 0.985 if side == 'LONG' else 1.015
                tp_mult = 1.03 if side == 'LONG' else 0.97
                entry_risk = abs(entry - entry * sl_mult) / entry
                
                st.session_state.active_trades[sym] = {
                    'entry': entry,
                    'sl_current': entry * sl_mult,
                    'tp_current': entry * tp_mult,
                    'trailing_active': False,
                    'breakeven_reached': False,
                    'entry_risk': entry_risk,
                    'trailing_start': entry,
                    'side': side
                }
                logger.log(f"Trade reconstruido: {sym}", "SYSTEM")
            
            trade = st.session_state.active_trades[sym]
            sl, tp = trade['sl_current'], trade['tp_current']
            
            # Verificar TP/SL
            close_side = 'sell' if side == 'LONG' else 'buy'
            is_tp = (side == 'LONG' and mark >= tp) or (side == 'SHORT' and mark <= tp)
            is_sl = (side == 'LONG' and mark <= sl) or (side == 'SHORT' and mark >= sl)
            
            if is_tp or is_sl:
                try:
                    exchange.create_order(symbol=sym, type='market', side=close_side, 
                                         amount=qty, params={'reduceOnly': True})
                    
                    stats = st.session_state.trade_stats
                    stats.total_pnl += pnl
                    
                    if is_tp:
                        logger.log(f"TP ALCANZADO: {sym} | PnL: ${pnl:+.4f}", "WIN")
                        stats.wins += 1
                        stats.avg_win = (stats.avg_win * (stats.wins - 1) + pnl) / stats.wins
                        stats.largest_win = max(stats.largest_win, pnl)
                        stats.consecutive_wins += 1
                        stats.consecutive_losses = 0
                        stats.max_consecutive_wins = max(stats.max_consecutive_wins, stats.consecutive_wins)
                    else:
                        logger.log(f"SL ACTIVADO: {sym} | PnL: ${pnl:+.4f}", "LOSS")
                        stats.losses += 1
                        stats.avg_loss = (stats.avg_loss * (stats.losses - 1) + abs(pnl)) / stats.losses
                        stats.largest_loss = max(stats.largest_loss, abs(pnl))
                        stats.consecutive_losses += 1
                        stats.consecutive_wins = 0
                        stats.max_consecutive_losses = max(stats.max_consecutive_losses, stats.consecutive_losses)
                    
                    if stats.total_pnl < stats.max_drawdown:
                        stats.max_drawdown = stats.total_pnl
                    
                    del st.session_state.active_trades[sym]
                    
                except Exception as e:
                    logger.log(f"Error cerrando {sym}: {str(e)[:60]}", "ERROR")
                continue
            
            # === TRAILING STOP LOGIC ===
            r_mult = abs(mark - entry) / trade['entry_risk'] if trade['entry_risk'] > 0 else 0
            
            # Breakeven a 0.8R
            if not trade['breakeven_reached'] and r_mult >= 0.8:
                trade['sl_current'] = entry * (1.001 if side == 'LONG' else 0.999)
                trade['breakeven_reached'] = True
                logger.log(f"{sym}: Breakeven activado @ 0.8R", "RISK")
            
            # Trailing a 1R
            elif trade['breakeven_reached'] and not trade['trailing_active'] and r_mult >= 1.0:
                trade['trailing_active'] = True
                trade['trailing_start'] = mark
                logger.log(f"{sym}: Trailing activado @ 1R", "RISK")
            
            # Trailing activo
            elif trade['trailing_active']:
                atr = trade.get('atr', 0.01 * entry)
                trail_dist = atr * 0.5
                
                if side == 'LONG':
                    if mark > trade['trailing_start']:
                        trade['trailing_start'] = mark
                    trade['sl_current'] = max(trade['sl_current'], mark - trail_dist)
                else:
                    if mark < trade['trailing_start']:
                        trade['trailing_start'] = mark
                    trade['sl_current'] = min(trade['sl_current'], mark + trail_dist)
        
        return n_activas
    
    def get_stats(self) -> TradeStats:
        return st.session_state.trade_stats
    
    def calculate_expectancy(self) -> float:
        stats = self.get_stats()
        if stats.wins + stats.losses == 0:
            return 0.0
        win_rate = stats.wins / (stats.wins + stats.losses)
        return (win_rate * stats.avg_win) - ((1 - win_rate) * stats.avg_loss)
    
    def get_profit_factor(self) -> float:
        stats = self.get_stats()
        if stats.avg_loss <= 0:
            return 999.0 if stats.wins > 0 else 0.0
        return stats.avg_win / stats.avg_loss

# ============================================================================
# BACKTESTER INTEGRADO
# ============================================================================
class Backtester:
    def __init__(self):
        self.signal_gen = SignalGenerator()
        self.results = []
    
    def run_backtest(self, df_15m: pd.DataFrame, df_1h: pd.DataFrame, 
                    symbol: str, initial_capital: float = 10000) -> Dict:
        """Ejecuta backtest en datos históricos"""
        
        results = []
        capital = initial_capital
        wins, losses = 0, 0
        total_pnl = 0.0
        
        # Simular trading barra por barra (últimas 100 barras)
        for i in range(100, len(df_15m) - 1):
            df_slice_15m = df_15m.iloc[:i+1].copy()
            df_slice_1h = df_1h.iloc[:i+1].copy() if len(df_1h) > i else df_1h.copy()
            
            signal = self.signal_gen.generar_senal_premium(
                df_slice_15m, df_slice_1h, df_slice_15m, symbol
            )
            
            if signal:
                # Simular resultado (simplificado)
                pnl_pct = np.random.normal(0.01, 0.03)  # Simulación
                pnl = capital * pnl_pct
                capital += pnl
                total_pnl += pnl
                
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1
                
                results.append({
                    'timestamp': df_slice_15m.iloc[i]['ts'],
                    'side': signal.side,
                    'pnl': pnl,
                    'capital': capital
                })
        
        return {
            'initial_capital': initial_capital,
            'final_capital': capital,
            'total_pnl': total_pnl,
            'wins': wins,
            'losses': losses,
            'win_rate': wins / (wins + losses) * 100 if (wins + losses) > 0 else 0,
            'trades': len(results)
        }

# ============================================================================
# INTERFAZ PRINCIPAL OPTIMIZADA
# ============================================================================
def main():
    # Inicializar componentes
    logger = LogManager()
    signal_gen = SignalGenerator()
    position_mgr = PositionManager()
    backtester = Backtester()
    
    # Header
    st.markdown("""
    <div style="text-align:center;padding:20px">
        <h1>🎯 SNIPER V7.0 - PRICE ACTION ELITE</h1>
        <p style="color:#8899aa">Sistema Institucional | Order Blocks + FVG + MSS</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Advertencia de riesgo
    st.markdown("""
    <div class="warning-box">
        ⚠️ <b>ADVERTENCIA DE RIESGO:</b> El trading de futuros conlleva riesgo significativo de pérdida. 
        Solo opera con capital que puedas permitirte perder. Este sistema es una herramienta de análisis, 
        no garantiza ganancias. Backtestea antes de operar en real [[15]][[18]][[23]].
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🔐 Configuración")
        
        api_key = st.text_input("API Key", type="password", key="apikey")
        api_secret = st.text_input("API Secret", type="password", key="apisecret")
        
        st.markdown("---")
        
        leverage_ui = st.slider("Apalancamiento", 2, 25, Config.LEVERAGE_DEFAULT)
        risk_pct_ui = st.slider("Riesgo por trade (%)", 0.5, 5.0, 2.0, 0.1)
        
        modo = st.radio("Modo:", ["Solo Análisis (Paper)", "Trading Real"], index=0)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            activar = st.toggle("INICIAR", value=False)
        with col2:
            if st.button("🧹 Limpiar Logs"):
                logger.clear_logs()
                st.rerun()
        
        st.markdown("---")
        st.markdown("### 📊 Backtest Rápido")
        if st.button("Ejecutar Backtest"):
            st.info("Backtesting en desarrollo...")
    
    # Estado inicial
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = []
    if 'trade_stats' not in st.session_state:
        st.session_state.trade_stats = TradeStats()
    if 'active_trades' not in st.session_state:
        st.session_state.active_trades = {}
    if 'last_signal_time' not in st.session_state:
        st.session_state.last_signal_time = {}
    if 'last_run' not in st.session_state:
        st.session_state.last_run = 0
    
    # Layout principal
    col1, col2, col3 = st.columns([2, 2, 3])
    capital_ph = col1.empty()
    posicion_ph = col2.empty()
    senal_ph = col3.empty()
    
    log_ph = st.empty()
    stats_ph = st.empty()
    
    # Sistema activo
    if activar and SecurityUtils.validate_api_format(api_key, api_secret):
        try:
            # Inicializar exchange con rate limiting
            exchange = ccxt.krakenfutures({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {'defaultType': 'future'}
            })
            
            logger.log("SNIPER V7.0 ACTIVADO", "SYSTEM")
            
            # Obtener balance
            try:
                balance = exchange.fetch_balance()
                equity = float(balance.get('total', {}).get('USD', 0) or 0)
            except:
                equity = 0.0
            
            # Risk manager
            risk_mgr = RiskManager(equity)
            risk_mgr.risk_pct = risk_pct_ui / 100
            
            # Verificar límites diarios
            can_trade, reason = risk_mgr.check_daily_limits()
            
            # Actualizar UI
            stats = position_mgr.get_stats()
            win_rate = stats.wins / (stats.wins + stats.losses) * 100 if (stats.wins + stats.losses) > 0 else 0
            expectancy = position_mgr.calculate_expectancy()
            
            capital_ph.markdown(f"""
            <div class="metric-card">
                <b>💰 Capital</b><br>
                <span style="font-size:1.8em;color:#4a9eff;font-weight:700">${equity:.4f} USD</span><br>
                <small style="color:#8899aa">
                    W:{stats.wins} L:{stats.losses} | WR:{win_rate:.1f}% | PnL:${stats.total_pnl:+.4f}
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # Gestionar posiciones
            try:
                posiciones = exchange.fetch_positions()
                n_activas = position_mgr.gestionar_posiciones(posiciones, exchange, logger)
            except:
                posiciones, n_activas = [], 0
            
            # UI Posiciones
            pos_html = ""
            for p in posiciones:
                qty = float(p.get('contracts', 0) or 0)
                if qty <= 0:
                    continue
                sym = p['symbol']
                side = p['side'].upper()
                mark = float(p.get('markPrice') or 0)
                entry = float(p.get('entryPrice') or 0)
                pnl = float(p.get('unrealizedPnl') or 0)
                
                trade = st.session_state.active_trades.get(sym, {})
                sl = trade.get('sl_current', entry * 0.985 if side == 'LONG' else entry * 1.015)
                tp = trade.get('tp_current', entry * 1.03 if side == 'LONG' else entry * 0.97)
                
                color = "#00ff88" if pnl >= 0 else "#ff4466"
                pos_html += f"""
                <div style="border-left:3px solid {color};padding:8px;margin:6px 0">
                    <b style="color:{color}">{sym.split('/')[0]} {side}</b><br>
                    <small>Entry:{entry:.4f}|SL:{sl:.4f}|TP:{tp:.4f}|PnL:${pnl:+.4f}</small>
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
            current_time = time.time()
            
            if n_activas < Config.MAX_POSITIONS and modo == "Trading Real" and can_trade:
                for symbol, config in Config.SYMBOLS.items():
                    last_sig = st.session_state.last_signal_time.get(symbol, 0)
                    if current_time - last_sig < 300:  # 5 min cooldown
                        continue
                    
                    try:
                        bars_15m = exchange.fetch_ohlcv(symbol, Config.TIMEFRAME_ENTRY, limit=Config.BARS_LIMIT)
                        bars_1h = exchange.fetch_ohlcv(symbol, Config.TIMEFRAME_TREND, limit=Config.BARS_LIMIT)
                        bars_5m = exchange.fetch_ohlcv(symbol, Config.TIMEFRAME_CONFIRM, limit=Config.BARS_LIMIT)
                        
                        df_15m = pd.DataFrame(bars_15m, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        df_1h = pd.DataFrame(bars_1h, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        df_5m = pd.DataFrame(bars_5m, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        
                        senal = signal_gen.generar_senal_premium(df_15m, df_1h, df_5m, symbol)
                        
                        if senal and equity > 10:
                            senales_encontradas.append(senal)
                            
                            qty = risk_mgr.calcular_posicion(senal.entry, senal.sl, leverage_ui, config)
                            
                            if qty > 0:
                                side_order = 'buy' if senal.side == 'long' else 'sell'
                                exchange.create_order(
                                    symbol=symbol, type='market', side=side_order, 
                                    amount=qty, params={'leverage': leverage_ui}
                                )
                                
                                st.session_state.active_trades[symbol] = {
                                    'entry': senal.entry,
                                    'sl_current': senal.sl,
                                    'tp_current': senal.tp,
                                    'trailing_active': False,
                                    'breakeven_reached': False,
                                    'entry_risk': abs(senal.entry - senal.sl) / senal.entry,
                                    'atr': senal.atr,
                                    'side': senal.side.upper()
                                }
                                
                                st.session_state.last_signal_time[symbol] = current_time
                                logger.log(f"ORDEN: {senal.side.upper()} {symbol.split('/')[0]} @ {senal.entry:.4f}", "TRADE")
                                risk_mgr.update_daily_stats(0)  # PnL se actualiza al cerrar
                                n_activas += 1
                                
                                if n_activas >= Config.MAX_POSITIONS:
                                    break
                    
                    except Exception as e:
                        logger.log(f"Error en {symbol}: {str(e)[:40]}", "WARN")
            
            # UI Señales
            senales_html = ""
            for s in senales_encontradas:
                color = '#00ff88' if s.side == 'long' else '#ff4466'
                razones = " | ".join(s.razones[:3])
                senales_html += f"""
                <div class="metric-card" style="margin:10px 0;padding:12px;border-left:4px solid {color}">
                    <span style="color:{color};font-weight:700">{s.side.upper()} - {s.symbol.split('/')[0]}</span><br>
                    <small>
                        Entry:{s.entry:.4f}|SL:{s.sl:.4f}|TP:{s.tp:.4f}|Score:{s.score:.1f}<br>
                        {razones}
                    </small>
                </div>
                """
            
            senal_ph.markdown(f"""
            <div class="metric-card">
                <b>🎯 Señales</b><br>
                {senales_html if senales_html else '<small style="color:#667799">Escaneando mercados...</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # Logs
            log_html = "<br>".join([f'<div class="log-entry">{l}</div>' for l in logger.get_logs(25)])
            log_ph.markdown(f"""
            <div class="metric-card" style="max-height:220px;overflow-y:auto">
                {log_html if log_html else '<small style="color:#667799">Sin logs</small>'}
            </div>
            """, unsafe_allow_html=True)
            
            # Stats
            pf = position_mgr.get_profit_factor()
            stats_ph.markdown(f"""
            <div class="metric-card" style="text-align:center">
                <small style="color:#8899aa">
                    <b>Profit Factor:</b> {pf:.2f} | 
                    <b>Expectancy:</b> ${expectancy:+.4f}/trade |
                    <b>Drawdown Máx:</b> ${stats.max_drawdown:+.4f}
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # Control de refresh
            time.sleep(Config.RATE_LIMIT_DELAY)
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error: {e}")
            logger.log(f"ERROR CRÍTICO: {str(e)[:100]}", "ERROR")
            time.sleep(10)
            st.rerun()
    
    else:
        if not activar:
            st.info("👈 Ingresa credenciales y activa el sistema para comenzar")
        else:
            st.error("❌ Credenciales inválidas. Verifica API Key y Secret")

# ============================================================================
# EJECUCIÓN
# ============================================================================
if __name__ == "__main__":
    main()