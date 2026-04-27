import json
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL_SUMM, OPENAI_MODEL_SYNTH, PROMPTS_DIR

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return Path(path).read_text()


def call_json(
    prompt: str,
    *,
    model: str | None = None,
    purpose: str = "summ",
    temperature: float = 0.2,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Call OpenAI in JSON mode and return the parsed dict.

    purpose="summ" → cheap model; purpose="synth" → strong model.
    """
    chosen = model or (OPENAI_MODEL_SYNTH if purpose == "synth" else OPENAI_MODEL_SUMM)
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client().chat.completions.create(
                model=chosen,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_err}")
