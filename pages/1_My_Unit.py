import plotly.graph_objects as go
import streamlit as st

from utils import (
    THEME_ORDER, org_units, unit_scorecard, load_org_scores,
    unit_hierarchy_context, hierarchy_level_theme_scores,
    fmt_pct, fmt_delta_pp, require_password,
)

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

    hierarchy_ctx = unit_hierarchy_context(unit) if granularity == "division_department" else None
    if hierarchy_ctx:
        st.caption(f"{hierarchy_ctx['group']} → {hierarchy_ctx['subgroup']}")
        if isinstance(hierarchy_ctx.get("doubtful"), str) and hierarchy_ctx["doubtful"]:
            st.caption(f"⚠️ Faculty/PS grouping is uncertain for this unit: {hierarchy_ctx['doubtful']}")
    elif granularity == "division_department":
        st.caption("No faculty/Professional-Services grouping found for this unit.")
    else:
        st.caption("Faculty/PS grouping is only available for Division/Department, not Sub-Division.")

    theme_rows = scorecard[scorecard["row_type"] == "theme"].set_index("theme").loc[THEME_ORDER].reset_index()

    st.subheader("Shape of strengths & weaknesses")
    st.caption("Toggle layers to compare this unit up the org hierarchy.")

    LAYER_COLORS = {
        "unit": BLUE, "subgroup": "#1baf7a", "group": "#eda100", "overall": "#8a8a86",
    }

    # Build the shared set of layers once — both the radar and the bar chart
    # below plot exactly this list, so toggling a layer affects both charts
    # together rather than each chart having its own separate controls.
    layers = [(unit, theme_rows.set_index("theme")["score"], LAYER_COLORS["unit"])]

    show_overall = st.checkbox("University Overall", value=True)
    if show_overall:
        overall_scores = load_org_scores()
        overall_theme = overall_scores[
            (overall_scores["granularity"] == granularity) & (overall_scores["row_type"] == "theme")
            & (overall_scores["org_unit"] == "Overall")
        ].set_index("theme")["score"]
        layers.append(("University Overall", overall_theme, LAYER_COLORS["overall"]))

    if hierarchy_ctx:
        c1, c2 = st.columns(2)
        show_group = c1.checkbox(hierarchy_ctx["group"], value=True)
        show_subgroup = c2.checkbox(hierarchy_ctx["subgroup"], value=True)

        if show_group or show_subgroup:
            include_self = st.toggle(
                f"Include {unit}'s own responses in the group/subgroup averages",
                value=False,
                help="Off (default): compares this unit against the rest of "
                     "its group/subgroup, excluding its own responses. On: "
                     "compares against the whole group/subgroup including "
                     "this unit — a number it partly contributes to itself.",
            )
        if show_group:
            group_scores = hierarchy_level_theme_scores(
                "group", hierarchy_ctx["group"], exclude_unit=None if include_self else unit,
            )
            layers.append((hierarchy_ctx["group"], group_scores, LAYER_COLORS["group"]))
        if show_subgroup:
            subgroup_scores = hierarchy_level_theme_scores(
                "subgroup", hierarchy_ctx["subgroup"], exclude_unit=None if include_self else unit,
            )
            layers.append((hierarchy_ctx["subgroup"], subgroup_scores, LAYER_COLORS["subgroup"]))

    # Narrow-to-wide order regardless of which order checkboxes were toggled
    # in: this unit, then its subgroup (school), then its group (faculty),
    # then University Overall.
    layer_rank = {unit: 0, (hierarchy_ctx or {}).get("subgroup"): 1,
                  (hierarchy_ctx or {}).get("group"): 2, "University Overall": 3}
    layers.sort(key=lambda layer: layer_rank.get(layer[0], 99))

    radar_theta = THEME_ORDER + [THEME_ORDER[0]]  # close the loop
    fig_radar = go.Figure()
    for name, scores, color in layers:
        vals = list(scores.reindex(THEME_ORDER)) + [scores.reindex(THEME_ORDER).iloc[0]]
        is_unit = name == unit
        rgb = tuple(int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        fig_radar.add_trace(go.Scatterpolar(
            r=vals, theta=radar_theta, name=name,
            line=dict(color=color, dash="dot" if name == "University Overall" else None),
            fill="toself" if is_unit else "none",
            fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.15)" if is_unit else None,
        ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(range=[0, 1], tickformat=".0%")),
        height=460, margin=dict(t=30, b=10, l=40, r=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_radar, width='stretch')

    st.subheader("Theme scores by layer")
    st.caption("\"Holistic\" is each layer's mean score across all 7 themes.")
    BAR_CATEGORIES = THEME_ORDER + ["Holistic"]
    fig_bars = go.Figure()
    for name, scores, color in layers:
        theme_vals = scores.reindex(THEME_ORDER)
        vals = list(theme_vals) + [theme_vals.mean()]
        fig_bars.add_trace(go.Bar(
            x=vals, y=BAR_CATEGORIES, orientation="h", name=name, marker_color=color,
            text=[f"{v * 100:.0f}%" if v == v else "n/a" for v in vals], textposition="outside",
        ))
    fig_bars.update_layout(
        xaxis=dict(range=[0, 1], tickformat=".0%", title=None),
        yaxis=dict(autorange="reversed", title=None, categoryorder="array", categoryarray=BAR_CATEGORIES[::-1]),
        barmode="group",
        height=max(320, 32 * len(layers) * len(BAR_CATEGORIES)), margin=dict(t=30, b=10, l=10, r=40),
        plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_bars, width='stretch')

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
