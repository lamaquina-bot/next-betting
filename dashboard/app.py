import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os

# ── Config ──────────────────────────────────────────────────────────────
API_URL = os.getenv("API_URL", "http://localhost:8000/api")

st.set_page_config(
    page_title="MOLINO · NEXT Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Dark theme via CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #0e1117; color: #fafafa; }
    [data-testid="stHeader"] { background-color: #0e1117; }
    [data-testid="stMetricValue"] { font-size: 2rem; }
    .stMetric { background-color: #161b22; border-radius: 10px; padding: 1rem; }
    .stMetric label { font-size: 1.1rem; }
    table { color: #fafafa !important; }
    thead tr th { color: #fafafa !important; }
</style>
""", unsafe_allow_html=True)

# ── API helpers ─────────────────────────────────────────────────────────
def api_get(endpoint: str):
    try:
        r = requests.get(f"{API_URL}/{endpoint}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Error conectando al backend: {e}")
        return None


# ── Header ──────────────────────────────────────────────────────────────
st.title("⚽ MOLINO · NEXT Dashboard")
st.caption("Plataforma de apuestas de valor")

# ── KPI row ─────────────────────────────────────────────────────────────
bankroll_data = api_get("bankroll")
value_bets_data = api_get("value-bets/today")
dashboard_data = api_get("dashboard/summary")

bankroll_val = dashboard_data.get("current_balance", 0) if dashboard_data else 0
roi_val = dashboard_data.get("roi", 0.0) if dashboard_data else 0.0
win_rate_val = dashboard_data.get("win_rate", 0.0) if dashboard_data else 0.0
picks_count = len(value_bets_data) if isinstance(value_bets_data, list) else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("💰 Bankroll", f"${bankroll_val:,.0f}")
k2.metric("📈 ROI Total", f"{roi_val:.1f}%", delta_color="normal" if roi_val >= 0 else "inverse")
k3.metric("🎯 Win Rate", f"{win_rate_val:.1f}%")
k4.metric("📅 Picks Hoy", picks_count)

st.divider()

# ── Tabs ────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Value Bets Hoy",
    "💰 Bankroll",
    "📊 Performance",
    "📋 Historial",
])

# ── Tab 1: Value Bets Hoy ──────────────────────────────────────────────
with tab1:
    st.header("Value Bets de Hoy")
    if value_bets_data and isinstance(value_bets_data, list) and len(value_bets_data) > 0:
        df = pd.DataFrame(value_bets_data)
        display_cols = [c for c in ["fixture_id", "outcome", "model_prob", "market_odds", "edge_pct", "stake"] if c in df.columns]
        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No hay picks disponibles para hoy. Vuelve más tarde.")

# ── Tab 2: Bankroll ────────────────────────────────────────────────────
with tab2:
    st.header("Evolución del Bankroll")
    history = api_get("bankroll?days=90")
    if history and isinstance(history, list) and len(history) > 0:
        df_hist = pd.DataFrame(history)
        if "date" in df_hist.columns and "balance" in df_hist.columns:
            fig = px.line(
                df_hist, x="date", y="balance",
                labels={"date": "Fecha", "balance": "Balance ($)"},
                line_shape="spline",
            )
            fig.update_traces(line_color="#00d4aa", line_width=3)
            fig.update_layout(
                paper_bgcolor="#0e1117",
                plot_bgcolor="#161b22",
                font_color="#fafafa",
                font_size=14,
                xaxis_title="Fecha",
                yaxis_title="Balance ($)",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Formato de historial inesperado.")
    else:
        st.info("Sin historial de bankroll todavía.")

# ── Tab 3: Performance ─────────────────────────────────────────────────
with tab3:
    st.header("Métricas de Rendimiento")
    perf = api_get("dashboard/summary")
    if perf:
        c1, c2, c3 = st.columns(3)
        c1.metric("Sharpe Ratio", f"{perf.get('sharpe_ratio', 0):.2f}")
        c2.metric("Avg Edge", f"{perf.get('avg_edge', 0):.1f}%")
        c3.metric("Total Apuestas", perf.get("total_bets", 0))

        league_data = perf.get("by_league", [])
        if league_data:
            df_league = pd.DataFrame(league_data)
            st.subheader("Hit Rate por Liga")
            fig2 = px.bar(
                df_league, x="league", y="hit_rate",
                color="hit_rate",
                color_continuous_scale=["#ff4b4b", "#00d4aa"],
                labels={"league": "Liga", "hit_rate": "Hit Rate (%)"},
            )
            fig2.update_layout(
                paper_bgcolor="#0e1117",
                plot_bgcolor="#161b22",
                font_color="#fafafa",
                font_size=14,
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Sin datos de performance.")

# ── Tab 4: Historial ───────────────────────────────────────────────────
with tab4:
    st.header("Historial de Apuestas")
    history_bets = api_get("value-bets?status=resolved")
    if history_bets and isinstance(history_bets, list) and len(history_bets) > 0:
        df_bets = pd.DataFrame(history_bets)
        display_cols = [c for c in ["date", "fixture", "outcome", "odds", "stake", "result", "profit"] if c in df_bets.columns]
        st.dataframe(
            df_bets[display_cols],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Sin historial de apuestas todavía.")

# ── Footer ──────────────────────────────────────────────────────────────
st.divider()
st.caption("MOLINO NEXT · Dashboard v0.1 · Conectado a " + API_URL)
