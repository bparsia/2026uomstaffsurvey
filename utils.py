"""Shared data loaders and helpers for the UoM Staff Survey 2026 app."""
import io
import tarfile
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA_ENC = ROOT / "data.enc"

THEME_ORDER = ["Engagement", "Purpose", "Enablement", "Autonomy", "Reward", "Leadership", "EDI"]


def require_password() -> None:
    """Password gate — must be the first Streamlit call on every page script.

    st.navigation()/st.Page() makes each pages/*.py independently reachable
    (sidebar nav, direct URL), so gating only in app.py does NOT protect the
    other pages — each page script needs its own call to this. Remove once
    the app is public.
    """
    password = st.secrets.get("APP_PASSWORD", "")
    if not password:
        return
    if st.session_state.get("authenticated"):
        return
    pwd = st.text_input("Password", type="password")
    if pwd == password:
        st.session_state["authenticated"] = True
        st.rerun()
    elif pwd:
        st.error("Incorrect password.")
    st.stop()


def ensure_data_decrypted() -> None:
    """Decrypt data.enc into data/ if data/ is missing or empty.

    data/*.csv are gitignored — only the encrypted data.enc is committed.
    Locally, run extract.py directly and data/ is already populated, so this
    is a no-op. On a fresh deploy (e.g. Streamlit Cloud), data/ won't exist
    yet, so this decrypts data.enc using the DATA_KEY secret.
    """
    if DATA.exists() and any(DATA.glob("*.csv")):
        return
    if not DATA_ENC.exists():
        raise FileNotFoundError(
            "Neither data/*.csv nor data.enc found. Run extract.py (and "
            "encrypt_data.py, if you need to regenerate data.enc)."
        )
    key = st.secrets.get("DATA_KEY")
    if not key:
        raise RuntimeError("DATA_KEY secret not set — cannot decrypt data.enc.")

    from cryptography.fernet import Fernet
    fernet = Fernet(key.encode())
    decrypted = fernet.decrypt(DATA_ENC.read_bytes())

    DATA.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(decrypted), mode="r:gz") as tar:
        tar.extractall(DATA, filter="data")


ensure_data_decrypted()


@st.cache_data
def load_meta() -> pd.Series:
    return pd.read_csv(DATA / "meta.csv").iloc[0]


@st.cache_data
def load_themes() -> pd.DataFrame:
    return pd.read_csv(DATA / "themes.csv")


@st.cache_data
def load_questions() -> pd.DataFrame:
    return pd.read_csv(DATA / "questions.csv")


@st.cache_data
def load_theme_comparisons() -> pd.DataFrame:
    return pd.read_csv(DATA / "theme_comparisons.csv")


@st.cache_data
def load_question_comparisons() -> pd.DataFrame:
    return pd.read_csv(DATA / "question_comparisons.csv")


@st.cache_data
def load_org_scores() -> pd.DataFrame:
    return pd.read_csv(DATA / "org_scores.csv")


@st.cache_data
def load_org_deltas() -> pd.DataFrame:
    return pd.read_csv(DATA / "org_deltas.csv")


@st.cache_data
def load_comments_themed() -> pd.DataFrame:
    df = pd.read_csv(DATA / "comments_themed.csv")
    df["themes"] = df["themes"].fillna("")
    return df


def org_units(granularity: str) -> list[str]:
    """Sorted org unit names for a granularity, excluding 'Overall'."""
    scores = load_org_scores()
    units = scores.loc[scores["granularity"] == granularity, "org_unit"].unique()
    return sorted(u for u in units if u != "Overall")


def unit_scorecard(granularity: str, org_unit: str) -> pd.DataFrame:
    """Theme + question rows for one org unit, with its delta vs Overall."""
    scores = load_org_scores()
    deltas = load_org_deltas()

    s = scores[(scores["granularity"] == granularity) & (scores["org_unit"] == org_unit)]
    d = deltas[(deltas["granularity"] == granularity) & (deltas["org_unit"] == org_unit)]

    merged = s.merge(
        d[["theme", "question", "row_type", "delta_pp"]],
        on=["theme", "question", "row_type"], how="left",
    )
    return merged


def fmt_pct(v: float) -> str:
    if pd.isna(v):
        return "n/a"
    return f"{v * 100:.0f}%"


def fmt_delta_pp(v: float) -> str:
    if pd.isna(v):
        return "n/a"
    return f"{v:+.0f}pp"


def comments_for_theme(theme: str) -> pd.DataFrame:
    df = load_comments_themed()
    return df[df["themes"].str.contains(theme, regex=False)]


SOURCES = ROOT / "sources"


@st.cache_data
def load_org_hierarchy() -> pd.DataFrame:
    """Faculty/Professional-Services grouping for division_department units.

    Best-effort mapping from unit name to (group, subgroup) — see
    sources/org_hierarchy.csv and its `doubtful` column for units the mapping
    is genuinely unsure about. Division/Department only — Sub-Division has no
    equivalent hierarchy mapping.
    """
    df = pd.read_csv(SOURCES / "org_hierarchy.csv")
    df["group"] = df["group"].fillna("Unclassified")
    df["subgroup"] = df["subgroup"].fillna("Unclassified")
    return df


def unit_theme_deltas(granularity: str = "division_department") -> pd.DataFrame:
    """Wide table: one row per org unit, one column per theme's delta_pp vs Overall."""
    deltas = load_org_deltas()
    d = deltas[
        (deltas["granularity"] == granularity) & (deltas["row_type"] == "theme")
        & (deltas["org_unit"] != "Overall")
    ]
    wide = d.pivot(index="org_unit", columns="theme", values="delta_pp")[THEME_ORDER]
    return wide


def holistic_ranking(granularity: str = "division_department") -> pd.DataFrame:
    """Composite standing per org unit across all 7 themes.

    Three complementary metrics, since no single number is safe here — a unit
    that's strong on 6 themes and badly negative on 1 should not look "fine"
    on average:
      - mean_delta_pp: average delta across all 7 themes (overall standing)
      - worst_delta_pp: its single lowest theme delta (surfaces a hidden problem area)
      - themes_below: how many of the 7 themes are below Overall (breadth of trouble)

    Units below the survey's minimum-N reporting threshold have no theme
    scores at all (every cell 'n/a' in the source) and are dropped.
    """
    wide = unit_theme_deltas(granularity)
    wide = wide.dropna(how="all")
    scores = load_org_scores()
    n_by_unit = (
        scores[(scores["granularity"] == granularity) & (scores["row_type"] == "theme")]
        .drop_duplicates("org_unit").set_index("org_unit")["n_responses"]
    )

    out = pd.DataFrame({
        "mean_delta_pp": wide.mean(axis=1),
        "worst_delta_pp": wide.min(axis=1),
        "worst_theme": wide.idxmin(axis=1),
        "themes_below": (wide < 0).sum(axis=1),
    })
    out["n_responses"] = n_by_unit.reindex(out.index)
    return out.reset_index().rename(columns={"index": "org_unit"})


def _bin_pack(sizes: "pd.Series[int]", target_n: int) -> list[list[str]]:
    """Greedily bin-pack items (largest first) into groups targeting target_n total.

    Then repeatedly merges the two smallest under-target groups so no item is
    left stranded alone just because it was processed after every other group
    had already crossed target_n.
    """
    pools: list[list[str]] = []
    pool_totals: list[int] = []
    for item, n in sizes.sort_values(ascending=False).items():
        placed = False
        for i, total in enumerate(pool_totals):
            if total + n <= target_n * 1.5 and total < target_n:
                pools[i].append(item)
                pool_totals[i] += n
                placed = True
                break
        if not placed:
            pools.append([item])
            pool_totals.append(n)

    while True:
        under = [i for i, t in enumerate(pool_totals) if t < target_n]
        if len(under) < 2:
            break
        under.sort(key=lambda i: pool_totals[i])
        a, b = under[0], under[1]
        if pool_totals[a] + pool_totals[b] > target_n * 1.5:
            break
        pools[a].extend(pools[b])
        pool_totals[a] += pool_totals[b]
        del pools[b]
        del pool_totals[b]

    return pools


def synthetic_pools(granularity: str = "division_department", target_n: int = 150) -> pd.DataFrame:
    """Group org units into pools of roughly equal total response count.

    Small units (n as low as ~11) dominate "extreme delta" rankings on noise
    alone; large units (n up to ~1600) barely move. Bin-packs units into
    pools targeting `target_n` total responses each — but only ever merges
    units within the same hierarchy subgroup (sources/org_hierarchy.csv), so
    a pool never mixes e.g. a Law department with an Estates team just
    because their headcounts happen to add up. Some pools land under
    target_n if their subgroup is small — that's honest, not a bug.
    Pool score/delta = response-weighted average of its member units.

    Units below the survey's minimum-N reporting threshold (no score at all,
    every theme cell 'n/a' in the source) are excluded entirely — pooling
    enough of them together to hit target_n would still carry zero signal.
    Units with no hierarchy mapping (Unclassified) are pooled among themselves.
    """
    scores = load_org_scores()
    deltas = load_org_deltas()
    hierarchy = load_org_hierarchy()
    s = scores[(scores["granularity"] == granularity) & (scores["row_type"] == "theme")]
    d = deltas[(deltas["granularity"] == granularity) & (deltas["row_type"] == "theme")]
    merged = s.merge(d[["org_unit", "theme", "delta_pp"]], on=["org_unit", "theme"], how="left")
    merged = merged[merged["org_unit"] != "Overall"]
    merged = merged.merge(
        hierarchy[["unit", "group", "subgroup"]].rename(columns={"unit": "org_unit"}),
        on="org_unit", how="left",
    )
    merged["group"] = merged["group"].fillna("Unclassified")
    merged["subgroup"] = merged["subgroup"].fillna("Unclassified")

    has_any_score = merged.groupby("org_unit")["score"].apply(lambda s: s.notna().any())
    merged = merged[merged["org_unit"].isin(has_any_score[has_any_score].index)]

    sizes = merged.drop_duplicates("org_unit").set_index("org_unit")["n_responses"]
    unit_subgroup = merged.drop_duplicates("org_unit").set_index("org_unit")["subgroup"]

    unit_to_pool: dict[str, str] = {}
    for subgroup, group_sizes in sizes.groupby(unit_subgroup):
        subgroup_pools = _bin_pack(group_sizes, target_n)
        for i, pool in enumerate(subgroup_pools):
            pool_name = subgroup if len(subgroup_pools) == 1 else f"{subgroup} / {chr(65 + i)}"
            for unit in pool:
                unit_to_pool[unit] = pool_name
    merged["pool"] = merged["org_unit"].map(unit_to_pool)

    def weighted(g):
        # Units below the minimum-N reporting threshold have real headcount
        # (n_responses) but no score for this theme (NaN) — they still count
        # toward the pool's total headcount, but must not enter the weighted
        # score/delta average (would silently understate it via a NaN-padded
        # denominator).
        has_score = g["score"].notna()
        w = g.loc[has_score, "n_responses"]
        return pd.Series({
            "score": (g.loc[has_score, "score"] * w).sum() / w.sum() if len(w) else float("nan"),
            "delta_pp": (g.loc[has_score, "delta_pp"] * w).sum() / w.sum() if len(w) else float("nan"),
            "n_responses": g["n_responses"].sum(),
            "n_units": g["org_unit"].nunique(),
            "member_units": ", ".join(sorted(g["org_unit"].unique())),
        })

    return merged.groupby(["pool", "theme"]).apply(weighted, include_groups=False).reset_index()
