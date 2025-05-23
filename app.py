# app.py
import streamlit as st, stripe
from utils import supabase                 # already initialised
from pages import tutor_chat, quiz, flashcards, study_plan, progress

# Stripe helpers stay here (omitted for brevity)

SYSTEM_PROMPT = (
    "You are a certified South Carolina DMV Permit Test Tutor specializing in helping teenagers "
    "prepare for their written learner’s permit exam.\n\n"
    "Your job is to clearly explain driving laws, road signs, traffic rules, and safety principles "
    "using ONLY the information found in:\n"
    "- The South Carolina Driver’s Manual (2024 edition)\n"
    "- The official SC DMV Practice Test\n\n"
    "Key instructions:\n"
    "- ONLY use facts found in the manual or practice test.\n"
    "- DO NOT make up laws, facts, or explanations.\n"
    "- Use language appropriate for 15–17‑year‑olds.\n"
    "- Quiz format: Question #, A.–D., Answer.\n"
    "- Flashcard format: Q:, A:.\n"
    "- Return exactly N questions OR 10 flashcards with **no extra text**."
)

# --- Auth gate ---
st.set_page_config(page_title="SC DMV AI Tutor")
st.title("SC DMV Permit Test Tutor")
if "user" not in st.session_state:
    # call your existing login_ui() here (you can move it to utils and import)
    from utils import login_ui
    login_ui(); st.stop()

user = st.session_state["user"]
has_access = user_has_access(user.id)         # keep function in this file or utils

# Sidebar
if not has_access:
    st.sidebar.warning("🚧 Quiz & Flashcards require purchase.")
    if st.sidebar.button("Buy Lifetime Access"):
        st.experimental_redirect(create_checkout_session(user.email))

page = st.sidebar.radio(
    "Navigation",
    ["Tutor Chat",
     *([\"Practice Quiz\",\"Flashcards\"] if has_access else []),
     "Study Plan","Progress Tracker"]
)

# Router
if page == "Tutor Chat":
    tutor_chat.render(SYSTEM_PROMPT)
elif page == "Practice Quiz":
    quiz.render(SYSTEM_PROMPT, user.id)
elif page == "Flashcards":
    flashcards.render(SYSTEM_PROMPT)
elif page == "Study Plan":
    study_plan.render()
elif page == "Progress Tracker":
    progress.render(user.id)
