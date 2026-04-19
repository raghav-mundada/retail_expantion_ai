"""
Thin OpenAI wrapper used by all agents.
Uses gpt-4o-mini — cheap, fast, plenty smart for structured argumentation.
"""

import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client: OpenAI | None = None


def get_llm() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def chat(
    system: str,
    user: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    json_mode: bool = False,
) -> str:
    """
    One-shot LLM call. Returns the raw string content.
    Set json_mode=True if you want guaranteed valid JSON back.
    """
    client = get_llm()

    kwargs: dict = {
        "model"      : model,
        "temperature": temperature,
        "messages"   : [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def chat_json(system: str, user: str, model: str = "gpt-4o-mini") -> dict:
    """LLM call that always returns parsed JSON."""
    raw = chat(system, user, model=model, temperature=0.4, json_mode=True)
    return json.loads(raw)
