import streamlit as st
from collections import defaultdict
from utils import supabase

def render(user_id):
    st.header("Your Progress")
    data = supabase.table("quiz_scores").select("*").eq("user_id",user_id).execute().data
    if not data:
        st.info("No attempts yet.")
        return
    daily = defaultdict(lambda: {"c":0,"t":0})
    for r in data:
        d = r["date"]; daily[d]["c"]+=r["correct"]; daily[d]["t"]+=r["attempted"]
    for d in sorted(daily, reverse=True):
        c,t = daily[d]["c"], daily[d]["t"]
        st.markdown(f"**{d}** – {c}/{t} ({c/t*100:.1f} %)")
    tot_c = sum(r["correct"] for r in data); tot_t = sum(r["attempted"] for r in data)
    st.metric("Overall Accuracy", f\"{tot_c/tot_t*100:.1f}%\")

