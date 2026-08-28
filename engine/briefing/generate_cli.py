"""
engine/briefing/generate_cli.py
=================================
Run: python -m engine.briefing.generate_cli [model_name]

Regenerates the Briefing narrative from the current DB state and caches it
to shared/state/briefing_narrative.json. Meant to be called at the end of
RUN_FUND_TOTAL.bat (after data/ML/mirroring steps, before the dashboard
launches) so the narrative reflects the run that just happened, not
whatever was cached from last time.

Fails soft: if Ollama isn't reachable, logs and exits 0 rather than
blocking the rest of the pipeline / dashboard launch. The Briefing page's
Regenerate button remains available regardless.
"""

import sys

from engine.briefing.data import gather_all, narrator_payload
from engine.briefing.narrator import generate_narrative, DEFAULT_MODEL, AVAILABLE_MODELS


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    if model not in AVAILABLE_MODELS:
        print(f"[briefing] Unknown model '{model}', falling back to {DEFAULT_MODEL}")
        model = DEFAULT_MODEL

    print(f"[briefing] Gathering rollup data...")
    data = gather_all()
    payload = narrator_payload(*data)

    print(f"[briefing] Generating narrative with {model}...")
    result = generate_narrative(payload, model=model)

    if result["ok"]:
        print(f"[briefing] Narrative cached OK ({result['generated_at']}).")
    else:
        print(f"[briefing] Generation failed (non-fatal, pipeline continues): {result['error']}")
    # Always exit 0 — a failed narrative should never block the pipeline/dashboard.
    sys.exit(0)


if __name__ == "__main__":
    main()
