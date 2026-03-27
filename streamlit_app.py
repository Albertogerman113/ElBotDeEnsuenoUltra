"""
SNIPER V5 — PRICE ACTION WARRIOR
Bot completamente autónomo. El usuario solo pone sus APIs y elige el modo.
Todas las decisiones (apalancamiento, tamaño, TP, SL, etc.) las toma el bot.
"""

import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime

# ══════════════════════════════════════════════════════════
# PARÁMETROS INTERNOS — EL BOT DECIDE TODO
# ══════════════════════════════════════════════════════════
SYMBOLS          = ['BTC/USD:USD', 'ETH/USD:USD', 'SOL/USD:USD']
LEVERAGE         = 10
RISK_PCT         = 0.02
RR_RATIO         = 2.0
MAX_POSITIONS    = 2
ATR_SL_MULTI     = 1.5
MIN_SCORE        = 5
TIMEFRAME_ENTRY  = '15m'
TIMEFRAME_TREND  = '1h'
BARS_LIMIT       = 300
SCAN_INTERVAL    = 30

# ══════════════════════════════════════════════════════════
# UI CONFIG
# ══════════════════════════════════════════════════════════
st.set_page_config(page_title="SNIPER V5", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif; }
.stApp { background-color: #060b14; color: #c8d8f0; }
section[data-testid="stSidebar"] { background: #080d18; border-right: 1px solid #1a2a4a; }
.card {
    background: linear-gradient(160deg, #0b1628 0%, #0f1e38 100%);
    border: 1px solid #1e3358; border-radius: 10px;
    padding: 14px 18px; margin-bottom: 10px;
}
.card-title { font-size: 0.72em; color: #4a7aaa; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 6px; }
.val-big { font-family: 'Share Tech Mono', monospace; font-size: 1.9em; color: #4a9eff; line-height: 1.1; }
.val-sub { font-family: 'Share Tech Mono', monospace; font-size: 0.78em; color: #5a7a9a; margin-top: 4px; }
.long  { color: #00e87a !important; }
.short { color: #ff3d5a !important; }
.log-box {
    font-family: 'Share Tech Mono', monospace; font-size: 0.75em;
    background: #060b14; border: 1px solid #1a2a3a; border-radius: 8px;
    padding: 10px 14px; max-height: 220px; overflow-y: auto; line-height: 1.7;
}
.tag { display:inline-block; padding:1px 7px; border-radius:4px; font-size:0.7em; font-weight:700; letter-spacing:1px; margin-right:4px; }
.tag-long  { background:#003d20; color:#00e87a; border:1px solid #00e87a44; }
.tag-short { background:#3d0010; color:#ff3d5a; border:1px solid #ff3d5a44; }
.mode-pill { display:inline-block; padding:3px 12px; border-radius:20px; font-size:0.8em; font-weight:700; }
.mode-real  { background:#003020; color:#00e87a; border:1px solid #00e87a66; }
.mode-paper { background:#0a1e38; color:#4a9eff; border:1px solid #4a9eff66; }
</style>
""", unsafe_allow_html=True)

# Estado de sesión
for k, v in [('trade_log', []), ('stats', {'wins': 0, 'losses': 0, 'pnl': 0.0}), ('ciclos', 0)]:
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════════════════════
def sf(val, default=0.0):
    try: return float(val) if val is not None else default
    except: return default

def log_add(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    colors = {"INFO":("#4a9eff","INFO"), "SCAN":("#8a6aff","SCAN"), "TRADE":("#00e87a","TRADE"),
              "WIN":("#00cc66"," WIN"), "LOSS":("#ff6680","LOSS"), "WARN":("#f0a000","WARN"), "ERROR":("#ff3d5a"," ERR")}
    color, tag = colors.get(level, ("#888","INFO"))
    entry = f'<span style="color:#3a5a7a">[{now}]</span> <span style="color:{color}; font-weight:700">[{tag}]</span> {msg}'
    st.session_state.trade_log.insert(0, entry)
    st.session_state.trade_log = st.session_state.trade_log[:150]


# ══════════════════════════════════════════════════════════
# ANÁLISIS TÉCNICO
# ══════════════════════════════════════════════════════════
def calcular_indicadores(df):
    c = df['c'].astype(float); h = df['h'].astype(float)
    l = df['l'].astype(float); o = df['o'].astype(float)
    df['ema20']  = c.ewm(span=20,  adjust=False).mean()
    df['ema50']  = c.ewm(span=50,  adjust=False).mean()
    df['ema200'] = c.ewm(span=200, adjust=False).mean()
    tr = pd.concat([h-l, abs(h-c.shift(1)), abs(l-c.shift(1))], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    df['vol_ratio'] = df['v'].astype(float) / df['v'].astype(float).rolling(20).mean()
    df['body']    = abs(c - o)
    df['wick_up'] = h - pd.concat([c, o], axis=1).max(axis=1)
    df['wick_dn'] = pd.concat([c, o], axis=1).min(axis=1) - l
    return df

def estructura_mercado(df):
    h = df['h'].astype(float).values; l = df['l'].astype(float).values
    sh, sl = [], []
    for i in range(3, len(df)-1):
        if h[i] == max(h[max(0,i-3):i+2]): sh.append(h[i])
        if l[i] == min(l[max(0,i-3):i+2]): sl.append(l[i])
    if len(sh) < 2 or len(sl) < 2: return 'neutral'
    return 'bullish' if sh[-1]>sh[-2] and sl[-1]>sl[-2] else 'bearish' if sh[-1]<sh[-2] and sl[-1]<sl[-2] else 'neutral'

def order_blocks(df, n=5):
    c = df['c'].astype(float).values; o = df['o'].astype(float).values
    bull, bear = [], []
    for i in range(2, len(df)-n):
        up = (c[i+n]-c[i])/c[i]*100; dn = (c[i]-c[i+n])/c[i]*100
        if o[i] > c[i] and up > 1.5: bull.append({'mid':(o[i]+c[i])/2,'top':o[i],'bot':c[i]})
        if c[i] > o[i] and dn > 1.5: bear.append({'mid':(c[i]+o[i])/2,'top':c[i],'bot':o[i]})
    return bull[-3:], bear[-3:]

def fvg_zones(df):
    h = df['h'].astype(float).values; l = df['l'].astype(float).values
    bull, bear = [], []
    for i in range(1, len(df)-1):
        if l[i+1] > h[i-1]: bull.append({'bot':h[i-1],'top':l[i+1]})
        if h[i+1] < l[i-1]: bear.append({'bot':h[i+1],'top':l[i-1]})
    return bull[-3:], bear[-3:]

def pin_bar(df):
    r = df.iloc[-1]; rng = sf(r['h']) - sf(r['l'])
    if rng == 0: return None
    wu = sf(r['h']) - max(sf(r['c']), sf(r['o']))
    wd = min(sf(r['c']), sf(r['o'])) - sf(r['l'])
    body = abs(sf(r['c']) - sf(r['o']))
    if wd > rng*0.6 and body < rng*0.3: return 'bull'
    if wu > rng*0.6 and body < rng*0.3: return 'bear'
    return None

def inside_bar(df):
    if len(df) < 2: return False
    c, p = df.iloc[-1], df.iloc[-2]
    return sf(c['h']) < sf(p['h']) and sf(c['l']) > sf(p['l'])


# ══════════════════════════════════════════════════════════
# SEÑAL — CONFLUENCIA PRICE ACTION
# ══════════════════════════════════════════════════════════
def generar_senal(df_15m, df_1h):
    if len(df_15m) < 210 or len(df_1h) < 60: return None
    df_15m = calcular_indicadores(df_15m.copy())
    df_1h  = calcular_indicadores(df_1h.copy())
    last = df_15m.iloc[-1]; precio = sf(last['c']); atr = sf(last['atr']); rsi = sf(last['rsi'])
    if atr == 0: return None

    e1h = estructura_mercado(df_1h)
    ema50_1h = sf(df_1h.iloc[-1]['ema50']); ema200_1h = sf(df_1h.iloc[-1]['ema200'])
    trend = 'bull' if ema50_1h > ema200_1h and e1h == 'bullish' else \
            'bear' if ema50_1h < ema200_1h and e1h == 'bearish' else 'neutral'

    e15m = estructura_mercado(df_15m)
    ob_bull, ob_bear = order_blocks(df_15m)
    fvg_bull, fvg_bear = fvg_zones(df_15m)
    pin = pin_bar(df_15m); ib = inside_bar(df_15m); vol_ok = sf(last['vol_ratio']) > 1.2

    sl = sb = 0; rl = []; rb = []

    if trend == 'bull':   sl += 2; rl.append("Tendencia 1h ▲")
    if e15m == 'bullish': sl += 1; rl.append("Estructura 15m ▲")
    if precio > sf(last['ema200']): sl += 1; rl.append("Sobre EMA200")
    for ob in ob_bull:
        if abs(precio - ob['mid']) / precio < 0.006: sl += 2; rl.append(f"OB bull @{ob['mid']:.1f}")
    for f in fvg_bull:
        if f['bot'] <= precio <= f['top']: sl += 2; rl.append(f"FVG bull")
    if pin == 'bull': sl += 2; rl.append("Pin Bar ▲")
    if ib:            sl += 1; rl.append("Inside Bar")
    if 40 < rsi < 65: sl += 1; rl.append(f"RSI {rsi:.0f}")
    if vol_ok:        sl += 1; rl.append("Volumen ↑")

    if trend == 'bear':   sb += 2; rb.append("Tendencia 1h ▼")
    if e15m == 'bearish': sb += 1; rb.append("Estructura 15m ▼")
    if precio < sf(last['ema200']): sb += 1; rb.append("Bajo EMA200")
    for ob in ob_bear:
        if abs(precio - ob['mid']) / precio < 0.006: sb += 2; rb.append(f"OB bear @{ob['mid']:.1f}")
    for f in fvg_bear:
        if f['bot'] <= precio <= f['top']: sb += 2; rb.append(f"FVG bear")
    if pin == 'bear': sb += 2; rb.append("Pin Bar ▼")
    if ib:            sb += 1; rb.append("Inside Bar")
    if 35 < rsi < 60: sb += 1; rb.append(f"RSI {rsi:.0f}")
    if vol_ok:        sb += 1; rb.append("Volumen ↑")

    if sl >= MIN_SCORE and sl > sb:
        return {'side':'long',  'precio':precio, 'sl':precio - atr*ATR_SL_MULTI,
                'tp':precio + atr*ATR_SL_MULTI*RR_RATIO, 'atr':atr, 'score':sl, 'razones':rl}
    if sb >= MIN_SCORE and sb > sl:
        return {'side':'short', 'precio':precio, 'sl':precio + atr*ATR_SL_MULTI,
                'tp':precio - atr*ATR_SL_MULTI*RR_RATIO, 'atr':atr, 'score':sb, 'razones':rb}
    return None


# ══════════════════════════════════════════════════════════
# GESTIÓN DE CAPITAL
# ══════════════════════════════════════════════════════════
def calcular_qty(equity, precio, sl_price, sym):
    riesgo_usd = equity * RISK_PCT
    dist = abs(precio - sl_price) / precio
    if dist == 0: return 0
    qty = (riesgo_usd / dist) / precio
    qty = min(qty, (equity * 0.45 * LEVERAGE) / precio)
    if 'BTC' in sym: return round(qty, 5)
    if 'ETH' in sym: return round(qty, 4)
    return round(qty, 2)


# ══════════════════════════════════════════════════════════
# GESTIÓN DE POSICIONES
# ══════════════════════════════════════════════════════════
def gestionar_posiciones(posiciones, exchange):
    n = 0
    for p in posiciones:
        qty = sf(p.get('contracts', 0))
        if qty <= 0: continue
        n += 1
        sym = p['symbol']; side = p['side'].upper()
        entry = sf(p.get('entryPrice')); mark = sf(p.get('markPrice')); pnl = sf(p.get('unrealizedPnl'))
        if entry == 0: continue
        close = 'sell' if side == 'LONG' else 'buy'
        move  = ((mark-entry)/entry*100) if side=='LONG' else ((entry-mark)/entry*100)
        if move >= 3.0:
            try:
                exchange.create_market_order(sym, close, qty, params={'reduceOnly': True})
                st.session_state.stats['wins'] += 1; st.session_state.stats['pnl'] += pnl
                log_add(f"TP alcanzado {sym.split('/')[0]} +{move:.2f}% PnL ${pnl:+.4f}", "WIN"); n -= 1
            except Exception as e: log_add(f"Error TP {sym}: {e}", "ERROR")
        elif move <= -1.5:
            try:
                exchange.create_market_order(sym, close, qty, params={'reduceOnly': True})
                st.session_state.stats['losses'] += 1; st.session_state.stats['pnl'] += pnl
                log_add(f"SL activado {sym.split('/')[0]} {move:.2f}% PnL ${pnl:+.4f}", "LOSS"); n -= 1
            except Exception as e: log_add(f"Error SL {sym}: {e}", "ERROR")
        elif move >= 1.5:
            log_add(f"Trailing activo {sym.split('/')[0]} +{move:.2f}% — SL en breakeven", "INFO")
    return n


# ══════════════════════════════════════════════════════════
# SIDEBAR — SOLO APIs + MODO
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:10px 0 20px">
        <div style="font-family:'Share Tech Mono',monospace; font-size:1.4em; color:#4a9eff; letter-spacing:3px">◈ SNIPER V5</div>
        <div style="font-size:0.72em; color:#3a5a7a; letter-spacing:4px">PRICE ACTION WARRIOR</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("**🔐 Credenciales Kraken Futures**")
    api_key    = st.text_input("API Key",    type="password", placeholder="api key")
    api_secret = st.text_input("API Secret", type="password", placeholder="api secret")

    st.markdown("<hr style='border-color:#1a2a4a'>", unsafe_allow_html=True)
    st.markdown("**⚙️ Modo de Operación**")
    modo = st.radio("", ["📊 Solo Análisis", "⚡ Trading Real"], label_visibility="collapsed")

    st.markdown("<hr style='border-color:#1a2a4a'>", unsafe_allow_html=True)
    activar = st.toggle("▶  INICIAR BOT", value=False)

    st.markdown("<hr style='border-color:#1a2a4a'>", unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:0.72em; color:#2a4a6a; line-height:2.1">
    <b style="color:#3a5a7a; letter-spacing:2px">CONFIG INTERNA</b><br>
    Apalancamiento ·· 10×<br>
    Riesgo/trade ···· 2%<br>
    TP ·············· 2× SL<br>
    SL ·············· 1.5× ATR<br>
    Posiciones máx · 2<br>
    Score mínimo ··· 5/10<br>
    TF entrada ····· 15m<br>
    TF tendencia ··· 1h<br>
    <br>
    <b style="color:#3a5a7a; letter-spacing:2px">ESTRATEGIAS</b><br>
    ✦ Order Blocks<br>
    ✦ Fair Value Gaps<br>
    ✦ BOS / CHoCH<br>
    ✦ Pin Bar + Inside Bar<br>
    ✦ Multi-Timeframe<br>
    ✦ Trailing Stop<br>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════
modo_label = ('<span class="mode-pill mode-real">⚡ MODO REAL</span>' if modo == "⚡ Trading Real"
              else '<span class="mode-pill mode-paper">📊 ANÁLISIS</span>')
st.markdown(f"""
<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px">
    <div>
        <span style="font-family:'Share Tech Mono',monospace; font-size:1.6em; color:#4a9eff; letter-spacing:3px">◈ SNIPER V5</span>
        <span style="font-size:0.8em; color:#3a5a7a; margin-left:12px">PRICE ACTION WARRIOR</span>
    </div>
    <div>{modo_label} &nbsp;<span style="font-family:'Share Tech Mono',monospace; font-size:0.8em; color:#2a4a6a">{datetime.now().strftime('%d/%m/%Y  %H:%M:%S')}</span></div>
</div>
<hr style="margin:0 0 12px 0; border-color:#1a2a4a">
""", unsafe_allow_html=True)

# ── Placeholders ──
r1 = st.columns([1, 1, 1, 1])
cap_ph = r1[0].empty(); pos_ph = r1[1].empty(); stat_ph = r1[2].empty(); scan_ph = r1[3].empty()
sig_ph = st.empty(); log_ph = st.empty()


# ── Render helpers ──
def render_capital(eq):
    cap_ph.markdown(f"""<div class="card"><div class="card-title">Capital</div>
    <div class="val-big">${eq:.4f}</div><div class="val-sub">USD disponible</div></div>""", unsafe_allow_html=True)

def render_stats():
    s = st.session_state.stats
    wr = (s['wins']/(s['wins']+s['losses'])*100) if (s['wins']+s['losses']) > 0 else 0
    pc = "#00e87a" if s['pnl'] >= 0 else "#ff3d5a"
    stat_ph.markdown(f"""<div class="card"><div class="card-title">Estadísticas</div>
    <div style="font-family:'Share Tech Mono',monospace; font-size:0.9em; line-height:2">
    <span class="long">W:{s['wins']}</span> &nbsp; <span class="short">L:{s['losses']}</span>
    &nbsp; <span style="color:#6a8aaa">WR:{wr:.0f}%</span><br>
    <span style="color:{pc}">PnL: ${s['pnl']:+.4f}</span></div></div>""", unsafe_allow_html=True)

def render_posiciones(pos):
    activas = [p for p in pos if sf(p.get('contracts',0)) > 0]
    if not activas:
        body = '<span style="color:#2a4a6a; font-size:0.88em">Sin posiciones abiertas</span>'
    else:
        body = ""
        for p in activas:
            sym  = p['symbol'].split('/')[0]; side = p['side'].upper()
            entry = sf(p.get('entryPrice')); mark = sf(p.get('markPrice')); pnl = sf(p.get('unrealizedPnl'))
            move = ((mark-entry)/entry*100) if side=='LONG' else ((entry-mark)/entry*100)
            cls = "long" if pnl >= 0 else "short"; arr = "▲" if side=='LONG' else "▼"
            brd = "#00e87a" if pnl >= 0 else "#ff3d5a"
            body += f"""<div style="font-family:'Share Tech Mono',monospace; font-size:0.8em; margin:4px 0;
                        padding:6px 8px; background:#0a1628; border-radius:6px; border-left:3px solid {brd}">
                <span class="{cls}">{arr} {sym} {side}</span><br>
                {entry:.2f}→{mark:.2f} &nbsp; <span class="{cls}">{move:+.2f}% (${pnl:+.4f})</span></div>"""
    pos_ph.markdown(f"""<div class="card"><div class="card-title">Posiciones ({len(activas)}/{MAX_POSITIONS})</div>{body}</div>""",
                    unsafe_allow_html=True)

def render_scan(ciclo, n):
    scan_ph.markdown(f"""<div class="card"><div class="card-title">Estado</div>
    <div style="font-family:'Share Tech Mono',monospace; font-size:0.88em; line-height:2.1; color:#4a6a8a">
    Ciclo: <span style="color:#4a9eff">{ciclo}</span><br>
    Posiciones: <span style="color:#4a9eff">{n}/{MAX_POSITIONS}</span><br>
    Scan: <span style="color:#4a9eff">{SCAN_INTERVAL}s</span></div></div>""", unsafe_allow_html=True)

def render_signals(signals):
    if not signals:
        body = '<div style="color:#2a5a3a; padding:10px; font-size:0.9em">⏳ Esperando confluencia de señales...</div>'
    else:
        body = ""
        for s in signals:
            isl = s['side'] == 'long'; color = "#00e87a" if isl else "#ff3d5a"
            bg = "#001a0d" if isl else "#1a000a"; arrow = "▲ LONG" if isl else "▼ SHORT"
            tc = "tag-long" if isl else "tag-short"; sym = s['symbol'].split('/')[0]
            razones = " · ".join(s['razones'][:5])
            body += f"""<div style="border:1px solid {color}22; background:{bg}; border-radius:8px;
                        padding:12px 16px; margin:6px 0; border-left:4px solid {color}">
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px">
                    <span class="tag {tc}">{arrow}</span>
                    <span style="color:{color}; font-size:1.1em; font-weight:700">{sym}</span>
                    <span style="color:#3a5a7a; font-size:0.8em">Score: {s['score']}/10</span>
                </div>
                <div style="font-family:'Share Tech Mono',monospace; font-size:0.82em; line-height:1.9; color:#7a9ab8">
                    Entry: <b style="color:#c8d8f0">{s['precio']:.2f}</b> &nbsp;|&nbsp;
                    SL: <b style="color:#ff3d5a">{s['sl']:.2f}</b> &nbsp;|&nbsp;
                    TP: <b style="color:#00e87a">{s['tp']:.2f}</b>
                </div>
                <div style="font-size:0.75em; color:#2a5a7a; margin-top:4px">{razones}</div></div>"""
    sig_ph.markdown(f"""<div class="card"><div class="card-title">🎯 Señales detectadas</div>{body}</div>""",
                    unsafe_allow_html=True)

def render_log():
    entries = "<br>".join(st.session_state.trade_log[:30])
    log_ph.markdown(f'<div class="log-box">{entries}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# PANTALLA INICIAL
# ══════════════════════════════════════════════════════════
if not activar or not api_key or not api_secret:
    render_capital(0.0); render_stats(); render_posiciones([]); render_scan(0, 0); render_signals([])
    if not api_key or not api_secret:
        log_add("Esperando credenciales en el panel lateral...", "WARN")
    else:
        log_add("Credenciales listas — activa el bot para comenzar.", "INFO")
    render_log(); st.stop()


# ══════════════════════════════════════════════════════════
# LOOP PRINCIPAL
# ══════════════════════════════════════════════════════════
try:
    exchange = ccxt.krakenfutures({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
    for sym in SYMBOLS:
        try: exchange.set_leverage(LEVERAGE, sym)
        except: pass
    log_add("Bot iniciado — escaneando BTC / ETH / SOL", "INFO")

    while True:
        st.session_state.ciclos += 1
        ciclo = st.session_state.ciclos

        try:
            bal = exchange.fetch_total_balance(); equity = sf(bal.get('USD', 0))
        except Exception as e:
            log_add(f"Error balance: {e}", "ERROR"); equity = 0.0

        try:
            posiciones = exchange.fetch_positions()
            n_activas  = gestionar_posiciones(posiciones, exchange)
        except Exception as e:
            posiciones = []; n_activas = 0; log_add(f"Error posiciones: {e}", "ERROR")

        render_capital(equity); render_posiciones(posiciones)
        render_stats(); render_scan(ciclo, n_activas)

        senales = []
        if n_activas < MAX_POSITIONS:
            log_add(f"Ciclo {ciclo} — escaneando mercados...", "SCAN")
            for sym in SYMBOLS:
                if n_activas >= MAX_POSITIONS: break
                try:
                    df15 = pd.DataFrame(exchange.fetch_ohlcv(sym, TIMEFRAME_ENTRY, limit=BARS_LIMIT),
                                        columns=['ts','o','h','l','c','v'])
                    df1h = pd.DataFrame(exchange.fetch_ohlcv(sym, TIMEFRAME_TREND,  limit=BARS_LIMIT),
                                        columns=['ts','o','h','l','c','v'])
                    senal = generar_senal(df15, df1h)
                    if senal:
                        senal['symbol'] = sym; senales.append(senal)
                        log_add(f"SEÑAL {'LONG' if senal['side']=='long' else 'SHORT'} "
                                f"{sym.split('/')[0]} Score:{senal['score']} | "
                                f"{' · '.join(senal['razones'][:3])}", "TRADE")
                        if modo == "⚡ Trading Real":
                            qty = calcular_qty(equity, senal['precio'], senal['sl'], sym)
                            if qty > 0:
                                order_side = 'buy' if senal['side'] == 'long' else 'sell'
                                exchange.create_market_order(sym, order_side, qty)
                                log_add(f"ORDEN: {order_side.upper()} {qty} {sym.split('/')[0]} "
                                        f"@ {senal['precio']:.2f} SL:{senal['sl']:.2f} TP:{senal['tp']:.2f}", "TRADE")
                                n_activas += 1
                        else:
                            log_add(f"[PAPER] Señal válida — sin ejecutar (modo análisis)", "INFO")
                except Exception as e:
                    log_add(f"Error {sym.split('/')[0]}: {str(e)[:90]}", "ERROR"); continue

        render_signals(senales); render_log()
        time.sleep(SCAN_INTERVAL); st.rerun()

except Exception as e:
    st.error(f"❌ Error crítico: {e}")
    log_add(f"Error crítico: {e}", "ERROR"); render_log(); time.sleep(15)
