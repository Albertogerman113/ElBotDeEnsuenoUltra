# ============================================================================
# SNIPER V10 MAX RISK - YOLO COMPOUND MODE
# ============================================================================
# ⚠️⚠️⚠️ ADVERTENCIA: ESTE BOT PUEDE LIQUIDAR TODO TU CAPITAL ⚠️⚠️⚠️
#
# Configuración MÁXIMA agresividad:
#   - 50x apalancamiento (máximo Kraken Futures)
#   - 8% riesgo por trade (cada loss = 8% del capital)
#   - 95% exposición (casi todo el capital en juego)
#   - Sin límite de pérdidas diarias (solo pausa por 3 losses seguidas)
#   - Score mínimo 3.0 (acepta casi cualquier setup)
#   - Sin filtro ADX (opera siempre)
#   - Todos los símbolos desde el inicio
#   - 3 posiciones simultáneas
#   - 15+ trades por día
#   - Trailing ultra-agresivo (BE a 0.8R)
#
# MATEMÁTICA REAL:
#   Con $3.50, 50x leverage = $175 notional
#   Ganancia 1% de BTC = $1.75 (50% de tu capital)
#   Pérdida 2% de BTC = LIQUIDACIÓN TOTAL
#
# Si ganas 3 trades de 1% seguidos: $3.50 → $5.29 → $7.94 → $11.91
# Si pierdes 1 trade de 2%: $0.00 (LIQUIDADO)
#
# ES BINARIO: O CRECES RÁPIDO O QUEBRAS TODO.
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

st.set_page_config(
    page_title="SNIPER V10 | 🔥 MAX RISK YOLO",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# ESTILOS
# ============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
    .stApp { background: linear-gradient(135deg, #1a0000 0%, #0a0000 50%, #1a0000 100%); color: #ffcccc; font-family: 'JetBrains Mono', monospace; }
    .mc { background: linear-gradient(135deg, #2a0a0a 0%, #1a0505 100%); border: 1px solid #ff2244; border-radius: 10px; padding: 14px; margin: 6px 0; box-shadow: 0 4px 20px rgba(255,0,0,0.15); }
    .mc-gold { background: linear-gradient(135deg, #2a2a0a 0%, #1a1a05 100%); border: 1px solid #ffaa00; border-radius: 10px; padding: 14px; margin: 6px 0; box-shadow: 0 4px 20px rgba(255,170,0,0.2); }
    .mc-green { background: linear-gradient(135deg, #0a2a0a 0%, #051a05 100%); border: 1px solid #00ff44; border-radius: 10px; padding: 14px; margin: 6px 0; }
    h1 { color: #ff2200 !important; text-shadow: 0 0 30px rgba(255,34,0,0.5); }
    .stButton>button { background: linear-gradient(135deg, #ff2200 0%, #cc0000 100%); color: white; border: none; border-radius: 8px; font-weight: 700; }
    .progress-bar-bg { background: #2a0a0a; border-radius: 8px; height: 26px; border: 1px solid #ff2244; overflow: hidden; }
    .progress-bar-fill { height: 100%; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 0.75em; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# FASES - MÁXIMA AGRESIVIDAD EN TODAS
# ============================================================================
class Phases:
    TARGET = 60.0
    PHASES = {
        1: {
            'name': 'YOLO SEMILLA', 'emoji': '🔥', 'equity_min': 0, 'equity_max': 10,
            'color': '#ff2200',
            'leverage': 50, 'risk_pct': 0.08, 'rr_ratio': 2.5,
            'max_positions': 2, 'max_daily_trades': 15,
            'max_daily_loss_pct': 0.40, 'max_consecutive_losses': 4,
            'symbols': ['BTC/USD:USD', 'ETH/USD:USD'],
            'exposure_pct': 0.95, 'min_score': 3.0, 'adx_min': 0,
            'desc': '50x lev, 8% risk, 95% exposure. TODO O NADA.'
        },
        2: {
            'name': 'YOLO CRECIMIENTO', 'emoji': '⚡', 'equity_min': 10, 'equity_max': 30,
            'color': '#ffaa00',
            'leverage': 30, 'risk_pct': 0.06, 'rr_ratio': 2.5,
            'max_positions': 3, 'max_daily_trades': 15,
            'max_daily_loss_pct': 0.30, 'max_consecutive_losses': 5,
            'symbols': ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD'],
            'exposure_pct': 0.90, 'min_score': 3.5, 'adx_min': 0,
            'desc': '30x lev, 6% risk. Acelerar con más símbolos.'
        },
        3: {
            'name': 'YOLO CONSOLIDACIÓN', 'emoji': '💎', 'equity_min': 30, 'equity_max': 60,
            'color': '#00ff44',
            'leverage': 20, 'risk_pct': 0.05, 'rr_ratio': 2.5,
            'max_positions': 3, 'max_daily_trades': 12,
            'max_daily_loss_pct': 0.25, 'max_consecutive_losses': 5,
            'symbols': ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD'],
            'exposure_pct': 0.85, 'min_score': 3.5, 'adx_min': 0,
            'desc': '20x lev. Proteger ganancias, no retroceder.'
        }
    }
    @staticmethod
    def get_phase(eq): return 0 if eq >= Phases.TARGET else (3 if eq >= 30 else (2 if eq >= 10 else 1))
    @staticmethod
    def get_cfg(eq):
        p = Phases.get_phase(eq)
        if p == 0: return {'name':'META','emoji':'🏆','color':'#00ffff','leverage':0,'risk_pct':0,'max_positions':0,'symbols':[],'desc':'¡OBJETIVO!','rr_ratio':0,'exposure_pct':0}
        return Phases.PHASES[p]

SYMBOLS_CFG = {
    'BTC/USD:USD': {'min_size': 0.00001, 'tick_size': 0.00001},
    'ETH/USD:USD': {'min_size': 0.0001, 'tick_size': 0.0001},
    'SOL/USD:USD': {'min_size': 0.001, 'tick_size': 0.001}
}

# ============================================================================
# SESSION STATE
# ============================================================================
def init_ss():
    defaults = {
        'trade_log': [],
        'trade_stats': {
            'wins':0,'losses':0,'total_pnl':0.0,'total_fees_paid':0.0,'net_pnl':0.0,
            'avg_win':0.0,'avg_loss':0.0,'max_drawdown':0.0,'largest_win':0.0,'largest_loss':0.0,
            'consecutive_wins':0,'consecutive_losses':0,'max_consecutive_wins':0,'max_consecutive_losses':0,
            'total_trades':0,'profit_factor':0.0,'peak_equity':0.0,'starting_equity':0.0
        },
        'active_trades':{},'last_signal_candle':{},'daily_trades':0,
        'daily_pnl':0.0,'weekly_pnl':0.0,'last_reset_date':datetime.now().strftime('%Y-%m-%d'),
        'last_week_reset':datetime.now().strftime('%Y-%W'),'equity_cache':0.0,'loop_count':0
    }
    for k, d in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = d
        elif isinstance(d, dict) and isinstance(st.session_state[k], dict):
            for sk, sv in d.items():
                if sk not in st.session_state[k]:
                    st.session_state[k][sk] = sv

# ============================================================================
# LOG
# ============================================================================
class Log:
    def __init__(self): pass
    def log(self, msg, lvl="INFO"):
        icons = {"INFO":"📊","TRADE":"🎯","WIN":"💰","LOSS":"💀","WARN":"⚡","ERROR":"☠️","SYSTEM":"⚙️","RISK":"🛡️","PHASE":"🔄","MILESTONE":"🏆","DEBUG":"🔍","YOLO":"🔥"}
        now = datetime.now().strftime("%H:%M:%S")
        entry = f"[{now}] {icons.get(lvl,'•')} [{lvl}] {msg}"
        st.session_state.trade_log.insert(0, entry)
        st.session_state.trade_log = st.session_state.trade_log[:500]
    def get(self, n=40): return st.session_state.trade_log[:n]
    def clear(self): st.session_state.trade_log = []

# ============================================================================
# UTILS
# ============================================================================
def sf(v, d=0.0):
    try:
        if v is None: return d
        f = float(v)
        return f if not np.isnan(f) else d
    except: return d

def get_eq(): return st.session_state.get('equity_cache', 0.0)

def set_eq(v):
    st.session_state.equity_cache = v
    s = st.session_state.trade_stats
    if v > s.get('peak_equity', 0): s['peak_equity'] = v
    if s.get('starting_equity', 0) == 0 and v > 0: s['starting_equity'] = v

def est_fees(n): return n * 0.001

def candle_ts():
    now = datetime.now(timezone.utc)
    return int(now.timestamp()) // 900 * 900

def check_cd(sym):
    cur = candle_ts()
    last = st.session_state.last_signal_candle.get(sym, 0)
    return (cur - last) >= 900  # SOLO 1 vela de cooldown (era 2)

def progress(eq): return max(0, min(100, (eq - 3.5) / (60 - 3.5) * 100))

def check_limits(pcfg):
    today = datetime.now().strftime('%Y-%m-%d')
    if st.session_state.get('last_reset_date') != today:
        st.session_state.daily_trades = 0
        st.session_state.daily_pnl = 0.0
        st.session_state.last_reset_date = today
    cw = datetime.now().strftime('%Y-%W')
    if st.session_state.get('last_week_reset') != cw:
        st.session_state.weekly_pnl = 0.0
        st.session_state.last_week_reset = cw
    if st.session_state.daily_trades >= pcfg['max_daily_trades']:
        return False, f"Límite diario ({pcfg['max_daily_trades']})"
    eq = get_eq()
    if eq > 0 and st.session_state.daily_pnl < -eq * pcfg['max_daily_loss_pct']:
        return False, f"Pérdida diaria {pcfg['max_daily_loss_pct']*100:.0f}%"
    s = st.session_state.trade_stats
    if s['consecutive_losses'] >= pcfg['max_consecutive_losses']:
        return False, f"{pcfg['max_consecutive_losses']} losses seguidos"
    return True, "OK"

# ============================================================================
# INDICADORES
# ============================================================================
class Ind:
    @staticmethod
    def calc(df):
        df = df.copy()
        c,h,l,o,v = (df[x].astype(float) for x in ['c','h','l','o','v'])
        for s in [9,20,50,100,200]:
            df[f'ema{s}'] = c.ewm(span=s, adjust=False).mean()
        tr = pd.concat([h-l, abs(h-c.shift(1)), abs(l-c.shift(1))], axis=1).max(axis=1)
        df['tr']=tr; df['atr']=tr.rolling(14).mean(); df['atr_pct']=(df['atr']/c*100).fillna(0)
        delta=c.diff(); gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
        loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
        rs=gain/loss.replace(0,np.nan); df['rsi']=(100-(100/(1+rs))).fillna(50)
        df['vol_ma']=v.rolling(20).mean(); df['vol_ratio']=(v/df['vol_ma']).fillna(1)
        # ADX
        pdm=h.diff().where((h.diff()>(-l.diff()))&(h.diff()>0),0)
        mdm=(-l.diff()).where(((-l.diff())>h.diff())&((-l.diff())>0),0)
        atrs=tr.ewm(alpha=1/14,adjust=False).mean()
        df['pdi']=(100*pdm.ewm(alpha=1/14,adjust=False).mean()/atrs).fillna(0)
        df['mdi']=(100*mdm.ewm(alpha=1/14,adjust=False).mean()/atrs).fillna(0)
        dx=100*abs(df['pdi']-df['mdi'])/(df['pdi']+df['mdi']).replace(0,np.nan)
        df['adx']=dx.ewm(alpha=1/14,adjust=False).mean().fillna(0)
        df['hlc3']=(h+l+c)/3; df['vwap']=(df['hlc3']*v).cumsum()/v.cumsum()
        return df

    @staticmethod
    def mss(df):
        if len(df)<35: return 'neutral',None,None
        H,L,cls=df['h'].astype(float).values,df['l'].astype(float).values,df['c'].astype(float).values
        w=5; sh,sl=[],[]
        for i in range(w,len(df)-1):
            a,b=max(0,i-w),min(len(H),i+w+1)
            if H[i]>=max(H[a:b]): sh.append((i,H[i]))
            if L[i]<=min(L[a:b]): sl.append((i,L[i]))
        if len(sh)<3 or len(sl)<3: return 'neutral',None,None
        lhh,phh=sh[-1][1],sh[-2][1]; lll,pll=sl[-1][1],sl[-2][1]
        if sh[-1][0]<len(df)-20 or sl[-1][0]<len(df)-20: return 'neutral',lll,lhh
        if lhh>phh and lll>pll: return ('bullish_mss' if cls[-1]>lhh else 'bullish'),lll,lhh
        if lhh<phh and lll<pll: return ('bearish_mss' if cls[-1]<lll else 'bearish'),lll,lhh
        return 'neutral',lll,lhh

    @staticmethod
    def ob(df):
        ob_b,ob_s=[],[]
        c,o=df['c'].astype(float).values,df['o'].astype(float).values
        v=df['v'].astype(float).values
        vm=df['v'].astype(float).rolling(20).mean().values; pr=c[-1]
        for i in range(5,len(df)-7):
            va=vm[i] if not np.isnan(vm[i]) else v[i]
            if o[i]>c[i]:
                mu=(c[i+5]-o[i])/(o[i]+1e-10)*100
                if mu>1.0 and v[i]/(va+1e-10)>1.0 and abs(pr-(o[i]+c[i])/2)/pr*100<3:
                    ob_b.append({'mid':(o[i]+c[i])/2,'top':o[i],'bot':c[i],'str':mu*v[i]/(va+1e-10)})
            if c[i]>o[i]:
                md=(o[i]-c[i+5])/(o[i]+1e-10)*100
                if md>1.0 and v[i]/(va+1e-10)>1.0 and abs(pr-(c[i]+o[i])/2)/pr*100<3:
                    ob_s.append({'mid':(c[i]+o[i])/2,'top':c[i],'bot':o[i],'str':md*v[i]/(va+1e-10)})
        ob_b.sort(key=lambda x:abs(pr-x['mid'])); ob_s.sort(key=lambda x:abs(pr-x['mid']))
        return ob_b[:3],ob_s[:3]

    @staticmethod
    def fvg(df):
        fb,fs=[],[]
        H,L=df['h'].astype(float).values,df['l'].astype(float).values
        for i in range(1,len(df)-1):
            if L[i+1]>H[i-1]:
                g=(L[i+1]-H[i-1])/(H[i-1]+1e-10)
                if g>=0.003:
                    filled=any(lw<H[i-1] for lw in L[i+2:]) if i+2<len(L) else False
                    if not filled: fb.append({'bot':H[i-1],'top':L[i+1],'gap':g})
            if H[i+1]<L[i-1]:
                g=(L[i-1]-H[i+1])/(L[i-1]+1e-10)
                if g>=0.003:
                    filled=any(hh>L[i-1] for hh in H[i+2:]) if i+2<len(H) else False
                    if not filled: fs.append({'bot':H[i+1],'top':L[i-1],'gap':g})
        return fb[-3:],fs[-3:]

    @staticmethod
    def candle(df):
        p={'pin':None,'engulfing':None}
        if len(df)<2: return p
        la,pr=df.iloc[-1],df.iloc[-2]
        bd=abs(float(la['c'])-float(la['o'])); rng=float(la['h'])-float(la['l'])
        if rng>1e-10:
            wu=float(la['h'])-max(float(la['c']),float(la['o']))
            wd=min(float(la['c']),float(la['o']))-float(la['l'])
            if wd>rng*0.55 and bd/rng<0.3: p['pin']='bull_pin'
            elif wu>rng*0.55 and bd/rng<0.3: p['pin']='bear_pin'
        cb=float(la['c'])-float(la['o']); pb=float(pr['c'])-float(pr['o'])
        cv=float(la['v']); va=float(df['v'].iloc[-20:].mean()) if len(df)>=20 else float(pr['v'])
        if pb<0 and cb>0 and float(la['o'])<=float(pr['c']) and float(la['c'])>=float(pr['o']) and cv>va*1.0:
            p['engulfing']='bull_engulfing'
        elif pb>0 and cb<0 and float(la['o'])>=float(pr['c']) and float(la['c'])<=float(pr['o']) and cv>va*1.0:
            p['engulfing']='bear_engulfing'
        return p

# ============================================================================
# SEÑALES
# ============================================================================
def gen_signal(d15, d1h, d4h, symbol, log, pcfg):
    if len(d15)<60 or len(d1h)<60: return None
    d15,d1h,d4h = Ind.calc(d15), Ind.calc(d1h), Ind.calc(d4h)
    la=d15.iloc[-1]
    price,atr,atr_pct,rsi,vol_r,adx = float(la['c']),float(la['atr']),float(la['atr_pct']),float(la['rsi']),float(la['vol_ratio']),float(la['adx'])
    pdi,mdi=float(la['pdi']),float(la['mdi'])
    t15='bull' if price>float(la['ema50']) else 'bear'
    l1h=d1h.iloc[-1]; t1h='bull' if float(l1h['ema50'])>float(l1h['ema200']) else ('bear' if float(l1h['ema50'])<float(l1h['ema200']) else 'neutral')
    l4h=d4h.iloc[-1]; t4h='bull' if float(l4h['ema50'])>float(l4h['ema200']) else ('bear' if float(l4h['ema50'])<float(l4h['ema200']) else 'neutral')
    al=0
    if t4h=='bull' and t1h=='bull' and t15=='bull': al=3
    elif t4h=='bear' and t1h=='bear' and t15=='bear': al=-3
    elif t1h=='bull' and t15=='bull': al=2
    elif t1h=='bear' and t15=='bear': al=-2
    elif t15=='bull': al=1
    elif t15=='bear': al=-1
    st,sw_lo,sw_hi=Ind.mss(d15)
    ob_b,ob_s=Ind.ob(d15); fvg_b,fvg_s=Ind.fvg(d15); pats=Ind.candle(d15)
    vwap=float(la.get('vwap',price))
    
    sL,sS,rL,rS=0.0,0.0,[],[]
    # Tendencia (0-6)
    if al==3: sL+=6; rL.append("TriBull")
    elif al==2: sL+=4; rL.append("1H+15Bull")
    elif al==1: sL+=2; rL.append("15Bull")
    if al==-3: sS+=6; rS.append("TriBear")
    elif al==-2: sS+=4; rS.append("1H+15Bear")
    elif al==-1: sS+=2; rS.append("15Bear")
    # Estructura (0-3)
    if st=='bullish_mss': sL+=3; rL.append("MSS")
    elif st=='bullish': sL+=2; rL.append("StrB")
    if st=='bearish_mss': sS+=3; rS.append("MSS")
    elif st=='bearish': sS+=2; rS.append("StrB")
    # OB (0-2) - zona más amplia (3%)
    for ob in ob_b:
        if ob['bot']<=price<=ob['top']: sL+=2; rL.append("OB"); break
    for ob in ob_s:
        if ob['bot']<=price<=ob['top']: sS+=2; rS.append("OB"); break
    # FVG (0-2) - gap mínimo más bajo (0.3%)
    for f in fvg_b:
        if f['bot']<=price<=f['top']: sL+=2; rL.append("FVG"); break
    for f in fvg_s:
        if f['bot']<=price<=f['top']: sS+=2; rS.append("FVG"); break
    # Patrones (0-2.5)
    if pats['engulfing']=='bull_engulfing': sL+=2.5; rL.append("Engulf")
    elif pats['pin']=='bull_pin': sL+=2; rL.append("Pin")
    if pats['engulfing']=='bear_engulfing': sS+=2.5; rS.append("Engulf")
    elif pats['pin']=='bear_pin': sS+=2; rS.append("Pin")
    # RSI (0-2)
    if 30<rsi<60: sL+=2; rL.append(f"R{rsi:.0f}")
    elif 20<rsi<=30: sL+=1.5; rL.append(f"RO{rsi:.0f}")
    if 40<rsi<70: sS+=2; rS.append(f"R{rsi:.0f}")
    elif 70<=rsi<80: sS+=1.5; rS.append(f"RO{rsi:.0f}")
    if rsi>=80: sL-=1
    if rsi<=20: sS-=1
    # Volumen (0-1.5)
    if vol_r>1.3: sL+=1.5; sS+=1.5; rL.append(f"V{vol_r:.1f}"); rS.append(f"V{vol_r:.1f}")
    elif vol_r>1.0: sL+=1; sS+=1
    # VWAP (0-1)
    if price>vwap: sL+=1
    else: sS+=1
    # DI (0-1)
    if pdi>mdi*1.1: sL+=1
    elif mdi>pdi*1.1: sS+=1
    # Contra 4H
    if t4h=='bull' and al<0: sS-=2
    if t4h=='bear' and al>0: sL-=2
    sL,sS=max(0,sL),max(0,sS)
    MS=pcfg['min_score']
    
    log.log(f"{symbol}: L={sL:.1f} S={sS:.1f} Min={MS} RSI={rsi:.0f} Vol={vol_r:.1f}", "DEBUG")
    
    rr=pcfg['rr_ratio']
    if sL>=MS and sL>sS+0.8:
        sl_d=atr*1.5; sl=price-sl_d
        if sw_lo and sw_lo<sl and sw_lo>price*0.95: sl=sw_lo*0.999
        if (price-sl)/price<0.005: sl=price*0.995
        tp=price+(price-sl)*rr
        return {'symbol':symbol,'side':'long','entry':price,'sl':sl,'tp':tp,'atr':atr,'atr_pct':atr_pct,'score':sL,'razones':rL,'adx':adx,'rsi':rsi,'ts':datetime.now(timezone.utc)}
    if sS>=MS and sS>sL+0.8:
        sl_d=atr*1.5; sl=price+sl_d
        if sw_hi and sw_hi>sl and sw_hi<price*1.05: sl=sw_hi*1.001
        if (sl-price)/price<0.005: sl=price*1.005
        tp=price-(sl-price)*rr
        return {'symbol':symbol,'side':'short','entry':price,'sl':sl,'tp':tp,'atr':atr,'atr_pct':atr_pct,'score':sS,'razones':rS,'adx':adx,'rsi':rsi,'ts':datetime.now(timezone.utc)}
    return None

# ============================================================================
# POSICIÓN
# ============================================================================
def calc_pos(eq, price, sl, lev, scfg, pcfg, log):
    if eq<=0 or price<=0: return 0.0
    risk_usd = eq * pcfg['risk_pct']
    if risk_usd < 0.02: risk_usd = eq * 0.03
    dsl = abs(price-sl)/price
    if dsl < 0.003: dsl = 0.005
    denom = dsl + 0.001
    notional = risk_usd / denom
    qty = notional / price
    ms = scfg.get('min_size', 0.0001)
    log.log(f"Calc: eq=${eq:.2f} risk=${risk_usd:.4f} dsl={dsl:.4f} notional=${notional:.2f} qty_raw={qty:.8f} min={ms}", "DEBUG")
    if qty < ms:
        mr = (ms*price)/lev
        mm = eq * pcfg['exposure_pct']
        log.log(f"Qty < min. margin_req=${mr:.4f} max_margin=${mm:.4f}", "DEBUG")
        if mr <= mm: qty = ms; log.log(f"Using min_size: {ms}", "WARN")
        else: 
            log.log(f"Cannot afford min_size margin ${mr:.4f} > ${mm:.4f}", "ERROR")
            return 0
    mx = (eq*pcfg['exposure_pct']*lev)/price
    if qty > mx: qty = mx
    tick = scfg.get('tick_size', 0.01)
    if tick > 0: qty = round(qty/tick)*tick
    mg = (qty*price)/lev
    if mg > eq*pcfg['exposure_pct']:
        qty = (eq*pcfg['exposure_pct']*lev)/price
        qty = round(qty/tick)*tick
    qty = max(0, qty)
    if qty > 0:
        log.log(f"Pos: {qty} | Lev:{lev}x | Margin:${mg:.4f} | Risk:${risk_usd:.4f}", "YOLO")
    return qty

# ============================================================================
# GESTIÓN POSICIONES
# ============================================================================
def manage_pos(pos, ex, log, pcfg):
    n=0
    for p in pos:
        qty=sf(p.get('contracts',0))
        if qty<=0: continue
        n+=1
        sym=p['symbol']; side=p['side'].upper()
        mark=sf(p.get('markPrice')); pnl=sf(p.get('unrealizedPnl')); entry=sf(p.get('entryPrice'))
        if sym not in st.session_state.active_trades:
            # ATR mínimo: 0.5% del precio como floor (nunca menos)
            ea = max(abs(mark-entry)*0.5, entry*0.005) if entry>0 and mark>0 else entry*0.01
            sd = ea * 1.5
            sl = entry - sd if side=='LONG' else entry + sd
            td = sd * pcfg['rr_ratio']
            tp = entry + td if side=='LONG' else entry - td
            
            # PROTECCIÓN: TP debe estar a suficiente distancia para cubrir fees
            # Fees = 0.1% round trip → necesitamos al menos 0.2% de ganancia para ser rentable
            min_tp_dist = entry * 0.003  # Mínimo 0.3%
            if side=='LONG' and (tp - entry) < min_tp_dist:
                tp = entry + min_tp_dist
            elif side=='SHORT' and (entry - tp) < min_tp_dist:
                tp = entry - min_tp_dist
            
            log.log(f"New pos: {sym} {side} @ {entry:.2f} | SL:{sl:.2f} TP:{tp:.2f} | Dist:{(tp-entry)/entry*100:.2f}%", "SYSTEM")
            st.session_state.active_trades[sym]={
                'entry':entry,'sl':sl,'tp':tp,'trail':False,'be':False,
                'risk':abs(entry-sl)/entry if entry>0 else 0.015,'side':side,
                'oqty':qty,'cqty':qty,'hi':mark,'lo':mark,'mfe':0.0,
                'opened':datetime.now(timezone.utc),'atr':ea
            }
        tr=st.session_state.active_trades[sym]
        if side=='LONG':
            tr['hi']=max(tr['hi'],mark); tr['mfe']=max(tr['mfe'],(mark-entry)/entry)
        else:
            tr['lo']=min(tr['lo'],mark); tr['mfe']=max(tr['mfe'],(entry-mark)/entry)
        cs='sell' if side=='LONG' else 'buy'
        is_tp=(side=='LONG' and mark>=tr['tp']) or (side=='SHORT' and mark<=tr['tp'])
        is_sl=(side=='LONG' and mark<=tr['sl']) or (side=='SHORT' and mark>=tr['sl'])
        # PROTECCIÓN: No trigger TP si el neto sería negativo (fees > ganancia)
        notional_est = tr['cqty'] * entry
        fees_est = est_fees(notional_est)
        is_tp_real = is_tp and (pnl > fees_est * 1.1)
        if is_tp_real or is_sl:
            try:
                ex.create_order(symbol=sym,type='market',side=cs,amount=tr['cqty'],params={'reduceOnly':True})
                notional=tr['cqty']*entry; fees=est_fees(notional); net=pnl-fees
                s=st.session_state.trade_stats
                s['total_pnl']+=pnl; s['total_fees_paid']+=fees; s['net_pnl']+=net; s['total_trades']+=1
                dur=(datetime.now(timezone.utc)-tr.get('opened',datetime.now(timezone.utc))).total_seconds()/60
                if is_tp_real:
                    s['wins']+=1; w=s['wins']
                    s['avg_win']=(s['avg_win']*(w-1)+net)/w if w>0 else net
                    s['largest_win']=max(s['largest_win'],net)
                    s['consecutive_wins']+=1; s['consecutive_losses']=0
                    s['max_consecutive_wins']=max(s['max_consecutive_wins'],s['consecutive_wins'])
                    log.log(f"✅ TP: {sym} Net ${net:+.4f} Fees ${fees:.4f} {dur:.0f}m", "WIN")
                else:
                    s['losses']+=1; lc=s['losses']
                    s['avg_loss']=(s['avg_loss']*(lc-1)+abs(net))/lc if lc>0 else abs(net)
                    s['largest_loss']=max(s['largest_loss'],abs(net))
                    s['consecutive_losses']+=1; s['consecutive_wins']=0
                    s['max_consecutive_losses']=max(s['max_consecutive_losses'],s['consecutive_losses'])
                    log.log(f"💀 SL: {sym} Net ${net:+.4f} MFE {tr['mfe']*100:.1f}%", "LOSS")
                if s.get('net_pnl',0)<s.get('max_drawdown',0): s['max_drawdown']=s.get('net_pnl',0)
                st.session_state.daily_pnl+=net; st.session_state.weekly_pnl+=net
                if s['avg_loss']>0: s['profit_factor']=s['avg_win']/s['avg_loss']
                else: s['profit_factor']=999.0 if s['wins']>0 else 0.0
                del st.session_state.active_trades[sym]
            except Exception as e:
                log.log(f"Err close: {str(e)[:60]}", "ERROR")
            continue
        # TRAILING AGRESIVO
        # Floor para entry_risk: mínimo 0.005 (0.5%) para evitar R absurdos
        entry_risk = max(tr['risk'], entry * 0.005)
        rm = abs(mark-entry)/entry_risk
        
        if not tr['be'] and rm >= 0.8:
            tr['sl'] = entry*(1.001 if side=='LONG' else 0.999)
            tr['be'] = True
            log.log(f"{sym}: BE @ {rm:.1f}R", "RISK")
        elif tr['be'] and not tr['trail'] and rm >= 1.2:
            tr['trail'] = True
            tr['ts'] = mark
            log.log(f"{sym}: Trail @ {rm:.1f}R", "RISK")
        elif tr.get('trail'):
            at = tr.get('atr', entry_risk*entry)
            td = at * 0.4
            if side=='LONG':
                if mark > tr.get('ts', mark): tr['ts'] = mark
                tr['sl'] = max(tr['sl'], mark-td)
            else:
                if mark < tr.get('ts', mark): tr['ts'] = mark
                tr['sl'] = min(tr['sl'], mark+td)
    return n

# ============================================================================
# MAIN
# ============================================================================
def main():
    init_ss()
    log=Log()
    
    st.markdown("""
    <div style="text-align:center;padding:12px">
        <h1>🔥 SNIPER V10 | MAX RISK YOLO MODE 🔥</h1>
        <p style="color:#ff4444;font-size:1.1em">$3.50 → $60 | 50x Leverage | 95% Exposure | NO LIMITS</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background:linear-gradient(135deg,#3a0000,#1a0000);border:2px solid #ff0000;border-radius:10px;padding:14px;margin:8px 0">
        <b style="color:#ff0000">⚠️ MODO YOLO ACTIVADO - RIESGO MÁXIMO ⚠️</b><br>
        <span style="color:#ff8888">
        • 50x apalancamiento (2% en contra = LIQUIDACIÓN TOTAL)<br>
        • 8% de riesgo por trade<br>
        • 95% del capital expuesto<br>
        • Score mínimo 3.0 (acepta setups mediocres)<br>
        • Sin filtro ADX<br>
        • 1 sola vela de cooldown entre señales<br>
        • Spread reducido a 0.8 (más trades)<br>
        • Trailing BE a 0.8R (captura ganancias rápido)<br>
        • <b style="color:#ff0000">Probabilidad real de liquidación: ALTA</b>
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### 🔐 Conexión")
        api_key=st.text_input("API Key",type="password",key="apikey")
        api_secret=st.text_input("API Secret",type="password",key="apisecret")
        st.markdown("---")
        target=st.number_input("Meta ($)",value=60.0,min_value=10.0,max_value=1000.0,step=10.0)
        Phases.TARGET=target
        st.markdown("---")
        modo=st.radio("Modo:",["Solo Análisis","Trading Real"],index=1)
        st.markdown("---")
        c1,c2=st.columns(2)
        with c1: activar=st.toggle("🔥 YOLO",value=False)
        with c2:
            if st.button("🧹 Reset"):
                log.clear()
                st.session_state.trade_stats={'wins':0,'losses':0,'total_pnl':0.0,'total_fees_paid':0.0,'net_pnl':0.0,
                    'avg_win':0.0,'avg_loss':0.0,'max_drawdown':0.0,'largest_win':0.0,'largest_loss':0.0,
                    'consecutive_wins':0,'consecutive_losses':0,'max_consecutive_wins':0,'max_consecutive_losses':0,
                    'total_trades':0,'profit_factor':0.0,'peak_equity':0.0,'starting_equity':0.0}
                st.session_state.active_trades={}; st.session_state.daily_trades=0
                st.session_state.daily_pnl=0.0; st.session_state.weekly_pnl=0.0
                st.session_state.last_signal_candle={}; st.rerun()
        st.markdown("---")
        eq=get_eq(); ph=Phases.get_phase(eq); pc=Phases.get_cfg(eq)
        st.markdown(f"**Fase:** {pc.get('emoji','')} {pc.get('name','N/A')}")
        st.markdown(f"**Equity:** ${eq:.4f}")
        st.markdown(f"**Trades:** {st.session_state.daily_trades}/{pc.get('max_daily_trades',0)}")
        st.markdown(f"**Neto:** ${st.session_state.trade_stats.get('net_pnl',0):+.4f}")
        cl=st.session_state.trade_stats.get('consecutive_losses',0)
        if cl>=2: st.markdown(f"<span style='color:#ff0000'>⚠️ {cl} losses seguidos</span>",unsafe_allow_html=True)
    
    ct1,ct2=st.columns([3,2])
    prog_ph=ct1.empty(); phase_ph=ct2.empty()
    cm1,cm2,cm3=st.columns([2,2,3])
    cap_ph=cm1.empty(); pos_ph=cm2.empty(); sig_ph=cm3.empty()
    log_ph=st.empty(); stat_ph=st.empty()
    
    if activar and api_key and api_secret:
        try:
            ex=ccxt.krakenfutures({'apiKey':api_key,'secret':api_secret,'enableRateLimit':True,'options':{'defaultType':'future'}})
            st.session_state.loop_count=st.session_state.get('loop_count',0)+1
            lc=st.session_state.loop_count
            
            try:
                bal=ex.fetch_balance()
                eq=sf(bal.get('total',{}).get('USD',0))
                if eq==0: eq=sf(bal.get('free',{}).get('USD',0))
                if eq==0: eq=sf(bal.get('used',{}).get('USD',0))+sf(bal.get('free',{}).get('USD',0))
                set_eq(eq)
            except Exception as e:
                eq=get_eq()
                if lc<=2: log.log(f"Bal err: {str(e)[:50]}", "ERROR")
            
            eq=get_eq(); ph=Phases.get_phase(eq); pc=Phases.get_cfg(eq)
            
            if lc<=2:
                log.log("="*50, "YOLO")
                log.log(f"🔥 V10 MAX RISK | Equity: ${eq:.4f}", "YOLO")
                log.log(f"Fase {ph}: {pc.get('name','')}", "PHASE")
                log.log(f"Lev:{pc.get('leverage',0)}x Risk:{pc.get('risk_pct',0)*100:.0f}% Exp:{pc.get('exposure_pct',0)*100:.0f}%", "YOLO")
                log.log(f"Symbols: {pc.get('symbols',[])}", "PHASE")
                log.log(f"Target: ${Phases.TARGET}", "SYSTEM")
                log.log("="*50, "YOLO")
            
            # Milestones
            for mv,(mn,me) in {10:('$10','🔥'),20:('$20','⚡'),30:('$30','🚀'),40:('$40','💫'),50:('$50','⭐')}.items():
                if eq>=mv and not st.session_state.get(f'ms_{mv}',False):
                    st.session_state[f'ms_{mv}']=True; log.log(f"{me} {mn} ALCANZADO!", "MILESTONE")
            if eq>=Phases.TARGET and not st.session_state.get('ms_done',False):
                st.session_state.ms_done=True; log.log("🏆 ¡META ALCANZADA!", "MILESTONE")
            
            old_ph=st.session_state.get('last_phase',ph)
            if 'last_phase' not in st.session_state: st.session_state.last_phase=ph
            if ph!=old_ph and ph>0:
                log.log(f"🔄 FASE {old_ph} → {ph}!", "PHASE")
                st.session_state.last_phase=ph
            
            # Progress
            prog=progress(eq); pcol='#ff2200' if prog<20 else ('#ffaa00' if prog<50 else ('#00ff44' if prog<90 else '#00ffff'))
            ms_h=""
            for mv in [10,20,30,40,50,60]:
                ms_h += f" <span style='color:#00ff44'>✓{mv}</span>" if st.session_state.get(f'ms_{mv}', eq>=mv) else f" <span style='color:#444'>○{mv}</span>"
            
            prog_ph.markdown(f"""
            <div class="mc-gold">
                <b>📈 PROGRESO: $3.50 → ${Phases.TARGET:.0f}</b><br>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width:{prog:.1f}%;background:linear-gradient(90deg,{pcol},{pcol}88)">${eq:.2f} ({prog:.1f}%)</div>
                </div>
                <span style="font-size:0.8em">{ms_h}</span>
            </div>""",unsafe_allow_html=True)
            
            if ph>0:
                pp=max(0,min(100,(eq-Phases.PHASES[ph]['equity_min'])/(Phases.PHASES[ph]['equity_max']-Phases.PHASES[ph]['equity_min'])*100))
            else: pp=100
            phase_ph.markdown(f"""
            <div class="mc">
                <b>{pc.get('emoji','')} FASE {ph}: {pc.get('name','N/A')}</b><br>
                <span style="color:{pc.get('color','#fff')}">{pp:.0f}%</span><br>
                <small style="color:#8888aa">Lev:{pc.get('leverage',0)}x | Risk:{pc.get('risk_pct',0)*100:.0f}% | Exp:{pc.get('exposure_pct',0)*100:.0f}%<br>{pc.get('desc','')}</small>
            </div>""",unsafe_allow_html=True)
            
            # META
            if ph==0:
                log.log("🏆 ¡META! Deteniendo bot.", "MILESTONE")
                s=st.session_state.trade_stats
                sw=s.get('wins',0); sl2=s.get('losses',0)
                wr=sw/(sw+sl2)*100 if (sw+sl2)>0 else 0
                cap_ph.markdown(f"""
                <div class="mc-green" style="text-align:center">
                    <b style="color:#00ffff;font-size:1.3em">🏆 ¡META ALCANZADA! 🏆</b><br>
                    <span style="font-size:2em;color:#00ff44;font-weight:700">${eq:.2f}</span><br>
                    <small>Trades:{s.get('total_trades',0)} WR:{wr:.1f}% Neto:{s.get('net_pnl',0):+.2f}</small>
                </div>""",unsafe_allow_html=True)
                time.sleep(60); st.rerun(); return
            
            dok,dreason=check_limits(pc)
            
            # Capital UI
            s=st.session_state.trade_stats
            sw=s.get('wins',0); sl2=s.get('losses',0)
            wr=sw/(sw+sl2)*100 if (sw+sl2)>0 else 0
            net=s.get('net_pnl',s.get('total_pnl',0))
            nc='#00ff44' if net>=0 else '#ff2200'
            cap_ph.markdown(f"""
            <div class="mc">
                <b>💰 Capital</b><br>
                <span style="font-size:1.6em;color:{pc.get('color','#4a9eff')};font-weight:700">${eq:.4f}</span><br>
                <small style="color:#8899aa">W:{sw} L:{sl2} | WR:{wr:.0f}%<br>
                <span style="color:{nc}">Neto: ${net:+.4f}</span></small>
            </div>""",unsafe_allow_html=True)
            
            # Posiciones
            n_act=0
            try:
                positions=ex.fetch_positions()
                n_act=manage_pos(positions,ex,log,pc)
            except Exception as e:
                positions,n_act=[],0
                log.log(f"Pos err: {str(e)[:50]}", "ERROR")
            
            pos_html=""
            for p in positions:
                qty=sf(p.get('contracts',0))
                if qty<=0: continue
                sym=p['symbol']; side=p['side'].upper()
                mark=sf(p.get('markPrice')); entry=sf(p.get('entryPrice')); pnl=sf(p.get('unrealizedPnl'))
                tr=st.session_state.active_trades.get(sym,{})
                sl=tr.get('sl',0); tp=tr.get('tp',0); mfe=tr.get('mfe',0)*100
                cl="#00ff44" if pnl>=0 else "#ff2200"
                trl="🔄" if tr.get('trail') else ""; be="✅" if tr.get('be') else ""
                pos_html+=(
                    f'<hr style="border-color:{cl};opacity:0.3;margin:4px 0">'
                    f'<b style="color:{cl}">{sym.split("/")[0]} {side}</b> {trl}{be}<br>'
                    f'<span style="color:#aaa;font-size:0.82em">'
                    f'@{entry:.2f}|SL:{sl:.2f}|TP:{tp:.2f}|PnL:${pnl:+.4f}|MFE:{mfe:.1f}%</span>'
                )
            if pos_html:
                pf=f'<b>📈 Pos ({n_act}/{pc["max_positions"]})</b><br>{pos_html}'
            else:
                pf=f'<b>📈 Pos (0/{pc["max_positions"]})</b><br><span style="color:#667">Sin pos</span>'
            pos_ph.markdown(f'<div class="mc">{pf}</div>',unsafe_allow_html=True)
            
            # Señales
            signals=[]
            can_trade=dok and n_act<pc['max_positions'] and modo=="Trading Real" and eq>1.0
            if not dok and lc%10==0: log.log(f"Bloqueado: {dreason}", "WARN")
            
            if can_trade:
                if lc%5==0: log.log("🔥 Scanning...", "YOLO")
                for symbol in pc['symbols']:
                    if symbol not in SYMBOLS_CFG: continue
                    if not check_cd(symbol): continue
                    if n_act>=pc['max_positions']: break
                    try:
                        b15=ex.fetch_ohlcv(symbol,'15m',limit=200)
                        b1h=ex.fetch_ohlcv(symbol,'1h',limit=200)
                        b4h=ex.fetch_ohlcv(symbol,'4h',limit=200)
                        if len(b15)<60: continue
                        d15=pd.DataFrame(b15,columns=['ts','o','h','l','c','v'])
                        d1h=pd.DataFrame(b1h,columns=['ts','o','h','l','c','v'])
                        d4h=pd.DataFrame(b4h,columns=['ts','o','h','l','c','v'])
                        sig=gen_signal(d15,d1h,d4h,symbol,log,pc)
                        if not sig: continue
                        signals.append(sig)
                        scfg=SYMBOLS_CFG[symbol]
                        qty=calc_pos(eq,sig['entry'],sig['sl'],pc['leverage'],scfg,pc,log)
                        ms=scfg['min_size']
                        if qty>=ms*0.7:
                            try:
                                so='buy' if sig['side']=='long' else 'sell'
                                notional=qty*sig['entry']; fees=est_fees(notional)
                                log.log(f"📦 {so} {qty} {symbol} N:${notional:.2f} Fees:${fees:.4f}","TRADE")
                                ex.create_order(symbol=symbol,type='market',side=so,amount=qty,params={'leverage':pc['leverage']})
                                st.session_state.active_trades[symbol]={
                                    'entry':sig['entry'],'sl':sig['sl'],'tp':sig['tp'],'trail':False,'be':False,
                                    'risk':abs(sig['entry']-sig['sl'])/sig['entry'],'atr':sig['atr'],
                                    'side':sig['side'].upper(),'oqty':qty,'cqty':qty,
                                    'hi':sig['entry'],'lo':sig['entry'],'mfe':0.0,
                                    'opened':datetime.now(timezone.utc),'score':sig['score'],'razones':sig['razones']
                                }
                                st.session_state.last_signal_candle[symbol]=candle_ts()
                                st.session_state.daily_trades+=1; n_act+=1
                                log.log(f"✅ {sig['side'].upper()} {qty} {symbol} @ {sig['entry']:.2f} S:{sig['score']:.1f} | {', '.join(sig['razones'][:3])}","WIN")
                                if n_act>=pc['max_positions']: break
                            except Exception as e:
                                em=str(e)
                                log.log(f"❌ Order: {em[:100]}", "ERROR")
                                if "margin" in em.lower() or "insufficient" in em.lower():
                                    try:
                                        qr=qty*0.4
                                        if qr>=ms:
                                            ex.create_order(symbol=symbol,type='market',side=so,amount=qr,params={'leverage':pc['leverage']})
                                            st.session_state.last_signal_candle[symbol]=candle_ts()
                                            st.session_state.daily_trades+=1
                                            log.log(f"✅ Retry: {qr} {symbol}","WIN")
                                    except Exception as e2:
                                        log.log(f"Retry fail: {str(e2)[:60]}","ERROR")
                        else:
                            log.log(f"{symbol}: Qty {qty} < {ms}","WARN")
                    except Exception as e:
                        log.log(f"{symbol}: {str(e)[:60]}", "ERROR")
            
            sig_html=""
            for s in signals:
                cl='#00ff44' if s['side']=='long' else '#ff2200'
                rz=" | ".join(s['razones'][:3])
                sig_html+=(
                    f'<hr style="border-color:{cl};opacity:0.4;margin:5px 0">'
                    f'<span style="color:{cl};font-weight:700;font-size:1em">{s["side"].upper()} {s["symbol"].split("/")[0]}</span>'
                    f' <span style="color:#888">S:{s["score"]:.1f}</span><br>'
                    f'<span style="color:#ccc;font-size:0.85em">@{s["entry"]:.2f}|SL:{s["sl"]:.2f}|TP:{s["tp"]:.2f}|RR:{pc["rr_ratio"]}:1</span><br>'
                    f'<span style="color:#889;font-size:0.78em">{rz}</span>'
                )
            sf_html=f'<b>🎯 Señales ({len(signals)})</b><br>{sig_html}' if sig_html else '<b>🎯 Señales (0)</b><br><span style="color:#667">Scanning...</span>'
            sig_ph.markdown(f'<div class="mc">{sf_html}</div>',unsafe_allow_html=True)
            
            # Logs
            logs=log.get(30)
            lh="<br>".join([f'<span style="font-family:monospace;font-size:0.72em;color:#99aabb">{l}</span>' for l in logs]) if logs else '<span style="color:#667">No logs</span>'
            log_ph.markdown(f'<div class="mc" style="max-height:280px;overflow-y:auto">{lh}</div>',unsafe_allow_html=True)
            
            # Stats
            pf=s.get('profit_factor',0)
            sw=s.get('wins',0); sl2=s.get('losses',0)
            ev=(wr/100*s.get('avg_win',0))-((1-wr/100)*s.get('avg_loss',0)) if (sw+sl2)>0 else 0
            stat_ph.markdown(f"""
            <div class="mc" style="text-align:center">
                <small style="color:#8899aa">
                    <b>PF:</b> {pf:.2f} | <b>Exp:</b> ${ev:+.4f}/t | <b>DD:</b> ${s.get('max_drawdown',0):+.4f}<br>
                    <b>Win:</b> ${s.get('avg_win',0):.4f} | <b>Loss:</b> ${s.get('avg_loss',0):.4f} | <b>Fees:</b> ${s.get('total_fees_paid',0):.4f}<br>
                    <b>Streak W:</b> {s.get('max_consecutive_wins',0)} | <b>Streak L:</b> {s.get('max_consecutive_losses',0)} | <b>Total:</b> {s.get('total_trades',0)}
                </small>
            </div>""",unsafe_allow_html=True)
            
            time.sleep(12)
            st.rerun()
        except Exception as e:
            st.error(f"❌ {e}")
            log.log(f"CRITICAL: {str(e)[:150]}", "ERROR")
            import traceback
            log.log(traceback.format_exc()[:300], "ERROR")
            time.sleep(12)
            st.rerun()
    else:
        if not activar: st.info("👈 API Key + Secret + Toggle 🔥 YOLO")
        elif not api_key or not api_secret: st.error("❌ API Key y Secret requeridos")

if __name__ == "__main__":
    main()
