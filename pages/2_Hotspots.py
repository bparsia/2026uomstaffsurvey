import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (
    THEME_ORDER, load_org_scores, load_org_deltas, load_org_hierarchy,
    holistic_ranking, synthetic_pools, require_password,
)

require_password()

BLUE = "#2a78d6"
RED = "#e34948"

st.title("Hotspots")
st.caption(
    "Small units (low response counts) can swing on a handful of responses; "
    "treat extreme values as indicative, not statistically robust."
)

tab_theme, tab_holistic, tab_treemap = st.tabs(["By theme", "Holistic ranking", "Treemap"])

# ── By theme ──────────────────────────────────────────────────────────────
with tab_theme:
    c1, c2, c3 = st.columns(3)
    granularity_label = c1.radio(
        "Granularity", ["Division / Department", "Sub-Division"], horizontal=True, key="theme_gran",
    )
    granularity = "division_department" if granularity_label == "Division / Department" else "sub_division"

    theme_pick = c2.selectbox("Theme", THEME_ORDER, key="theme_pick")

    scores = load_org_scores()
    deltas = load_org_deltas()

    question_options = ["(theme score)"] + sorted(
        scores.loc[
            (scores["granularity"] == granularity) & (scores["row_type"] == "question")
            & (scores["theme"] == theme_pick), "question",
        ].dropna().unique()
    )
    question_pick = c3.selectbox("Question (optional)", question_options, key="question_pick")

    row_type = "theme" if question_pick == "(theme score)" else "question"
    match_col, match_val = ("theme", theme_pick) if row_type == "theme" else ("question", question_pick)

    s = scores[
        (scores["granularity"] == granularity) & (scores["row_type"] == row_type)
        & (scores[match_col] == match_val) & (scores["org_unit"] != "Overall")
    ]
    d = deltas[
        (deltas["granularity"] == granularity) & (deltas["row_type"] == row_type)
        & (deltas[match_col] == match_val) & (deltas["org_unit"] != "Overall")
    ]
    merged = s.merge(d[["org_unit", "delta_pp"]], on="org_unit", how="left").sort_values("delta_pp")

    min_n = st.slider("Minimum responses", 0, int(merged["n_responses"].max()), 10, key="min_n_theme")
    merged = merged[merged["n_responses"] >= min_n]

    left, right = st.columns(2)
    with left:
        st.subheader("Lowest (below Overall)")
        st.dataframe(
            merged.sort_values("delta_pp").head(10)[["org_unit", "n_responses", "score", "delta_pp"]].rename(
                columns={"org_unit": "Unit", "n_responses": "N", "score": "Score", "delta_pp": "Delta (pp)"}
            ),
            column_config={
                "Score": st.column_config.NumberColumn(format="%.0%%"),
                "Delta (pp)": st.column_config.NumberColumn(format="%+.0f"),
            },
            hide_index=True, width='stretch',
        )
    with right:
        st.subheader("Highest (above Overall)")
        st.dataframe(
            merged.sort_values("delta_pp", ascending=False).head(10)[["org_unit", "n_responses", "score", "delta_pp"]].rename(
                columns={"org_unit": "Unit", "n_responses": "N", "score": "Score", "delta_pp": "Delta (pp)"}
            ),
            column_config={
                "Score": st.column_config.NumberColumn(format="%.0%%"),
                "Delta (pp)": st.column_config.NumberColumn(format="%+.0f"),
            },
            hide_index=True, width='stretch',
        )

    st.divider()
    st.subheader("Full ranked table")
    st.dataframe(
        merged[["org_unit", "n_responses", "score", "delta_pp"]].rename(
            columns={"org_unit": "Unit", "n_responses": "N", "score": "Score", "delta_pp": "Delta (pp)"}
        ),
        column_config={
            "Score": st.column_config.NumberColumn(format="%.0%%"),
            "Delta (pp)": st.column_config.NumberColumn(format="%+.0f"),
        },
        hide_index=True, width='stretch',
    )

# ── Holistic ranking ──────────────────────────────────────────────────────
with tab_holistic:
    st.caption(
        "No single number is safe here — a unit that's strong on six themes "
        "and badly negative on one would look 'fine' on a plain average. "
        "These three views are complementary, not a single ranking: overall "
        "standing, worst single theme, and how many themes are below "
        "Overall (breadth of trouble). Units below the survey's "
        "minimum-response reporting threshold (no scores at all) are excluded."
    )
    unit_mode = st.radio(
        "Compare", ["Real units", "Synthetic equal-size pools"], horizontal=True,
        help="Synthetic pools group units within the same faculty/PS subgroup "
             "to roughly equal response counts, so small units don't dominate on noise alone.",
    )

    if unit_mode == "Real units":
        h = holistic_ranking()
        hierarchy = load_org_hierarchy()
        h = h.merge(hierarchy[["unit", "group", "subgroup"]], left_on="org_unit", right_on="unit", how="left")
        h = h.drop(columns="unit").rename(columns={"org_unit": "Unit"})
        min_n2 = st.slider("Minimum responses", 0, int(h["n_responses"].max()), 20, key="min_n_holistic")
        h = h[h["n_responses"] >= min_n2]
    else:
        pools = synthetic_pools()
        wide = pools.pivot(index="pool", columns="theme", values="delta_pp")[THEME_ORDER]
        meta = pools.drop_duplicates("pool").set_index("pool")[["n_responses", "n_units", "member_units"]]
        h = wide.copy()
        h["mean_delta_pp"] = wide.mean(axis=1)
        h["worst_delta_pp"] = wide.min(axis=1)
        h["worst_theme"] = wide.idxmin(axis=1)
        h["themes_below"] = (wide < 0).sum(axis=1)
        h = h.join(meta).reset_index().rename(columns={"pool": "Unit"})

    metric_choice = st.selectbox(
        "Rank by", ["Mean delta (overall standing)", "Worst single theme", "Themes below Overall"],
    )
    sort_col = {
        "Mean delta (overall standing)": "mean_delta_pp",
        "Worst single theme": "worst_delta_pp",
        "Themes below Overall": "themes_below",
    }[metric_choice]

    display_cols = ["Unit", "n_responses", "mean_delta_pp", "worst_delta_pp", "worst_theme", "themes_below"]
    if "group" in h.columns:
        display_cols = ["Unit", "group", "subgroup"] + display_cols[1:]

    left, right = st.columns(2)
    with left:
        st.subheader("Worst standing")
        st.dataframe(
            h.sort_values(sort_col).head(15)[display_cols].rename(columns={
                "n_responses": "N", "mean_delta_pp": "Mean Δ (pp)", "worst_delta_pp": "Worst Δ (pp)",
                "worst_theme": "Worst theme", "themes_below": "Themes below",
                "group": "Group", "subgroup": "Subgroup",
            }),
            hide_index=True, width='stretch',
        )
    with right:
        st.subheader("Best standing")
        st.dataframe(
            h.sort_values(sort_col, ascending=False).head(15)[display_cols].rename(columns={
                "n_responses": "N", "mean_delta_pp": "Mean Δ (pp)", "worst_delta_pp": "Worst Δ (pp)",
                "worst_theme": "Worst theme", "themes_below": "Themes below",
                "group": "Group", "subgroup": "Subgroup",
            }),
            hide_index=True, width='stretch',
        )

# ── Treemap ───────────────────────────────────────────────────────────────
with tab_treemap:
    st.caption(
        "Box area = response count (n). Box color = delta vs. Overall on the "
        "selected theme (or the holistic mean delta across all 7 themes). "
        "Parent boxes (faculty/subgroup) are colored by the response-weighted "
        "average of their children. Grouped by faculty/Professional-Services "
        "structure — see sources/org_hierarchy.csv (best-effort mapping from "
        "unit names; some units are flagged doubtful there)."
    )
    theme_pick_tm = st.selectbox("Theme", ["Holistic (mean across all themes)"] + THEME_ORDER, key="treemap_theme")

    hierarchy = load_org_hierarchy()

    if theme_pick_tm == "Holistic (mean across all themes)":
        h = holistic_ranking()
        tm = h.rename(columns={"mean_delta_pp": "delta_pp"})[["org_unit", "n_responses", "delta_pp"]]
    else:
        scores = load_org_scores()
        deltas = load_org_deltas()
        s = scores[
            (scores["granularity"] == "division_department") & (scores["row_type"] == "theme")
            & (scores["theme"] == theme_pick_tm) & (scores["org_unit"] != "Overall")
        ]
        d = deltas[
            (deltas["granularity"] == "division_department") & (deltas["row_type"] == "theme")
            & (deltas["theme"] == theme_pick_tm) & (deltas["org_unit"] != "Overall")
        ]
        tm = s.merge(d[["org_unit", "delta_pp"]], on="org_unit", how="left")[["org_unit", "n_responses", "delta_pp"]]

    tm = tm.merge(hierarchy[["unit", "group", "subgroup"]], left_on="org_unit", right_on="unit", how="left")
    tm["group"] = tm["group"].fillna("Unclassified")
    tm["subgroup"] = tm["subgroup"].fillna("Unclassified")
    tm = tm.dropna(subset=["delta_pp"])  # below minimum-N units have no score/delta

    max_abs = max(abs(tm["delta_pp"].min()), abs(tm["delta_pp"].max()), 1)

    # Three levels: unit -> subgroup -> group (group has no parent, root level).
    # A subgroup display name like "Faculty Office" or "Cross-faculty
    # Research Institutes" can legitimately repeat across different groups
    # (FBMH's Faculty Office is a different entity from FSE's) — Plotly
    # treemaps identify nodes by `ids`, not `labels`, so subgroup/group ids
    # are namespaced with their parent to stay unique even when the display
    # label repeats.
    tm["subgroup_id"] = tm["group"] + " / " + tm["subgroup"]
    tm["_wsum"] = tm["delta_pp"] * tm["n_responses"]

    def rollup(g):
        n = g["n_responses"].sum()
        return pd.Series({"n_responses": n, "delta_pp": g["_wsum"].sum() / n})

    subgroups = (
        tm.groupby(["subgroup_id", "subgroup", "group"])
        .apply(rollup, include_groups=False).reset_index()
    )
    groups = tm.groupby("group").apply(rollup, include_groups=False).reset_index()

    ids = list(tm["org_unit"]) + list(subgroups["subgroup_id"]) + list(groups["group"])
    labels = list(tm["org_unit"]) + list(subgroups["subgroup"]) + list(groups["group"])
    parents = list(tm["subgroup_id"]) + list(subgroups["group"]) + [""] * len(groups)
    values = list(tm["n_responses"]) + list(subgroups["n_responses"]) + list(groups["n_responses"])
    colors = list(tm["delta_pp"]) + list(subgroups["delta_pp"]) + list(groups["delta_pp"])
    texts = (
        [f"{u}<br>{n} responses<br>{delta:+.0f}pp" for u, n, delta in
         zip(tm["org_unit"], tm["n_responses"], tm["delta_pp"])]
        + [f"{lbl}<br>{n} responses<br>{delta:+.0f}pp (weighted avg)" for lbl, n, delta in
           zip(subgroups["subgroup"], subgroups["n_responses"], subgroups["delta_pp"])]
        + [f"{lbl}<br>{n} responses<br>{delta:+.0f}pp (weighted avg)" for lbl, n, delta in
           zip(groups["group"], groups["n_responses"], groups["delta_pp"])]
    )

    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values,
        branchvalues="total",
        marker=dict(
            colors=colors,
            colorscale=[[0, RED], [0.5, "#f0efec"], [1, BLUE]],
            cmid=0, cmin=-max_abs, cmax=max_abs,
            colorbar=dict(title="Δ pp"),
            showscale=True,
        ),
        text=texts,
        hovertemplate="%{label}<br>%{value} responses<extra></extra>",
    ))
    fig.update_layout(height=650, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, width='stretch')
