import streamlit as st
from utils import query_gpt, parse_quiz, save_score

def render(system_prompt, user_id):
    st.header("Practice Quiz")
    n = st.slider("Questions", 5, 10, 5)
    topic = st.selectbox("Topic",
             ["General","Road Signs","Right of Way","Alcohol Laws","Speed Limits","Traffic Signals"])

    if st.button("Generate"):
        prompt = (f"Generate exactly {n} multiple-choice questions for '{topic}'. "
                  "Strict format (Question #: ... Answer: X).")
        with st.spinner("Generating…"):
            raw = query_gpt([{"role":"system","content":system_prompt},
                             {"role":"user","content":prompt}])
        st.session_state.quiz = parse_quiz(raw)
        st.session_state.answers = {}

    if "quiz" in st.session_state:
        for i,q in enumerate(st.session_state.quiz):
            opts = ["Select…"]+[f"{k}. {v}" for k,v in q["options"].items()]
            choice = st.radio(q["question"], opts, key=f"q{i}", index=0)
            st.session_state.answers[i] = None if choice=="Select…" else choice[0]

        all_done = all(a is not None for a in st.session_state.answers.values())
        if st.button("Submit", disabled=not all_done):
            corr = sum(1 for i,q in enumerate(st.session_state.quiz)
                         if st.session_state.answers[i]==q["answer"])
            save_score(user_id, topic, corr, len(st.session_state.quiz))
            st.success(f"{corr}/{len(st.session_state.quiz)} correct")
            st.markdown("**Answers**")
            for i,q in enumerate(st.session_state.quiz):
                st.markdown(f"- Q{i+1}: {q['answer']}")

