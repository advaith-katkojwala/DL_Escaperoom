"""Version 2 - Streamlit UI.   Run:  streamlit run v2/app_v2.py

Works with or without a Gemini key: without one it runs in offline mode (rule-based
parsing, plain engine text), which is handy for testing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root (for llm.py)

import json

import streamlit as st

from llm import make_llm
from v2_core import EscapeRoomV2

st.set_page_config(page_title="AI Escape Room v2", page_icon="🗝️")
st.title("🗝️ The Locked Library - Version 2")
st.caption("Reliable edition: Python owns the rules and the game state; the AI only narrates.")

if "llm_ready" not in st.session_state:
    st.session_state.llm, st.session_state.status = make_llm()
    st.session_state.llm_ready = True


def new_game():
    st.session_state.room = EscapeRoomV2(st.session_state.llm)
    st.session_state.chat = [{"role": "assistant", "content": st.session_state.room.intro}]


if "room" not in st.session_state:
    new_game()

room: EscapeRoomV2 = st.session_state.room
game = room.game

with st.sidebar:
    st.header("How to play")
    st.markdown(
        "Type what you want to do in plain English: *examine the desk*, *take the glass*, "
        "*use the key on the painting*, *enter 123 on the drawer*. Ask for a **hint** if stuck."
    )
    st.caption(st.session_state.status)
    if st.button("🔄 Restart game"):
        new_game()
        st.rerun()
    st.subheader("🎒 Inventory")
    st.write(", ".join(game.cfg["items"][i]["name"] for i in game.inventory) or "_empty_")
    st.subheader("🧩 Progress")
    milestones = [("Drawer opened", "drawer_open"), ("Painting opened", "painting_open"),
                  ("Keypad powered", "door_powered"), ("Door opened", "door_open")]
    for label, flag in milestones:
        st.write(("✅ " if flag in game.flags else "⬜ ") + label)
    if st.toggle("Developer view: game state"):
        st.code(json.dumps(game.snapshot(), indent=2), language="json")

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if game.escaped:
    st.success("🎉 You escaped the library! Press Restart to play again.")
elif prompt := st.chat_input("What do you do?"):
    st.session_state.chat.append({"role": "user", "content": prompt})
    out = room.play(prompt)
    st.session_state.chat.append({"role": "assistant", "content": out["reply"]})
    st.rerun()
