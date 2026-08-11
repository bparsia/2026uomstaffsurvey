import streamlit as st

from utils import THEME_ORDER, load_org_scores, load_org_deltas, require_password

require_password()

st.title("Hotspots")
st.caption(
    "Ranked by delta vs. Overall (percentage points) — units with unusually "
    "high or low scores relative to the whole university. Small units (low "
    "response counts) can swing on a handful of responses; treat as "
    "indicative, not statistically robust."
)

c1, c2, c3 = st.columns(3)
granularity_label = c1.radio("Granularity", ["Division / Department", "Sub-Division"], horizontal=True)
granularity = "division_department" if granularity_label == "Division / Department" else "sub_division"

theme_pick = c2.selectbox("Theme", THEME_ORDER)

scores = load_org_scores()
deltas = load_org_deltas()

theme_scores = scores[
    (scores["granularity"] == granularity) & (scores["row_type"] == "theme")
    & (scores["theme"] == theme_pick) & (scores["org_unit"] != "Overall")
]
question_options = ["(theme score)"] + sorted(
    scores.loc[
        (scores["granularity"] == granularity) & (scores["row_type"] == "question")
        & (scores["theme"] == theme_pick), "question",
    ].dropna().unique()
)
question_pick = c3.selectbox("Question (optional)", question_options)

if question_pick == "(theme score)":
    s = scores[
        (scores["granularity"] == granularity) & (scores["row_type"] == "theme")
        & (scores["theme"] == theme_pick) & (scores["org_unit"] != "Overall")
    ]
    d = deltas[
        (deltas["granularity"] == granularity) & (deltas["row_type"] == "theme")
        & (deltas["theme"] == theme_pick) & (deltas["org_unit"] != "Overall")
    ]
else:
    s = scores[
        (scores["granularity"] == granularity) & (scores["row_type"] == "question")
        & (scores["question"] == question_pick) & (scores["org_unit"] != "Overall")
    ]
    d = deltas[
        (deltas["granularity"] == granularity) & (deltas["row_type"] == "question")
        & (deltas["question"] == question_pick) & (deltas["org_unit"] != "Overall")
    ]

merged = s.merge(d[["org_unit", "delta_pp"]], on="org_unit", how="left").sort_values("delta_pp")

min_n = st.slider("Minimum responses", 0, int(merged["n_responses"].max()), 10)
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
