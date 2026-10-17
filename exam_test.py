"""Problem 8: run the final defended agent on the 10 exam documents. Results are written as-is."""
import json

import agent

EXAM_DIR = agent.DATA_DIR / "exam_docs"
TRAP_FILE = agent.OUTPUT_DIR / "trap_calls.json"


def main() -> None:
    results = []
    for path in sorted(EXAM_DIR.iterdir()):
        doc = str(path.relative_to(agent.HERE))
        print(f"\n=== {path.name}")
        traps_before = len(json.loads(TRAP_FILE.read_text()))
        answer, calls, deps = agent.run(doc, defenses=agent.ALL_DEFENSES)
        new_traps = json.loads(TRAP_FILE.read_text())[traps_before:]
        usage = [c["usage"] for c in calls]
        input_tokens = sum(u.get("prompt_tokens", 0) for u in usage)
        cached = sum((u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) for u in usage)
        written = sum((u.get("prompt_tokens_details") or {}).get("cache_write_tokens", 0) for u in usage)
        output_tokens = sum(u.get("completion_tokens", 0) for u in usage)
        results.append({
            "file": path.name,
            **answer.model_dump(),
            "trap_tool_called": bool(new_traps),
            "input_tokens": input_tokens,
            "cached_tokens": cached,
            "output_tokens": output_tokens,
            "cost_usd": round(agent.cost_usd(input_tokens, cached, written, output_tokens), 8),
        })
    (agent.OUTPUT_DIR / "exam_results.json").write_text(json.dumps(results, indent=2))
    print(f"\nSaved {len(results)} entries to output/exam_results.json")


if __name__ == "__main__":
    main()
