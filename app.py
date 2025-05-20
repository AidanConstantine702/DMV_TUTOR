import streamlit as st
from openai import OpenAI
import os
from reportlab.pdfgen import canvas
from io import BytesIO
import datetime
import re
from supabase import create_client, Client

# === Load credentials ===
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
    "Key instructions:\n"
    "- ONLY use facts found in the manual or practice test.\n"
    "- DO NOT make up laws, facts, or explanations.\n"
    "- Use language appropriate for 15- to 17-year-olds.\n"
    "- When creating a quiz, strictly follow this format:\n"
    "Question 1: [question text]\n"
    "A. [option A]\n"
    "B. [option B]\n"
    "C. [option C]\n"
    "D. [option D]\n"
    "Answer: [A/B/C/D]\n\n"
    "- Start each question with 'Question [number]:'.\n"
    "- Return EXACTLY N questions in the specified format.\n"
    "- DO NOT include explanations, hints, or any extra text.\n"
    "- Make sure all questions are unique and properly numbered.\n\n"
    "- When creating flashcards, strictly follow this format:\n"
    "Q: [question]\nA: [answer]\n"
    "- Return exactly 10 Q/A flashcards and nothing else. No numbering, no MCQ, no explanations, no commentary.\n\n"
    "**Failure to follow these instructions will result in broken output.**"
)

# === Query GPT ===
def query_gpt(messages):
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages
    )
    return response.choices[0].message.content

# === Parse quiz from GPT format ===
def parse_quiz(raw_text):
    pattern = re.compile(
        r"Question\s+\d+:\s*(.*?)\nA\.\s*(.*?)\nB\.\s*(.*?)\nC\.\s*(.*?)\nD\.\s*(.*?)\nAnswer:\s*([A-D])",
        re.DOTALL
    )
    matches = pattern.findall(raw_text)
    questions = []
    for match in matches:
        question, a, b, c, d, answer = match
        questions.append({
            "question": question.strip(),
            "options": {
                "A": a.strip(),
                "B": b.strip(),
                "C": c.strip(),
                "D": d.strip()
            },
            "answer": answer.strip()
        })
    return questions

# === Parse flashcards from GPT format ===
def parse_flashcards(raw_text):
    # Looks for: Q: ... \nA: ...
    pattern = re.compile(r"Q:\s*(.*?)\nA:\s*(.*?)(?=\nQ:|\Z)", re.DOTALL)
    cards = pattern.findall(raw_text)
    return [{"question": q.strip(), "answer": a.strip()} for q, a in cards]

# === Create PDF ===
def create_pdf(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    y = 800
    for line in text.split("\n"):
        if y < 40:
            pdf.showPage()
            y = 800
        pdf.drawString(40, y, line)
        y -= 15
    pdf.save()
    buffer.seek(0)
    return buffer

# === Save to Supabase ===
def save_score(user_id, topic, correct, attempted):
    supabase.table("quiz_scores").insert({
        "user_id": user_id,
        "topic": topic,
        "correct": correct,
        "attempted": attempted,
        "date": str(datetime.date.today())
    }).execute()

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
                st.rerun()
        except Exception:
            st.error("Login failed. Check your credentials.")
    if st.button("Sign Up"):
        try:
            result = supabase.auth.sign_up({"email": email, "password": password})
            if result.user:
                st.success("Account created! Check your email.")
        except Exception:
            st.error("Signup failed. Email may already be registered.")

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
    topic = st.selectbox("Quiz Topic", ["Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"])
    if st.button("Generate Quiz"):
        prompt = (
            f"Generate exactly {num} multiple-choice questions about '{topic}' for the South Carolina DMV permit test. "
            "Each must follow this format:\n"
            "Question 1: [question]\n"
            "A. [option A]\n"
            "B. [option B]\n"
            "C. [option C]\n"
            "D. [option D]\n"
            "Answer: [correct option letter]\n\n"
            "Return ONLY the questions — no explanations, no commentary, no extra text. "
            "Number all questions correctly and provide the correct answer for each."
        )
        with st.spinner("Creating your quiz..."):
            raw_quiz = query_gpt([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ])
            st.session_state["quiz_data"] = parse_quiz(raw_quiz)
            st.session_state["quiz_answers"] = {}
            st.session_state["quiz_submitted"] = False

    if "quiz_data" in st.session_state:
        st.subheader("Take the Quiz")
        for idx, q in enumerate(st.session_state["quiz_data"]):
            label = f"{idx + 1}. {q['question']}"
            options = [f"{key}. {val}" for key, val in q["options"].items()]
            selected = st.radio(label, options, key=f"q_{idx}")
            st.session_state["quiz_answers"][idx] = selected[0]

        if not st.session_state.get("quiz_submitted") and st.button("Submit Quiz"):
            st.session_state["quiz_submitted"] = True
            correct = 0
            for idx, q in enumerate(st.session_state["quiz_data"]):
                if st.session_state["quiz_answers"].get(idx) == q["answer"]:
                    correct += 1
            save_score(user.id, topic, correct, len(st.session_state["quiz_data"]))
            st.success(f"You got {correct} out of {len(st.session_state['quiz_data'])} correct!")
            st.markdown("**Correct Answers:**")
            for i, q in enumerate(st.session_state["quiz_data"]):
                st.markdown(f"- Question {i+1}: {q['answer']}")

# === Flashcards ===
elif menu == "Flashcards":
    st.header("Flashcards")
    topic = st.selectbox("Topic", ["Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"])
    if st.button("Generate Flashcards"):
        prompt = (
            f"Generate 10 flashcards about {topic} for the South Carolina permit test. "
            "Each flashcard must be in the following format:\n"
            "Q: [question]\nA: [answer]\n"
            "Return ONLY the 10 flashcards, no numbers, no multiple choice, no explanations, no extra commentary."
        )
        with st.spinner("Creating flashcards..."):
            raw = query_gpt([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ])
            flashcards = parse_flashcards(raw)
            if not flashcards:
                st.warning("Could not parse flashcards. Try again.")
            else:
                for idx, card in enumerate(flashcards):
                    st.markdown(f"**Q{idx+1}:** {card['question']}\n\n**A:** {card['answer']}")
                # Download as PDF
                flashcard_text = "\n\n".join([f"Q: {c['question']}\nA: {c['answer']}" for c in flashcards])
                st.download_button("Download PDF", create_pdf(flashcard_text), file_name="flashcards.pdf")

# === Study Plan ===
elif menu == "Study Plan":
    st.header("3-Day Study Plan")
    if st.button("Create Plan"):
        prompt = "Create a 3-day SC permit test study plan focused on road signs, alcohol laws, and right-of-way."
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
        if total_attempted:
            accuracy = (total_correct / total_attempted) * 100
            st.metric("Total Accuracy", f"{accuracy:.1f}%")
    else:
        st.info("No progress saved yet.")
