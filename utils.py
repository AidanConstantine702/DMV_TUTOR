# utils.py
import re, datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from openai import OpenAI
from supabase import create_client, Client

# ----- init external clients -----
supabase: Client = create_client(
    st.secrets["supabase"]["url"],
    st.secrets["supabase"]["key"],
)
openai_client = OpenAI(api_key=st.secrets["openai_api_key"])

# ----- GPT helpers -----
def query_gpt(messages):
    resp = openai_client.chat.completions.create(model="gpt-4-turbo",
                                                 messages=messages)
    return resp.choices[0].message.content

QUIZ_RX  = re.compile(r"Question\\s+\\d+:\\s*(.*?)\\nA\\.\\s*(.*?)\\nB\\.\\s*(.*?)"
                      r"\\nC\\.\\s*(.*?)\\nD\\.\\s*(.*?)\\nAnswer:\\s*([A-D])",
                      re.DOTALL)
FLASH_RX = re.compile(r"Q:\\s*(.*?)\\nA:\\s*(.*?)(?=\\nQ:|\\Z)", re.DOTALL)

def parse_quiz(text):
    return [{"question": q.strip(),
             "options": {"A": a.strip(), "B": b.strip(), "C": c.strip(), "D": d.strip()},
             "answer": ans.strip()}
            for q, a, b, c, d, ans in QUIZ_RX.findall(text)]

def parse_flashcards(text):
    return [{"question": q.strip(), "answer": a.strip()} for q, a in FLASH_RX.findall(text)]

# ----- Supabase score store -----
def save_score(uid, topic, correct, total):
    supabase.table("quiz_scores").insert({
        "user_id": uid,
        "topic": topic,
        "correct": correct,
        "attempted": total,
        "date": str(datetime.date.today())
    }).execute()

# ----- PDF helper -----
def create_pdf(text):
    buf = BytesIO()
    pdf = canvas.Canvas(buf)
    y = 800
    for line in text.split("\\n"):
        if y < 40: pdf.showPage(); y = 800
        pdf.drawString(40, y, line); y -= 15
    pdf.save(); buf.seek(0)
    return buf

