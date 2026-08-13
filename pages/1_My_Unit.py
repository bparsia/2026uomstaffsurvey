import plotly.graph_objects as go
import streamlit as st

from utils import THEME_ORDER, org_units, unit_scorecard, load_org_scores, fmt_pct, fmt_delta_pp, require_password

require_password()

BLUE = "#2a78d6"
RED = "#e34948"

st.title("My Unit")
st.caption(
    "Division and Department are peer-level organisational units in this "
    "survey, not a hierarchy — pick the granularity that matches your unit."
)

granularity_label = st.radio(
    "Granularity", ["Division / Department", "Sub-Division"], horizontal=True,
)
granularity = "division_department" if granularity_label == "Division / Department" else "sub_division"

units = org_units(granularity)
unit = st.selectbox("Find your unit", units)

if unit:
    scorecard = unit_scorecard(granularity, unit)
    n = scorecard["n_responses"].iloc[0] if len(scorecard) else None
    st.caption(f"{int(n):,} responses" if n == n else "")

    st.subheader("Theme scores vs. Overall")
    theme_rows = scorecard[scorecard["row_type"] == "theme"].set_index("theme").loc[THEME_ORDER].reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=theme_rows["score"], y=theme_rows["theme"], orientation="h",
        marker_color=BLUE, name=unit,
        text=[f"{v * 100:.0f}%" for v in theme_rows["score"]], textposition="outside",
    ))
    fig.update_layout(
        xaxis=dict(range=[0, 1], tickformat=".0%", title=None),
        yaxis=dict(autorange="reversed", title=None),
        height=320, margin=dict(t=10, b=10, l=10, r=40),
        plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
        showlegend=False,
    )
    st.plotly_chart(fig, width='stretch')

    st.subheader("Shape of strengths & weaknesses")
    overall_scores = load_org_scores()
    overall_theme = overall_scores[
        (overall_scores["granularity"] == granularity) & (overall_scores["row_type"] == "theme")
        & (overall_scores["org_unit"] == "Overall")
    ].set_index("theme").loc[THEME_ORDER]["score"]

    radar_theta = THEME_ORDER + [THEME_ORDER[0]]  # close the loop
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=list(overall_theme) + [overall_theme.iloc[0]], theta=radar_theta,
        name="University Overall", line=dict(color="#8a8a86", dash="dot"),
        fill="none",
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=list(theme_rows["score"]) + [theme_rows["score"].iloc[0]], theta=radar_theta,
        name=unit, line=dict(color=BLUE), fill="toself", fillcolor="rgba(42,120,214,0.15)",
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(range=[0, 1], tickformat=".0%")),
        height=420, margin=dict(t=30, b=10, l=40, r=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_radar, width='stretch')

    st.subheader("Delta vs. Overall (percentage points)")
    colors = [RED if v < 0 else BLUE for v in theme_rows["delta_pp"].fillna(0)]
    fig2 = go.Figure(go.Bar(
        x=theme_rows["delta_pp"], y=theme_rows["theme"], orientation="h",
        marker_color=colors,
        text=[fmt_delta_pp(v) for v in theme_rows["delta_pp"]], textposition="outside",
    ))
    fig2.update_layout(
        xaxis=dict(title="pp vs. Overall", zeroline=True, zerolinecolor="#c9c8c2"),
        yaxis=dict(autorange="reversed", title=None),
        height=320, margin=dict(t=10, b=10, l=10, r=40),
        plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    )
    st.plotly_chart(fig2, width='stretch')

    st.subheader("Question-level detail")
    theme_filter = st.selectbox("Filter by theme", ["All"] + THEME_ORDER)
    q_rows = scorecard[scorecard["row_type"] == "question"].copy()
    if theme_filter != "All":
        q_rows = q_rows[q_rows["theme"] == theme_filter]
    q_rows = q_rows.sort_values("score")

    st.dataframe(
        q_rows[["theme", "question", "score", "delta_pp"]].rename(
            columns={"theme": "Theme", "question": "Question", "score": "Score", "delta_pp": "Delta (pp)"}
        ),
        column_config={
            "Score": st.column_config.NumberColumn(format="%.0%%"),
            "Delta (pp)": st.column_config.NumberColumn(format="%+.0f"),
        },
        hide_index=True,
        width='stretch',
    )
