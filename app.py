import streamlit as st
from openai import OpenAI
import os
from reportlab.pdfgen import canvas
from io import BytesIO
import datetime
import re

# === Load OpenAI API key ===
api_key = st.secrets.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    project="proj_36JJwFCLQG34Xyiqb0EWUJlN"
)

# === Enhanced System Prompt ===
SYSTEM_PROMPT = (
    "You are a certified South Carolina DMV Permit Test Tutor specializing in helping teenagers "
    "prepare for their written learner’s permit exam.

"
    "Your job is to clearly explain driving laws, road signs, traffic rules, and safety principles "
    "using only the information found in:
"
    "- The South Carolina Driver’s Manual (2024 edition), and
"
    "- The official SC DMV Practice Test: https://practice.dmv-test-pro.com/south-carolina/sc-permit-practice-test-19/

"
    "Your audience is 15- to 17-year-old students. Always speak in an encouraging, friendly tone. "
    "Break down complex topics into simple, relatable language.

"
    "Key instructions:
"
    "- Only provide information verified in the Driver’s Manual or Practice Test.
"
    "- Do not make up laws, facts, or statistics.
"
    "- Use examples that relate to real-world driving in South Carolina.
"
    "- Format responses using short paragraphs, numbered lists, or bold labels when helpful.
"
    "- If a user asks for a quiz or flashcards, format the response accordingly.
"
    "For quizzes, follow this format strictly:
"
    "Question 1: [question text]
"
    "A. [option A]
"
    "B. [option B]
"
    "C. [option C]
"
    "D. [option D]
"
    "Answer: [Correct letter]

"
    "Return exactly N questions, no explanations.

"
    "If a user gives a score (e.g., 'I got 6/10'), give personalized encouragement and advice on what to review.

"
    "If asked something outside the DMV content, say:
"
    "**'I’m here to help you study for the South Carolina permit test. Try asking me about road rules, signs, or safe driving!'**"
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

# === Parse Quiz Format ===
def parse_quiz(raw_text):
    questions = []
    chunks = raw_text.strip().split("\n\n")
    for chunk in chunks:
        lines = chunk.strip().split("\n")
        if len(lines) >= 6:
            question = lines[0].split(":", 1)[-1].strip()
            options = {line[0]: line[3:].strip() for line in lines[1:5]}
            correct = lines[5].split(":", 1)[-1].strip().upper()
            questions.append({
                "question": question,
                "options": options,
                "answer": correct
            })
    return questions

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
        st.chat_message(msg["role"]).write(msg["content"])
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
        prompt = f"Generate a {num}-question multiple choice quiz based on the SC permit test."
        with st.spinner("Creating your quiz..."):
            raw_quiz = query_gpt([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ])
            quiz_data = parse_quiz(raw_quiz)
            st.session_state["quiz_data"] = quiz_data
            st.session_state["quiz_answers"] = {}
            st.session_state["quiz_submitted"] = False

    if "quiz_data" in st.session_state:
        st.subheader("Take the Quiz")
        for idx, q in enumerate(st.session_state["quiz_data"]):
            selected = st.radio(
                f"{idx+1}. {q['question']}",
                [f"{key}. {val}" for key, val in q["options"].items()],
                key=f"q_{idx}"
            )
            st.session_state["quiz_answers"][idx] = selected[0]

        if not st.session_state.get("quiz_submitted") and st.button("Submit Quiz"):
            st.session_state["quiz_submitted"] = True
            correct_answers = 0
            for idx, q in enumerate(st.session_state["quiz_data"]):
                if st.session_state["quiz_answers"].get(idx) == q["answer"]:
                    correct_answers += 1
            save_score(user["id"], topic, correct_answers, len(st.session_state["quiz_data"]))
            st.success(f"You got {correct_answers} out of {len(st.session_state['quiz_data'])} correct!")

            st.markdown("**Correct Answers:**")
            for i, q in enumerate(st.session_state["quiz_data"]):
                st.markdown(f"- Question {i+1}: {q['answer']}")

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
