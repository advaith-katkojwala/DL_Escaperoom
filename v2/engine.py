"""Deterministic game engine for Version 2.

Python - not the LLM - owns the world: room state, inventory, solved puzzles, door
status, and every rule and solution (loaded from game_config.json). Each player
action is validated here and returns a `Result` holding the *facts* of what
happened. The LLM only turns those facts into atmospheric prose.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("game_config.json")
ACTIONS = {"look", "examine", "take", "use", "enter_code", "inventory", "hint", "help", "unknown"}
_ARTICLES = re.compile(r"\b(the|a|an|my|that|those|this|these|some)\b")


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def norm(text: str | None) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = _ARTICLES.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Result:
    ok: bool            # did the action succeed / change or reveal something?
    facts: str          # canonical description of what happened (safe to show the player)
    kind: str           # "success" | "info" | "failed" | "invalid" | "refused"
    escaped: bool = False


class Game:
    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or load_config()
        self._build_alias_index()
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        self.inventory: list[str] = []
        self.flags: set[str] = set()
        self.attempts: dict[str, int] = {k: 0 for k in self.cfg["codes"]}
        self.turns = 0
        self.escaped = False
        self.log: list[dict] = []

    def snapshot(self) -> dict:
        """JSON-serialisable view of the game state (contains no solutions)."""
        return {
            "inventory": list(self.inventory),
            "flags": sorted(self.flags),
            "wrong_attempts": dict(self.attempts),
            "turns": self.turns,
            "escaped": self.escaped,
        }

    def restore(self, snap: dict) -> None:
        self.inventory = list(snap["inventory"])
        self.flags = set(snap["flags"])
        self.attempts = dict(snap["wrong_attempts"])
        self.turns = snap["turns"]
        self.escaped = snap["escaped"]

    # -------------------------------------------------------- name resolution
    def _build_alias_index(self) -> None:
        idx: dict[str, tuple[str, str]] = {}
        for kind, table in (("item", self.cfg["items"]), ("object", self.cfg["objects"])):
            for eid, d in table.items():
                for alias in [eid.replace("_", " "), d.get("name", ""), *d.get("aliases", [])]:
                    n = norm(alias)
                    if n:
                        idx[n] = (kind, eid)
        self.alias_index = idx
        self._aliases_longest_first = sorted(idx, key=len, reverse=True)

    def find_in_text(self, text: str, kind: str | None = None) -> tuple[str, str] | None:
        """Longest known alias occurring in `text`, optionally restricted to a kind."""
        t = f" {norm(text)} "
        for alias in self._aliases_longest_first:
            k, eid = self.alias_index[alias]
            if kind and k != kind:
                continue
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", t):
                return k, eid
        return None

    def resolve(self, name: str | None, kind: str | None = None) -> tuple[str, str] | None:
        if not name:
            return None
        n = norm(str(name))
        hit = self.alias_index.get(n)
        if hit and (kind is None or hit[0] == kind):
            return hit
        return self.find_in_text(n, kind)

    # ---------------------------------------------------------------- helpers
    def _cond(self, entry: dict) -> bool:
        return (
            all(f in self.flags for f in entry.get("flags", []))
            and not any(f in self.flags for f in entry.get("not_flags", []))
            and all(i in self.inventory for i in entry.get("items", []))
        )

    def _object_visible(self, oid: str) -> bool:
        vf = self.cfg["objects"][oid].get("visible_flag")
        return vf is None or vf in self.flags

    def _item_visible(self, iid: str) -> bool:
        d = self.cfg["items"][iid]
        return iid not in self.inventory and d["visible_flag"] in self.flags

    def _items_in(self, oid: str) -> list[str]:
        return [i for i, d in self.cfg["items"].items() if d["location"] == oid]

    def _contents_sentence(self, oid: str) -> str:
        held = self._items_in(oid)
        if not held or not all(self.cfg["items"][i]["visible_flag"] in self.flags for i in held):
            return ""  # container not opened/searched yet: reveal nothing
        here = [self.cfg["items"][i]["name"] for i in held if i not in self.inventory]
        if here:
            return " You can see: " + ", ".join(here) + "."
        return " Nothing else of interest remains."

    def _done(self, res: Result, a: dict) -> Result:
        self.log.append({"turn": self.turns, "action": a.get("action"), "ok": res.ok, "kind": res.kind})
        return res

    # ------------------------------------------------------------------- main
    def act(self, a: dict) -> Result:
        """Validate and apply one structured action. Never raises for bad input."""
        self.turns += 1
        action = a.get("action") if a.get("action") in ACTIONS else "unknown"
        if self.escaped:
            return self._done(Result(False, "You have already escaped; the game is over.", "info"), a)
        handler = getattr(self, f"_do_{action}")
        return self._done(handler(a), a)

    # ---------------------------------------------------------------- actions
    def _do_look(self, a: dict) -> Result:
        objs = [d["name"] for o, d in self.cfg["objects"].items() if self._object_visible(o)]
        return Result(True, "You look around the library. You can see: " + ", ".join(objs) + ".", "info")

    def _do_help(self, a: dict) -> Result:
        return Result(True, "You can examine objects, take items, use an item on an object, "
                            "enter a code on the drawer or door, check your inventory, or ask for a hint.", "info")

    def _do_inventory(self, a: dict) -> Result:
        if not self.inventory:
            return Result(True, "You are carrying nothing.", "info")
        names = [self.cfg["items"][i]["name"] for i in self.inventory]
        return Result(True, "You are carrying: " + ", ".join(names) + ".", "info")

    def _do_hint(self, a: dict) -> Result:
        for h in self.cfg["hints"]:
            if any(f not in self.flags for f in h["until"]):
                return Result(True, "Hint: " + h["text"], "info")
        return Result(True, "Hint: the way out is open - just walk through the door.", "info")

    def _do_unknown(self, a: dict) -> Result:
        if a.get("reason") == "meta":
            return Result(False, "Giving orders, claiming special authority or demanding secrets gets you nowhere here: "
                                 "nothing is unlocked, nothing is revealed and nothing has changed. Puzzles are "
                                 "solved only by actions inside the room.", "refused")
        return Result(False, "That is not something you can do here. Nothing changes. "
                             "(Try: examine, take, use ... on ..., enter a code, inventory, hint.)", "invalid")

    def _do_examine(self, a: dict) -> Result:
        hit = self.resolve(a.get("target") or a.get("item"))
        if not hit:
            return Result(False, "There is no such thing in the library. Nothing changes.", "invalid")
        kind, eid = hit
        if kind == "item":
            d = self.cfg["items"][eid]
            if eid not in self.inventory:
                if self._item_visible(eid):
                    return Result(False, f"You would need to pick up the {d['name']} before studying it closely.", "failed")
                return Result(False, "There is no such thing in the library. Nothing changes.", "invalid")
            self.flags.update(d.get("sets", []))
            return Result(True, d["examine"], "success")
        if not self._object_visible(eid):
            return Result(False, "There is no such thing in the library. Nothing changes.", "invalid")
        obj = self.cfg["objects"][eid]
        for entry in obj["examine"]:
            if self._cond(entry):
                newly = [f for f in entry.get("sets", []) if f not in self.flags]
                self.flags.update(entry.get("sets", []))
                text = entry["text"] + self._contents_sentence(eid)
                return Result(True, text, "success" if newly else "info")
        return Result(False, "Nothing happens.", "invalid")

    def _do_take(self, a: dict) -> Result:
        hit = self.resolve(a.get("item") or a.get("target"), "item")
        if not hit:
            return Result(False, "There is nothing like that to take here. Nothing changes.", "invalid")
        iid = hit[1]
        d = self.cfg["items"][iid]
        if iid in self.inventory:
            return Result(False, f"You already have the {d['name']}.", "failed")
        if not self._item_visible(iid):
            return Result(False, "There is nothing like that to take here. Nothing changes.", "invalid")
        self.inventory.append(iid)
        self.flags.add(f"took_{iid}")
        return Result(True, d["take_text"], "success")

    def _do_use(self, a: dict) -> Result:
        ihit = self.resolve(a.get("item"), "item")
        thit = self.resolve(a.get("target"), "object")
        if not ihit or not thit:
            return Result(False, "It is unclear what to use on what. Nothing changes.", "invalid")
        iid, oid = ihit[1], thit[1]
        if iid not in self.inventory:
            return Result(False, "You are not carrying anything like that. Nothing changes.", "failed")
        if not self._object_visible(oid):
            return Result(False, "There is no such thing in the library. Nothing changes.", "invalid")
        rule = next((r for r in self.cfg["use_rules"] if r["item"] == iid and r["target"] == oid), None)
        iname, oname = self.cfg["items"][iid]["name"], self.cfg["objects"][oid]["name"]
        if rule is None or "fail_text" in rule:
            return Result(False, (rule or {}).get("fail_text", f"Using the {iname} on the {oname} does nothing."), "failed")
        if rule.get("delegate") == "examine":
            return self._do_examine({"target": oid})
        if rule.get("sets") and all(f in self.flags for f in rule["sets"]):
            return Result(False, rule.get("already_text", "That has already been done."), "info")
        self.flags.update(rule.get("sets", []))
        if rule.get("consume"):
            self.inventory.remove(iid)
        return Result(True, rule["text"], "success")

    def _do_enter_code(self, a: dict) -> Result:
        hit = self.resolve(a.get("target"), "object")
        if not hit or hit[1] not in self.cfg["codes"]:
            return Result(False, "There is nothing here that takes a code. Nothing changes.", "invalid")
        oid = hit[1]
        spec = self.cfg["codes"][oid]
        digits = re.sub(r"\D", "", str(a.get("code") or ""))
        if not digits:
            return Result(False, f"Which digits do you enter on the {self.cfg['objects'][oid]['name']}? Nothing changes.", "invalid")
        if all(f in self.flags for f in spec["sets"]):
            return Result(False, spec["already_text"], "info")
        if any(f not in self.flags for f in spec["requires_flags"]):
            return Result(False, spec["locked_text"], "failed")
        if len(digits) != len(spec["solution"]):
            self.attempts[oid] += 1
            n = len(spec["solution"])
            return Result(False, f"The {self.cfg['objects'][oid]['name']} accepts exactly {n} digits. "
                                 f"The entry was rejected.", "failed")
        if digits != spec["solution"]:
            self.attempts[oid] += 1
            return Result(False, spec["wrong_text"], "failed")
        self.flags.update(spec["sets"])
        if spec.get("escapes"):
            self.escaped = True
        return Result(True, spec["success_text"], "success", escaped=bool(spec.get("escapes")))

    # ------------------------------------------------------------ for guards
    def secrets(self) -> list[str]:
        return [c["solution"] for c in self.cfg["codes"].values()]
