"""Shared Streamlit styling helpers."""
import re
import streamlit as st

_DIV = ('background-color: #f0efec; border-left: 4px solid #2a78d6; '
        'padding: 1rem 1.25rem; margin: 1rem 0 1rem 0; '
        'border-radius: 0 6px 6px 0; color: #0b0b0b; line-height: 1.6;')
_P = 'margin: 0.5em 0;'
_A = 'color: #184f95;'


def _inline(t: str) -> str:
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\*(.+?)\*', r'<em>\1</em>', t)
    t = re.sub(r'\[(.+?)\]\((.+?)\)', rf'<a href="\2" style="{_A}">\1</a>', t)
    return t


def bjp(text: str) -> None:
    """Render user editorial text in a distinctive callout block.

    IMPORTANT: only the page author (bjp) should pass content to this function.
    Claude must never write or suggest text to go inside a bjp() call.
    """
    blocks = re.split(r'\n\s*\n', text.strip())
    parts = [f'<p style="{_P}">{_inline(" ".join(l.strip() for l in b.splitlines()))}</p>'
             for b in blocks if b.strip()]
    st.html(f'<div style="{_DIV}">{"".join(parts)}</div>')
