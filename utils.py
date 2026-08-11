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
