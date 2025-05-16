import streamlit as st
from openai import OpenAI
import os
from reportlab.pdfgen import canvas
from io import BytesIO
import datetime

# === Load OpenAI API key ===
api_key = st.secrets.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    project="proj_36JJwFCLQG34Xyiqb0EWUJlN"
)

# === Enhanced System Prompt ===
SYSTEM_PROMPT = (
    "You are a certified South Carolina DMV Permit Test Tutor specializing in helping teenagers "
    "prepare for their written learner’s permit exam.\n\n"
    "Your job is to clearly explain driving laws, road signs, traffic rules, and safety principles "
    "using only the information found in:\n"
    "- The South Carolina Driver’s Manual (2024 edition), and\n"
    "- The official SC DMV Practice Test: https://practice.dmv-test-pro.com/south-carolina/sc-permit-practice-test-19/\n\n"
    "Your audience is 15- to 17-year-old students. Always speak in an encouraging, friendly tone. "
    "Break down complex topics into simple, relatable language.\n\n"
    "Key instructions:\n"
    "- Only provide information verified in the Driver’s Manual or Practice Test.\n"
    "- Do not make up laws, facts, or statistics.\n"
    "- Use examples that relate to real-world driving in South Carolina.\n"
    "- Format responses using short paragraphs, numbered lists, or bold labels when helpful.\n"
    "- If a user asks for a quiz or flashcards, format the response accordingly (MCQs or Q&A).\n"
    "- If a user gives a score (e.g., 'I got 6/10'), give personalized encouragement and advice on what to review.\n\n"
    "If asked something outside the DMV content (e.g., “How do I get a job?”), politely say:\n"
    "**“I’m here to help you study for the South Carolina permit test. Try asking me about road rules, signs, or safe driving!”**\n\n"
    "Stay focused, accurate, and friendly — your goal is to help students feel confident and ready for their exam."
)

# === GPT Query Function ===
def query_gpt(messages):
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages
    )
    return response.choices[0].message.content

# === PDF Export Function ===
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

# === Simulated User Session ===
def login_placeholder():
    if "user" not in st.session_state:
        st.session_state["user"] = {
            "id": "demo_user",
            "email": "demo@example.com"
        }
        st.session_state["progress_log"] = []

# === Save Quiz Score ===

# === Flashcards ===
elif menu == "Flashcards":
    st.header("Flashcards")
    topic = st.selectbox("Topic", ["Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"])
    if st.button("Generate Flashcards"):
        prompt = f"Generate 10 flashcards for '{topic}' using Q&A format based only on the SC permit test."
        with st.spinner("Creating flashcards..."):
            flashcards = query_gpt([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ])
            st.markdown(flashcards)
            st.download_button("Download PDF", create_pdf(flashcards), file_name="flashcards.pdf")

# === Study Plan ===
elif menu == "Study Plan":
    st.header("3-Day Study Plan")
    if st.button("Create Plan"):
        prompt = "I'm a 15-year-old preparing for the SC permit test. Create a 3-day plan focused on road signs, alcohol laws, and right-of-way rules."
        with st.spinner("Planning..."):
            plan = query_gpt([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ])
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

# === App Setup ===
st.set_page_config(page_title="SC DMV AI Tutor", layout="centered")
st.title("SC DMV Permit Test Tutor")

login_placeholder()
user = st.session_state["user"]

menu = st.sidebar.radio("Navigation", ["Tutor Chat", "Practice Quiz", "Flashcards", "Study Plan", "Progress Tracker"])

# === Tutor Chat ===
if menu == "Tutor Chat":
    st.header("Chat with Your DMV Tutor")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    for msg in st.session_state.chat_history[1:]:
        if msg["role"] == "user":
            st.chat_message("user").write(msg["content"])
        else:
            st.chat_message("assistant").write(msg["content"])

    user_input = st.chat_input("Ask a question about the permit test...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.spinner("Thinking..."):
            response = query_gpt(st.session_state.chat_history)
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.chat_message("user").write(user_input)
        st.chat_message("assistant").write(response)

    if st.button("Clear Chat"):
        st.session_state.chat_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        st.rerun()

# === Practice Quiz ===
elif menu == "Practice Quiz":
    st.header("Practice Quiz")
    num = st.slider("Number of Questions", 5, 10, 5)
    topic = st.text_input("Topic (optional)", "General")

    if st.button("Generate Quiz"):
        prompt = (
            f"Generate a {num}-question multiple choice quiz based on the SC permit test. "
            f"Each question should have a question and 4 choices labeled A-D. Do not mark the correct answer."
        )
        with st.spinner("Creating your quiz..."):
            quiz_text = query_gpt([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ])
            questions = quiz_text.strip().split("

")
            st.session_state["quiz_data"] = questions
            st.session_state["quiz_answers"] = {}

    if "quiz_data" in st.session_state:
        st.subheader("Take the Quiz")
        for idx, q in enumerate(st.session_state["quiz_data"]):
            if not q.strip():
                continue
            parts = q.split("
")
            question_text = parts[0]
            options = parts[1:]
            selected = st.radio(question_text, options, key=f"q_{idx}")
            st.session_state["quiz_answers"][idx] = selected

        if st.button("Submit Quiz"):
            attempted = len(st.session_state["quiz_data"])
            correct_answers = 0
            save_score(user["id"], topic, correct_answers, attempted)
            st.success("Quiz submitted! Your score has been recorded.")
            del st.session_state["quiz_data"]
            del st.session_state["quiz_answers"]

