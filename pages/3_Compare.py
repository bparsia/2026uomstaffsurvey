import plotly.graph_objects as go
import streamlit as st

from utils import THEME_ORDER, org_units, load_org_scores, require_password

require_password()

BLUE = "#2a78d6"
COMPARE_COLORS = ["#2a78d6", "#e34948", "#1baf7a", "#eda100"]  # validated categorical slots 1,8,5,4

st.title("Compare Units")
st.caption(
    "Overlay up to 4 units' 7-theme profiles. Units below the survey's "
    "minimum-response reporting threshold have no scores and won't plot."
)

granularity_label = st.radio(
    "Granularity", ["Division / Department", "Sub-Division"], horizontal=True,
)
granularity = "division_department" if granularity_label == "Division / Department" else "sub_division"

units = org_units(granularity)
picked = st.multiselect("Units to compare", units, max_selections=4)

if picked:
    scores = load_org_scores()
    theme_scores = scores[
        (scores["granularity"] == granularity) & (scores["row_type"] == "theme")
    ]

    radar_theta = THEME_ORDER + [THEME_ORDER[0]]
    fig = go.Figure()

    overall_row = theme_scores[theme_scores["org_unit"] == "Overall"].set_index("theme").reindex(THEME_ORDER)
    fig.add_trace(go.Scatterpolar(
        r=list(overall_row["score"]) + [overall_row["score"].iloc[0]], theta=radar_theta,
        name="University Overall", line=dict(color="#8a8a86", dash="dot"),
    ))

    no_data = []
    for i, unit in enumerate(picked):
        row = theme_scores[theme_scores["org_unit"] == unit].set_index("theme")
        row = row.reindex(THEME_ORDER)
        if row["score"].isna().all():
            no_data.append(unit)
            continue
        r = list(row["score"]) + [row["score"].iloc[0]]
        fig.add_trace(go.Scatterpolar(
            r=r, theta=radar_theta, name=unit,
            line=dict(color=COMPARE_COLORS[i % len(COMPARE_COLORS)]),
        ))

    if no_data:
        st.warning(f"No scores available (below minimum-response threshold): {', '.join(no_data)}")

    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 1], tickformat=".0%")),
        height=500, margin=dict(t=30, b=10, l=40, r=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, width='stretch')

    st.subheader("Theme scores")
    table = theme_scores[theme_scores["org_unit"].isin(["Overall"] + picked)].pivot(
        index="theme", columns="org_unit", values="score"
    ).loc[THEME_ORDER][["Overall"] + picked].rename(columns={"Overall": "University Overall"})
    st.dataframe(
        table.style.format("{:.0%}", na_rep="n/a"),
        width='stretch',
    )
