# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Streamlit app presenting results from the 2026 University of Manchester
staff survey, published by UMUCU (the UCU branch at the University of
Manchester). Source data lives in `Staff Survey 2026/` (gitignored, not
committed — see Security below) as four dashboard exports:

- `Main University of Manchester Survey 2026 - Survey Overall.xlsx` — top-line results
- `Main University of Manchester Survey 2026_Comp Div-Dept.xlsx` — results broken out by Division/Department
- `Main University of Manchester Survey 2026_Comp Sub-Div.xlsx` — results broken out by Sub-Division
- `Main University of Manchester Survey 2026_AllComments.xlsx` — free-text comments

`extract.py` parses these into tidy CSVs under `data/` (gitignored). The four
workbooks share no respondent ID — comments cannot be joined to an org unit;
theme linkage for comments is a separate, user-maintained editorial mapping
(`sources/theme_category_map.csv`), not derived from any shared key.

## Commands

- Extract data: `uv run python3 extract.py` (reads `Staff Survey 2026/`, writes `data/*.csv`)
- Re-encrypt after extraction changes: `uv run python3 encrypt_data.py` (writes `data.enc`)
- Run the app: `uv run streamlit run app.py`

## Architecture

- **`app.py`**: entry point — `st.set_page_config`, password gate, branding, `st.navigation` over `pages/`.
- **`pages/N_Name.py`**: one page per file, numerically prefixed for nav order. Each is a standalone script, not a function library.
- **`utils.py`**: cached data loaders (`@st.cache_data`) reading from `data/`; also owns `ensure_data_decrypted()` (runs on import) and `require_password()`.
- **`styles.py`**: `bjp()` renders user-written editorial commentary in a visually distinct callout block.
  - **`bjp()` calls are strictly user-authored.** Claude must never write or suggest text to go inside a `bjp()` call.
- **`branding/branding.py`**: placeholder UMUCU branding (no real logo assets yet) — keep swappable, don't hardcode another branch's assets/copy.

## Security — data must stay out of git

This repo is public (free Streamlit Community Cloud requires it), and the
survey data — especially free-text comments — is not for public release. Two
layers protect it:

1. **Encryption at rest in git.** `data/*.csv`, `Staff Survey 2026/*.xlsx`,
   and `.streamlit/secrets.toml` are gitignored and must never be committed.
   Only `data.enc` (a Fernet-encrypted tar.gz of `data/`, built by
   `encrypt_data.py`) is committed. `utils.ensure_data_decrypted()` decrypts
   it back into `data/` at runtime using the `DATA_KEY` secret.
2. **Password gate on the running app.** Every page calls
   `utils.require_password()` as its first Streamlit call — this must stay
   true for *every* file added under `pages/`, since `st.navigation`/`st.Page`
   makes each page independently reachable by direct URL, bypassing any gate
   that only lives in `app.py`.

`DATA_KEY` and `APP_PASSWORD` live only in `.streamlit/secrets.toml` locally
(gitignored) and in the Streamlit Cloud app's secrets dashboard for
deployment — never in a committed file.

Before adding any new data export or page: keep raw/derived data under
`Staff Survey 2026/` or `data/` (already ignored) rather than elsewhere, and
re-run `encrypt_data.py` before committing so `data.enc` stays in sync.
