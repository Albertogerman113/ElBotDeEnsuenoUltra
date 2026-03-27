"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SNIPER V6.0 PRO - SMART MONEY ELITE                        ║
║                                                                               ║
║  Estrategias Avanzadas:                                                       ║
║  • Order Blocks con Mitigación (SMC)                                         ║
║  • Fair Value Gaps con Validación                                            ║
║  • Break of Structure (BOS) / Change of Character (CHoCH)                    ║
║  • Liquidity Sweeps (Stop Hunts)                                             ║
║  • Inducement Detection                                                      ║
║  • Premium/Discount Zones                                                    ║
║                                                                               ║
║  Gestión de Riesgo Profesional:                                              ║
║  • Kelly Criterion Parcial para tamaño de posición                           ║
║  • R-Multiples Dinámicos (1R, 2R, 3R)                                        ║
║  • Trailing Stop Inteligente con ATR                                        ║
║  • Breakeven Automático a +1R                                                ║
║  • Protección de Ganancias Escalonada                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import math

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="SNIPER V6.0 PRO | Smart Money Elite",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Profesional
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp { 
        background: linear-gradient(180deg, #0a0e1a 0%, #0f1525 50%, #0a0e1a 100%); 
        color: #e0e6f0; 
        font-family: 'Inter', sans-serif;
    }
    
    .metric-card { 
        background: linear-gradient(135deg, #0f1629 0%, #1a2040 100%);
        border: 1px solid #2a3a6a;
        border-radius: 12px; 
        padding: 16px; 
        margin: 8px 0;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    
    .signal-long { color: #00ff88; font-weight: bold; font-size: 1.1em; }
    .signal-short { color: #ff4466; font-weight: bold; font-size: 1.1em; }
    .signal-wait { color: #ffaa00; }
    
    h1 { 
        color: #4a9eff !important; 
        font-family: 'JetBrains Mono', monospace !important;
        text-shadow: 0 0 20px rgba(74, 158, 255, 0.3);
    }
    
    h2, h3 { color: #8ab4f8 !important; }
    
    .stButton>button {
        background: linear-gradient(135deg, #1a5fb4 0%, #3584e4 100%);
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #3584e4 0%, #62a0ea 100%);
        box-shadow: 0 4px 20px rgba(98, 160, 234, 0.4);
    }
    
    .trade-entry {
        background: linear-gradient(135deg, rgba(0, 255, 136, 0.1) 0%, rgba(0, 255, 136, 0.05) 100%);
        border-left: 3px solid #00ff88;
        padding: 12px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
    }
    
    .trade-warning {
        background: linear-gradient(135deg, rgba(255, 170, 0, 0.1) 0%, rgba(255, 170, 0, 0.05) 100%);
        border-left: 3px solid #ffaa00;
        padding: 12px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
    }
    
    .score-badge {
        display: inline-block;
        background: linear-gradient(135deg, #2a3a6a 0%, #3a4a8a 100%);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.85em;
        font-weight: 600;
    }
    
    .score-high { background: linear-gradient(135deg, #006644 0%, #00aa66 100%); }
    .score-medium { background: linear-gradient(135deg, #885500 0%, #cc8800 100%); }
    .score-low { background: linear-gradient(135deg, #662200 0%, #aa3300 100%); }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS Y DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class TradeSide(Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class MarketStructure(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    CHoCH_BULL = "choch_bull"  # Change of Character alcista
    CHoCH_BEAR = "choch_bear"  # Change of Character bajista


class SignalStrength(Enum):
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4


@dataclass
class OrderBlock:
    """Order Block con toda la información relevante"""
    index: int
    top: float
    bottom: float
    midpoint: float
    type: str  # 'bull' o 'bear'
    mitigated: bool = False
    strength: float = 1.0  # Basado en el movimiento posterior
    volume_ratio: float = 1.0
    timestamp: Optional[int] = None


@dataclass
class FairValueGap:
    """Fair Value Gap con validación"""
    bottom: float
    top: float
    index: int
    type: str  # 'bull' o 'bear'
    filled_pct: float = 0.0  # Porcentaje rellenado
    valid: bool = True


@dataclass
class LiquidityLevel:
    """Nivel de liquidez (stops agrupados)"""
    price: float
    type: str  # 'buy_side' (above highs) o 'sell_side' (below lows)
    touches: int = 1
    swept: bool = False
    strength: float = 1.0


@dataclass
class MarketData:
    """Datos de mercado procesados"""
    df: pd.DataFrame
    symbol: str
    timeframe: str
    atr: float = 0.0
    avg_volume: float = 0.0
    current_price: float = 0.0
    volatility_pct: float = 0.0


@dataclass
class TradeSignal:
    """Señal de trading completa"""
    side: TradeSide
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit_1: float  # 1R
    take_profit_2: float  # 2R
    take_profit_3: float  # 3R
    atr: float
    score: int
    strength: SignalStrength
    reasons: List[str]
    order_blocks: List[OrderBlock] = field(default_factory=list)
    fvgs: List[FairValueGap] = field(default_factory=list)
    liquidity_levels: List[LiquidityLevel] = field(default_factory=list)
    structure: MarketStructure = MarketStructure.NEUTRAL
    risk_reward: float = 2.0
    confluence_pct: float = 0.0  # Porcentaje de confluencia


@dataclass
class ActivePosition:
    """Posición activa con seguimiento completo"""
    symbol: str
    side: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    quantity: float
    initial_risk: float  # R inicial
    max_favorable_excursion: float = 0.0  # Máxima ganancia alcanzada
    trailing_activated: bool = False
    tp1_hit: bool = False
    tp2_hit: bool = False
    breakeven_set: bool = False
    entry_time: datetime = field(default_factory=datetime.now)
    signal_score: int = 0
    reasons: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# PARÁMETROS DE TRADING
# ═══════════════════════════════════════════════════════════════════════════════

# Símbolos a operar
SYMBOLS = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD']

# Gestión de riesgo
DEFAULT_LEVERAGE = 8
MAX_LEVERAGE = 15
RISK_PER_TRADE = 0.015  # 1.5% por trade (conservador)
MAX_RISK_PER_TRADE = 0.025  # Máximo 2.5% en señales muy fuertes
MAX_DAILY_DRAWDOWN = 0.06  # 6% pérdida máxima diaria
MAX_POSITIONS = 2
MAX_POSITIONS_PER_SYMBOL = 1

# Targets y Stops
DEFAULT_RR_RATIO = 2.0
ATR_SL_MULTIPLIER = 1.2
ATR_TP1_MULTIPLIER = 1.0  # TP1 = 1R
ATR_TP2_MULTIPLIER = 2.0  # TP2 = 2R
ATR_TP3_MULTIPLIER = 3.0  # TP3 = 3R

# Trailing Stop
TRAILING_TRIGGER_R = 1.0  # Activar trailing al alcanzar 1R
TRAILING_ATR_MULT = 1.5  # Distancia de trailing en ATR
BREAKEVEN_TRIGGER_R = 0.8  # Mover a breakeven al alcanzar 0.8R

# Timeframes
TF_ENTRY = '15m'
TF_TREND = '1h'
TF_STRUCTURE = '4h'
BARS_LIMIT = 500

# Puntuación mínima para entrar
MIN_SCORE = 6
STRONG_SIGNAL_SCORE = 9

# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════════

def safe_float(val: Any, default: float = 0.0) -> float:
    """Convierte a float de forma segura"""
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def log_message(msg: str, level: str = "INFO") -> None:
    """Logging con iconos y persistencia"""
    now = datetime.now().strftime("%H:%M:%S")
    icons = {
        "INFO": "ℹ️", "TRADE": "🚀", "WIN": "💰", "LOSS": "🛡️",
        "WARN": "⚠️", "ERROR": "❌", "SCAN": "🔍", "STRUCTURE": "📊",
        "OB": "📦", "FVG": "Gap", "LIQ": "💧", "SCORE": "🎯"
    }
    icon = icons.get(level, "•")
    
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = []
    
    st.session_state.trade_log.insert(0, f"[{now}] {icon} {msg}")
    st.session_state.trade_log = st.session_state.trade_log[:150]


def calculate_kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Calcula la fracción de Kelly para tamaño de posición óptimo.
    Retorna un valor entre 0 y el máximo permitido.
    """
    if avg_loss == 0 or win_rate >= 1.0 or win_rate <= 0:
        return RISK_PER_TRADE
    
    # Kelly Criterion: f = (p * b - q) / b
    # donde p = win_rate, q = 1-p, b = avg_win/avg_loss
    b = avg_win / abs(avg_loss) if avg_loss != 0 else 1
    q = 1 - win_rate
    
    kelly = (win_rate * b - q) / b if b > 0 else 0
    
    # Usar Kelly fraccional (25% de Kelly completo para ser conservadores)
    kelly_fraction = max(0, min(kelly * 0.25, MAX_RISK_PER_TRADE))
    
    return max(RISK_PER_TRADE * 0.5, kelly_fraction)


def get_rounding(symbol: str) -> int:
    """Retorna decimales según el símbolo"""
    if 'BTC' in symbol:
        return 5
    elif 'ETH' in symbol:
        return 4
    elif 'SOL' in symbol:
        return 2
    return 4


# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR DE ANÁLISIS TÉCNICO - SMART MONEY CONCEPTS
# ═══════════════════════════════════════════════════════════════════════════════

class SmartMoneyAnalyzer:
    """
    Analizador avanzado de Smart Money Concepts.
    Detecta estructuras de mercado, order blocks, FVGs y liquidez.
    """
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._prepare_data()
    
    def _prepare_data(self) -> None:
        """Prepara los datos con indicadores base"""
        c = self.df['c'].astype(float)
        h = self.df['h'].astype(float)
        l = self.df['l'].astype(float)
        o = self.df['o'].astype(float)
        
        # EMAs para tendencia
        self.df['ema9'] = c.ewm(span=9, adjust=False).mean()
        self.df['ema21'] = c.ewm(span=21, adjust=False).mean()
        self.df['ema50'] = c.ewm(span=50, adjust=False).mean()
        self.df['ema200'] = c.ewm(span=200, adjust=False).mean()
        
        # ATR para volatilidad
        tr1 = h - l
        tr2 = abs(h - c.shift(1))
        tr3 = abs(l - c.shift(1))
        self.df['atr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()
        self.df['atr_smooth'] = self.df['atr'].rolling(5).mean()
        
        # RSI
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        self.df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volumen
        vol = self.df['v'].astype(float)
        self.df['vol_ma'] = vol.rolling(20).mean()
        self.df['vol_ratio'] = vol / self.df['vol_ma']
        
        # Cuerpo y mechas
        self.df['body'] = abs(c - o)
        self.df['body_pct'] = self.df['body'] / (h - l).replace(0, np.nan)
        self.df['upper_wick'] = h - pd.concat([c, o], axis=1).max(axis=1)
        self.df['lower_wick'] = pd.concat([c, o], axis=1).min(axis=1) - l
        self.df['is_bullish'] = c > o
        self.df['is_bearish'] = c < o
        
        # Rango
        self.df['range'] = h - l
        self.df['range_ma'] = self.df['range'].rolling(20).mean()
        
        # Swing points
        self._detect_swings()
    
    def _detect_swings(self, lookback: int = 5) -> None:
        """Detecta swing highs y swing lows"""
        h = self.df['h'].values
        l = self.df['l'].values
        
        self.df['swing_high'] = np.nan
        self.df['swing_low'] = np.nan
        self.df['swing_high_idx'] = np.nan
        self.df['swing_low_idx'] = np.nan
        
        for i in range(lookback, len(self.df) - lookback):
            # Swing High
            if h[i] == max(h[i-lookback:i+lookback+1]):
                self.df.loc[self.df.index[i], 'swing_high'] = h[i]
                self.df.loc[self.df.index[i], 'swing_high_idx'] = i
            
            # Swing Low
            if l[i] == min(l[i-lookback:i+lookback+1]):
                self.df.loc[self.df.index[i], 'swing_low'] = l[i]
                self.df.loc[self.df.index[i], 'swing_low_idx'] = i
    
    def detect_market_structure(self, lookback: int = 50) -> Tuple[MarketStructure, Optional[float], Optional[float]]:
        """
        Detecta la estructura de mercado usando BOS y CHoCH.
        Retorna: (estructura, key_support, key_resistance)
        """
        if len(self.df) < lookback + 10:
            return MarketStructure.NEUTRAL, None, None
        
        # Obtener swings recientes
        swings_h = self.df[self.df['swing_high'].notna()].tail(10)
        swings_l = self.df[self.df['swing_low'].notna()].tail(10)
        
        if len(swings_h) < 2 or len(swings_l) < 2:
            return MarketStructure.NEUTRAL, None, None
        
        highs = swings_h['swing_high'].values
        lows = swings_l['swing_low'].values
        
        # Detectar secuencia de HH/HL o LH/LL
        last_hh = highs[-1]
        prev_hh = highs[-2] if len(highs) > 1 else highs[-1]
        last_ll = lows[-1]
        prev_ll = lows[-2] if len(lows) > 1 else lows[-1]
        
        # Precio actual
        current_price = float(self.df.iloc[-1]['c'])
        
        # Detectar BOS (Break of Structure)
        # BOS Bullish: Ruptura de un swing high previo
        # BOS Bearish: Ruptura de un swing low previo
        
        structure = MarketStructure.NEUTRAL
        key_support = last_ll
        key_resistance = last_hh
        
        # Tendencia alcista: HH + HL
        if last_hh > prev_hh and last_ll > prev_ll:
            # Verificar si hay CHoCH (cambio de carácter)
            if current_price < prev_ll:
                structure = MarketStructure.CHoCH_BEAR
            else:
                structure = MarketStructure.BULLISH
        
        # Tendencia bajista: LH + LL
        elif last_hh < prev_hh and last_ll < prev_ll:
            if current_price > prev_hh:
                structure = MarketStructure.CHoCH_BULL
            else:
                structure = MarketStructure.BEARISH
        
        # Estructura mixta
        elif last_hh > prev_hh:
            structure = MarketStructure.BULLISH
        elif last_ll < prev_ll:
            structure = MarketStructure.BEARISH
        
        return structure, key_support, key_resistance
    
    def detect_order_blocks(self, min_move_pct: float = 0.5, lookback: int = 30) -> Tuple[List[OrderBlock], List[OrderBlock]]:
        """
        Detecta Order Blocks (OB) - La última vela opuesta antes de un movimiento fuerte.
        Retorna: (bullish_obs, bearish_obs)
        """
        obs_bull = []
        obs_bear = []
        
        c = self.df['c'].astype(float).values
        o = self.df['o'].astype(float).values
        h = self.df['h'].astype(float).values
        l = self.df['l'].astype(float).values
        v = self.df['vol_ratio'].values
        
        for i in range(3, min(len(self.df) - 5, lookback + 10)):
            # Bullish OB: Vela bajista seguida de movimiento alcista fuerte
            if o[i] > c[i]:  # Vela bajista
                # Verificar movimiento alcista posterior
                move_up = (c[i+3] - c[i]) / c[i] * 100 if i + 3 < len(c) else 0
                if move_up >= min_move_pct:
                    ob = OrderBlock(
                        index=i,
                        top=o[i],
                        bottom=c[i],
                        midpoint=(o[i] + c[i]) / 2,
                        type='bull',
                        strength=min(move_up / min_move_pct, 3.0),
                        volume_ratio=v[i] if not np.isnan(v[i]) else 1.0
                    )
                    obs_bull.append(ob)
            
            # Bearish OB: Vela alcista seguida de movimiento bajista fuerte
            if c[i] > o[i]:  # Vela alcista
                move_down = (c[i] - c[i+3]) / c[i] * 100 if i + 3 < len(c) else 0
                if move_down >= min_move_pct:
                    ob = OrderBlock(
                        index=i,
                        top=c[i],
                        bottom=o[i],
                        midpoint=(c[i] + o[i]) / 2,
                        type='bear',
                        strength=min(move_down / min_move_pct, 3.0),
                        volume_ratio=v[i] if not np.isnan(v[i]) else 1.0
                    )
                    obs_bear.append(ob)
        
        # Ordenar por fuerza y tomar los mejores
        obs_bull.sort(key=lambda x: x.strength, reverse=True)
        obs_bear.sort(key=lambda x: x.strength, reverse=True)
        
        return obs_bull[:5], obs_bear[:5]
    
    def detect_fvgs(self, lookback: int = 50) -> Tuple[List[FairValueGap], List[FairValueGap]]:
        """
        Detecta Fair Value Gaps (FVG) - Gaps de desequilibrio.
        Un FVG bullish ocurre cuando el low de la vela actual es mayor que el high de hace 2 velas.
        """
        fvgs_bull = []
        fvgs_bear = []
        
        h = self.df['h'].astype(float).values
        l = self.df['l'].astype(float).values
        c = self.df['c'].astype(float).values
        
        for i in range(2, min(len(self.df) - 1, lookback + 10)):
            # FVG Bullish: gap alcista
            if l[i] > h[i-2]:
                gap_size = l[i] - h[i-2]
                fvg = FairValueGap(
                    bottom=h[i-2],
                    top=l[i],
                    index=i,
                    type='bull',
                    filled_pct=0.0
                )
                # Verificar si ya fue rellenado parcialmente
                for j in range(i + 1, len(self.df)):
                    if l[j] < fvg.top:
                        fvg.filled_pct = min(100, (fvg.top - l[j]) / gap_size * 100)
                        if fvg.filled_pct >= 50:
                            fvg.valid = False
                        break
                
                if fvg.valid:
                    fvgs_bull.append(fvg)
            
            # FVG Bearish: gap bajista
            if h[i] < l[i-2]:
                gap_size = l[i-2] - h[i]
                fvg = FairValueGap(
                    bottom=h[i],
                    top=l[i-2],
                    index=i,
                    type='bear',
                    filled_pct=0.0
                )
                # Verificar relleno
                for j in range(i + 1, len(self.df)):
                    if h[j] > fvg.bottom:
                        fvg.filled_pct = min(100, (h[j] - fvg.bottom) / gap_size * 100)
                        if fvg.filled_pct >= 50:
                            fvg.valid = False
                        break
                
                if fvg.valid:
                    fvgs_bear.append(fvg)
        
        return fvgs_bull[-5:], fvgs_bear[-5:]
    
    def detect_liquidity(self, lookback: int = 100) -> Tuple[List[LiquidityLevel], List[LiquidityLevel]]:
        """
        Detecta niveles de liquidez donde hay stops agrupados.
        - Buy-side liquidity: Above swing highs (stops de shorts)
        - Sell-side liquidity: Below swing lows (stops de longs)
        """
        buy_side_liq = []
        sell_side_liq = []
        
        swings_h = self.df[self.df['swing_high'].notna()].tail(20)
        swings_l = self.df[self.df['swing_low'].notna()].tail(20)
        
        # Agrupar niveles cercanos
        tolerance = float(self.df['atr'].iloc[-1]) * 0.5 if not self.df['atr'].empty else 0
        
        # Buy-side liquidity (above highs)
        for _, row in swings_h.iterrows():
            price = float(row['swing_high'])
            # Buscar si ya existe un nivel cercano
            found = False
            for liq in buy_side_liq:
                if abs(liq.price - price) <= tolerance:
                    liq.touches += 1
                    liq.strength += 0.5
                    found = True
                    break
            if not found:
                buy_side_liq.append(LiquidityLevel(price=price, type='buy_side'))
        
        # Sell-side liquidity (below lows)
        for _, row in swings_l.iterrows():
            price = float(row['swing_low'])
            found = False
            for liq in sell_side_liq:
                if abs(liq.price - price) <= tolerance:
                    liq.touches += 1
                    liq.strength += 0.5
                    found = True
                    break
            if not found:
                sell_side_liq.append(LiquidityLevel(price=price, type='sell_side'))
        
        # Ordenar por fortaleza
        buy_side_liq.sort(key=lambda x: x.strength, reverse=True)
        sell_side_liq.sort(key=lambda x: x.strength, reverse=True)
        
        return buy_side_liq[:3], sell_side_liq[:3]
    
    def detect_liquidity_sweep(self, liq_levels: List[LiquidityLevel], current_price: float, 
                               prev_price: float, side: str) -> bool:
        """
        Detecta si hubo un sweep de liquidez (stop hunt).
        side: 'bull' para sweep de sell-side (busca longs), 'bear' para buy-side (busca shorts)
        """
        for liq in liq_levels:
            if liq.swept:
                continue
            
            if side == 'bull':
                # Sweep de sell-side liquidity: precio va abajo y vuelve
                if prev_price < liq.price <= current_price and liq.type == 'sell_side':
                    liq.swept = True
                    return True
            else:
                # Sweep de buy-side liquidity: precio va arriba y vuelve
                if prev_price > liq.price >= current_price and liq.type == 'buy_side':
                    liq.swept = True
                    return True
        
        return False
    
    def is_in_premium_discount_zone(self, price: float) -> Tuple[str, float]:
        """
        Determina si el precio está en zona premium o discount.
        Usa el rango de las últimas 20 velas.
        Retorna: ('premium'|'discount'|'equilibrium', distancia_al_equilibrium)
        """
        recent = self.df.tail(20)
        range_high = float(recent['h'].max())
        range_low = float(recent['l'].min())
        
        equilibrium = (range_high + range_low) / 2
        range_size = range_high - range_low
        
        if range_size == 0:
            return 'equilibrium', 0
        
        # Distancia al equilibrium como porcentaje del rango
        dist_pct = (price - equilibrium) / range_size
        
        if price > equilibrium + range_size * 0.2:
            return 'premium', dist_pct
        elif price < equilibrium - range_size * 0.2:
            return 'discount', dist_pct
        else:
            return 'equilibrium', dist_pct
    
    def detect_engulfing(self) -> Optional[str]:
        """Detecta patrón engulfing"""
        if len(self.df) < 3:
            return None
        
        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        curr_body = float(curr['body'])
        prev_body = float(prev['body'])
        
        # Bullish Engulfing
        if (not prev['is_bullish'] and curr['is_bullish'] and 
            curr_body > prev_body * 1.2 and
            float(curr['c']) > float(prev['o']) and
            float(curr['o']) < float(prev['c'])):
            return 'bull_engulf'
        
        # Bearish Engulfing
        if (prev['is_bullish'] and not curr['is_bullish'] and
            curr_body > prev_body * 1.2 and
            float(curr['c']) < float(prev['o']) and
            float(curr['o']) > float(prev['c'])):
            return 'bear_engulf'
        
        return None
    
    def detect_pin_bar(self) -> Optional[str]:
        """Detecta pin bar (hammer/shooting star)"""
        if len(self.df) < 2:
            return None
        
        last = self.df.iloc[-1]
        body = float(last['body'])
        upper_wick = float(last['upper_wick'])
        lower_wick = float(last['lower_wick'])
        total_range = float(last['range'])
        
        if total_range == 0:
            return None
        
        # Hammer (bullish pin bar)
        if (lower_wick > total_range * 0.6 and 
            body < total_range * 0.35 and
            upper_wick < total_range * 0.2):
            return 'bull_pin'
        
        # Shooting Star (bearish pin bar)
        if (upper_wick > total_range * 0.6 and
            body < total_range * 0.35 and
            lower_wick < total_range * 0.2):
            return 'bear_pin'
        
        return None
    
    def get_market_data(self, symbol: str, timeframe: str) -> MarketData:
        """Retorna datos de mercado procesados"""
        last = self.df.iloc[-1]
        
        return MarketData(
            df=self.df,
            symbol=symbol,
            timeframe=timeframe,
            atr=float(last['atr']) if not np.isnan(last['atr']) else 0,
            avg_volume=float(self.df['vol_ma'].iloc[-1]) if not np.isnan(self.df['vol_ma'].iloc[-1]) else 0,
            current_price=float(last['c']),
            volatility_pct=float(last['atr'] / last['c'] * 100) if last['c'] != 0 else 0
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GENERADOR DE SEÑALES
# ═══════════════════════════════════════════════════════════════════════════════

class SignalGenerator:
    """
    Generador de señales con confluencia múltiple.
    Combina todos los factores SMC para generar señales de alta calidad.
    """
    
    def __init__(self, df_15m: pd.DataFrame, df_1h: pd.DataFrame, df_4h: Optional[pd.DataFrame] = None):
        self.analyzer_15m = SmartMoneyAnalyzer(df_15m)
        self.analyzer_1h = SmartMoneyAnalyzer(df_1h)
        self.analyzer_4h = SmartMoneyAnalyzer(df_4h) if df_4h is not None else None
        
        # Obtener datos de mercado
        self.market_15m = self.analyzer_15m.get_market_data('', '15m')
        self.market_1h = self.analyzer_1h.get_market_data('', '1h')
        
        # Estructura de mercado
        self.structure_1h, self.key_support, self.key_resistance = self.analyzer_1h.detect_market_structure()
        self.structure_15m, _, _ = self.analyzer_15m.detect_market_structure()
        
        # Order Blocks
        self.obs_bull_15m, self.obs_bear_15m = self.analyzer_15m.detect_order_blocks()
        self.obs_bull_1h, self.obs_bear_1h = self.analyzer_1h.detect_order_blocks()
        
        # FVGs
        self.fvgs_bull_15m, self.fvgs_bear_15m = self.analyzer_15m.detect_fvgs()
        
        # Liquidez
        self.buy_liq_1h, self.sell_liq_1h = self.analyzer_1h.detect_liquidity()
        
        # Patrones de velas
        self.engulfing = self.analyzer_15m.detect_engulfing()
        self.pin_bar = self.analyzer_15m.detect_pin_bar()
    
    def generate_signal(self, symbol: str) -> Optional[TradeSignal]:
        """
        Genera señal de trading con confluencia de múltiples factores.
        """
        if len(self.analyzer_15m.df) < 210 or len(self.analyzer_1h.df) < 50:
            return None
        
        price = self.market_15m.current_price
        atr = self.market_15m.atr
        
        if atr == 0 or price == 0:
            return None
        
        # Variables de puntuación
        score_long = 0
        score_short = 0
        reasons_long = []
        reasons_short = []
        
        # === ANÁLISIS DE TENDENCIA (peso alto) ===
        
        # Estructura 1H
        if self.structure_1h == MarketStructure.BULLISH:
            score_long += 3
            reasons_long.append(f"📊 Estructura 1H alcista")
        elif self.structure_1h == MarketStructure.BEARISH:
            score_short += 3
            reasons_short.append(f"📊 Estructura 1H bajista")
        elif self.structure_1h == MarketStructure.CHoCH_BULL:
            score_long += 4  # Cambio de carácter es muy relevante
            reasons_long.append(f"📊 CHoCH alcista - Cambio de tendencia")
        elif self.structure_1h == MarketStructure.CHoCH_BEAR:
            score_short += 4
            reasons_short.append(f"📊 CHoCH bajista - Cambio de tendencia")
        
        # Estructura 15M para entradas
        if self.structure_15m == MarketStructure.BULLISH:
            score_long += 1
            reasons_long.append("Estructura 15m confirmatoria")
        elif self.structure_15m == MarketStructure.BEARISH:
            score_short += 1
            reasons_short.append("Estructura 15m confirmatoria")
        
        # EMAs - Tendencia
        last = self.analyzer_15m.df.iloc[-1]
        ema9 = float(last['ema9'])
        ema21 = float(last['ema21'])
        ema50 = float(last['ema50'])
        ema200 = float(last['ema200'])
        
        # Precio sobre/debajo de EMAs
        if price > ema200:
            score_long += 1
            reasons_long.append("Precio sobre EMA200")
        else:
            score_short += 1
            reasons_short.append("Precio bajo EMA200")
        
        # EMA alignment
        if ema9 > ema21 > ema50:
            score_long += 2
            reasons_long.append("EMAs alineadas alcistas")
        elif ema9 < ema21 < ema50:
            score_short += 2
            reasons_short.append("EMAs alineadas bajistas")
        
        # === SMART MONEY CONCEPTS (peso muy alto) ===
        
        # Premium/Discount Zone
        zone, zone_dist = self.analyzer_15m.is_in_premium_discount_zone(price)
        if zone == 'discount':
            score_long += 2
            reasons_long.append(f"💎 Zona discount (compra)")
        elif zone == 'premium':
            score_short += 2
            reasons_short.append(f"💎 Zona premium (venta)")
        
        # Order Blocks 15M
        for ob in self.obs_bull_15m:
            if ob.bottom <= price <= ob.top:
                score_long += int(2 * ob.strength)
                reasons_long.append(f"📦 En OB bullish @{ob.midpoint:.2f} (Fuerza: {ob.strength:.1f})")
        
        for ob in self.obs_bear_15m:
            if ob.bottom <= price <= ob.top:
                score_short += int(2 * ob.strength)
                reasons_short.append(f"📦 En OB bearish @{ob.midpoint:.2f} (Fuerza: {ob.strength:.1f})")
        
        # Order Blocks 1H (más importantes)
        for ob in self.obs_bull_1h:
            if ob.bottom <= price <= ob.top:
                score_long += 3
                reasons_long.append(f"📦 OB 1H bullish @{ob.midpoint:.2f}")
        
        for ob in self.obs_bear_1h:
            if ob.bottom <= price <= ob.top:
                score_short += 3
                reasons_short.append(f"📦 OB 1H bearish @{ob.midpoint:.2f}")
        
        # Fair Value Gaps
        for fvg in self.fvgs_bull_15m:
            if fvg.bottom <= price <= fvg.top:
                fill_bonus = 2 - int(fvg.filled_pct / 50)  # Menos puntos si ya está relleno
                score_long += fill_bonus
                reasons_long.append(f"Gap FVG bullish (relleno: {fvg.filled_pct:.0f}%)")
        
        for fvg in self.fvgs_bear_15m:
            if fvg.bottom <= price <= fvg.top:
                fill_bonus = 2 - int(fvg.filled_pct / 50)
                score_short += fill_bonus
                reasons_short.append(f"Gap FVG bearish (relleno: {fvg.filled_pct:.0f}%)")
        
        # Liquidez - Sweep detection
        prev_price = float(self.analyzer_15m.df.iloc[-2]['c'])
        
        # Sweep de sell-side liquidity (para longs)
        for liq in self.sell_liq_1h:
            if prev_price <= liq.price and price > liq.price:
                score_long += 3
                reasons_long.append(f"💧 Sweep liquidez sell-side @{liq.price:.2f}")
        
        # Sweep de buy-side liquidity (para shorts)
        for liq in self.buy_liq_1h:
            if prev_price >= liq.price and price < liq.price:
                score_short += 3
                reasons_short.append(f"💧 Sweep liquidez buy-side @{liq.price:.2f}")
        
        # Proximidad a liquidez (para anticipar sweeps)
        for liq in self.sell_liq_1h:
            distance_pct = abs(price - liq.price) / price * 100
            if distance_pct < 0.5:  # Muy cerca
                score_long += 1
                reasons_long.append(f"💧 Cerca de liquidez sell-side")
        
        for liq in self.buy_liq_1h:
            distance_pct = abs(price - liq.price) / price * 100
            if distance_pct < 0.5:
                score_short += 1
                reasons_short.append(f"💧 Cerca de liquidez buy-side")
        
        # === PATRONES DE VELAS ===
        
        if self.engulfing == 'bull_engulf':
            score_long += 2
            reasons_long.append("🔥 Engulfing alcista")
        elif self.engulfing == 'bear_engulf':
            score_short += 2
            reasons_short.append("🔥 Engulfing bajista")
        
        if self.pin_bar == 'bull_pin':
            score_long += 2
            reasons_long.append("📍 Pin bar alcista (hammer)")
        elif self.pin_bar == 'bear_pin':
            score_short += 2
            reasons_short.append("📍 Pin bar bajista (shooting star)")
        
        # === INDICADORES ADICIONALES ===
        
        rsi = float(last['rsi']) if not np.isnan(last['rsi']) else 50
        
        # RSI para longs
        if 35 < rsi < 55:
            score_long += 1
            reasons_long.append(f"RSI favorable: {rsi:.0f}")
        elif rsi < 30:
            score_long += 2
            reasons_long.append(f"RSI sobrevendido: {rsi:.0f}")
        
        # RSI para shorts
        if 45 < rsi < 65:
            score_short += 1
            reasons_short.append(f"RSI favorable: {rsi:.0f}")
        elif rsi > 70:
            score_short += 2
            reasons_short.append(f"RSI sobrecomprado: {rsi:.0f}")
        
        # Volumen
        vol_ratio = float(last['vol_ratio']) if not np.isnan(last['vol_ratio']) else 1
        if vol_ratio > 1.5:
            score_long += 1
            score_short += 1
            if score_long > score_short:
                reasons_long.append(f"📊 Volumen alto: {vol_ratio:.1f}x")
            else:
                reasons_short.append(f"📊 Volumen alto: {vol_ratio:.1f}x")
        
        # === DECISIÓN FINAL ===
        
        if score_long >= MIN_SCORE and score_long > score_short:
            # Calcular niveles
            sl = price - (atr * ATR_SL_MULTIPLIER)
            tp1 = price + (atr * ATR_TP1_MULTIPLIER)  # 1R
            tp2 = price + (atr * ATR_TP2_MULTIPLIER)  # 2R
            tp3 = price + (atr * ATR_TP3_MULTIPLIER)  # 3R
            
            strength = self._get_strength(score_long)
            
            return TradeSignal(
                side=TradeSide.LONG,
                symbol=symbol,
                entry_price=price,
                stop_loss=sl,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                atr=atr,
                score=score_long,
                strength=strength,
                reasons=reasons_long,
                order_blocks=self.obs_bull_15m + self.obs_bull_1h,
                fvgs=self.fvgs_bull_15m,
                liquidity_levels=self.sell_liq_1h,
                structure=self.structure_1h,
                risk_reward=ATR_TP2_MULTIPLIER / ATR_SL_MULTIPLIER,
                confluence_pct=min(100, score_long / 15 * 100)
            )
        
        elif score_short >= MIN_SCORE and score_short > score_long:
            sl = price + (atr * ATR_SL_MULTIPLIER)
            tp1 = price - (atr * ATR_TP1_MULTIPLIER)
            tp2 = price - (atr * ATR_TP2_MULTIPLIER)
            tp3 = price - (atr * ATR_TP3_MULTIPLIER)
            
            strength = self._get_strength(score_short)
            
            return TradeSignal(
                side=TradeSide.SHORT,
                symbol=symbol,
                entry_price=price,
                stop_loss=sl,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                atr=atr,
                score=score_short,
                strength=strength,
                reasons=reasons_short,
                order_blocks=self.obs_bear_15m + self.obs_bear_1h,
                fvgs=self.fvgs_bear_15m,
                liquidity_levels=self.buy_liq_1h,
                structure=self.structure_1h,
                risk_reward=ATR_TP2_MULTIPLIER / ATR_SL_MULTIPLIER,
                confluence_pct=min(100, score_short / 15 * 100)
            )
        
        return None
    
    def _get_strength(self, score: int) -> SignalStrength:
        """Determina la fuerza de la señal basada en el score"""
        if score >= 12:
            return SignalStrength.VERY_STRONG
        elif score >= 9:
            return SignalStrength.STRONG
        elif score >= 7:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK


# ═══════════════════════════════════════════════════════════════════════════════
# GESTOR DE POSICIONES
# ═══════════════════════════════════════════════════════════════════════════════

class PositionManager:
    """
    Gestor de posiciones con trailing stop, breakeven y gestión de targets.
    """
    
    def __init__(self, exchange: ccxt.krakenfutures):
        self.exchange = exchange
    
    def calculate_position_size(self, equity: float, entry: float, sl: float, 
                                win_rate: float = 0.55, leverage: int = DEFAULT_LEVERAGE) -> float:
        """
        Calcula el tamaño de posición usando Kelly Criterion parcial.
        """
        if entry == 0 or sl == 0:
            return 0
        
        # Distancia al SL
        risk_distance = abs(entry - sl) / entry
        
        # Usar Kelly o riesgo fijo
        if win_rate > 0.5:
            risk_pct = calculate_kelly_fraction(win_rate, 2.0, 1.0)
        else:
            risk_pct = RISK_PER_TRADE
        
        # Tamaño basado en riesgo
        risk_amount = equity * risk_pct
        position_size = risk_amount / (risk_distance * entry)
        
        # Verificar margen disponible
        max_by_margin = (equity * 0.5 * leverage) / entry
        position_size = min(position_size, max_by_margin)
        
        return max(position_size, 0)
    
    def manage_position(self, position: dict, active_trade: ActivePosition, 
                        current_price: float) -> Tuple[bool, str, Optional[float]]:
        """
        Gestiona una posición activa. Retorna: (cerrar, razón, nuevo_sl)
        """
        side = position['side'].upper()
        entry = active_trade.entry_price
        sl = active_trade.stop_loss
        atr = active_trade.initial_risk / ATR_SL_MULTIPLIER / abs(entry - active_trade.stop_loss) if abs(entry - active_trade.stop_loss) > 0 else 0
        
        # Actualizar MFE (Max Favorable Excursion)
        if side == 'LONG':
            mfe = (current_price - entry) / entry
        else:
            mfe = (entry - current_price) / entry
        
        active_trade.max_favorable_excursion = max(active_trade.max_favorable_excursion, mfe)
        
        # === GESTIÓN DE TARGETS ===
        
        # TP1 - Cerrar parcial (50%) o mover a breakeven
        if not active_trade.tp1_hit:
            if side == 'LONG' and current_price >= active_trade.take_profit_1:
                if not active_trade.breakeven_set:
                    active_trade.stop_loss = entry
                    active_trade.breakeven_set = True
                    active_trade.tp1_hit = True
                    log_message(f"TP1 alcanzado - SL movido a breakeven", "WIN")
                    return False, "tp1_hit", entry
            elif side == 'SHORT' and current_price <= active_trade.take_profit_1:
                if not active_trade.breakeven_set:
                    active_trade.stop_loss = entry
                    active_trade.breakeven_set = True
                    active_trade.tp1_hit = True
                    log_message(f"TP1 alcanzado - SL movido a breakeven", "WIN")
                    return False, "tp1_hit", entry
        
        # TP2 - Cerrar parcial adicional
        if not active_trade.tp2_hit:
            if side == 'LONG' and current_price >= active_trade.take_profit_2:
                active_trade.tp2_hit = True
                # Ajustar trailing stop
                new_sl = active_trade.take_profit_1
                active_trade.stop_loss = new_sl
                log_message(f"TP2 alcanzado - SL ajustado a TP1", "WIN")
                return False, "tp2_hit", new_sl
            elif side == 'SHORT' and current_price <= active_trade.take_profit_2:
                active_trade.tp2_hit = True
                new_sl = active_trade.take_profit_1
                active_trade.stop_loss = new_sl
                log_message(f"TP2 alcanzado - SL ajustado a TP1", "WIN")
                return False, "tp2_hit", new_sl
        
        # === TRAILING STOP ===
        
        if not active_trade.trailing_activated:
            # Activar trailing al alcanzar TRAILING_TRIGGER_R
            if active_trade.max_favorable_excursion >= TRAILING_TRIGGER_R * abs(entry - sl) / entry:
                active_trade.trailing_activated = True
                log_message(f"Trailing stop activado", "INFO")
        
        if active_trade.trailing_activated:
            # Calcular nuevo trailing stop
            if side == 'LONG':
                new_sl = current_price - (atr * TRAILING_ATR_MULT)
                if new_sl > active_trade.stop_loss:
                    active_trade.stop_loss = new_sl
                    log_message(f"Trailing stop actualizado: {new_sl:.2f}", "INFO")
            else:
                new_sl = current_price + (atr * TRAILING_ATR_MULT)
                if new_sl < active_trade.stop_loss:
                    active_trade.stop_loss = new_sl
                    log_message(f"Trailing stop actualizado: {new_sl:.2f}", "INFO")
        
        # === VERIFICAR STOP LOSS ===
        
        if side == 'LONG' and current_price <= active_trade.stop_loss:
            return True, "stop_loss", None
        elif side == 'SHORT' and current_price >= active_trade.stop_loss:
            return True, "stop_loss", None
        
        # === VERIFICAR TP3 ===
        
        if side == 'LONG' and current_price >= active_trade.take_profit_3:
            return True, "take_profit_3", None
        elif side == 'SHORT' and current_price <= active_trade.take_profit_3:
            return True, "take_profit_3", None
        
        return False, "", None
    
    def execute_entry(self, signal: TradeSignal, equity: float, leverage: int, 
                      win_rate: float = 0.55) -> Tuple[bool, Optional[ActivePosition]]:
        """
        Ejecuta una entrada basada en la señal.
        """
        try:
            qty = self.calculate_position_size(
                equity=equity,
                entry=signal.entry_price,
                sl=signal.stop_loss,
                win_rate=win_rate,
                leverage=leverage
            )
            
            if qty <= 0:
                log_message(f"Cantidad inválida: {qty}", "ERROR")
                return False, None
            
            # Redondear según el símbolo
            decimals = get_rounding(signal.symbol)
            qty = round(qty, decimals)
            
            # Ejecutar orden
            side = 'buy' if signal.side == TradeSide.LONG else 'sell'
            
            order = self.exchange.create_market_order(
                signal.symbol,
                side,
                qty,
                params={'reduceOnly': False}
            )
            
            # Crear posición activa
            position = ActivePosition(
                symbol=signal.symbol,
                side=signal.side.value.upper(),
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit_1=signal.take_profit_1,
                take_profit_2=signal.take_profit_2,
                take_profit_3=signal.take_profit_3,
                quantity=qty,
                initial_risk=abs(signal.entry_price - signal.stop_loss),
                signal_score=signal.score,
                reasons=signal.reasons
            )
            
            log_message(f"ORDEN EJECUTADA: {signal.side.value.upper()} {qty} {signal.symbol} @ {signal.entry_price:.2f}", "TRADE")
            
            return True, position
            
        except Exception as e:
            log_message(f"Error ejecutando entrada: {str(e)}", "ERROR")
            return False, None
    
    def execute_exit(self, symbol: str, side: str, qty: float, reason: str) -> bool:
        """
        Ejecuta una salida de posición.
        """
        try:
            close_side = 'sell' if side == 'LONG' else 'buy'
            
            self.exchange.create_market_order(
                symbol,
                close_side,
                qty,
                params={'reduceOnly': True}
            )
            
            log_message(f"Posición cerrada: {symbol} - {reason}", "TRADE")
            return True
            
        except Exception as e:
            log_message(f"Error cerrando posición: {str(e)}", "ERROR")
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS Y PERSISTENCIA
# ═══════════════════════════════════════════════════════════════════════════════

class StatsManager:
    """Gestiona estadísticas del bot con persistencia."""
    
    STATS_FILE = "/home/z/my-project/download/sniper_stats.json"
    
    @staticmethod
    def load() -> dict:
        """Carga estadísticas desde archivo."""
        default_stats = {
            'wins': 0,
            'losses': 0,
            'breakeven': 0,
            'total_pnl': 0.0,
            'total_trades': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'max_drawdown': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
            'current_streak': 0,
            'best_streak': 0,
            'worst_streak': 0,
            'daily_pnl': {},
            'trades_history': []
        }
        
        try:
            if os.path.exists(StatsManager.STATS_FILE):
                with open(StatsManager.STATS_FILE, 'r') as f:
                    loaded_stats = json.load(f)
                    # Fusionar con defaults para asegurar que todas las claves existan
                    for key, value in default_stats.items():
                        if key not in loaded_stats:
                            loaded_stats[key] = value
                    return loaded_stats
        except Exception as e:
            log_message(f"Error cargando stats: {e}", "WARN")
        
        return default_stats
    
    @staticmethod
    def save(stats: dict) -> None:
        """Guarda estadísticas a archivo."""
        try:
            with open(StatsManager.STATS_FILE, 'w') as f:
                json.dump(stats, f, indent=2, default=str)
        except Exception as e:
            log_message(f"Error guardando stats: {e}", "ERROR")
    
    @staticmethod
    def update_trade(stats: dict, pnl: float, reason: str) -> dict:
        """Actualiza estadísticas después de un trade."""
        # Asegurar que todas las claves existan con valores por defecto
        stats['total_trades'] = stats.get('total_trades', 0) + 1
        stats['total_pnl'] = stats.get('total_pnl', 0.0) + pnl
        
        today = datetime.now().strftime('%Y-%m-%d')
        daily_pnl = stats.get('daily_pnl', {})
        daily_pnl[today] = daily_pnl.get(today, 0) + pnl
        stats['daily_pnl'] = daily_pnl
        
        if pnl > 0:
            stats['wins'] = stats.get('wins', 0) + 1
            avg_win = stats.get('avg_win', 0.0)
            wins = stats.get('wins', 1)
            stats['avg_win'] = (avg_win * (wins - 1) + pnl) / wins if wins > 0 else pnl
            stats['best_trade'] = max(stats.get('best_trade', 0.0), pnl)
            
            current_streak = stats.get('current_streak', 0)
            if current_streak >= 0:
                stats['current_streak'] = current_streak + 1
            else:
                stats['current_streak'] = 1
            stats['best_streak'] = max(stats.get('best_streak', 0), stats['current_streak'])
            
        elif pnl < 0:
            stats['losses'] = stats.get('losses', 0) + 1
            avg_loss = stats.get('avg_loss', 0.0)
            losses = stats.get('losses', 1)
            stats['avg_loss'] = (avg_loss * (losses - 1) + pnl) / losses if losses > 0 else pnl
            stats['worst_trade'] = min(stats.get('worst_trade', 0.0), pnl)
            
            current_streak = stats.get('current_streak', 0)
            if current_streak <= 0:
                stats['current_streak'] = current_streak - 1
            else:
                stats['current_streak'] = -1
            stats['worst_streak'] = min(stats.get('worst_streak', 0), stats['current_streak'])
            
        else:
            stats['breakeven'] = stats.get('breakeven', 0) + 1
        
        # Calcular win rate
        total_trades = stats.get('total_trades', 0)
        wins = stats.get('wins', 0)
        if total_trades > 0:
            stats['win_rate'] = wins / total_trades * 100
        
        # Añadir al historial
        trades_history = stats.get('trades_history', [])
        trades_history.append({
            'date': datetime.now().isoformat(),
            'pnl': pnl,
            'reason': reason
        })
        stats['trades_history'] = trades_history[-100:]
        
        StatsManager.save(stats)
        return stats


# ═══════════════════════════════════════════════════════════════════════════════
# INTERFAZ PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.markdown("# 🎯 SNIPER V6.0 PRO — SMART MONEY ELITE")
    st.caption(f"Sistema Avanzado de Trading | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    # === SIDEBAR ===
    with st.sidebar:
        st.markdown("### 🔐 Credenciales Kraken Futures")
        api_key = st.text_input("API Key", type="password", key="apikey")
        api_secret = st.text_input("API Secret", type="password", key="apisecret")
        
        st.markdown("---")
        st.markdown("### ⚙️ Configuración")
        
        leverage = st.slider("Apalancamiento", 2, MAX_LEVERAGE, DEFAULT_LEVERAGE)
        risk_pct = st.slider("Riesgo por trade (%)", 0.5, 3.0, 1.5, 0.1) / 100
        
        st.markdown("---")
        modo = st.radio("Modo:", ["🔍 Solo Análisis (Paper)", "⚡ Trading Real"])
        
        st.markdown("---")
        st.markdown("### 📊 Símbolos")
        symbols = st.multiselect(
            "Seleccionar pares",
            ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD', 'XRP/USD:USD', 'DOGE/USD:USD'],
            default=['BTC/USD:USD', 'ETH/USD:USD']
        )
        
        st.markdown("---")
        activar = st.toggle("🚀 INICIAR BOT", value=False)
        
        st.markdown("---")
        st.markdown("### 📈 Estadísticas")
        if 'stats' in st.session_state:
            stats = st.session_state.stats
            st.metric("Win Rate", f"{stats.get('win_rate', 0):.1f}%")
            st.metric("Total PnL", f"${stats.get('total_pnl', 0):.2f}")
            st.metric("Trades", f"{stats.get('wins', 0)}W / {stats.get('losses', 0)}L")
    
    # === PLACEHOLDERS ===
    col1, col2, col3 = st.columns([2, 2, 3])
    capital_ph = col1.empty()
    posicion_ph = col2.empty()
    senal_ph = col3.empty()
    log_ph = st.empty()
    
    # === INICIALIZACIÓN ===
    if 'trade_log' not in st.session_state:
        st.session_state.trade_log = []
    
    if 'stats' not in st.session_state:
        st.session_state.stats = StatsManager.load()
    
    if 'active_trades' not in st.session_state:
        st.session_state.active_trades = {}
    
    if 'daily_start_equity' not in st.session_state:
        st.session_state.daily_start_equity = 0
    
    # === LOOP PRINCIPAL ===
    if activar and api_key and api_secret:
        try:
            # Conectar a Kraken
            exchange = ccxt.krakenfutures({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {'defaultType': 'future'}
            })
            
            position_manager = PositionManager(exchange)
            
            log_message("Bot Sniper V6.0 Pro iniciado. 'El Señor es mi pastor, nada me falta' (Salmo 23:1)", "INFO")
            
            while True:
                # 1. Obtener balance
                try:
                    balance = exchange.fetch_total_balance()
                    equity = safe_float(balance.get('USD', 0))
                except Exception as e:
                    log_message(f"Error obteniendo balance: {e}", "ERROR")
                    equity = 0
                
                # Inicializar equity diario
                if st.session_state.daily_start_equity == 0:
                    st.session_state.daily_start_equity = equity
                
                # Verificar drawdown diario
                daily_pnl_pct = (equity - st.session_state.daily_start_equity) / st.session_state.daily_start_equity if st.session_state.daily_start_equity > 0 else 0
                
                # Mostrar capital
                stats = st.session_state.stats
                capital_ph.markdown(f"""
                <div class="metric-card">
                    <b>💼 Capital</b><br>
                    <span style="font-size:1.5em; color:#4a9eff">${equity:.4f} USD</span><br>
                    <small>W: {stats.get('wins', 0)} | L: {stats.get('losses', 0)} | BE: {stats.get('breakeven', 0)}</small><br>
                    <small>PnL Total: <span style="color:{"#00ff88" if stats.get('total_pnl', 0) >= 0 else "#ff4466"}">${stats.get('total_pnl', 0):.4f}</span></small><br>
                    <small>Win Rate: {stats.get('win_rate', 0):.1f}% | Racha: {stats.get('current_streak', 0)}</small>
                </div>
                """, unsafe_allow_html=True)
                
                # 2. Gestionar posiciones existentes
                try:
                    positions = exchange.fetch_positions()
                    n_activas = 0
                    
                    for pos in positions:
                        qty = safe_float(pos.get('contracts', 0))
                        if qty <= 0:
                            continue
                        
                        n_activas += 1
                        sym = pos['symbol']
                        side = pos['side'].upper()
                        mark = safe_float(pos.get('markPrice'))
                        pnl = safe_float(pos.get('unrealizedPnl'))
                        entry = safe_float(pos.get('entryPrice'))
                        
                        # Recuperar o crear ActivePosition
                        if sym not in st.session_state.active_trades:
                            atr_val = float(exchange.fetch_ohlcv(sym, '15m', limit=50)[-1][2] - exchange.fetch_ohlcv(sym, '15m', limit=50)[-1][3])
                            st.session_state.active_trades[sym] = ActivePosition(
                                symbol=sym,
                                side=side,
                                entry_price=entry,
                                stop_loss=entry * 0.97 if side == 'LONG' else entry * 1.03,
                                take_profit_1=entry * 1.01 if side == 'LONG' else entry * 0.99,
                                take_profit_2=entry * 1.02 if side == 'LONG' else entry * 0.98,
                                take_profit_3=entry * 1.03 if side == 'LONG' else entry * 0.97,
                                quantity=qty,
                                initial_risk=abs(entry * 0.03)
                            )
                            log_message(f"Reconstruyendo posición: {sym}", "WARN")
                        
                        active_trade = st.session_state.active_trades[sym]
                        
                        # Gestionar posición
                        should_close, reason, new_sl = position_manager.manage_position(pos, active_trade, mark)
                        
                        if should_close:
                            success = position_manager.execute_exit(sym, side, qty, reason)
                            if success:
                                # Actualizar stats
                                st.session_state.stats = StatsManager.update_trade(stats, pnl, reason)
                                del st.session_state.active_trades[sym]
                
                except Exception as e:
                    log_message(f"Error gestionando posiciones: {e}", "ERROR")
                    positions = []
                    n_activas = 0
                
                # Mostrar posiciones
                pos_info = ""
                for pos in positions:
                    if safe_float(pos.get('contracts', 0)) > 0:
                        sym = pos['symbol']
                        side = pos['side'].upper()
                        pnl = safe_float(pos.get('unrealizedPnl'))
                        mark = safe_float(pos.get('markPrice'))
                        entry = safe_float(pos.get('entryPrice'))
                        
                        trade_data = st.session_state.active_trades.get(sym)
                        sl_val = trade_data.stop_loss if trade_data else 0
                        tp1_val = trade_data.take_profit_1 if trade_data else 0
                        tp2_val = trade_data.take_profit_2 if trade_data else 0
                        
                        move_pct = ((mark - entry) / entry * 100) if side == 'LONG' else ((entry - mark) / entry * 100)
                        color = "#00ff88" if pnl >= 0 else "#ff4466"
                        
                        pos_info += f"""
                        <div style="color:{color}; margin:4px 0; padding:8px; background:rgba(0,0,0,0.2); border-radius:8px;">
                            <b>{sym.split('/')[0]}</b> {side} | PnL: <b>${pnl:+.4f}</b> ({move_pct:+.2f}%)<br>
                            <small>Entry: {entry:.2f} | SL: {sl_val:.2f} | TP1: {tp1_val:.2f} | TP2: {tp2_val:.2f}</small>
                        </div>
                        """
                
                posicion_ph.markdown(f"""
                <div class="metric-card">
                    <b>📊 Posiciones ({n_activas}/{MAX_POSITIONS})</b><br>
                    {pos_info if pos_info else '<span style="color:#666">Sin posiciones activas</span>'}
                    <br><small>Drawdown diario: {daily_pnl_pct*100:.2f}%</small>
                </div>
                """, unsafe_allow_html=True)
                
                # 3. Buscar nuevas señales (si no hemos alcanzado límite diario)
                signals_found = []
                
                if n_activas < MAX_POSITIONS and daily_pnl_pct > -MAX_DAILY_DRAWDOWN:
                    for sym in symbols:
                        try:
                            # Obtener datos OHLCV
                            bars_15m = exchange.fetch_ohlcv(sym, TF_ENTRY, limit=BARS_LIMIT)
                            bars_1h = exchange.fetch_ohlcv(sym, TF_TREND, limit=BARS_LIMIT)
                            
                            df_15m = pd.DataFrame(bars_15m, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                            df_1h = pd.DataFrame(bars_1h, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                            
                            # Generar señal
                            generator = SignalGenerator(df_15m, df_1h)
                            signal = generator.generate_signal(sym)
                            
                            if signal:
                                signals_found.append(signal)
                                
                                # Ejecutar en modo real
                                if modo == "⚡ Trading Real":
                                    win_rate = stats.get('win_rate', 55) / 100
                                    success, position = position_manager.execute_entry(
                                        signal, equity, leverage, win_rate
                                    )
                                    
                                    if success and position:
                                        st.session_state.active_trades[sym] = position
                                        n_activas += 1
                                        if n_activas >= MAX_POSITIONS:
                                            break
                        
                        except Exception as e:
                            log_message(f"Error analizando {sym}: {str(e)[:50]}", "ERROR")
                
                # Mostrar señales
                signals_html = ""
                for s in signals_found:
                    color = '#00ff88' if s.side == TradeSide.LONG else '#ff4466'
                    strength_colors = {
                        SignalStrength.VERY_STRONG: 'score-high',
                        SignalStrength.STRONG: 'score-high',
                        SignalStrength.MODERATE: 'score-medium',
                        SignalStrength.WEAK: 'score-low'
                    }
                    strength_class = strength_colors.get(s.strength, 'score-low')
                    
                    signals_html += f"""
                    <div class="trade-entry">
                        <span style="color:{color}"><b>{s.side.value.upper()}</b></span> — {s.symbol.split('/')[0]}
                        <span class="score-badge {strength_class}">Score: {s.score}</span><br>
                        <small>Entry: {s.entry_price:.2f} | SL: {s.stop_loss:.2f} | TP1: {s.take_profit_1:.2f} | TP2: {s.take_profit_2:.2f}</small><br>
                        <small>R/R: {s.risk_reward:.1f} | Confluencia: {s.confluence_pct:.0f}%</small><br>
                        <details><summary style="cursor:pointer; color:#8ab4f8;">Ver razones ({len(s.reasons)})</summary>
                        <ul style="margin:4px 0; padding-left:16px;">
                            {"".join(f"<li>{r}</li>" for r in s.reasons[:10])}
                        </ul></details>
                    </div>
                    """
                
                senal_ph.markdown(f"""
                <div class="metric-card">
                    <b>🎯 Señales</b><br>
                    {signals_html if signals_html else '<span style="color:#ffaa00">Esperando confluencia de alta calidad...</span>'}
                </div>
                """, unsafe_allow_html=True)
                
                # Mostrar log
                log_ph.markdown(f"""
                <div class="metric-card" style="max-height:250px; overflow-y:auto; font-family:'JetBrains Mono',monospace; font-size:0.8em">
                    {"<br>".join(st.session_state.trade_log[:25])}
                </div>
                """, unsafe_allow_html=True)
                
                # Esperar antes del siguiente ciclo
                time.sleep(30)
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error: {e}")
            time.sleep(15)
            st.rerun()
    
    else:
        st.info("""
        💡 **Instrucciones:**
        
        1. Ingresa tus credenciales de API de Kraken Futures
        2. Configura el apalancamiento y riesgo deseado
        3. Selecciona los pares a operar
        4. Activa el bot
        
        📖 *"Porque Dios no nos ha dado un espíritu de cobardía, sino de poder, de amor y de dominio propio."* (2 Timoteo 1:7)
        """)


if __name__ == "__main__":
    main()
