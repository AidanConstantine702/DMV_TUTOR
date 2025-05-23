import streamlit as st
from utils import query_gpt, parse_flashcards, create_pdf

def render(system_prompt):
    st.header("Flashcards")
    topic = st.selectbox("Topic", ["General","Road Signs","Right of Way",
                                   "Alcohol Laws","Speed Limits","Traffic Signals"])
    if st.button("Generate"):
        prompt = f"Generate 10 flashcards for '{topic}'. Q:/A: only."
        with st.spinner("Generating…"):
            raw = query_gpt([{"role":"system","content":system_prompt},
                             {"role":"user","content":prompt}])
        st.session_state.cards = parse_flashcards(raw)
        st.session_state.reveal = [False]*10

    if "cards" in st.session_state:
        for i,c in enumerate(st.session_state.cards):
            st.markdown(f"**Q{i+1}: {c['question']}**")
            if not st.session_state.reveal[i]:
                if st.button("Reveal", key=f"reveal{i}"):
                    st.session_state.reveal[i]=True
            else:
                st.success(f"A{i+1}: {c['answer']}")
            st.write('---')
        txt = "\\n\\n".join([f\"Q{i+1}: {c['question']}\\nA{i+1}: {c['answer']}\" for i,c in enumerate(st.session_state.cards)])
        st.download_button("PDF", create_pdf(txt), "flashcards.pdf")

