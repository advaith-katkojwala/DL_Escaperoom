"""Thin wrapper around the Google Gemini API (free tier).

Both versions of the game use this module. If no API key (or no `google-genai`
package) is available, `make_llm()` returns (None, reason) and Version 2 falls
back to its deterministic offline mode, so the game still runs and can be tested.

Setup:
    pip install -r requirements.txt
    cp .env.example .env  and put your free key from https://aistudio.google.com/apikey in it
    (or: export GEMINI_API_KEY="...")
Optional:
    export GEMINI_MODEL="gemini-2.5-flash"   # change if Google renames/retires it
"""
from __future__ import annotations

import os

try:  # optional: load a local .env file (never commit it)
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class LLMError(RuntimeError):
    """Raised when the LLM call fails (network, quota, bad key, ...)."""


def get_api_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        return key
    try:  # Streamlit secrets (.streamlit/secrets.toml), if running under Streamlit
        import streamlit as st

        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None


class GeminiClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=api_key)
        self.model = model

    def generate(
        self,
        system: str,
        prompt: str,
        history: list[tuple[str, str]] | None = None,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> str:
        """history: list of (role, text) with role in {"user", "assistant"}."""
        t = self._types
        contents = []
        for role, text in history or []:
            contents.append(
                t.Content(role="model" if role == "assistant" else "user",
                          parts=[t.Part(text=text)])
            )
        contents.append(t.Content(role="user", parts=[t.Part(text=prompt)]))
        cfg = t.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        try:
            resp = self._client.models.generate_content(
                model=self.model, contents=contents, config=cfg
            )
            return (resp.text or "").strip()
        except Exception as exc:  # SDK raises several exception types
            raise LLMError(str(exc)) from exc


def make_llm():
    """Return (client_or_None, status_message)."""
    key = get_api_key()
    if not key:
        return None, "No GEMINI_API_KEY found - running in offline mode."
    try:
        return GeminiClient(key), f"Connected to Gemini ({DEFAULT_MODEL})."
    except ImportError:
        return None, "Package `google-genai` is not installed - running in offline mode."
    except Exception as exc:
        return None, f"Could not start Gemini client ({exc}) - running in offline mode."
