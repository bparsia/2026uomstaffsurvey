import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (
    THEME_ORDER, load_org_scores, load_org_hierarchy,
    load_org_hierarchy_ps_faculty_offices, load_theme_comparisons,
    faculty_office_comparison, require_password,
)

require_password()

BLUE = "#2a78d6"
RED = "#e34948"

_BOILERPLATE_PREFIX = re.compile(r"^(Division|Department|School|Faculty) of ", re.IGNORECASE)


def shorten(name: str, max_len: int = 24) -> str:
    """Shorten a long name for on-box display, semantically not by character count.

    Plotly auto-shrinks each box's text to its own rendered size, but has no
    "clip to box" option — a name that's still too long even at the smallest
    readable font just overflows the box edge. Two passes before falling back
    to a hard cut:
      1. Drop generic boilerplate prefixes ("Division of ", "School of ", …)
         — usually redundant with the parent box's own label anyway.
      2. Trim to the last whole word that fits max_len, rather than slicing
         mid-word.
    The full name always appears in the hover tooltip regardless.
    """
    if len(name) <= max_len:
        return name
    stripped = _BOILERPLATE_PREFIX.sub("", name)
    if len(stripped) <= max_len:
        return stripped
    words = stripped.split(" ")
    out = ""
    for w in words:
        candidate = f"{out} {w}".strip()
        if len(candidate) > max_len:
            break
        out = candidate
    return (out or stripped[:max_len]).rstrip(",;&") + "…"

st.title("Hotspot Map")
st.caption(
    "Box area = response count (n). Box color = delta vs. the selected "
    "baseline, on the selected theme (or the holistic mean delta across all "
    "7 themes). Parent boxes (faculty/subgroup) are colored by the "
    "response-weighted average of their children. Grouped by "
    "faculty/Professional-Services structure — see sources/org_hierarchy.csv "
    "(best-effort mapping from unit names; some units are flagged doubtful "
    "there)."
)
theme_pick_tm = st.selectbox("Theme", ["Holistic (mean across all themes)"] + THEME_ORDER, key="treemap_theme")

theme_comparisons = load_theme_comparisons()
EXTERNAL_BENCHMARKS = [b for b in theme_comparisons["benchmark"].unique() if b != "Filtered Results"]
baseline_pick = st.selectbox("Baseline", ["University Overall"] + EXTERNAL_BENCHMARKS, key="treemap_baseline")
if baseline_pick != "University Overall":
    st.caption(
        f"'{baseline_pick}' is a single whole-university benchmark figure "
        "(not broken out by department) — every unit's delta below is its "
        "own score minus that one external number, not a per-unit external "
        "comparison."
    )
    bench_check = theme_comparisons[theme_comparisons["benchmark"] == baseline_pick].set_index("theme")["score"]
    missing_themes = [t for t in THEME_ORDER if pd.isna(bench_check.get(t))]
    if missing_themes:
        st.caption(
            f"⚠️ '{baseline_pick}' has no figure for {', '.join(missing_themes)} — "
            "those theme(s) are excluded from every unit's delta (and from "
            "the holistic mean) when this baseline is selected."
        )

fac_office_to_ps = st.toggle(
    "Group Faculty Offices under Professional Services",
    value=False,
    help="Faculty Office staff are professional-services roles administratively "
         "embedded in a faculty. Off (default): each faculty's own Faculty "
         "Office units stay nested inside that faculty. On: all Faculty "
         "Office units move into one combined subgroup under Professional "
         "Services instead.",
)

hierarchy = load_org_hierarchy_ps_faculty_offices() if fac_office_to_ps else load_org_hierarchy()

scores = load_org_scores()
unit_scores = scores[
    (scores["granularity"] == "division_department") & (scores["row_type"] == "theme")
    & (scores["org_unit"] != "Overall")
].copy()

if theme_pick_tm != "Holistic (mean across all themes)":
    unit_scores = unit_scores[unit_scores["theme"] == theme_pick_tm]

if baseline_pick == "University Overall":
    overall = scores[
        (scores["granularity"] == "division_department") & (scores["row_type"] == "theme")
        & (scores["org_unit"] == "Overall")
    ].set_index("theme")["score"]
else:
    bench = theme_comparisons[theme_comparisons["benchmark"] == baseline_pick].set_index("theme")["score"]
    overall = bench

unit_scores["baseline_score"] = unit_scores["theme"].map(overall)
unit_scores["delta_pp"] = (unit_scores["score"] - unit_scores["baseline_score"]) * 100

if theme_pick_tm == "Holistic (mean across all themes)":
    tm = unit_scores.dropna(subset=["delta_pp"]).groupby("org_unit", as_index=False).agg(
        n_responses=("n_responses", "first"), delta_pp=("delta_pp", "mean"),
    )
else:
    tm = unit_scores[["org_unit", "n_responses", "delta_pp"]]

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
# See shorten() — Plotly auto-shrinks text per box but never clips it, so
# names too long even at the smallest readable font overflow the box edge.
# Full names still appear in the hover tooltip (hover_names below).
labels = [shorten(n) for n in tm["org_unit"]] + [shorten(n) for n in subgroups["subgroup"]] + [shorten(n) for n in groups["group"]]
parents = list(tm["subgroup_id"]) + list(subgroups["group"]) + [""] * len(groups)
values = list(tm["n_responses"]) + list(subgroups["n_responses"]) + list(groups["n_responses"])
colors = list(tm["delta_pp"]) + list(subgroups["delta_pp"]) + list(groups["delta_pp"])
# On-box text is the label only (textinfo="label") — stats go in the hover
# tooltip via hovertext/hovertemplate instead of also being drawn on the box,
# which previously showed the unit name twice (once from `labels`, once from
# `text` when textinfo defaulted to "label+text").
hover_names = list(tm["org_unit"]) + list(subgroups["subgroup"]) + list(groups["group"])
hover_stats = (
    [f"{n} responses<br>{delta:+.0f}pp" for n, delta in zip(tm["n_responses"], tm["delta_pp"])]
    + [f"{n} responses<br>{delta:+.0f}pp (avg)" for n, delta in zip(subgroups["n_responses"], subgroups["delta_pp"])]
    + [f"{n} responses<br>{delta:+.0f}pp (avg)" for n, delta in zip(groups["n_responses"], groups["delta_pp"])]
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
    textinfo="label",
    hovertext=hover_names,
    text=hover_stats,
    hovertemplate="%{hovertext}<br>%{text}<extra></extra>",
))
fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
st.plotly_chart(fig, width='stretch', height=650)

st.divider()
st.subheader("Faculty Office effect on faculty standing")
st.caption(
    "Holistic mean delta vs. Overall (percentage points), computed with vs. "
    "without each faculty's own Faculty Office units — shows how much the "
    "Faculty Office is pulling its faculty's overall standing up or down "
    "relative to its academic departments. Independent of the toggle above."
)
comparison = faculty_office_comparison()
st.dataframe(
    comparison.rename(columns={
        "faculty": "Faculty",
        "mean_delta_incl_fac_office": "Mean Δ incl. Faculty Office (pp)",
        "mean_delta_excl_fac_office": "Mean Δ excl. Faculty Office (pp)",
        "difference": "Difference (pp)",
    }),
    column_config={
        "Mean Δ incl. Faculty Office (pp)": st.column_config.NumberColumn(format="%+.1f"),
        "Mean Δ excl. Faculty Office (pp)": st.column_config.NumberColumn(format="%+.1f"),
        "Difference (pp)": st.column_config.NumberColumn(format="%+.1f"),
    },
    hide_index=True, width='stretch',
)
