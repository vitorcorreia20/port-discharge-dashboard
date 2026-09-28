"""Dashboard executivo — Descarga de granel solido | Agosto/2026.

Conecta automaticamente em `porto.db`. Se o banco nao existir, executa
`seed_data.py` para cria-lo. Backend: SQLite + Pandas. Graficos: Plotly.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "porto.db"
SEED_SCRIPT = BASE_DIR / "seed_data.py"

st.set_page_config(
    page_title="Porto · Descarga Granel Sólido — Ago/2026",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# CSS customizado — tema escuro / elegante / responsivo
# ----------------------------------------------------------------------------
st.markdown(
    """
<style>
  :root { color-scheme: dark; }
  .stApp { background: radial-gradient(1200px 600px at 15% -5%, #12263f 0%, #0b1220 55%, #070b14 100%); }
  .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px; }
  h1, h2, h3 { letter-spacing: -0.02em; }
  .hero { border: 1px solid rgba(148,163,184,.18); background: linear-gradient(180deg, rgba(30,58,95,.55), rgba(13,25,43,.65));
          border-radius: 18px; padding: 20px 22px; margin-bottom: 14px;
          box-shadow: 0 12px 40px rgba(0,0,0,.35); }
  .hero h1 { margin: 0; font-size: 1.65rem; }
  .hero p { margin: .35rem 0 0 0; color: #aebdd2; }
  .kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 6px 0 14px 0; }
  @media (max-width: 900px) { .kpi-grid { grid-template-columns: 1fr; } }
  .kpi-card { border: 1px solid rgba(148,163,184,.18); border-radius: 16px; padding: 16px 18px;
              background: linear-gradient(180deg, rgba(21,38,63,.85), rgba(10,18,32,.9));
              box-shadow: 0 10px 30px rgba(0,0,0,.35); position: relative; overflow: hidden; }
  .kpi-card::after { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; }
  .kpi-card.blue::after { background: #38bdf8; } .kpi-card.green::after { background: #34d399; }
  .kpi-card.amber::after { background: #fbbf24; }
  .kpi-label { font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; color: #93a5c0; }
  .kpi-value { font-size: 2rem; font-weight: 800; margin: .15rem 0; color: #f1f5f9; }
  .kpi-sub { font-size: .85rem; color: #9fb0c8; }
  .panel { border: 1px solid rgba(148,163,184,.16); border-radius: 16px; padding: 16px 18px;
            background: rgba(10,18,32,.72); box-shadow: 0 10px 30px rgba(0,0,0,.30); margin-bottom: 14px; }
  .panel h3 { margin: 0 0 4px 0; font-size: 1.05rem; }
  .panel .hint { color: #8fa1bb; font-size: .83rem; margin-bottom: 8px; }
  .badge { display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .75rem; font-weight: 700; }
  .badge.ok { background: rgba(52,211,153,.15); color: #6ee7b7; border: 1px solid rgba(52,211,153,.4); }
  .badge.warn { background: rgba(251,191,36,.14); color: #fcd34d; border: 1px solid rgba(251,191,36,.4); }
  .badge.err { background: rgba(248,113,113,.14); color: #fca5a5; border: 1px solid rgba(248,113,113,.45); }
  section[data-testid="stSidebar"] { background: #0a1120; border-right: 1px solid rgba(148,163,184,.14); }
  .stDataFrame { border-radius: 12px; overflow: hidden; }
  footer { color: #6b7d99; }
</style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def ensure_db() -> Path:
    """Garante que porto.db exista; se nao, roda seed_data.py automaticamente."""
    if not DB_PATH.exists():
        with st.spinner("Banco `porto.db` não encontrado — gerando dados de Agosto/2026…"):
            if SEED_SCRIPT.exists():
                result = subprocess.run(
                    [sys.executable, str(SEED_SCRIPT)],
                    capture_output=True,
                    text=True,
                    cwd=str(BASE_DIR),
                )
                if result.returncode != 0:
                    st.error(f"Falha ao gerar o banco:\n{result.stderr}")
                    st.stop()
            else:
                st.error("`seed_data.py` não encontrado e `porto.db` ausente.")
                st.stop()
    return DB_PATH


def get_con() -> sqlite3.Connection:
    con = sqlite3.connect(str(ensure_db()), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


@st.cache_data(show_spinner=False)
def load_atracacoes() -> pd.DataFrame:
    con = get_con()
    df = pd.read_sql_query("SELECT * FROM atracacoes ORDER BY id_atracacao", con)
    con.close()
    return df


@st.cache_data(show_spinner=False)
def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    con = get_con()
    df = pd.read_sql_query(sql, con, params=params)
    con.close()
    return df


# ----------------------------------------------------------------------------
# Sidebar — filtros
# ----------------------------------------------------------------------------
ensure_db()
df_atr = load_atracacoes()
navios = df_atr["navio"].tolist()
transportadoras_all = sorted(
    query_df("SELECT DISTINCT transportadora FROM viagens ORDER BY 1")["transportadora"].tolist()
)

st.sidebar.markdown("### ⚓ Filtros operacionais")
sel_navios = st.sidebar.multiselect("Navio / Atracação", navios, default=navios)
sel_transp = st.sidebar.multiselect("Transportadora", transportadoras_all, default=transportadoras_all)

if not sel_navios:
    st.warning("Selecione ao menos um navio na barra lateral.")
    st.stop()
if not sel_transp:
    st.warning("Selecione ao menos uma transportadora na barra lateral.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.caption(
    "Peso líquido (t) = (peso_bruto_kg − tara_kg) / 1000 · "
    "Apenas pesagens válidas (bruto > tara, tara > 0) compõem os KPIs. "
    "Inconsistências aparecem na tabela de auditoria."
)
if st.sidebar.button("🔄 Recarregar dados"):
    st.cache_data.clear()
    st.rerun()

# placeholders SQL
nav_ph = ",".join("?" for _ in sel_navios)
tra_ph = ",".join("?" for _ in sel_transp)

# ----------------------------------------------------------------------------
# Hero
# ----------------------------------------------------------------------------
status_map = {
    row["navio"]: ("✅ Concluído" if pd.notna(row["fim_descarga"]) else "🟡 Em operação")
    for _, row in df_atr.iterrows()
}
status_txt = " · ".join(f"{n} ({status_map[n]})" for n in sel_navios)
st.markdown(
    f"""
<div class="hero">
  <h1>⚓ Terminal de Granel Sólido — Descarga Navio → Caminhão</h1>
  <p>Agosto/2026 · {status_txt} · Fluxo: Entrada vazio → Tara → Carregamento no cais → Bruto → Saída do pátio</p>
</div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# KPIs (respeitam os filtros)
# ----------------------------------------------------------------------------
kpi_prancha = query_df(
    f"""
    SELECT a.navio, a.toneladas_manifestadas,
           COUNT(p.id_pesagem) AS n_validas,
           COALESCE(SUM((p.peso_bruto_kg - p.tara_kg)/1000.0),0) AS total_t,
           COALESCE((JULIANDAY(COALESCE(a.fim_descarga,
               (SELECT MAX(p2.hora_bruto) FROM pesagens p2
                JOIN viagens v2 ON v2.id_viagem=p2.id_viagem
                WHERE v2.id_atracacao=a.id_atracacao)))
               - JULIANDAY(a.inicio_descarga))*24.0,0) AS horas
    FROM atracacoes a
    LEFT JOIN viagens v ON v.id_atracacao=a.id_atracacao AND v.transportadora IN ({tra_ph})
    LEFT JOIN pesagens p ON p.id_viagem=v.id_viagem
        AND p.peso_bruto_kg > p.tara_kg AND p.tara_kg > 0
    WHERE a.navio IN ({nav_ph})
    GROUP BY a.id_atracacao
    """,
    tuple(sel_transp) + tuple(sel_navios),
)
total_t = float(kpi_prancha["total_t"].sum()) if not kpi_prancha.empty else 0.0
total_horas = float(kpi_prancha["horas"].sum()) if not kpi_prancha.empty else 0.0
prancha_media = (total_t / total_horas) if total_horas > 0 else 0.0

meta_total = float(
    query_df(
        f"SELECT COALESCE(SUM(toneladas_manifestadas),0) AS m FROM atracacoes WHERE navio IN ({nav_ph})",
        tuple(sel_navios),
    )["m"].iloc[0]
)
progresso = (total_t / meta_total * 100.0) if meta_total > 0 else 0.0

tempo_df = query_df(
    f"""
    SELECT COALESCE(AVG((JULIANDAY(v.saida_patio)-JULIANDAY(v.entrada_patio))*1440.0),0) AS tmedio,
           COUNT(*) AS n
    FROM viagens v JOIN atracacoes a ON a.id_atracacao=v.id_atracacao
    WHERE a.navio IN ({nav_ph}) AND v.transportadora IN ({tra_ph})
      AND v.entrada_patio IS NOT NULL AND v.saida_patio IS NOT NULL
    """,
    tuple(sel_navios) + tuple(sel_transp),
)
tempo_medio = float(tempo_df["tmedio"].iloc[0]) if not tempo_df.empty else 0.0
n_viagens = int(tempo_df["n"].iloc[0]) if not tempo_df.empty else 0

n_anomalias = int(
    query_df(
        f"""
        SELECT COUNT(*) AS n FROM viagens v
        JOIN pesagens p ON p.id_viagem=v.id_viagem
        JOIN atracacoes a ON a.id_atracacao=v.id_atracacao
        WHERE a.navio IN ({nav_ph}) AND v.transportadora IN ({tra_ph})
          AND (p.peso_bruto_kg <= p.tara_kg OR p.tara_kg <= 0
               OR p.hora_bruto < p.hora_tara
               OR (JULIANDAY(v.saida_patio)-JULIANDAY(v.entrada_patio))*1440.0 > 120)
        """,
        tuple(sel_navios) + tuple(sel_transp),
    )["n"].iloc[0]
)

st.markdown(
    f"""
<div class="kpi-grid">
  <div class="kpi-card blue">
    <div class="kpi-label">Prancha média de descarga (t/h)</div>
    <div class="kpi-value">{prancha_media:.2f}</div>
    <div class="kpi-sub">{total_t:,.1f} t descarregadas em {total_horas:,.1f} h de operação</div>
  </div>
  <div class="kpi-card green">
    <div class="kpi-label">Progresso do manifesto (%)</div>
    <div class="kpi-value">{progresso:.1f}%</div>
    <div class="kpi-sub">{total_t:,.1f} t de {meta_total:,.0f} t manifestadas</div>
  </div>
  <div class="kpi-card amber">
    <div class="kpi-label">Tempo médio no pátio (min)</div>
    <div class="kpi-value">{tempo_medio:.0f}</div>
    <div class="kpi-sub">{n_viagens} viagens · {n_anomalias} inconsistências em auditoria</div>
  </div>
</div>
    """.replace(",", "X").replace(".", ",").replace("X", "."),
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Gráfico 1 — Curva S: acumulado vs meta
# ----------------------------------------------------------------------------
st.markdown('<div class="panel"><h3>📈 Curva S — volume acumulado vs. meta manifestada</h3>'
            '<div class="hint">Acumulado considera apenas pesagens válidas, ordenadas por hora do bruto. '
            'Linha tracejada = meta do manifesto (filtro de navio).</div>',
            unsafe_allow_html=True)

curva = query_df(
    f"""
    SELECT a.navio, a.toneladas_manifestadas, p.hora_bruto,
           (p.peso_bruto_kg - p.tara_kg)/1000.0 AS liq_t
    FROM pesagens p
    JOIN viagens v ON v.id_viagem=p.id_viagem
    JOIN atracacoes a ON a.id_atracacao=v.id_atracacao
    WHERE a.navio IN ({nav_ph}) AND v.transportadora IN ({tra_ph})
      AND p.peso_bruto_kg > p.tara_kg AND p.tara_kg > 0
    ORDER BY p.hora_bruto
    """,
    tuple(sel_navios) + tuple(sel_transp),
)

if curva.empty:
    st.info("Sem pesagens válidas para os filtros selecionados.")
else:
    curva["hora_bruto"] = pd.to_datetime(curva["hora_bruto"])
    fig_s = go.Figure()
    palette = {"MV Vale Brasil": "#38bdf8", "MV Ore Amazon": "#34d399"}
    for navio, g in curva.groupby("navio"):
        g = g.sort_values("hora_bruto").copy()
        g["acumulado_t"] = g["liq_t"].cumsum()
        color = palette.get(navio, "#a78bfa")
        fig_s.add_trace(go.Scatter(
            x=g["hora_bruto"], y=g["acumulado_t"], mode="lines",
            name=f"{navio} — acumulado", line=dict(color=color, width=3),
            fill="tozeroy", fillcolor=color.replace(")", ",0.12)").replace("rgb", "rgba")
            if color.startswith("rgb") else "rgba(56,189,248,0.10)",
            hovertemplate="%{x|%d/%m %H:%M}<br>%{y:.1f} t<extra>" + navio + "</extra>",
        ))
        meta = float(g["toneladas_manifestadas"].iloc[0])
        fig_s.add_trace(go.Scatter(
            x=[g["hora_bruto"].min(), g["hora_bruto"].max()], y=[meta, meta],
            mode="lines", name=f"{navio} — meta ({meta:.0f} t)",
            line=dict(color=color, width=1.5, dash="dash"),
            hovertemplate=f"Meta {navio}: {meta:.0f} t<extra></extra>",
        ))
    fig_s.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=30, b=10), height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis_title="Data / hora do bruto", yaxis_title="Toneladas acumuladas (t)",
        hovermode="x unified",
    )
    st.plotly_chart(fig_s, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Gráfico 2 — Tempo de pátio por transportadora
# ----------------------------------------------------------------------------
st.markdown('<div class="panel"><h3>🚛 Permanência no pátio por transportadora</h3>'
            '<div class="hint">Média em minutos (entrada → saída do pátio). '
            'Barra em vermelho = gargalo (maior média). Linha tracejada = limite de 120 min.</div>',
            unsafe_allow_html=True)

patio = query_df(
    f"""
    SELECT v.transportadora,
           COUNT(*) AS n_viagens,
           AVG((JULIANDAY(v.saida_patio)-JULIANDAY(v.entrada_patio))*1440.0) AS tmedio,
           SUM(CASE WHEN (JULIANDAY(v.saida_patio)-JULIANDAY(v.entrada_patio))*1440.0 > 120 THEN 1 ELSE 0 END) AS n_estouro
    FROM viagens v JOIN atracacoes a ON a.id_atracacao=v.id_atracacao
    WHERE a.navio IN ({nav_ph}) AND v.transportadora IN ({tra_ph})
      AND v.entrada_patio IS NOT NULL AND v.saida_patio IS NOT NULL
    GROUP BY v.transportadora ORDER BY tmedio DESC
    """,
    tuple(sel_navios) + tuple(sel_transp),
)

if patio.empty:
    st.info("Sem viagens para os filtros selecionados.")
else:
    patio["tmedio"] = patio["tmedio"].round(1)
    max_t = patio["tmedio"].max()
    colors = ["#f87171" if v == max_t else "#38bdf8" for v in patio["tmedio"]]
    fig_b = go.Figure(go.Bar(
        y=patio["transportadora"], x=patio["tmedio"], orientation="h",
        marker_color=colors, text=patio["tmedio"].map(lambda v: f"{v:.1f} min"),
        textposition="outside",
        hovertemplate="%{y}<br>Média: %{x:.1f} min<br>Viagens: %{customdata[0]}<br>Estouros >120min: %{customdata[1]}<extra></extra>",
        customdata=patio[["n_viagens", "n_estouro"]].values,
    ))
    fig_b.add_vline(x=120, line_dash="dash", line_color="#fbbf24",
                    annotation_text="limite 120 min", annotation_position="top right")
    fig_b.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=70, t=20, b=10), height=max(280, 120 + 70 * len(patio)),
        xaxis_title="Tempo médio no pátio (min)", yaxis_title="",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig_b, use_container_width=True)
    cols = st.columns(len(patio))
    for col, (_, r) in zip(cols, patio.iterrows()):
        tag = "🔴 Gargalo" if r["tmedio"] == max_t else "🟢 Dentro do esperado"
        col.metric(f"{r['transportadora']} — {tag}",
                   f"{r['tmedio']:.1f} min", f"{int(r['n_viagens'])} viagens · {int(r['n_estouro'])} estouros")
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Tabela de auditoria
# ----------------------------------------------------------------------------
st.markdown('<div class="panel"><h3>🔍 Auditoria e qualidade de dados</h3>'
            '<div class="hint">Regras: <b>bruto ≤ tara</b> · <b>tara ≤ 0</b> · '
            '<b>hora do bruto anterior à tara</b> · <b>ciclo no pátio &gt; 120 min</b>.</div>',
            unsafe_allow_html=True)

audit = query_df(
    f"""
    SELECT v.id_viagem, a.navio, v.id_caminhao, v.transportadora,
           v.entrada_patio, v.saida_patio, p.hora_tara, p.tara_kg,
           p.hora_bruto, p.peso_bruto_kg,
           ROUND((p.peso_bruto_kg - p.tara_kg)/1000.0, 2) AS liquido_t,
           ROUND((JULIANDAY(v.saida_patio)-JULIANDAY(v.entrada_patio))*1440.0, 1) AS ciclo_min
    FROM viagens v
    JOIN pesagens p ON p.id_viagem=v.id_viagem
    JOIN atracacoes a ON a.id_atracacao=v.id_atracacao
    WHERE a.navio IN ({nav_ph}) AND v.transportadora IN ({tra_ph})
      AND (p.peso_bruto_kg <= p.tara_kg OR p.tara_kg <= 0
           OR p.hora_bruto < p.hora_tara
           OR (JULIANDAY(v.saida_patio)-JULIANDAY(v.entrada_patio))*1440.0 > 120)
    ORDER BY v.id_viagem
    """,
    tuple(sel_navios) + tuple(sel_transp),
)


def _motivos(r: pd.Series) -> str:
    m = []
    if r["peso_bruto_kg"] <= r["tara_kg"]:
        m.append("BRUTO ≤ TARA")
    if r["tara_kg"] <= 0:
        m.append("TARA ZERADA")
    if str(r["hora_bruto"]) < str(r["hora_tara"]):
        m.append("INVERSÃO TEMPORAL")
    if pd.notna(r["ciclo_min"]) and r["ciclo_min"] > 120:
        m.append(f"CICLO {r['ciclo_min']:.0f} MIN > 120")
    return " · ".join(m)


if audit.empty:
    st.success("✅ Nenhuma inconsistência para os filtros selecionados.")
else:
    audit["motivo"] = audit.apply(_motivos, axis=1)
    st.dataframe(
        audit[["id_viagem", "navio", "id_caminhao", "transportadora", "tara_kg",
               "peso_bruto_kg", "liquido_t", "ciclo_min", "motivo"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "id_viagem": st.column_config.NumberColumn("Viagem", format="%d"),
            "navio": "Navio",
            "id_caminhao": "Caminhão",
            "transportadora": "Transportadora",
            "tara_kg": st.column_config.NumberColumn("Tara (kg)", format="%.0f"),
            "peso_bruto_kg": st.column_config.NumberColumn("Bruto (kg)", format="%.0f"),
            "liquido_t": st.column_config.NumberColumn("Líquido (t)", format="%.2f"),
            "ciclo_min": st.column_config.NumberColumn("Ciclo (min)", format="%.1f"),
            "motivo": "Motivo do alerta",
        },
    )
    csv = audit.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Baixar auditoria (CSV)", csv, "auditoria_patio.csv", "text/csv")
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Rodapé metodológico
# ----------------------------------------------------------------------------
with st.expander("ℹ️ Metodologia e fórmulas"):
    st.markdown(
        """
- **Peso líquido (t)** = (`peso_bruto_kg` − `tara_kg`) / 1000. Apenas `bruto > tara` e `tara > 0` entram nos KPIs.
- **Prancha média (t/h)** = total líquido válido ÷ horas entre `inicio_descarga` e `fim_descarga`
  (navio em operação: usa `MAX(hora_bruto)` como fim provisório). Ver `vw_kpi_prancha`.
- **Progresso (%)** = acumulado válido ÷ `toneladas_manifestadas` × 100. Ver `vw_kpi_progresso`.
- **Tempo de pátio (min)** = (`saida_patio` − `entrada_patio`) em minutos via
  `(JULIANDAY(saída) − JULIANDAY(entrada)) × 1440`. Ver `vw_kpi_tempo_ciclo`.
- **Auditoria**: bruto ≤ tara · tara ≤ 0 · bruto antes da tara · ciclo > 120 min.
"""
    )
st.caption("Fonte: porto.db (SQLite, dados fictícios Agosto/2026) · Views: vw_kpi_prancha, vw_kpi_progresso, vw_kpi_tempo_ciclo")
