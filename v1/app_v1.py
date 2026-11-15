"""Version 1 - Streamlit UI.   Run:  streamlit run v1/app_v1.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root (for llm.py)

import streamlit as st

from llm import LLMError, make_llm
from v1_core import INSTRUCTIONS, INTRO, V1Game

st.set_page_config(page_title="AI Escape Room v1", page_icon="🗝️")
st.title("🗝️ The Locked Library - Version 1")

if "llm" not in st.session_state:
    st.session_state.llm, st.session_state.status = make_llm()

if st.session_state.llm is None:
    st.error(st.session_state.status + " Version 1 needs a Gemini API key "
             "(free at https://aistudio.google.com/apikey). Set GEMINI_API_KEY and reload.")
    st.stop()


def new_game():
    st.session_state.game = V1Game(st.session_state.llm)
    st.session_state.chat = [{"role": "assistant", "content": INTRO}]


if "game" not in st.session_state:
    new_game()

with st.sidebar:
    st.header("How to play")
    st.markdown(INSTRUCTIONS)
    st.caption(st.session_state.status)
    if st.button("🔄 Restart game"):
        new_game()
        st.rerun()

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if st.session_state.game.escaped:
    st.success("🎉 You escaped the library! Press Restart to play again.")
elif prompt := st.chat_input("What do you do?"):
    st.session_state.chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            reply = st.session_state.game.send(prompt)
        except LLMError as exc:
            reply = f"⚠️ The Game Master is unavailable right now ({exc})."
        st.markdown(reply)
    st.session_state.chat.append({"role": "assistant", "content": reply})
    if st.session_state.game.escaped:
        st.rerun()
