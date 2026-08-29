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
TRADE_LEVELS_PROMPT_PATH = Path(__file__).parent / "trade_levels_prompt.md"
CACHE_PATH = ROOT / "shared" / "state" / "briefing_narrative.json"
TRADE_LEVELS_CACHE_PATH = ROOT / "shared" / "state" / "trade_levels_cache.json"

OLLAMA_URL = "http://localhost:11434/api/generate"

# Models available for the picker, fastest/most-literal first.
# Reasoning models (deepseek-r1) intentionally last — slower and prone to
# editorializing in the "thinking" phase, which works against the
# no-generic-filler goal. Left available for comparison, not the default.
AVAILABLE_MODELS = [
    "deepseek-v3.1:671b-cloud",
    "qwen3-coder:480b-cloud",
    "qwen3:8b",
    "llama3.1:8b",
    "qwen2.5-coder:14b",
    "qwen2.5:3b",
    "deepseek-r1:8b",
    "deepseek-r1:14b",
]
CLOUD_MODEL = "deepseek-v3.1:671b-cloud"
DEFAULT_LOCAL_MODEL = "qwen3:8b"

_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think_tags(text: str) -> str:
    return _THINK_TAG_RE.sub("", text).strip()


def _load_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return "Summarize the following hedge fund system data plainly and concisely."


def _call_ollama(model: str, system_prompt: str, data_block: dict, timeout: int = 6000) -> str:
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
        
    metrics = {
        "eval_count": body.get("eval_count", 0),
        "eval_duration_ms": int(body.get("eval_duration", 0) / 1000000) if body.get("eval_duration") else 0
    }
    return body.get("response", ""), metrics


def _log_llm_metrics(prompt_type: str, model: str, metrics: dict):
    from engine.db.db import get_session
    from sqlalchemy import text
    try:
        session = get_session()
        session.execute(text("""
            INSERT INTO llm_metrics (prompt_type, model, eval_count, eval_duration_ms)
            VALUES (:prompt_type, :model, :eval_count, :eval_duration_ms)
        """), {
            "prompt_type": prompt_type,
            "model": model,
            "eval_count": metrics.get("eval_count"),
            "eval_duration_ms": metrics.get("eval_duration_ms")
        })
        session.commit()
    except Exception as e:
        print(f"Failed to log LLM metrics: {e}")
    finally:
        try:
            session.close()
        except Exception:
            pass


def generate_narrative(briefing_data: dict, model: str = None) -> dict:
    """Generate a fresh narrative and write it to the cache file.

    Returns dict: {ok, narrative, model, generated_at, error}
    """
    primary_model = model or CLOUD_MODEL
    fallback_model = DEFAULT_LOCAL_MODEL
    
    system_prompt = _load_prompt()
    result = {
        "ok": False,
        "narrative": "",
        "model": primary_model,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "error": None,
        "tax_advice": None,
    }
    
    # Architecture: Try primary (usually cloud), fallback to local if quota exhausted/unavailable
    models_to_try = [primary_model]
    if primary_model != fallback_model:
        models_to_try.append(fallback_model)
        
    for attempt_model in models_to_try:
        try:
            raw, metrics = _call_ollama(attempt_model, system_prompt, briefing_data)
            _log_llm_metrics("briefing_narrative", attempt_model, metrics)
            
            narrative = _strip_think_tags(raw)
            if not narrative:
                raise ValueError("Model returned empty response.")
            
            tax_advice = None
            if "## Tax Advisor" in narrative:
                parts = narrative.split("## Tax Advisor")
                narrative = parts[0].strip()
                tax_advice = parts[1].strip()
                
            result["ok"] = True
            result["narrative"] = narrative
            result["tax_advice"] = tax_advice
            result["model"] = attempt_model
            result["error"] = None # clear any prior errors
            break # Success, stop trying models
            
        except urllib.error.URLError as e:
            result["error"] = f"Could not reach Ollama at {OLLAMA_URL} — is it running? ({e})"
        except urllib.error.HTTPError as e:
            result["error"] = f"HTTP Error from Ollama (possibly Cloud quota exhausted or model not pulled): {e}"
        except Exception as e:
            result["error"] = str(e)
            
        if attempt_model != models_to_try[-1]:
            print(f"[WARN] Failed with {attempt_model}, falling back to {fallback_model}...")

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


def load_cached_trade_levels() -> dict:
    """Read the last generated trade levels, if any. Returns {} if none exists."""
    try:
        with open(TRADE_LEVELS_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def generate_trade_levels(must_check_tickers: list, model: str = None) -> dict:
    """Generate structured trade levels for the top 5 must-check tickers."""
    import yfinance as yf
    model = model or DEFAULT_MODEL
    try:
        system_prompt = TRADE_LEVELS_PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        system_prompt = "Output strict JSON with buy_limit_price, buy_rationale, sell_target_price, sell_rationale, stop_loss_price, key_risk_flag."

    # Enforce O(shortlist) cap to save inference cost (max 5)
    tickers_to_process = must_check_tickers[:5]
    results = []

    for item in tickers_to_process:
        ticker = item.get("ticker")
        if not ticker:
            continue
            
        # 1. Fetch live data context via yfinance
        try:
            # Use 1 month of daily data to get recent ATR and current price
            hist = yf.download(ticker, period="1mo", interval="1d", progress=False)
            if hist.empty:
                continue
            
            # Yfinance returns multi-index columns in recent versions if passing list, but single ticker is simple
            close_col = 'Close' if 'Close' in hist.columns else hist.columns[0]
            high_col = 'High' if 'High' in hist.columns else hist.columns[1]
            low_col = 'Low' if 'Low' in hist.columns else hist.columns[2]
            
            current_price = float(hist[close_col].iloc[-1])
            
            # Simple ATR approx: average of (High - Low) / Close over last 14 days
            tail = hist.tail(14)
            atr_pct = float(((tail[high_col] - tail[low_col]) / tail[close_col]).mean())
            
        except Exception as e:
            # Fallback if yfinance fails
            current_price = 100.0
            atr_pct = 0.03

        # 2. Earnings proximity (placeholder mock if not in item, ideally joined from db)
        earnings_days_away = 30 # Default placeholder unless calendar data is piped in
            
        # 3. Payload for LLM
        payload_data = {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "recent_atr_pct": round(atr_pct, 4),
            "earnings_days_away": earnings_days_away,
            "up_proba": item.get("up_proba"),
            "risk_reward_ratio": item.get("risk_reward_ratio"),
            "kelly_half": item.get("kelly_half")
        }

        # 4. Generate & Parse JSON
        try:
            raw_out, metrics = _call_ollama(model, system_prompt, payload_data, timeout=12000)
            _log_llm_metrics("trade_levels", model, metrics)
            clean_out = _strip_think_tags(raw_out)
            
            # Extract JSON block if it added markdown fences despite instructions
            if "```json" in clean_out:
                clean_out = clean_out.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_out:
                clean_out = clean_out.split("```")[1].split("```")[0].strip()
                
            parsed = json.loads(clean_out)
            
            # Guardrails (Backend Validation)
            buy_limit = float(parsed.get("buy_limit_price", current_price))
            if buy_limit > current_price * 1.05: # Catch wild hallucinations
                parsed["buy_limit_price"] = current_price
                parsed["buy_rationale"] = "WARNING: Model hallucinated high price, capped at current price."
                
            results.append({
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "levels": parsed
            })
        except Exception as e:
            print(f"Failed to generate levels for {ticker}: {e}")
            continue

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "tickers": results
    }

    try:
        TRADE_LEVELS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = TRADE_LEVELS_CACHE_PATH.with_suffix(".tmp.json")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        tmp.replace(TRADE_LEVELS_CACHE_PATH)
    except Exception:
        pass

    return output
