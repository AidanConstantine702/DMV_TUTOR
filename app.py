import streamlit as st
from openai import OpenAI
import datetime
import re
from io import BytesIO
from reportlab.pdfgen import canvas
from supabase import create_client, Client
import stripe

# ==================== STRIPE CONFIG ====================
stripe.api_key = st.secrets["stripe"]["secret_key"]
PRICE_ID = st.secrets["stripe"]["price_id"]
SUCCESS_URL = st.secrets["stripe"]["success_url"]
CANCEL_URL = st.secrets["stripe"]["cancel_url"]


def create_checkout_session(user_email: str) -> str:
    """Return a Stripe Checkout URL for lifetime access purchase."""
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        customer_email=user_email,
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        mode="payment",
        success_url=f"{SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=CANCEL_URL,
    )
    return session.url


def verify_and_grant_access(session_id: str, user_id: str) -> bool:
    """Verify checkout completion and upsert `user_access` row."""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            supabase.table("user_access").upsert({"user_id": user_id}).execute()
            return True
    except Exception as e:
        st.error(f"Stripe verification failed: {e}")
    return False


def user_has_access(user_id: str) -> bool:
    res = (
        supabase.table("user_access")
        .select("user_id")
        .eq("user_id", user_id)
        .execute()
    )
    return bool(res.data)

# ==================== ENV / CLIENTS ====================
supabase: Client = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
openai_client = OpenAI(api_key=st.secrets["openai_api_key"])

# ==================== SYSTEM PROMPT ====================
SYSTEM_PROMPT = (
    "You are a certified South Carolina DMV Permit Test Tutor specializing in helping teenagers "
    "prepare for their written learner’s permit exam.\n\n"
    "Your job is to clearly explain driving laws, road signs, traffic rules, and safety principles "
    "using only the information found in:\n"
    "- The South Carolina Driver’s Manual (2024 edition)\n"
    "- The official SC DMV Practice Test\n\n"
    "Key instructions:\n"
    "- ONLY use facts found in the manual or practice test.\n"
    "- DO NOT make up laws, facts, or explanations.\n"
    "- Use language appropriate for 15–17‑year‑olds.\n"
    "- Quiz format: Question #, A.–D., Answer.\n"
    "- Flashcard format: Q:, A:.\n"
    "- Return exactly N questions or 10 flashcards with **no extra text**."
)

# ==================== GPT HELPERS ====================

def query_gpt(messages):
    resp = openai_client.chat.completions.create(model="gpt-4-turbo", messages=messages)
    return resp.choices[0].message.content


# ==================== PARSERS ====================
QUIZ_RX = re.compile(
    r"Question\s+\d+:\s*(.*?)\nA\.\s*(.*?)\nB\.\s*(.*?)\nC\.\s*(.*?)\nD\.\s*(.*?)\nAnswer:\s*([A-D])",
    re.DOTALL,
)
FLASH_RX = re.compile(r"Q:\s*(.*?)\nA:\s*(.*?)(?=\nQ:|\Z)", re.DOTALL)

def parse_quiz(text):
    return [
        {
            "question": q.strip(),
            "options": {"A": a.strip(), "B": b.strip(), "C": c.strip(), "D": d.strip()},
            "answer": ans.strip(),
        }
        for q, a, b, c, d, ans in QUIZ_RX.findall(text)
    ]

def parse_flashcards(text):
    return [{"question": q.strip(), "answer": a.strip()} for q, a in FLASH_RX.findall(text)]

# ==================== PDF EXPORT ====================

def create_pdf(text):
    buf = BytesIO()
    pdf = canvas.Canvas(buf)
    y = 800
    for line in text.split("\n"):
        if y < 40:
            pdf.showPage(); y = 800
        pdf.drawString(40, y, line); y -= 15
    pdf.save(); buf.seek(0); return buf

# ==================== SCORE STORAGE ====================

def save_score(uid, topic, correct, total):
    supabase.table("quiz_scores").insert(
        {"user_id": uid, "topic": topic, "correct": correct, "attempted": total, "date": str(datetime.date.today())}
    ).execute()

# ==================== AUTH COMPONENT ====================

def login_ui():
    st.subheader("Login / Sign Up")
    email = st.text_input("Email")
    pw = st.text_input("Password", type="password")
    if st.button("Log In"):
        try:
            user = supabase.auth.sign_in_with_password({"email": email, "password": pw})
            if user.user:
                st.session_state["user"] = user.user; st.rerun()
        except Exception:
            st.error("Login failed.")
    if st.button("Sign Up"):
        try:
            if supabase.auth.sign_up({"email": email, "password": pw}).user:
                st.success("Check your email to verify your account.")
        except Exception:
            st.error("Signup failed.")

# ==================== STREAMLIT UI ====================

st.set_page_config(page_title="SC DMV AI Tutor", layout="centered")
st.title("SC DMV Permit Test Tutor")

if "user" not in st.session_state:
    login_ui(); st.stop()

user = st.session_state["user"]

# ---- Stripe redirect handler ----
params = st.query_params
if "session_id" in params and params["session_id"]:
    if verify_and_grant_access(params["session_id"], user.id):
        st.success("Payment confirmed – access unlocked!")
    st.query_params.clear()

has_access = user_has_access(user.id)

# ---- Sidebar paywall ----
if not has_access:
    st.sidebar.warning("🚧 Practice Quiz & Flashcards are locked until purchase.")
    if st.sidebar.button("Buy Lifetime Access"):
        st.sidebar.info("Redirecting to Stripe …")
        st.experimental_redirect(create_checkout_session(user.email))

menu = st.sidebar.radio(
    "Navigation",
    [
        "Tutor Chat",
        *(["Practice Quiz", "Flashcards"] if has_access else []),
        "Study Plan",
        "Progress Tracker",
    ],
)

# ==================== PAGES ====================

## 1. Tutor Chat
if menu == "Tutor Chat":
    st.header("Chat with Your DMV Tutor")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{"role": "system", "content": SYSTEM_PROMPT}]

    for m in st.session_state.chat_history[1:]:
        st.chat_message(m["role"]).write(m["content"])

    q = st.chat_input("Ask about the permit test …")
    if q:
        st.session_state.chat_history.append({"role": "user", "content": q})
        with st.spinner("Thinking …"):
            a = query_gpt(st.session_state.chat_history)
        st.session_state.chat_history.append({"role": "assistant", "content": a})
        st.chat_message("assistant").write(a)
    if st.button("Clear Chat"):
        st.session_state.chat_history = [{"role": "system", "content": SYSTEM_PROMPT}]; st.rerun()

## 2. Practice Quiz
elif menu == "Practice Quiz":
    st.header("Practice Quiz")
    n = st.slider("Number of Questions", 5, 10, 5)
    topic = st.selectbox("Topic", ["General", "Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"])

    if st.button("Generate Quiz"):
        prompt = (
            f"Generate exactly {n} multiple‑choice questions on '{topic}'. Follow the strict format."
        )
        with st.spinner("Generating …"):
            raw = query_gpt([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}])
        st.session_state.quiz = parse_quiz(raw); st.session_state.answers = {}

    if "quiz" in st.session_state:
        all_answered = True
        for i, qd in enumerate(st.session_state.quiz):
            opts = ["Select …"] + [f"{k}. {v}" for k, v in qd["options"].items()]
            choice = st.radio(qd["question"], opts, key=f"q{i}")
            st.session_state.answers[i] = None if choice == "Select …" else choice[0]
            all_answered &= st.session_state.answers[i] is not None

        if st.button("Submit", disabled=not all_answered):
            correct = sum(
                1 for i, qd in enumerate(st.session_state.quiz) if st.session_state.answers[i] == qd["answer"]
            )
            save_score(user.id, topic, correct, len(st.session_state.quiz))
            st.success(f"Score: {correct}/{len(st.session_state.quiz)}")

## 3. Flashcards
elif menu == "Flashcards":
    st.header("Flashcards")
    topic = st.selectbox("Topic", ["General", "Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"])

    if st.button("Generate Flashcards"):
        prompt = f"Generate 10 flashcards on '{topic}'. Strict Q:/A: only."
        with st.spinner("Generating …"):
            raw = query_gpt([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}])
        st.session_state.cards = parse_flashcards(raw)
        for i in range(10):
            st.session_state[f"show{i}"] = False

    if "cards" in st.session_state:
        for i, c in enumerate(st.session_state.cards):
            st.markdown(f"**Q{i+1}: {c['question']}**")
            if not st.session_state[f"show{i}"]:
                if st.button("Reveal", key=f"reveal{i}"):
                    st.session_state[f"show{i}"] = True
            if st.session_state[f"show{i}"]:
                st.success(f"A{i+1}: {c['answer']}")
            st.write("---")
        pdf_txt = "\n\n".join([f"Q{i+1}: {c['question']}\nA{i+1}: {c['answer']}" for i, c in enumerate(st.session_state.cards)])
        st.download_button("Download PDF", create_pdf(pdf_txt), "flashcards.pdf")

## 4. Study Plan
elif menu == "Study Plan":
    st.header("3‑Day Study Plan")
    plan = """**Day 1 – Road Signs & Basics**\n- Review Road Signs flashcards\n- ...
