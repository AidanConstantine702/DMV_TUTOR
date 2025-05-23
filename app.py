import streamlit as st
from openai import OpenAI
import os
from reportlab.pdfgen import canvas
from io import BytesIO
import datetime
import re
from supabase import create_client, Client
import stripe
stripe.api_key = st.secrets["stripe"]["secret_key"]
PRICE_ID       = st.secrets["stripe"]["price_id"]
SUCCESS_URL    = st.secrets["stripe"]["success_url"]
CANCEL_URL     = st.secrets["stripe"]["cancel_url"]

def create_checkout_session(user_email):
    """Create a Stripe Checkout session and return its URL."""
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        customer_email=user_email,
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        mode="payment",
        success_url=f"{SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=CANCEL_URL,
    )
    return session.url

def verify_and_grant_access(session_id, user_id):
    """
    Called once after redirect from Stripe.
    If payment is complete, write a row to user_access.
    """
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            supabase.table("user_access").upsert(
                {"user_id": user_id}  # purchased_at defaults to now()
            ).execute()
            return True
    except Exception as e:
        st.error(f"Stripe verification failed: {e}")
    return False

def user_has_access(user_id):
    """True/False for whether this user bought the product."""
    res = supabase.table("user_access").select("user_id").eq("user_id", user_id).execute()
    return bool(res.data)

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
    st.info("For each question, select your answer. No answer is selected by default. You must answer every question to submit the quiz.")
    num = st.slider("Number of Questions", 5, 10, 5)
    topic = st.selectbox(
        "Quiz Topic",
        ["General", "Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"]
    )
    if st.button("Generate Quiz"):
        prompt = (
            f"Generate exactly {num} multiple-choice questions for the topic '{topic}' from the South Carolina DMV permit test. "
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
        quiz_data = st.session_state["quiz_data"]
        all_answered = True
        for idx, q in enumerate(quiz_data):
            label = f"{idx + 1}. {q['question']}"
            options = ["Select an answer..."] + [f"{key}. {val}" for key, val in q["options"].items()]
            selected = st.radio(label, options, key=f"q_{idx}", index=0)
            if selected != "Select an answer...":
                st.session_state["quiz_answers"][idx] = selected[0]
            else:
                st.session_state["quiz_answers"][idx] = None
                all_answered = False

        if st.button("Submit Quiz", disabled=not all_answered):
            st.session_state["quiz_submitted"] = True
            correct = 0
            for idx, q in enumerate(quiz_data):
                if st.session_state["quiz_answers"].get(idx) == q["answer"]:
                    correct += 1
            save_score(user.id, topic, correct, len(quiz_data))
            st.success(f"You got {correct} out of {len(quiz_data)} correct!")
            st.markdown("**Correct Answers:**")
            for i, q in enumerate(quiz_data):
                st.markdown(f"- Question {i+1}: {q['answer']}")

# === Flashcards ===
elif menu == "Flashcards":
    st.header("Flashcards")
    topic = st.selectbox(
        "Flashcard Topic",
        ["General", "Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"]
    )
    if st.button("Generate Flashcards"):
        prompt = (
            f"Generate 10 flashcards for the topic '{topic}' using a Q&A format only from the SC permit test. "
            "Each flashcard should have a clear question and a short, clear answer. "
            "Use exactly this format for each flashcard: Q: [question]\nA: [answer]\n"
            "Return ONLY flashcards, no extra text, no multiple choice, and no explanations."
        )
        with st.spinner("Creating flashcards..."):
            raw_flashcards = query_gpt([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ])
            flashcards_data = parse_flashcards(raw_flashcards)
            st.session_state["flashcards_data"] = flashcards_data
            # Use unique session state keys for each flashcard reveal state
            for idx in range(len(flashcards_data)):
                st.session_state[f"flashcard_revealed_{idx}"] = False

    if "flashcards_data" in st.session_state:
        st.subheader(f"{topic} Flashcards")
        for idx, card in enumerate(st.session_state["flashcards_data"]):
            st.markdown(f"**Q{idx+1}: {card['question']}**")
            reveal_key = f"flashcard_revealed_{idx}"
            # If not revealed, show the button. If revealed, show the answer.
            if not st.session_state[reveal_key]:
                if st.button("Reveal Answer", key=f"reveal_btn_{idx}"):
                    st.session_state[reveal_key] = True
            if st.session_state[reveal_key]:
                st.success(f"**A{idx+1}: {card['answer']}**")
            st.write("---")
        # Download option
        flashcard_text = "\n\n".join([f"Q{idx+1}: {c['question']}\nA{idx+1}: {c['answer']}" for idx, c in enumerate(st.session_state["flashcards_data"])])
        st.download_button("Download PDF", create_pdf(flashcard_text), file_name="flashcards.pdf")

# === Study Plan ===
elif menu == "Study Plan":
    st.header("3-Day Study Plan")
    plan = """
**3-Day SC DMV Permit Test Study Plan**

**Day 1: Road Signs & Basic Rules**
- Go to the **Flashcards** page and select "Road Signs" to review all major traffic signs and their meanings.
- Use the **Practice Quiz** page and choose the "Road Signs" topic to test your knowledge (5–10 questions).
- Read the Road Signs and Pavement Markings sections in the SC Driver’s Manual (2024).

**Day 2: Right-of-Way & Traffic Laws**
- On the **Flashcards** page, select "Right of Way" and "Speed Limits" for quick review.
- Take a **Practice Quiz** on "Right of Way" (and optionally "Speed Limits").
- Review chapters on intersections, turns, and right-of-way rules in the manual.

**Day 3: Alcohol Laws, Safety, and Final Review**
- Use the **Flashcards** page to study "Alcohol Laws" and "Traffic Signals."
- Take a **General Practice Quiz** (select "General" as the topic for a mix of questions).
- Read about DUI, penalties, and safety laws in the manual.
- Go to the **Progress Tracker** to review your past quiz scores and focus on weak areas.

**Extra Tips:**
- Aim to answer all questions honestly—use quizzes and flashcards to target areas you get wrong.
- Repeat practice quizzes as needed, especially for any topic you feel less confident in.
- Don’t forget to rest and review any areas you missed before your test day!

Good luck—your consistent practice and use of these study tools will help you pass the SC permit test!
"""
    st.markdown(plan)
    st.download_button("Download PDF", create_pdf(plan), file_name="study_plan.pdf")

# === Progress Tracker ===
elif menu == "Progress Tracker":
    st.header("Your Progress")
    user_id = user.id
    response = supabase.table("quiz_scores").select("*").eq("user_id", user_id).execute()
    progress = response.data if response else []

    if progress:
        # Group attempts by date for daily accuracy
        from collections import defaultdict

        date_stats = defaultdict(lambda: {"correct": 0, "attempted": 0, "topics": []})
        for entry in progress:
            d = entry["date"]
            date_stats[d]["correct"] += entry["correct"]
            date_stats[d]["attempted"] += entry["attempted"]
            date_stats[d]["topics"].append(f'{entry["topic"]} — {entry["correct"]}/{entry["attempted"]} correct')

        # Display each day's stats and accuracy
        for d in sorted(date_stats.keys(), reverse=True):
            topics_str = "<br>".join(date_stats[d]["topics"])
            accuracy = (
                (date_stats[d]["correct"] / date_stats[d]["attempted"]) * 100
                if date_stats[d]["attempted"] else 0
            )
            st.markdown(
                f"**{d}**<br>{topics_str}<br>"
                f"<span style='color: #666;'>Daily Accuracy: <b>{accuracy:.1f}%</b></span><br><br>",
                unsafe_allow_html=True,
            )

        # Compute total accuracy
        total_correct = sum(x["correct"] for x in progress)
        total_attempted = sum(x["attempted"] for x in progress)
        if total_attempted:
            accuracy = (total_correct / total_attempted) * 100
            st.metric("Total Accuracy", f"{accuracy:.1f}%")
    else:
        st.info("No progress saved yet.")
