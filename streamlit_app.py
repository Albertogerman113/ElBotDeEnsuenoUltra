#!/usr/bin/env python3
"""
SNIPER V7.0 - Trading Bot Mejorado para Kraken Futures
============================================
Versión mejorada con:
- Umbrales de entrada reducidos y optimizados
- Panel de debug en tiempo real
- Detección mejorada de patrones (BOS, MSS, OB, FVG)
- Sistema de señales granular
- Gestión de posiciones mejorada
- Filtros de calidad
"""

import ccxt
import pandas as pd
import numpy as np
import streamlit as st
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import os

# Configuración de logging mejorada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SNIPER_V7')

# Función auxiliar para obtener tiempo UTC (compatible con versiones modernas)
def get_utc_now() -> datetime:
    """Retorna el tiempo UTC actual"""
    return datetime.now(timezone.utc)

# ============================================
# CONFIGURACIÓN GLOBAL MEJORADA
# ============================================

@dataclass
class Config:
    """Configuración del bot con umbrales optimizados"""
    # === UMBRALES DE ENTRADA (REDUCIDOS) ===
    MIN_SCORE_BASE: float = 4.5  # Reducido de 6.0
    MIN_SCORE_STRONG: float = 7.0  # Señales fuertes
    SCORE_DIFF_THRESHOLD: float = 0.5  # Reducido de 1.5
    
    # === DETECCIÓN DE PATRONES ===
    OB_STRENGTH: float = 0.012  # 1.2% (reducido de 1.8%)
    FVG_MIN_GAP: float = 0.002  # 0.2% (reducido de 0.3%)
    MSS_THRESHOLD: float = 0.003  # 0.3% para MSS
    BOS_THRESHOLD: float = 0.002  # 0.2% para BOS
    
    # === RSI (RANGOS AMPLIADOS) ===
    RSI_OVERSOLD: float = 35.0  # Ampliado de 30
    RSI_OVERBOUGHT: float = 65.0  # Ampliado de 70
    RSI_LONG_MIN: float = 30.0  # Ampliado de 35
    RSI_LONG_MAX: float = 55.0  # Ampliado de 50
    RSI_SHORT_MIN: float = 45.0  # Ampliado de 50
    RSI_SHORT_MAX: float = 70.0  # Ampliado de 65
    
    # === GESTIÓN DE POSICIONES ===
    SIGNAL_COOLDOWN: int = 180  # 3 minutos (reducido de 300)
    RISK_PER_TRADE: float = 0.01  # 1% del capital
    DEFAULT_LEVERAGE: int = 10
    MAX_LEVERAGE: int = 20
    
    # === STOP LOSS Y TAKE PROFIT ===
    DEFAULT_SL_PERCENT: float = 0.012  # 1.2%
    DEFAULT_TP_PERCENT: float = 0.03  # 3%
    TRAILING_STOP_TRIGGER: float = 0.015  # Activar en 1.5%
    TRAILING_STOP_DISTANCE: float = 0.008  # 0.8% trailing
    
    # === FILTROS DE CALIDAD ===
    MAX_SPREAD_PERCENT: float = 0.1  # 0.1% spread máximo
    MIN_VOLATILITY: float = 0.005  # 0.5% volatilidad mínima
    MIN_VOLUME_RATIO: float = 0.8  # Ratio mínimo vs volumen promedio
    
    # === SESIÓN DE TRADING ===
    LONDON_OPEN: int = 8
    LONDON_CLOSE: int = 17
    NY_OPEN: int = 14
    NY_CLOSE: int = 23
    
    # === TIMEFRAMES ===
    TIMEFRAME: str = '15m'
    LOOKBACK_CANDLES: int = 100
    
    # === SÍMBOLOS ===
    SYMBOLS: List[str] = field(default_factory=lambda: [
        'BTC/USD', 'ETH/USD', 'SOL/USD', 'XRP/USD', 'DOGE/USD'
    ])


class SignalStrength(Enum):
    """Niveles de fuerza de señal"""
    NONE = 0
    WEAK = 1      # Score 4.5 - 5.5
    MODERATE = 2  # Score 5.5 - 7.0
    STRONG = 3    # Score >= 7.0


@dataclass
class DebugInfo:
    """Información de debug para cada símbolo"""
    symbol: str
    timestamp: datetime
    price: float
    
    # Scores
    score_long: float = 0.0
    score_short: float = 0.0
    
    # Condiciones cumplidas
    conditions_long: Dict[str, bool] = field(default_factory=dict)
    conditions_short: Dict[str, bool] = field(default_factory=dict)
    
    # Indicadores
    rsi: float = 50.0
    ema_9: float = 0.0
    ema_21: float = 0.0
    ema_50: float = 0.0
    
    # Patrones
    ob_bullish: bool = False
    ob_bearish: bool = False
    fvg_bullish: bool = False
    fvg_bearish: bool = False
    mss_bullish: bool = False
    mss_bearish: bool = False
    bos_bullish: bool = False
    bos_bearish: bool = False
    
    # Filtros
    spread_ok: bool = True
    volatility_ok: bool = True
    volume_ok: bool = True
    session_ok: bool = True
    
    # Motivo de rechazo (si aplica)
    rejection_reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'score_long': self.score_long,
            'score_short': self.score_short,
            'conditions_long': self.conditions_long,
            'conditions_short': self.conditions_short,
            'rejection_reason': self.rejection_reason
        }


@dataclass
class Signal:
    """Señal de trading"""
    symbol: str
    direction: str  # 'long' o 'short'
    strength: SignalStrength
    score: float
    price: float
    stop_loss: float
    take_profit: float
    timestamp: datetime
    conditions_met: List[str]
    debug_info: DebugInfo
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'strength': self.strength.name,
            'score': self.score,
            'price': self.price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'timestamp': self.timestamp.isoformat(),
            'conditions_met': self.conditions_met
        }


class TechnicalAnalysis:
    """Análisis técnico mejorado con detección de patrones"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcula RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_ema(self, df: pd.DataFrame, periods: List[int]) -> Dict[int, pd.Series]:
        """Calcula EMAs para múltiples períodos"""
        emas = {}
        for period in periods:
            emas[period] = df['close'].ewm(span=period, adjust=False).mean()
        return emas
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcula ATR"""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    def detect_order_block(self, df: pd.DataFrame, lookback: int = 20) -> Tuple[bool, bool]:
        """
        Detecta Order Blocks con umbral reducido
        Retorna: (ob_bullish, ob_bearish)
        """
        if len(df) < lookback:
            return False, False
        
        recent = df.tail(lookback)
        
        # Order Block Bullish: Último mínimo es más alto que el anterior
        # y hay impulso alcista posterior
        lows = recent['low'].values
        highs = recent['high'].values
        closes = recent['close'].values
        opens = recent['open'].values if 'open' in recent.columns else closes  # Fallback a closes si no hay open
        
        ob_bullish = False
        ob_bearish = False
        
        # Buscar OB alcista
        for i in range(2, min(10, len(recent))):
            # Vela bajista seguida de impulso alcista
            bearish_candle = closes[-i] < opens[-i]
            bullish_move = (highs[-1] - lows[-i]) / lows[-i] if lows[-i] > 0 else 0
            
            if bearish_candle and bullish_move > self.config.OB_STRENGTH:
                ob_bullish = True
                break
        
        # Buscar OB bajista
        for i in range(2, min(10, len(recent))):
            # Vela alcista seguida de impulso bajista
            bullish_candle = closes[-i] > opens[-i]
            bearish_move = (highs[-i] - lows[-1]) / highs[-i] if highs[-i] > 0 else 0
            
            if bullish_candle and bearish_move > self.config.OB_STRENGTH:
                ob_bearish = True
                break
        
        return ob_bullish, ob_bearish
    
    def detect_fvg(self, df: pd.DataFrame) -> Tuple[bool, bool]:
        """
        Detecta Fair Value Gaps con umbral reducido
        Retorna: (fvg_bullish, fvg_bearish)
        """
        if len(df) < 3:
            return False, False
        
        # Obtener las últimas 3 velas
        candle1 = df.iloc[-3]
        candle2 = df.iloc[-2]
        candle3 = df.iloc[-1]
        
        fvg_bullish = False
        fvg_bearish = False
        
        # FVG Bullish: Gap entre máximo de vela 1 y mínimo de vela 3
        gap_bullish = (candle3['low'] - candle1['high']) / candle1['high']
        if gap_bullish > self.config.FVG_MIN_GAP:
            fvg_bullish = True
        
        # FVG Bearish: Gap entre mínimo de vela 1 y máximo de vela 3
        gap_bearish = (candle1['low'] - candle3['high']) / candle3['high']
        if gap_bearish > self.config.FVG_MIN_GAP:
            fvg_bearish = True
        
        return fvg_bullish, fvg_bearish
    
    def detect_mss(self, df: pd.DataFrame, lookback: int = 20) -> Tuple[bool, bool]:
        """
        Detecta Market Structure Shift
        Retorna: (mss_bullish, mss_bearish)
        """
        if len(df) < lookback:
            return False, False
        
        recent = df.tail(lookback)
        highs = recent['high'].values
        lows = recent['low'].values
        closes = recent['close'].values
        
        mss_bullish = False
        mss_bearish = False
        
        # MSS Bullish: Ruptura de estructura bajista (nuevo máximo local)
        # Buscar el máximo anterior
        prev_high_idx = -2
        for i in range(-3, -len(highs), -1):
            if highs[i] > highs[prev_high_idx]:
                prev_high_idx = i
        
        current_close = closes[-1]
        prev_high = highs[prev_high_idx]
        
        if current_close > prev_high and (current_close - prev_high) / prev_high > self.config.MSS_THRESHOLD:
            mss_bullish = True
        
        # MSS Bearish: Ruptura de estructura alcista (nuevo mínimo local)
        prev_low_idx = -2
        for i in range(-3, -len(lows), -1):
            if lows[i] < lows[prev_low_idx]:
                prev_low_idx = i
        
        prev_low = lows[prev_low_idx]
        
        if current_close < prev_low and (prev_low - current_close) / prev_low > self.config.MSS_THRESHOLD:
            mss_bearish = True
        
        return mss_bullish, mss_bearish
    
    def detect_bos(self, df: pd.DataFrame, lookback: int = 30) -> Tuple[bool, bool]:
        """
        Detecta Break of Structure
        Retorna: (bos_bullish, bos_bearish)
        """
        if len(df) < lookback:
            return False, False
        
        recent = df.tail(lookback)
        highs = recent['high'].values
        lows = recent['low'].values
        closes = recent['close'].values
        
        bos_bullish = False
        bos_bearish = False
        
        # BOS Bullish: Cierre por encima del máximo más alto reciente
        highest_high = np.max(highs[:-1])
        current_close = closes[-1]
        
        if current_close > highest_high and (current_close - highest_high) / highest_high > self.config.BOS_THRESHOLD:
            bos_bullish = True
        
        # BOS Bearish: Cierre por debajo del mínimo más bajo reciente
        lowest_low = np.min(lows[:-1])
        
        if current_close < lowest_low and (lowest_low - current_close) / lowest_low > self.config.BOS_THRESHOLD:
            bos_bearish = True
        
        return bos_bullish, bos_bearish
    
    def calculate_support_resistance(self, df: pd.DataFrame, lookback: int = 50) -> Tuple[float, float]:
        """
        Calcula niveles de soporte y resistencia dinámicos
        Retorna: (support, resistance)
        """
        if len(df) < lookback:
            return df['low'].min(), df['high'].max()
        
        recent = df.tail(lookback)
        
        # Usar pivots para encontrar niveles
        highs = recent['high'].values
        lows = recent['low'].values
        
        # Resistencia: Máximo de los máximos locales
        resistance = np.max(highs)
        
        # Soporte: Mínimo de los mínimos locales
        support = np.min(lows)
        
        return support, resistance
    
    def check_ema_alignment(self, emas: Dict[int, pd.Series]) -> Tuple[bool, bool]:
        """
        Verifica alineación de EMAs
        Retorna: (bullish_alignment, bearish_alignment)
        """
        if 9 not in emas or 21 not in emas or 50 not in emas:
            return False, False
        
        ema_9 = emas[9].iloc[-1]
        ema_21 = emas[21].iloc[-1]
        ema_50 = emas[50].iloc[-1]
        
        bullish_alignment = ema_9 > ema_21 > ema_50
        bearish_alignment = ema_9 < ema_21 < ema_50
        
        return bullish_alignment, bearish_alignment
    
    def analyze_volume(self, df: pd.DataFrame, lookback: int = 20) -> Tuple[float, bool]:
        """
        Analiza el volumen
        Retorna: (volume_ratio, volume_above_average)
        """
        if 'volume' not in df.columns or len(df) < lookback:
            return 1.0, True
        
        recent = df.tail(lookback)
        avg_volume = recent['volume'].iloc[:-1].mean()
        current_volume = recent['volume'].iloc[-1]
        
        if avg_volume > 0:
            volume_ratio = current_volume / avg_volume
        else:
            volume_ratio = 1.0
        
        volume_above_average = volume_ratio >= self.config.MIN_VOLUME_RATIO
        
        return volume_ratio, volume_above_average


class SniperBot:
    """Bot de trading SNIPER V7 mejorado"""
    
    def __init__(self, config: Config):
        self.config = config
        self.ta = TechnicalAnalysis(config)
        self.exchange: Optional[ccxt.Exchange] = None
        self.last_signal_time: Dict[str, datetime] = {}
        self.debug_info: Dict[str, DebugInfo] = {}
        self.signals_history: List[Signal] = []
        self.active_positions: Dict[str, Dict] = {}
        
        # Estado del sistema
        self.system_status = {
            'exchange_connected': False,
            'last_update': None,
            'errors_count': 0,
            'signals_generated': 0
        }
    
    def connect_exchange(self, api_key: str = None, secret: str = None) -> bool:
        """Conecta con Kraken Futures"""
        try:
            self.exchange = ccxt.kraken({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future'
                }
            })
            
            # Verificar conexión
            self.exchange.load_markets()
            self.system_status['exchange_connected'] = True
            logger.info("✅ Conexión exitosa con Kraken")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error conectando con Kraken: {e}")
            self.system_status['exchange_connected'] = False
            self.system_status['errors_count'] += 1
            return False
    
    def get_market_data(self, symbol: str, timeframe: str = None) -> Optional[pd.DataFrame]:
        """Obtiene datos del mercado"""
        if not self.exchange:
            return None
        
        timeframe = timeframe or self.config.TIMEFRAME
        
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=self.config.LOOKBACK_CANDLES
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df
            
        except Exception as e:
            logger.error(f"Error obteniendo datos para {symbol}: {e}")
            self.system_status['errors_count'] += 1
            return None
    
    def check_filters(self, df: pd.DataFrame, symbol: str) -> Tuple[bool, bool, bool, bool, str]:
        """
        Verifica filtros de calidad
        Retorna: (spread_ok, volatility_ok, volume_ok, session_ok, reason)
        """
        reasons = []
        
        # Verificar spread (usando high-low como proxy)
        if len(df) > 0:
            last_candle = df.iloc[-1]
            spread = (last_candle['high'] - last_candle['low']) / last_candle['close']
            spread_ok = spread < self.config.MAX_SPREAD_PERCENT
            if not spread_ok:
                reasons.append(f"Spread alto: {spread:.2%}")
        else:
            spread_ok = True
        
        # Verificar volatilidad
        if len(df) >= 14:
            returns = df['close'].pct_change().dropna()
            volatility = returns.std()
            volatility_ok = volatility > self.config.MIN_VOLATILITY
            if not volatility_ok:
                reasons.append(f"Volatilidad baja: {volatility:.4f}")
        else:
            volatility_ok = True
        
        # Verificar volumen
        volume_ratio, volume_ok = self.ta.analyze_volume(df)
        if not volume_ok:
            reasons.append(f"Volumen bajo: {volume_ratio:.2f}x")
        
        # Verificar sesión
        now = get_utc_now()
        hour = now.hour
        session_ok = (
            self.config.LONDON_OPEN <= hour <= self.config.LONDON_CLOSE or
            self.config.NY_OPEN <= hour <= self.config.NY_CLOSE
        )
        if not session_ok:
            reasons.append(f"Fuera de sesión activa: {hour}:00 UTC")
        
        reason = "; ".join(reasons) if reasons else "OK"
        
        return spread_ok, volatility_ok, volume_ok, session_ok, reason
    
    def calculate_scores(self, df: pd.DataFrame, symbol: str) -> Tuple[float, float, DebugInfo]:
        """
        Calcula scores para long y short con debug detallado
        Retorna: (score_long, score_short, debug_info)
        """
        debug = DebugInfo(
            symbol=symbol,
            timestamp=get_utc_now(),
            price=df['close'].iloc[-1] if len(df) > 0 else 0
        )
        
        score_long = 0.0
        score_short = 0.0
        
        conditions_long = {}
        conditions_short = {}
        
        # === 1. RSI ===
        rsi = self.ta.calculate_rsi(df)
        debug.rsi = rsi.iloc[-1] if len(rsi) > 0 else 50
        
        # RSI para long
        if self.config.RSI_LONG_MIN <= debug.rsi <= self.config.RSI_LONG_MAX:
            score_long += 1.5
            conditions_long['rsi_favorable'] = True
        else:
            conditions_long['rsi_favorable'] = False
        
        # RSI para short
        if self.config.RSI_SHORT_MIN <= debug.rsi <= self.config.RSI_SHORT_MAX:
            score_short += 1.5
            conditions_short['rsi_favorable'] = True
        else:
            conditions_short['rsi_favorable'] = False
        
        # === 2. EMA Alignment ===
        emas = self.ta.calculate_ema(df, [9, 21, 50])
        
        if 9 in emas:
            debug.ema_9 = emas[9].iloc[-1]
            debug.ema_21 = emas[21].iloc[-1]
            debug.ema_50 = emas[50].iloc[-1]
        
        bullish_ema, bearish_ema = self.ta.check_ema_alignment(emas)
        
        if bullish_ema:
            score_long += 2.0
            conditions_long['ema_alignment'] = True
        else:
            conditions_long['ema_alignment'] = False
        
        if bearish_ema:
            score_short += 2.0
            conditions_short['ema_alignment'] = True
        else:
            conditions_short['ema_alignment'] = False
        
        # === 3. Order Blocks ===
        ob_bullish, ob_bearish = self.ta.detect_order_block(df)
        debug.ob_bullish = ob_bullish
        debug.ob_bearish = ob_bearish
        
        if ob_bullish:
            score_long += 1.5
            conditions_long['order_block'] = True
        else:
            conditions_long['order_block'] = False
        
        if ob_bearish:
            score_short += 1.5
            conditions_short['order_block'] = True
        else:
            conditions_short['order_block'] = False
        
        # === 4. FVG ===
        fvg_bullish, fvg_bearish = self.ta.detect_fvg(df)
        debug.fvg_bullish = fvg_bullish
        debug.fvg_bearish = fvg_bearish
        
        if fvg_bullish:
            score_long += 1.0
            conditions_long['fvg'] = True
        else:
            conditions_long['fvg'] = False
        
        if fvg_bearish:
            score_short += 1.0
            conditions_short['fvg'] = True
        else:
            conditions_short['fvg'] = False
        
        # === 5. MSS (Market Structure Shift) ===
        mss_bullish, mss_bearish = self.ta.detect_mss(df)
        debug.mss_bullish = mss_bullish
        debug.mss_bearish = mss_bearish
        
        if mss_bullish:
            score_long += 2.0
            conditions_long['mss'] = True
        else:
            conditions_long['mss'] = False
        
        if mss_bearish:
            score_short += 2.0
            conditions_short['mss'] = True
        else:
            conditions_short['mss'] = False
        
        # === 6. BOS (Break of Structure) ===
        bos_bullish, bos_bearish = self.ta.detect_bos(df)
        debug.bos_bullish = bos_bullish
        debug.bos_bearish = bos_bearish
        
        if bos_bullish:
            score_long += 1.5
            conditions_long['bos'] = True
        else:
            conditions_long['bos'] = False
        
        if bos_bearish:
            score_short += 1.5
            conditions_short['bos'] = True
        else:
            conditions_short['bos'] = False
        
        # === 7. Volumen ===
        volume_ratio, volume_ok = self.ta.analyze_volume(df)
        debug.volume_ok = volume_ok
        
        if volume_ok:
            score_long += 0.5
            score_short += 0.5
            conditions_long['volume'] = True
            conditions_short['volume'] = True
        else:
            conditions_long['volume'] = False
            conditions_short['volume'] = False
        
        # Guardar condiciones en debug
        debug.conditions_long = conditions_long
        debug.conditions_short = conditions_short
        debug.score_long = score_long
        debug.score_short = score_short
        
        # Verificar filtros
        spread_ok, volatility_ok, volume_ok, session_ok, filter_reason = self.check_filters(df, symbol)
        debug.spread_ok = spread_ok
        debug.volatility_ok = volatility_ok
        debug.volume_ok = volume_ok
        debug.session_ok = session_ok
        
        return score_long, score_short, debug
    
    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Optional[Signal]:
        """Genera señal de trading con umbrales optimizados"""
        
        # Verificar cooldown
        if symbol in self.last_signal_time:
            time_since_last = get_utc_now() - self.last_signal_time[symbol]
            if time_since_last.total_seconds() < self.config.SIGNAL_COOLDOWN:
                logger.debug(f"{symbol}: En cooldown ({time_since_last.total_seconds():.0f}s restantes)")
                return None
        
        # Calcular scores
        score_long, score_short, debug = self.calculate_scores(df, symbol)
        self.debug_info[symbol] = debug
        
        # Determinar dirección
        direction = None
        score = 0.0
        
        # === LÓGICA DE SEÑAL MEJORADA ===
        # Ya NO requerimos diferencia de +1.5, solo que uno sea mayor que el otro
        
        if score_long >= self.config.MIN_SCORE_BASE and score_long > score_short:
            direction = 'long'
            score = score_long
        elif score_short >= self.config.MIN_SCORE_BASE and score_short > score_long:
            direction = 'short'
            score = score_short
        
        # Verificar filtros
        if not (debug.spread_ok and debug.volatility_ok and debug.session_ok):
            debug.rejection_reason = f"Filtros no pasados: spread={debug.spread_ok}, vol={debug.volatility_ok}, session={debug.session_ok}"
            logger.info(f"{symbol}: Señal rechazada - {debug.rejection_reason}")
            return None
        
        # Verificar score mínimo
        if direction is None:
            debug.rejection_reason = f"Score insuficiente: L={score_long:.1f}, S={score_short:.1f} (mín={self.config.MIN_SCORE_BASE})"
            logger.debug(f"{symbol}: {debug.rejection_reason}")
            return None
        
        # Determinar fuerza de la señal
        if score >= self.config.MIN_SCORE_STRONG:
            strength = SignalStrength.STRONG
        elif score >= 5.5:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK
        
        # Calcular SL y TP
        current_price = debug.price
        atr = self.ta.calculate_atr(df).iloc[-1] if len(df) >= 14 else current_price * 0.01
        
        if direction == 'long':
            stop_loss = current_price - atr * 1.5
            take_profit = current_price + atr * 3
        else:
            stop_loss = current_price + atr * 1.5
            take_profit = current_price - atr * 3
        
        # Obtener condiciones cumplidas
        conditions = debug.conditions_long if direction == 'long' else debug.conditions_short
        conditions_met = [k for k, v in conditions.items() if v]
        
        signal = Signal(
            symbol=symbol,
            direction=direction,
            strength=strength,
            score=score,
            price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=get_utc_now(),
            conditions_met=conditions_met,
            debug_info=debug
        )
        
        # Actualizar estado
        self.last_signal_time[symbol] = get_utc_now()
        self.signals_history.append(signal)
        self.system_status['signals_generated'] += 1
        
        logger.info(f"🚀 SEÑAL {strength.name} - {symbol} {direction.upper()} @ {current_price:.4f} | Score: {score:.1f} | Condiciones: {conditions_met}")
        
        return signal
    
    def place_order(self, signal: Signal) -> bool:
        """Coloca orden en el exchange"""
        if not self.exchange or not self.system_status['exchange_connected']:
            logger.warning("Exchange no conectado - no se puede colocar orden")
            return False
        
        try:
            # Calcular tamaño de posición
            balance = self.exchange.fetch_balance()
            available = balance.get('USD', {}).get('free', 0)
            
            if available <= 0:
                logger.warning("Balance insuficiente para abrir posición")
                return False
            
            risk_amount = available * self.config.RISK_PER_TRADE
            position_size = risk_amount / abs(signal.price - signal.stop_loss)
            
            # Colocar orden
            side = 'buy' if signal.direction == 'long' else 'sell'
            
            order = self.exchange.create_order(
                symbol=signal.symbol,
                type='market',
                side=side,
                amount=position_size,
                params={
                    'stopLoss': signal.stop_loss,
                    'takeProfit': signal.take_profit
                }
            )
            
            logger.info(f"✅ Orden colocada: {order['id']}")
            
            # Registrar posición activa
            self.active_positions[signal.symbol] = {
                'order_id': order['id'],
                'direction': signal.direction,
                'entry_price': signal.price,
                'size': position_size,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit,
                'timestamp': signal.timestamp
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error colocando orden: {e}")
            self.system_status['errors_count'] += 1
            return False
    
    def update_positions(self):
        """Actualiza posiciones activas con trailing stop"""
        if not self.exchange:
            return
        
        for symbol, position in list(self.active_positions.items()):
            try:
                # Obtener precio actual
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                
                # Calcular PnL
                if position['direction'] == 'long':
                    pnl_percent = (current_price - position['entry_price']) / position['entry_price']
                else:
                    pnl_percent = (position['entry_price'] - current_price) / position['entry_price']
                
                # Trailing stop
                if pnl_percent >= self.config.TRAILING_STOP_TRIGGER:
                    new_sl = current_price * (1 - self.config.TRAILING_STOP_DISTANCE)
                    if position['direction'] == 'long' and new_sl > position['stop_loss']:
                        position['stop_loss'] = new_sl
                        logger.info(f"📊 {symbol}: Trailing stop actualizado a {new_sl:.4f}")
                
                # Cierre parcial en 1R
                if pnl_percent >= self.config.DEFAULT_SL_PERCENT:
                    # TODO: Implementar cierre parcial
                    pass
                
            except Exception as e:
                logger.error(f"Error actualizando posición {symbol}: {e}")
    
    def run_analysis_cycle(self) -> List[Signal]:
        """Ejecuta un ciclo de análisis completo"""
        signals = []
        
        for symbol in self.config.SYMBOLS:
            try:
                df = self.get_market_data(symbol)
                
                if df is None or len(df) < 50:
                    logger.warning(f"{symbol}: Datos insuficientes")
                    continue
                
                signal = self.generate_signal(df, symbol)
                
                if signal:
                    signals.append(signal)
                    
                    if self.system_status['exchange_connected']:
                        self.place_order(signal)
                
            except Exception as e:
                logger.error(f"Error analizando {symbol}: {e}")
                self.system_status['errors_count'] += 1
        
        self.system_status['last_update'] = get_utc_now()
        
        return signals


# ============================================
# INTERFAZ STREAMLIT
# ============================================

def create_streamlit_app():
    """Crea la interfaz Streamlit"""
    
    st.set_page_config(
        page_title="SNIPER V7 - Trading Bot",
        page_icon="🎯",
        layout="wide"
    )
    
    st.title("🎯 SNIPER V7.0 - Trading Bot Mejorado")
    st.markdown("---")
    
    # Configuración
    config = Config()
    bot = SniperBot(config)
    
    # Sidebar - Configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # API Keys
        api_key = st.text_input("API Key", type="password")
        secret = st.text_input("Secret", type="password")
        
        # Umbrales
        st.subheader("Umbrales")
        min_score = st.slider("Score Mínimo", 3.0, 8.0, config.MIN_SCORE_BASE, 0.5)
        ob_strength = st.slider("OB Strength %", 0.5, 3.0, config.OB_STRENGTH * 100, 0.1) / 100
        fvg_gap = st.slider("FVG Gap %", 0.1, 1.0, config.FVG_MIN_GAP * 100, 0.05) / 100
        
        config.MIN_SCORE_BASE = min_score
        config.OB_STRENGTH = ob_strength
        config.FVG_MIN_GAP = fvg_gap
        
        # Conexión
        if st.button("🔗 Conectar a Kraken"):
            if api_key and secret:
                with st.spinner("Conectando..."):
                    success = bot.connect_exchange(api_key, secret)
                    if success:
                        st.success("✅ Conectado a Kraken")
                    else:
                        st.error("❌ Error de conexión")
            else:
                st.warning("⚠️ Ingrese API Key y Secret")
        
        # Modo
        st.subheader("Modo")
        live_trading = st.checkbox("Trading en vivo (REQUIERE API)", value=False)
        demo_mode = st.checkbox("Modo Demo (sin órdenes)", value=True)
    
    # Main content
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Señales Generadas", bot.system_status['signals_generated'])
    with col2:
        status = "🟢 Conectado" if bot.system_status['exchange_connected'] else "🔴 Desconectado"
        st.metric("Estado Exchange", status)
    with col3:
        st.metric("Errores", bot.system_status['errors_count'])
    
    st.markdown("---")
    
    # Panel de Debug
    st.header("🔍 Panel de Diagnóstico")
    
    if st.button("▶️ Ejecutar Análisis"):
        with st.spinner("Analizando mercados..."):
            signals = bot.run_analysis_cycle()
            
            if signals:
                st.success(f"✅ {len(signals)} señales generadas")
            else:
                st.info("ℹ️ No se generaron señales en este ciclo")
    
    # Mostrar debug info por símbolo
    st.subheader("📊 Estado por Símbolo")
    
    if bot.debug_info:
        for symbol, debug in bot.debug_info.items():
            with st.expander(f"📌 {symbol}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Scores**")
                    st.write(f"🔵 Long: **{debug.score_long:.1f}**")
                    st.write(f"🔴 Short: **{debug.score_short:.1f}**")
                    
                    st.markdown("**Indicadores**")
                    st.write(f"RSI: {debug.rsi:.1f}")
                    st.write(f"EMA 9/21/50: {debug.ema_9:.2f} / {debug.ema_21:.2f} / {debug.ema_50:.2f}")
                
                with col2:
                    st.markdown("**Patrones Detectados**")
                    patterns = []
                    if debug.ob_bullish: patterns.append("🟢 OB Bullish")
                    if debug.ob_bearish: patterns.append("🔴 OB Bearish")
                    if debug.fvg_bullish: patterns.append("🟢 FVG Bullish")
                    if debug.fvg_bearish: patterns.append("🔴 FVG Bearish")
                    if debug.mss_bullish: patterns.append("🟢 MSS Bullish")
                    if debug.mss_bearish: patterns.append("🔴 MSS Bearish")
                    if debug.bos_bullish: patterns.append("🟢 BOS Bullish")
                    if debug.bos_bearish: patterns.append("🔴 BOS Bearish")
                    
                    if patterns:
                        for p in patterns:
                            st.write(p)
                    else:
                        st.write("⚠️ Ningún patrón detectado")
                    
                    st.markdown("**Filtros**")
                    st.write(f"Spread: {'✅' if debug.spread_ok else '❌'}")
                    st.write(f"Volatilidad: {'✅' if debug.volatility_ok else '❌'}")
                    st.write(f"Volumen: {'✅' if debug.volume_ok else '❌'}")
                    st.write(f"Sesión: {'✅' if debug.session_ok else '❌'}")
                
                # Motivo de rechazo
                if debug.rejection_reason:
                    st.error(f"❌ **Motivo de rechazo:** {debug.rejection_reason}")
                
                # Condiciones detalladas
                with st.expander("📋 Condiciones Detalladas"):
                    cond_col1, cond_col2 = st.columns(2)
                    
                    with cond_col1:
                        st.markdown("**LONG**")
                        for cond, met in debug.conditions_long.items():
                            icon = "✅" if met else "❌"
                            st.write(f"{icon} {cond}")
                    
                    with cond_col2:
                        st.markdown("**SHORT**")
                        for cond, met in debug.conditions_short.items():
                            icon = "✅" if met else "❌"
                            st.write(f"{icon} {cond}")
    else:
        st.info("Ejecuta el análisis para ver el diagnóstico")
    
    st.markdown("---")
    
    # Historial de señales
    st.header("📜 Historial de Señales")
    
    if bot.signals_history:
        signals_df = pd.DataFrame([s.to_dict() for s in bot.signals_history])
        st.dataframe(signals_df, use_container_width=True)
    else:
        st.info("No hay señales en el historial")
    
    # Auto-refresh
    st.markdown("---")
    auto_refresh = st.checkbox("Auto-actualizar (60s)", value=False)
    
    if auto_refresh:
        time.sleep(60)
        st.rerun()


if __name__ == "__main__":
    # Ejecutar como bot standalone o como app Streamlit
    import sys
    
    if '--streamlit' in sys.argv:
        create_streamlit_app()
    else:
        # Modo bot standalone
        print("=" * 60)
        print("🎯 SNIPER V7.0 - Trading Bot Mejorado")
        print("=" * 60)
        print("\nPara ejecutar la interfaz Streamlit:")
        print("  streamlit run sniper_v7_improved.py -- --streamlit")
        print("\nEjecutando en modo consola...\n")
        
        config = Config()
        bot = SniperBot(config)
        
        # Simular datos para demo
        print("📊 Probando detección de patrones con datos simulados...")
        
        # Crear datos de prueba
        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
        
        # Simular datos de precio con tendencia realista
        base_price = 50000
        # Crear movimiento de precio más realista con oscilaciones
        returns = np.random.randn(100) * 0.02  # 2% de volatilidad
        # Añadir momentum
        for i in range(1, len(returns)):
            returns[i] = returns[i] * 0.7 + returns[i-1] * 0.3  # Autocorrelación
        
        closes = base_price * np.exp(np.cumsum(returns) / 100)
        
        # Crear high/low/open realistas
        volatility_factor = np.abs(np.random.randn(100)) * 0.01
        highs = closes * (1 + volatility_factor)
        lows = closes * (1 - volatility_factor)
        opens = closes * (1 + np.random.randn(100) * 0.005)
        volumes = np.random.randint(500, 2000, 100)
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        
        # Analizar
        score_long, score_short, debug = bot.calculate_scores(df, 'BTC/USD')
        
        print(f"\n📈 Resultados del análisis BTC/USD:")
        print(f"  Score Long:  {score_long:.1f}")
        print(f"  Score Short: {score_short:.1f}")
        print(f"  RSI: {debug.rsi:.1f}")
        print(f"\n🔍 Patrones detectados:")
        print(f"  OB Bullish:  {'✅' if debug.ob_bullish else '❌'}")
        print(f"  OB Bearish:  {'✅' if debug.ob_bearish else '❌'}")
        print(f"  FVG Bullish: {'✅' if debug.fvg_bullish else '❌'}")
        print(f"  FVG Bearish: {'✅' if debug.fvg_bearish else '❌'}")
        print(f"  MSS Bullish: {'✅' if debug.mss_bullish else '❌'}")
        print(f"  MSS Bearish: {'✅' if debug.mss_bearish else '❌'}")
        print(f"  BOS Bullish: {'✅' if debug.bos_bullish else '❌'}")
        print(f"  BOS Bearish: {'✅' if debug.bos_bearish else '❌'}")
        
        print(f"\n📋 Condiciones LONG:")
        for cond, met in debug.conditions_long.items():
            print(f"  {'✅' if met else '❌'} {cond}")
        
        print(f"\n📋 Condiciones SHORT:")
        for cond, met in debug.conditions_short.items():
            print(f"  {'✅' if met else '❌'} {cond}")
        
        # Generar señal
        signal = bot.generate_signal(df, 'BTC/USD')
        
        # Usar el debug_info actualizado del bot (no el original de calculate_scores)
        debug = bot.debug_info.get('BTC/USD', debug)
        
        if signal:
            print(f"\n🚀 SEÑAL GENERADA:")
            print(f"  Dirección: {signal.direction.upper()}")
            print(f"  Fuerza: {signal.strength.name}")
            print(f"  Score: {signal.score:.1f}")
            print(f"  Precio: {signal.price:.2f}")
            print(f"  SL: {signal.stop_loss:.2f}")
            print(f"  TP: {signal.take_profit:.2f}")
            print(f"  Condiciones: {signal.conditions_met}")
        else:
            print(f"\n❌ No se generó señal")
            print(f"  Motivo: {debug.rejection_reason}")
        
        print("\n" + "=" * 60)
        print("✅ Análisis completado")
        
        # Segunda prueba: Datos que generan señal exitosa
        print("\n" + "=" * 60)
        print("📊 PRUEBA 2: Datos con señal exitosa")
        print("=" * 60)
        
        # Crear datos de prueba con tendencia alcista fuerte (generará señal LONG)
        np.random.seed(123)
        dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
        
        # Tendencia alcista pronunciada
        base_price = 50000
        trend = np.linspace(-0.1, 0.1, 100)  # Tendencia alcista del -10% al +10%
        noise = np.random.randn(100) * 0.005
        
        closes = base_price * (1 + trend + noise)
        
        # Crear high/low/open con gap alcista en las últimas velas
        volatility_factor = np.abs(np.random.randn(100)) * 0.008
        highs = closes * (1 + volatility_factor)
        lows = closes * (1 - volatility_factor)
        
        # Añadir FVG alcista en las últimas 3 velas
        highs[-3] = closes[-3] * 1.005
        lows[-3] = closes[-3] * 0.995
        highs[-2] = closes[-2] * 1.006
        lows[-2] = closes[-2] * 0.994
        # Gap alcista: el mínimo de la vela actual es mayor que el máximo de hace 2 velas
        lows[-1] = highs[-3] * 1.003  # Gap del 0.3%
        highs[-1] = lows[-1] * 1.02
        closes[-1] = (highs[-1] + lows[-1]) / 2
        
        opens = closes * (1 + np.random.randn(100) * 0.003)
        volumes = np.random.randint(800, 2000, 100)
        
        df2 = pd.DataFrame({
            'timestamp': dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        
        # Configurar para permitir cualquier sesión
        test_config = Config()
        test_config.LONDON_OPEN = 0
        test_config.LONDON_CLOSE = 24
        test_config.NY_OPEN = 0
        test_config.NY_CLOSE = 24
        test_config.MIN_VOLATILITY = 0.0  # Desactivar filtro de volatilidad
        
        test_bot = SniperBot(test_config)
        
        # Generar señal
        signal2 = test_bot.generate_signal(df2, 'ETH/USD')
        debug2 = test_bot.debug_info.get('ETH/USD')
        
        if signal2:
            print(f"\n🚀 SEÑAL GENERADA EXITOSAMENTE:")
            print(f"  Símbolo: {signal2.symbol}")
            print(f"  Dirección: {signal2.direction.upper()}")
            print(f"  Fuerza: {signal2.strength.name}")
            print(f"  Score: {signal2.score:.1f}")
            print(f"  Precio: {signal2.price:.2f}")
            print(f"  Stop Loss: {signal2.stop_loss:.2f}")
            print(f"  Take Profit: {signal2.take_profit:.2f}")
            print(f"  Condiciones: {signal2.conditions_met}")
        else:
            print(f"\n❌ No se generó señal")
            if debug2:
                print(f"  Score Long: {debug2.score_long:.1f}")
                print(f"  Score Short: {debug2.score_short:.1f}")
                print(f"  Motivo: {debug2.rejection_reason}")
        
        print("\n" + "=" * 60)
        print("✅ Todas las pruebas completadas")
        print("=" * 60)
