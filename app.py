import streamlit as st

st.set_page_config(
    page_title="UoM Staff Survey 2026",
    page_icon="📋",
    layout="wide",
)

from utils import require_password

require_password()

from branding.branding import apply_branding

apply_branding(page_title="UoM Staff Survey 2026")

overview = st.Page("pages/0_Overview.py", title="Overview", icon="📊", default=True)
my_unit = st.Page("pages/1_My_Unit.py", title="My Unit", icon="🔍")
hotspots = st.Page("pages/2_Hotspots.py", title="Hotspots", icon="🔥")

pg = st.navigation([overview, my_unit, hotspots])
pg.run()
