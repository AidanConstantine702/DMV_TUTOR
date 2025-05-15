import streamlit as st
import openai
import os
from reportlab.pdfgen import canvas
from io import BytesIO
import datetime

# === Load API key ===
api_key = st.secrets["openai_api_key"]
openai.api_key = api_key

# === System Prompt for AI ===
SYSTEM_PROMPT = (
    "You are a South Carolina DMV permit tutor. Only use information from the SC DMV "
    "Driver's Manual and the SC DMV practice test website at "
    "https://practice.dmv-test-pro.com/south-carolina/sc-permit-practice-test-19/. "
    "Answer clearly and simply for a 15-year-old."
)

# === GPT Call Function ===
def query_gpt(user_prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response['choices'][0]['message']['content']

# === PDF Export ===
def create_pdf(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    lines = text.split("\n")
    y = 800
    for line in lines:
        if y < 40:
            pdf.showPage()
            y = 800
        pdf.drawString(40, y, line)
        y -= 15
    pdf.save()
    buffer.seek(0)
    return buffer

# === Simulated Login (Supabase-ready structure) ===
def login_placeholder():
    if "user" not in st.session_state:
        st.session_state["user"] = {
            "id": "demo_user",
            "email": "demo@example.com"
        }
        st.session_state["progress_log"] = []

# === Score Logging Function (placeholder for Supabase insert) ===
def save_score(user_id, topic, correct, attempted):
    if "progress_log" not in st.session_state:
        st.session_state["progress_log"] = []
    st.session_state["progress_log"].append({
        "user_id": user_id,
        "topic": topic,
        "correct": correct,
        "attempted": attempted,
        "date": str(datetime.date.today())
    })

# === App Interface ===
st.set_page_config(page_title="SC DMV AI Tutor", layout="centered")
st.title("SC DMV Permit Test Tutor")

login_placeholder()
user = st.session_state["user"]

menu = st.sidebar.radio("Navigation", ["Tutor Chat", "Practice Quiz", "Flashcards", "Study Plan", "Progress Tracker"])

# === Tutor Chat ===
if menu == "Tutor Chat":
    st.header("Chat with Your DMV Tutor")
    question = st.text_input("Ask a DMV question:")
    if st.button("Submit"):
        if question:
            with st.spinner("Thinking..."):
                response = query_gpt(question)
                st.write(response)

# === Practice Quiz ===
elif menu == "Practice Quiz":
    st.header("Practice Quiz")
    num = st.slider("Number of Questions", 5, 20, 10)
    topic = st.text_input("Topic (optional)", "General")
    if st.button("Generate Quiz"):
        prompt = (
            f"Generate a {num}-question multiple choice quiz based on the SC permit test. "
            f"Each question should have 4 choices A-D, and mark the correct answer with ✅."
        )
        with st.spinner("Creating your quiz..."):
            quiz = query_gpt(prompt)
            st.markdown(quiz)

    st.subheader("Track Your Results")
    correct = st.number_input("How many did you get right?", min_value=0, max_value=num, step=1)
    if st.button("Submit Score"):
        save_score(user["id"], topic, correct, num)
        st.success("Score saved!")

# === Flashcards ===
elif menu == "Flashcards":
    st.header("Flashcards")
    topic = st.selectbox("Topic", ["Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"])
    if st.button("Generate Flashcards"):
        prompt = f"Generate 10 flashcards for '{topic}' using Q&A format based only on the SC permit test."
        with st.spinner("Creating flashcards..."):
            flashcards = query_gpt(prompt)
            st.markdown(flashcards)
            st.download_button("Download PDF", create_pdf(flashcards), file_name="flashcards.pdf")

# === Study Plan ===
elif menu == "Study Plan":
    st.header("3-Day Study Plan")
    if st.button("Create Plan"):
        prompt = "I'm a 15-year-old preparing for the SC permit test. Create a 3-day plan focused on road signs, alcohol laws, and right-of-way rules."
        with st.spinner("Planning..."):
            plan = query_gpt(prompt)
            st.markdown(plan)
            st.download_button("Download PDF", create_pdf(plan), file_name="study_plan.pdf")

# === Progress Tracker ===
elif menu == "Progress Tracker":
    st.header("Your Progress")
    progress = st.session_state.get("progress_log", [])
    if progress:
        for entry in progress:
            st.markdown(f"**{entry['date']}** - {entry['topic']} — {entry['correct']}/{entry['attempted']} correct")
        total_correct = sum(x["correct"] for x in progress)
        total_attempted = sum(x["attempted"] for x in progress)
        if total_attempted > 0:
            accuracy = (total_correct / total_attempted) * 100
            st.metric("Total Accuracy", f"{accuracy:.1f}%")
    else:
        st.info("No progress saved yet.")
