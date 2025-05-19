import streamlit as st
from openai import OpenAI
import os
from reportlab.pdfgen import canvas
from io import BytesIO
import datetime
import re
from supabase import create_client, Client

# === Load credentials from secrets.toml ===
supabase_url = st.secrets["supabase"]["url"]
supabase_key = st.secrets["supabase"]["key"]
api_key = st.secrets["openai_api_key"]

# === Initialize Supabase and OpenAI ===
supabase: Client = create_client(supabase_url, supabase_key)
client = OpenAI(api_key=api_key, project="proj_36JJwFCLQG34Xyiqb0EWUJlN")

# === System Prompt ===
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
    "- If a user asks for a quiz or flashcards, format the response accordingly.\n"
    "For quizzes, follow this format strictly:\n"
    "Question 1: [question text]\n"
    "A. [option A]\n"
    "B. [option B]\n"
    "C. [option C]\n"
    "D. [option D]\n"
    "Answer: [Correct letter]\n\n"
    "Return exactly N questions, no explanations.\n\n"
    "If a user gives a score (e.g., 'I got 6/10'), give personalized encouragement and advice on what to review.\n\n"
    "If asked something outside the DMV content, say:\n"
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

# === Login UI ===
def login_ui():
    st.subheader("Login / Sign Up")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Log In"):
        try:
            user = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if user.user:
                st.session_state["user"] = user.user
                st.success("Logged in successfully!")
                st.rerun()  # <- Forces rerun to load app
        except Exception as e:
            st.error("Login failed. Check your email or password.")

    if st.button("Sign Up"):
        try:
            result = supabase.auth.sign_up({"email": email, "password": password})
            if result.user:
                st.success("Account created! Please check your email to confirm.")
        except Exception as e:
            st.error("Signup failed. Email may already be registered.")

# === Save Quiz Score ===
def save_score(user_id, topic, correct, attempted):
    data = {
        "user_id": user_id,
        "topic": topic,
        "correct": correct,
        "attempted": attempted,
        "date": str(datetime.date.today())
    }
    supabase.table("quiz_scores").insert(data).execute()

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

if "user" not in st.session_state:
    login_ui()
    st.stop()

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
        question_label = f"{idx+1}. {q['question']}"
        options = [f"{key}. {val}" for key, val in q["options"].items()]
        selected = st.radio(question_label, options, key=f"q_{idx}")
        st.session_state["quiz_answers"][idx] = selected[0]

    if not st.session_state.get("quiz_submitted") and st.button("Submit Quiz"):
        st.session_state["quiz_submitted"] = True
        correct_answers = 0
        for idx, q in enumerate(st.session_state["quiz_data"]):
            if st.session_state["quiz_answers"].get(idx) == q["answer"]:
                correct_answers += 1
        save_score(user.id, topic, correct_answers, len(st.session_state["quiz_data"]))
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
    user_id = user.id
    response = supabase.table("quiz_scores").select("*").eq("user_id", user_id).execute()
    progress = response.data if response else []
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
