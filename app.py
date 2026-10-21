import streamlit as st
import pandas as pd
import time
import os
from datetime import datetime
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

# Feltételezzük, hogy a BinaryOptionsToolsV2 a projekt mappájában van
from BinaryOptionsToolsV2.pocketoption import PocketOption
import config

st.set_page_config(
    page_title="PO Signal Bot",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ---------- Stílus ----------
st.markdown("""
<style>
    .stApp {
        background-color: #0f0f0f;
        color: #ffffff;
    }
    .stButton > button {
        width: 100%;
        height: 42px;
        font-size: 14px;
        font-weight: 600;
        border-radius: 10px;
        transition: all 0.2s ease-in-out;
    }
    .signal-box {
        text-align: center;
        padding: 24px 16px;
        border-radius: 16px;
        margin: 16px 0;
        font-size: 28px;
        font-weight: 800;
        color: white;
        box-shadow: 0 8px 16px rgba(0,0,0,0.4);
    }
    .card {
        background-color: #1c1c1e;
        border: 1px solid #2c2c2e;
        border-radius: 12px;
        padding: 12px 10px;
        text-align: center;
        margin-bottom: 10px;
        height: 85px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .card-title {
        font-size: 12px;
        color: #98989d;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .card-value {
        font-size: 16px;
        font-weight: 700;
    }
    .card-detail {
        font-size: 11px;
        color: #636366;
        margin-top: 4px;
    }
    .green { color: #30d158; }
    .red { color: #ff453a; }
    .gray { color: #d1d1d6; }
</style>
""", unsafe_allow_html=True)

st.markdown("### 📊 PO Signal Dashboard")
st.caption("Valódi OTC adatok • Részletes Elemzés")

# ---------- Kapcsolódás (Cache-elve, hogy ne szakadjon meg a websocket) ----------
@st.cache_resource(show_spinner=False)
def get_client():
    # Renderen környezeti változóból, amúgy configból veszi az SSID-t
    ssid = os.getenv("PO_SSID", config.SSID)
    client = PocketOption(ssid)
    time.sleep(3) # Kis várakozás a sikeres csatlakozáshoz
    return client

try:
    with st.spinner("Kapcsolódás a Pocket Option szervereihez..."):
        client = get_client()
except Exception as e:
    st.error(f"Kapcsolódási hiba: {e}")
    st.stop()

# ---------- Session state ----------
if "selected_pair" not in st.session_state:
    st.session_state.selected_pair = config.PAIRS[0]
if "timeframe" not in st.session_state:
    st.session_state.timeframe = 60
if "custom_pairs" not in st.session_state:
    st.session_state.custom_pairs = []

all_pairs = list(dict.fromkeys(config.PAIRS + st.session_state.custom_pairs))

# ---------- 1. Szekció: Pár és Időtáv Választó ----------
c1, c2 = st.columns([2, 1])
with c1:
    st.session_state.selected_pair = st.selectbox(
        "Kereskedési Pár", 
        all_pairs, 
        index=all_pairs.index(st.session_state.selected_pair) if st.session_state.selected_pair in all_pairs else 0
    )
with c2:
    tf_options = {60: "1 perc", 300: "5 perc", 900: "15 perc", 1800: "30 perc"}
    selected_tf_label = st.selectbox(
        "Időtáv", 
        list(tf_options.values()), 
        index=list(tf_options.keys()).index(st.session_state.timeframe)
    )
    st.session_state.timeframe = list(tf_options.keys())[list(tf_options.values()).index(selected_tf_label)]

with st.expander("➕ Új egyedi pár hozzáadása"):
    new_pair_input = st.text_input("Pár neve (pl. SOLUSD_otc)")
    if st.button("Hozzáadás"):
        if new_pair_input.strip():
            clean = new_pair_input.strip()
            if not clean.endswith("_otc"): clean += "_otc"
            if clean not in all_pairs:
                st.session_state.custom_pairs.append(clean)
                st.success("Hozzáadva!")
                time.sleep(0.5)
                st.rerun()

# ---------- 2. Szekció: Finomhangolás ----------
with st.expander("⚙️ Indikátor és Stratégia Finomhangolás"):
    st.markdown("**Mozgóátlagok (EMA)**")
    col1, col2 = st.columns(2)
    ema_fast_len = col1.number_input("EMA Gyors", min_value=3, max_value=50, value=9)
    ema_slow_len = col2.number_input("EMA Lassú", min_value=5, max_value=200, value=21)
    
    st.markdown("**RSI Beállítások**")
    col3, col4, col5 = st.columns(3)
    rsi_len = col3.number_input("RSI Periódus", 5, 50, 14)
    rsi_ob = col4.number_input("Túlvettség", 50, 100, 62)
    rsi_os = col5.number_input("Túladottság", 0, 50, 38)
    
    st.markdown("**Bollinger Beállítások**")
    col6, col7 = st.columns(2)
    bb_len = col6.number_input("BB Periódus", 5, 50, 20)
    bb_dev = col7.number_input("BB Szórás", 1.0, 5.0, 2.0, step=0.1)
    
    st.markdown("**Jelzési Küszöb**")
    threshold = st.slider("Szükséges szavazat a jelzéshez", 1.0, 5.0, 2.0, 0.5)

# ---------- 3. Szekció: Élő adatok kezelése ----------
st.markdown("<br>", unsafe_allow_html=True)
col_a, col_b = st.columns([3, 1])
with col_a:
    get_signal = st.button("🚀 Elemzés Kérése", type="primary", use_container_width=True)
with col_b:
    auto_refresh = st.toggle("Élő frissítés (10mp)", value=False)

# ---------- EREDMÉNYEK ----------
if get_signal or auto_refresh:
    pair = st.session_state.selected_pair
    tf = st.session_state.timeframe

    with st.spinner("Piaci adatok beolvasása..."):
        try:
            # Élő adat lekérése az adott pillanatban
            candles = client.get_candles(pair, tf, 120)

            if not candles or len(candles) < 50:
                st.warning("Nem sikerült elég gyertyát lekérni. Kérlek ellenőrizd az SSID-t vagy válassz másik párt.")
            else:
                df = pd.DataFrame(candles)
                if "close" not in df.columns:
                    st.error("Hibás adatformátum a brókertől.")
                    st.stop()

                close = df["close"].astype(float)

                # Indikátorok számítása
                ema_fast = EMAIndicator(close=close, window=ema_fast_len).ema_indicator()
                ema_slow = EMAIndicator(close=close, window=ema_slow_len).ema_indicator()
                rsi = RSIIndicator(close=close, window=rsi_len).rsi()
                macd_ind = MACD(close=close)
                macd = macd_ind.macd()
                macd_sig = macd_ind.macd_signal()
                bb = BollingerBands(close=close, window=bb_len, window_dev=bb_dev)
                bb_upper = bb.bollinger_hband()
                bb_lower = bb.bollinger_lband()
                bb_mid = bb.bollinger_mavg()

                # Utolsó lezárt gyertya (-2) használata a stabil jelzésekhez
                i = -2
                price = close.iloc[i]
                last_price = close.iloc[-1] # A legfrissebb tick árfolyam
                e_f = ema_fast.iloc[i]
                e_s = ema_slow.iloc[i]
                r = rsi.iloc[i]
                m = macd.iloc[i]
                ms = macd_sig.iloc[i]
                up = bb_upper.iloc[i]
                low = bb_lower.iloc[i]
                mid = bb_mid.iloc[i]

                # --- Szavazási Logika ---
                call_v, put_v = 0.0, 0.0

                if e_f > e_s:
                    call_v += 1.0; trend_txt, trend_pos = "UPTREND", True
                else:
                    put_v += 1.0; trend_txt, trend_pos = "DOWNTREND", False

                if r < rsi_os:
                    call_v += 1.2; rsi_status, rsi_pos = "OVERSOLD", True
                elif r > rsi_ob:
                    put_v += 1.2; rsi_status, rsi_pos = "OVERBOUGHT", False
                else:
                    if r > 50: call_v += 0.5
                    else: put_v += 0.5
                    rsi_status, rsi_pos = "NEUTRAL", None

                if m > ms:
                    call_v += 1.0; macd_status, macd_pos = "BULLISH CROSS", True
                else:
                    put_v += 1.0; macd_status, macd_pos = "BEARISH CROSS", False

                if price <= low:
                    call_v += 1.3; bb_status, bb_pos = "LOWER BAND", True
                elif price >= up:
                    put_v += 1.3; bb_status, bb_pos = "UPPER BAND", False
                else:
                    bb_status, bb_pos = "INSIDE BANDS", None

                # --- Döntéshozatal ---
                if call_v >= threshold and call_v > put_v:
                    signal, direction, color, bg = "CALL  ↑", "HIGHER", "#30d158", "linear-gradient(135deg, #122b1c, #0a170f)"
                elif put_v >= threshold and put_v > call_v:
                    signal, direction, color, bg = "PUT  ↓", "LOWER", "#ff453a", "linear-gradient(135deg, #2b1212, #170a0a)"
                else:
                    signal, direction, color, bg = "VÁRAKOZÁS", "Nincs egyértelmű irány", "#d1d1d6", "#1c1c1e"

                # --- UI: Fő Jelzés ---
                st.markdown(f"""
                <div class="signal-box" style="background: {bg}; border: 1px solid {color}55;">
                    <div style="font-size: 12px; color: #98989d; margin-bottom: 8px; text-transform: uppercase;">
                        {pair.replace('_otc','')} • {tf_options[tf]}
                    </div>
                    <div style="font-size: 36px; color: {color}; text-shadow: 0 0 10px {color}44;">{signal}</div>
                    <div style="font-size: 13px; margin-top: 10px; color: #d1d1d6;">
                        Művelet: <b>{direction}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # --- UI: Indikátor Kártyák Generáló ---
                def metric_card(title, value, detail, positive=None):
                    cls = "green" if positive is True else ("red" if positive is False else "gray")
                    return f"""
                    <div class="card">
                        <div class="card-title">{title}</div>
                        <div class="card-value {cls}">{value}</div>
                        <div class="card-detail">{detail}</div>
                    </div>
                    """

                st.markdown("<h4 style='font-size: 16px; margin-top: 10px;'>📡 Piaci Szenzorok</h4>", unsafe_allow_html=True)

                c1, c2 = st.columns(2)
                c1.markdown(metric_card(f"EMA {ema_fast_len}/{ema_slow_len}", trend_txt, f"Gyors: {e_f:.4f} | Lassú: {e_s:.4f}", trend_pos), unsafe_allow_html=True)
                c2.markdown(metric_card(f"RSI ({rsi_len})", f"{r:.1f}", f"Állapot: {rsi_status}", rsi_pos), unsafe_allow_html=True)

                c3, c4 = st.columns(2)
                c3.markdown(metric_card("MACD", macd_status, f"M: {m:.5f} | S: {ms:.5f}", macd_pos), unsafe_allow_html=True)
                c4.markdown(metric_card("Bollinger", bb_status, f"Ár: {price:.4f} | Alsó: {low:.4f}", bb_pos), unsafe_allow_html=True)

                st.markdown("<h4 style='font-size: 16px; margin-top: 10px;'>📊 Algoritmus Szavazatok</h4>", unsafe_allow_html=True)
                c5, c6, c7 = st.columns(3)
                c5.markdown(metric_card("CALL", f"{call_v:.1f}", "Fel szavazat", True if call_v > put_v else None), unsafe_allow_html=True)
                c6.markdown(metric_card("JELENLEGI ÁR", f"{last_price:.5f}", "Aktuális Piaci Ár"), unsafe_allow_html=True)
                c7.markdown(metric_card("PUT", f"{put_v:.1f}", "Le szavazat", False if put_v > call_v else None), unsafe_allow_html=True)

                st.markdown(f"<div style='text-align: center; color: #636366; font-size: 12px; margin-top: 15px;'>Frissítve: {datetime.now().strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)

                # Élő frissítési hurok aktiválása, ha be van kapcsolva
                if auto_refresh:
                    time.sleep(10) # 10 másodpercenként frissít, hogy ne terhelje túl az API-t
                    st.rerun()

        except Exception as e:
            st.error(f"Váratlan hiba történt az elemzés során: {e}")
            if auto_refresh:
                time.sleep(10)
                st.rerun()