import plotly.graph_objects as go
import streamlit as st

from utils import (
    THEME_ORDER, load_meta, load_themes, load_theme_comparisons, comments_for_theme,
    require_password,
)

require_password()

BLUE = "#2a78d6"
RED = "#e34948"

st.title("UoM Staff Survey 2026 — Overview")

meta = load_meta()
themes = load_themes().set_index("theme").loc[THEME_ORDER].reset_index()

c1, c2, c3 = st.columns(3)
c1.metric("Responses", f"{int(meta['response_count']):,}")
c2.metric("Panel size", f"{int(meta['panel_count']):,}")
c3.metric("Participation", f"{meta['participation'] * 100:.0f}%")

st.divider()

st.subheader("Theme scores")
fig = go.Figure(go.Bar(
    x=themes["score"], y=themes["theme"], orientation="h",
    marker_color=BLUE,
    text=[f"{v * 100:.0f}%" for v in themes["score"]],
    textposition="outside",
))
fig.update_layout(
    xaxis=dict(range=[0, 1], tickformat=".0%", title=None),
    yaxis=dict(autorange="reversed", title=None),
    height=320, margin=dict(t=10, b=10, l=10, r=40),
    plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
)
st.plotly_chart(fig, width='stretch')

st.divider()

st.subheader("How each theme compares to benchmarks")
comp = load_theme_comparisons()
benchmark_options = [b for b in comp["benchmark"].unique() if b != "Filtered Results"]
benchmark = st.selectbox("Benchmark", benchmark_options, index=benchmark_options.index("University of Manchester Survey 2025"))

bdf = comp[comp["benchmark"] == benchmark].set_index("theme").loc[THEME_ORDER].reset_index()
colors = [RED if v < 0 else BLUE for v in bdf["diff"].fillna(0)]
fig2 = go.Figure(go.Bar(
    x=bdf["diff"], y=bdf["theme"], orientation="h",
    marker_color=colors,
    text=[f"{v:+.0f}pp" if v == v else "n/a" for v in bdf["diff"]],
    textposition="outside",
))
fig2.update_layout(
    xaxis=dict(title="Percentage points vs. benchmark", zeroline=True, zerolinecolor="#c9c8c2"),
    yaxis=dict(autorange="reversed", title=None),
    height=320, margin=dict(t=10, b=10, l=10, r=40),
    plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
)
st.plotly_chart(fig2, width='stretch')

st.divider()

st.subheader("What people are saying")
st.caption(
    "Comments are matched to themes via category tags (see "
    "sources/theme_category_map.csv) — this is a whole-university view; "
    "comments cannot be broken out by organisational unit (the export has no "
    "unit column)."
)

theme_pick = st.selectbox("Theme", THEME_ORDER, key="comment_theme")
sentiment_pick = st.multiselect(
    "Sentiment", ["Positive", "Negative", "Mixed", "Neutral", "Not Analysed"],
    default=["Positive", "Negative"],
)

matched = comments_for_theme(theme_pick)
if sentiment_pick:
    matched = matched[matched["sentiment"].isin(sentiment_pick)]

st.caption(f"{len(matched):,} comments matched")
for _, row in matched.sample(min(10, len(matched)), random_state=0).iterrows():
    st.markdown(f"> {row['comment']}")
    st.caption(f"{row['sentiment']} · {row['question']}")
