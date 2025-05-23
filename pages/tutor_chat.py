import streamlit as st
from utils import query_gpt

def render(system_prompt):
    st.header("Chat with Your DMV Tutor")
    if "chat" not in st.session_state:
        st.session_state.chat = [{"role": "system", "content": system_prompt}]

    for m in st.session_state.chat[1:]:
        st.chat_message(m["role"]).write(m["content"])

    q = st.chat_input("Ask anything…")
    if q:
        st.session_state.chat.append({"role": "user", "content": q})
        with st.spinner("Thinking…"):
            a = query_gpt(st.session_state.chat)
        st.session_state.chat.append({"role": "assistant", "content": a})
        st.chat_message("assistant").write(a)

    if st.button("Clear"):
        st.session_state.chat = [{"role": "system", "content": system_prompt}]
        st.experimental_rerun()

