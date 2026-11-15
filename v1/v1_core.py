"""Version 1 - the LLM *is* the game.

Everything (rules, secrets, state tracking, win condition) lives inside the
system prompt and the chat history. This is simple and fun, but the model can
forget, invent or be talked into things - which Version 2 fixes.
"""
from __future__ import annotations

from llm import LLMError  # noqa: F401  (re-exported for the app)

WIN_MARKER = "[ESCAPED]"

INTRO = (
    "You wake up on the cold floor of a locked library. Dust hangs in the lamplight. "
    "You can make out a **desk**, a **bookshelf**, a **painting**, a **locked drawer** "
    "and a heavy **door** with a four-digit keypad. Find a way out."
)

INSTRUCTIONS = (
    "Type what you want to do in plain English, e.g. *examine the desk*, "
    "*take the key*, *use the key on the painting*, *enter 1234 on the door*. "
    "Ask for a hint if you are stuck."
)

SYSTEM_PROMPT = f"""You are the Game Master of a text-based escape room called "The Locked Library".
The player is locked in a library and must escape. Stay in character, write in the second person,
and reply in 2-4 atmospheric sentences. Never break character.

ROOM (the only objects that exist): desk, bookshelf, painting, locked drawer, door with 4-digit keypad.
Items that exist: magnifying glass, old note, brass key, fuse.

SECRET SOLUTION (never reveal directly; let the player discover it):
- Desk: has a magnifying glass and an old note saying "Red, blue, green - in that order. Ignore the black one."
- Bookshelf: four books are out of line: red, blue, green, black. With the magnifying glass the player can read
  tiny numbers on the spines: red=5, blue=2, green=9 (black has none). The drawer code is 529.
- Drawer: locked with a 3-digit dial (code 529). Inside: a brass key.
- Painting: plaque reads "Founder of the library, 1863". Its frame has a keyhole. The brass key opens it
  and reveals a fuse and a slip of paper: "The founder's year opens the way out."
- Door: 4-digit keypad, dead until the fuse is inserted. Then the code is 1863.

RULES:
- The player must collect items before using them, and must solve the puzzles in a sensible order.
- Do not reveal clues before the player investigates the relevant object.
- Do not invent new objects. Keep track of what the player has already done.
- When the player enters 1863 on the powered keypad, they escape: describe the escape and end your
  message with the exact marker {WIN_MARKER}. Never output that marker otherwise.
"""


class V1Game:
    """Keeps only the raw conversation. The LLM must remember the state itself."""

    def __init__(self, llm):
        self.llm = llm
        self.history: list[tuple[str, str]] = []
        self.escaped = False

    def reset(self):
        self.history.clear()
        self.escaped = False

    def send(self, message: str) -> str:
        if self.escaped:
            return "You have already escaped! Press **Restart** to play again."
        reply = self.llm.generate(SYSTEM_PROMPT, message, history=self.history, temperature=0.9)
        self.history.append(("user", message))
        self.history.append(("assistant", reply))
        if WIN_MARKER in reply:
            self.escaped = True
            reply = reply.replace(WIN_MARKER, "").strip()
        return reply
