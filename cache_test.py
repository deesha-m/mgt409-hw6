"""Problem 4: run all 12 practice documents with and without prompt caching and log every model call."""
import json
from datetime import datetime, timezone

import agent

DOCS = sorted((agent.DATA_DIR / "practice_docs").iterdir())
KEY = {row["file"]: row for row in json.loads((agent.DATA_DIR / "practice_key.json").read_text())}
FIELDS = ["vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision"]


def call_record(setup: str, doc: str, index: int, raw: dict) -> dict:
    usage = raw["usage"]
    prompt = usage.get("prompt_tokens", 0)
    details = usage.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens", 0)
    written = details.get("cache_write_tokens", 0)
    output = usage.get("completion_tokens", 0)
    return {
        "setup": setup,
        "document": doc,
        "call": index,
        "response_id": raw["response_id"],
        "model": raw["model"],
        "prompt_tokens": prompt,
        "cached_tokens": cached,
        "cache_write_tokens": written,
        "uncached_input_tokens": prompt - cached - written,
        "prompt_audio_tokens": details.get("audio_tokens", 0),
        "completion_tokens": output,
        "completion_tokens_details": usage.get("completion_tokens_details") or {},
        "total_tokens": usage.get("total_tokens", 0),
        "cost_usd": round(agent.cost_usd(prompt, cached, written, output), 8),
    }


def main() -> None:
    calls, answers = [], []
    for setup, cache in (("with_cache", True), ("without_cache", False)):
        for path in DOCS:
            doc = str(path.relative_to(agent.HERE))
            print(f"\n=== {setup}: {path.name}")
            answer, raw_calls, _ = agent.run(doc, cache=cache, defenses=frozenset())
            calls += [call_record(setup, doc, i, raw) for i, raw in enumerate(raw_calls, 1)]
            expected = KEY[path.name]
            wrong = [f for f in FIELDS if getattr(answer, f) != expected[f]]
            answers.append({"setup": setup, "document": path.name, "matches_key": not wrong, "wrong_fields": wrong})

    bad = [c for c in calls if c["setup"] == "without_cache" and c["cached_tokens"] > 0]
    if bad:
        raise SystemExit(f"Without-cache setup still read from cache on {len(bad)} calls - test invalid.")

    out = agent.OUTPUT_DIR / "cache_test.json"
    out.write_text(json.dumps({
        "run_at": datetime.now(timezone.utc).isoformat(),
        "prices": json.loads((agent.DATA_DIR / "prices.json").read_text()),
        "calls": calls,
        "answers": answers,
    }, indent=2))
    print(f"\nSaved {len(calls)} model calls to {out}")


if __name__ == "__main__":
    main()
