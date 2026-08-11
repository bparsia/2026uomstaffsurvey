"""UMUCU branding helpers for the UoM Staff Survey 2026 app.

Placeholder branding — no UMUCU logo assets exist yet. Swap in real
assets under branding/assets/ and update this module when available;
generic/text-based for now so the rest of the app doesn't depend on them.
"""
import streamlit as st

SITE_NAME = "UMUCU"


def apply_branding(*, page_title: str, page_icon: str | None = None) -> None:
    """Call before any other st.* calls (after set_page_config)."""
    st.sidebar.markdown(f"### {SITE_NAME}")
