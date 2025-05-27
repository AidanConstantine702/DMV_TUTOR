import streamlit as st
from openai import OpenAI
from io import BytesIO
from reportlab.pdfgen import canvas
import datetime
import re
from supabase import create_client, Client
import stripe
import streamlit as st

# ── Stripe config (all secrets must exist in .streamlit/secrets.toml) ──
stripe.api_key  = st.secrets["stripe"]["secret_key"]
PRICE_ID        = st.secrets["stripe"]["price_id"]
SUCCESS_URL     = st.secrets["stripe"]["success_url"]
CANCEL_URL      = st.secrets["stripe"]["cancel_url"]
# ────────────────────────────────────────────────────────────────────────


def create_checkout_session(user_email: str) -> str:
    """Return a Stripe Checkout URL for Lifetime‑Access purchase."""
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
    """If payment succeeded, upsert row in user_access and return True."""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        # Debug info – see what's actually coming back
        st.write("DEBUG: Stripe session.status:", session.status)
        st.write("DEBUG: Stripe payment_status:", session.payment_status)
        # The key thing is to check for payment_status == "paid"
        if session.payment_status == "paid":
            supabase_srv.table("user_access").upsert({"user_id": user_id}).execute()
            return True
    except Exception as e:
        st.error(f"Stripe verification failed: {e}")
    return False


def user_has_access(user_id: str) -> bool:
    """Check if the user already purchased Lifetime Access."""
    res = supabase.table("user_access").select("user_id").eq("user_id", user_id).execute()
    return bool(res.data)

# === Load credentials ===
supabase_url = st.secrets["supabase"]["url"]
supabase_key = st.secrets["supabase"]["key"]
api_key = st.secrets["openai_api_key"]
# === Initialize Supabase and OpenAI ===
supabase: Client = create_client(supabase_url, supabase_key)
client = OpenAI(api_key=api_key, project="proj_36JJwFCLQG34Xyiqb0EWUJlN")
# === Initialize Supabase "admin" client for bypassing RLS (used ONLY for access unlock) ===
supabase_srv: Client = create_client(supabase_url, st.secrets["supabase"]["service_key"])


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
        "\n\n"
    "Proactive guidance:\n"
    "- After answering the user's question, briefly suggest ONE effective test‑taking or study strategy (e.g. spaced repetition, practice under timed conditions).\n"
    "- Then, recommend a relevant feature of this website (Practice Quiz, Flashcards, Study Plan, or Progress Tracker) and explain in one sentence how using it will help them master the permit test faster.\n"
    "- Keep the tip + recommendation to a total of **two sentences** so it doesn't feel spammy."
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
# ---- Stripe redirect handler -------------------------------------------
params = st.query_params
sid = params.get("session_id")        # full ID, e.g. cs_live_a1B2C3...
if sid:                               # only run if present
    if verify_and_grant_access(sid, user.id):
        st.success("Payment confirmed – access unlocked! 🎉")
    st.query_params = {}              # clear ?session_id

has_access = user_has_access(user.id)   # do they own Lifetime Access?
checkout_url = None                    # will hold Stripe URL if we create one
# -------------------------------------------------------------------------

# ---- Pay‑wall button + navigation ------------------------------------
if not has_access:
    # ----- Step 1 -----
    st.sidebar.markdown("## 🪧 Step 1 — Select Lifetime Access plan")

    if st.sidebar.button("Buy Lifetime Access", key="btn_buy_sidebar"):
        checkout_url = create_checkout_session(user.email)

        # ----- Step 2 appears once plan is chosen -----
        st.sidebar.markdown("""
        ### ✅ Step 1 — Selected  
        ### 🏁 Step 2 — Complete payment
        """)
        st.sidebar.markdown(
            f"""
            <a href="{checkout_url}" target="_blank" rel="noopener noreferrer">
                <button style="padding:0.6em 1.2em; font-size:1rem;">
                    Open Secure Stripe Checkout
                </button>
            </a>
            """,
            unsafe_allow_html=True,
        )
        st.sidebar.info("Checkout opens in a new tab. "
                        "Return here after payment is complete.")
    else:
        st.sidebar.markdown("*Click the button above to start.*")

# build nav_items … (unchanged)

# ----- Navigation -------------------------------------------------------
if has_access:
    nav_items = [
        "Tutor Chat",
        "Practice Quiz",
        "Flashcards",
        "Study Plan",
        "Progress Tracker",
    ]
else:
    nav_items = ["What You Get"]          # CTA page only before purchase

menu = st.sidebar.radio("Navigation", nav_items)
# ------------------------------------------------------------------------

# === What You Get (CTA) ================================================
if menu == "What You Get":
    st.header("Unlock the Full DMV Tutor Experience 🚀")

    st.markdown("""
### Lifetime Access – $30 one‑time

| Feature | Why it rocks |
|---------|--------------|
| **AI Tutor Chat** | Ask *any* permit question and get teen‑friendly answers 24/7. |
| **Practice Quizzes** | Auto‑graded SC‑specific quizzes that track what you miss. |
| **Smart Flashcards** | Tap to reveal, repeat the tricky ones – perfect for quick study bursts. |
| **3‑Day “Permit‑Ready” Plan** | A bite‑sized schedule that tells you exactly what to do each day. |
| **Progress Tracker** | See your accuracy %, spot weak topics, and watch your score climb. |

---

### Ready to roll?
Click **“Buy Lifetime Access”** in the sidebar to open secure Stripe Checkout.  
Come back with everything unlocked in under a minute!
""")

    st.stop()   # prevent other pages from rendering until purchase
# =======================================================================

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
    if not has_access:
        st.error("Please purchase Lifetime Access to use Practice Quizzes.")
        st.stop()

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
            correct = sum(
                1 for idx, q in enumerate(quiz_data)
                if st.session_state["quiz_answers"].get(idx) == q["answer"]
            )
            save_score(user.id, topic, correct, len(quiz_data))
            st.success(f"You got {correct} out of {len(quiz_data)} correct!")
            st.markdown("**Correct Answers:**")
            for i, q in enumerate(quiz_data):
                st.markdown(f"- Question {i+1}: {q['answer']}")

# === Flashcards ===
elif menu == "Flashcards":
    if not has_access:
        st.error("Please purchase Lifetime Access to use Flashcards.")
        st.stop()

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
            st.session_state["flashcard_revealed"] = [False] * len(flashcards_data)

    if "flashcards_data" in st.session_state:
        st.subheader(f"{topic} Flashcards")

        for idx, card in enumerate(st.session_state["flashcards_data"]):
            st.markdown(f"**Q{idx+1}: {card['question']}**")
            if not st.session_state["flashcard_revealed"][idx]:
                if st.button("Reveal Answer", key=f"reveal_btn_{idx}"):
                    st.session_state["flashcard_revealed"][idx] = True

            if st.session_state["flashcard_revealed"][idx]:
                st.success(f"**A{idx+1}: {card['answer']}**")
            st.write("---")

        # Download option
        flashcard_text = "\n\n".join(
            [f"Q{idx+1}: {c['question']}\nA{idx+1}: {c['answer']}" 
             for idx, c in enumerate(st.session_state["flashcards_data"])]
        )
        st.download_button(
            "Download PDF", create_pdf(flashcard_text), file_name="flashcards.pdf"
        )

# === Study Plan ===
elif menu == "Study Plan":
    st.header("3-Day Study Plan")
    plan = """
## 🚦 3‑Day “Permit‑Ready” Study Plan  
_All you need is right here on your DMV Tutor site_

---

### DAY 1 – MASTER THE BASICS

• **10 min – Game Plan Kick‑Off**  
  ○ Skim this schedule and set a mini‑goal for today.  
  ○ Tool: 3‑Day Plan page  

• **20 min – Chat with the AI Tutor**  
  ○ Ask: “What mistakes do first‑time drivers make most?”  
  ○ Get quick, teen‑friendly explanations.  

• **25 min – General Quiz Attack**  
  ○ Go to _Practice Quiz → General_.  
  ○ Discover what you already know (or don’t).  

• **15 min – Traffic Signals Flashcards**  
  ○ Flashcards → Traffic Signals to lock in light colors & arrow shapes.  

• **5 min – Progress Check‑In**  
  ○ Enter today’s quiz score in _Progress Tracker_.  
  ○ Jot one topic that felt tough—AI Tutor will focus on it tomorrow.  

---

### DAY 2 – DIAL IN THE DETAILS

• **10 min – Road Signs Warm‑Up**  
  ○ Flashcards → Road Signs (speedy picture‑memory boost).  

• **20 min – Rapid‑Fire Q&A**  
  ○ AI Tutor: “Give me 5 tips to remember right‑of‑way rules.”  

• **25 min – Right‑of‑Way Quiz**  
  ○ Practice Quiz → Right of Way.  
  ○ Put those fresh tips to the test.  

• **15 min – Speed Limits Flashcards**  
  ○ Flashcards → Speed Limits to nail the numbers.  

• **10 min – Progress Tracker Update**  
  ○ Mark new scores, celebrate streaks, spot weak points.  

• **Evening Mini‑Challenge (Optional 10 min)**  
  ○ Re‑take yesterday’s General Quiz and beat your score.  

---

### DAY 3 – GAME‑DAY SIMULATION

• **15 min – Flashcard Fix‑Up**  
  ○ Hit any topic where you’re under 80 %. Lightning review.  

• **35 min – Full‑Length Mock Quiz**  
  ○ Practice Quiz → General. Do it twice back‑to‑back for real‑test stamina.  

• **15 min – Last‑Minute AI Tutor Grill‑Session**  
  ○ Ask: “Quiz me on 10 tricky alcohol‑law questions.”  
  ○ Get instant correction & tips.  

• **5 min – Final Progress High‑Five**  
  ○ Open _Progress Tracker_, admire the glow‑up, and breathe. You’re ready!  

---

### PRO TIPS

• **Chunk it → Check it:** tick off each block in Progress Tracker for a mini dopamine hit.  
• **Speak answers out loud:** saying flashcard answers cements memory.  
• **Move & hydrate:** quick stretch or sip of water between blocks keeps your brain sharp.  
• **Use “Explain like I’m 14”:** anytime you’re lost, type this to the AI Tutor for a simpler breakdown.  

Stick to the plan, trust the tools, and you’ll cruise through the SC permit test. **You got this!** 🚗💨
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
