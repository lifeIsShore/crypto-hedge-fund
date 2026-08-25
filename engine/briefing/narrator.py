"""
engine/briefing/narrator.py
============================
Calls a local Ollama model to turn the Briefing rollup data into a short
plain-English summary. Uses urllib only (no new dependency, matches the
existing pattern in flask_app.py's check_api_connectivity()).

Design principles (see todos/NEW-briefing-tab-TODO.md §6):
  - Generated on-demand (button / scheduled hook), NOT on every page load.
  - Result is cached to shared/state/briefing_narrative.json with a
    timestamp + model name, so the /briefing route can render instantly.
  - Reasoning models (deepseek-r1 family) wrap output in <think>...</think>
    — stripped before caching so it never leaks into the UI.
"""

import json
import re
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = Path(__file__).parent / "narrator_prompt.md"
CACHE_PATH = ROOT / "shared" / "state" / "briefing_narrative.json"

OLLAMA_URL = "http://localhost:11434/api/generate"

# Models available for the picker, fastest/most-literal first.
# Reasoning models (deepseek-r1) intentionally last — slower and prone to
# editorializing in the "thinking" phase, which works against the
# no-generic-filler goal. Left available for comparison, not the default.
AVAILABLE_MODELS = [
    "qwen3:8b",
    "llama3.1:8b",
    "qwen2.5-coder:14b",
    "qwen2.5:3b",
    "deepseek-r1:8b",
    "deepseek-r1:14b",
]
DEFAULT_MODEL = "qwen3:8b"

_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think_tags(text: str) -> str:
    return _THINK_TAG_RE.sub("", text).strip()


def _load_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return "Summarize the following hedge fund system data plainly and concisely."


def _call_ollama(model: str, system_prompt: str, data_block: dict, timeout: int = 300) -> str:
    payload = {
        "model": model,
        "system": system_prompt,
        "prompt": "DATA:\n" + json.dumps(data_block, default=str, indent=2),
        "stream": False,
        "keep_alive": "1h",
        "options": {"temperature": 0.2},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body.get("response", "")


def generate_narrative(briefing_data: dict, model: str = None) -> dict:
    """Generate a fresh narrative and write it to the cache file.

    Returns dict: {ok, narrative, model, generated_at, error}
    """
    model = model or DEFAULT_MODEL
    system_prompt = _load_prompt()
    result = {
        "ok": False,
        "narrative": "",
        "model": model,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "error": None,
    }
    try:
        raw = _call_ollama(model, system_prompt, briefing_data)
        narrative = _strip_think_tags(raw)
        if not narrative:
            raise ValueError("Model returned empty response.")
        result["ok"] = True
        result["narrative"] = narrative
    except urllib.error.URLError as e:
        result["error"] = f"Could not reach Ollama at {OLLAMA_URL} — is it running? ({e})"
    except Exception as e:
        result["error"] = str(e)

    _write_cache(result)
    return result


def _write_cache(result: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp.json")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        tmp.replace(CACHE_PATH)
    except Exception:
        pass  # cache is best-effort; the caller already has the fresh result


def load_cached_narrative() -> dict:
    """Read the last generated narrative, if any. Returns {} if none exists."""
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
