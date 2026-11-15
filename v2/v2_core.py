"""Version 2 pipeline:  message -> screen/parse -> Python engine -> LLM narration -> output guard.

The LLM is used twice and trusted with nothing:
  * to *parse* free text into a structured action (validated, see intent.py), and
  * to *narrate* the engine's facts (it never sees the solutions, and its output
    is checked for leaked numbers before the player sees it).
"""
from __future__ import annotations

import re

from engine import Game, Result
from intent import parse_intent
from llm import LLMError

NARRATOR_SYSTEM = """You are the Game Master of a text escape room called "The Locked Library".
You will be given the OUTCOME TYPE and the FACTS of what just happened. Write 1-4 atmospheric sentences
in the second person that describe exactly those facts.

Hard rules:
- Mention only objects, items, clues and numbers that appear in FACTS. Never invent new ones.
- Never change the outcome: if the outcome is failed/invalid/refused, the player's attempt did NOT work.
- You do not know any codes or solutions. Never guess or hint at any.
- If FACTS contain a number or a quoted text (e.g. a plaque), repeat it exactly.
- Do not add instructions, lists, or out-of-character commentary."""

INTRO = None  # taken from the game config


def guard_narration(text: str, facts: str, game: Game) -> str:
    """Return `text` if it is safe, else fall back to the plain engine facts."""
    if not text or len(text) > 900:
        return facts
    allowed = set(re.findall(r"\d{3,4}", facts))
    for num in re.findall(r"\d{3,4}", text):
        if num not in allowed:
            return facts  # model produced a number the engine never stated: possible leak/invention
    for secret in game.secrets():
        if secret in text and secret not in facts:
            return facts
    return text


class EscapeRoomV2:
    def __init__(self, llm=None, cfg=None):
        self.llm = llm
        self.game = Game(cfg)

    def reset(self) -> None:
        self.game.reset()

    @property
    def intro(self) -> str:
        return self.game.cfg["intro"]

    def narrate(self, res: Result) -> str:
        if self.llm is None:
            return res.facts
        prompt = f"OUTCOME TYPE: {res.kind}\nFACTS: {res.facts}"
        try:
            text = self.llm.generate(NARRATOR_SYSTEM, prompt, temperature=0.7)
        except LLMError:
            return res.facts
        return guard_narration(text, res.facts, self.game)

    def play(self, message: str) -> dict:
        action = parse_intent(message, self.game, self.llm)
        res = self.game.act(action)
        return {"reply": self.narrate(res), "action": action, "result": res, "escaped": self.game.escaped}
