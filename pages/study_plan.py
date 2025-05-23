import streamlit as st
from utils import create_pdf

PLAN = \"\"\"**Day 1 – Road Signs & Basics**
- Flashcards: *Road Signs*
- 5‑question quiz on *Road Signs*

**Day 2 – Right‑of‑Way & Speed**
- Flashcards: *Right of Way* + *Speed Limits*
- 5‑question quiz on *Right of Way*

**Day 3 – Alcohol & Review**
- Flashcards: *Alcohol Laws* + *Traffic Signals*
- 10‑question *General* quiz\"\"\"\n

def render():
    st.header("3‑Day Study Plan")
    st.markdown(PLAN)
    st.download_button("Download PDF", create_pdf(PLAN), "study_plan.pdf")

