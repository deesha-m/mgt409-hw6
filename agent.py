"""Campus Customs vendor desk agent.

Usage: python agent.py --doc data/practice_docs/p01_bluehen_quote.html [--defenses all|none|code,design,prompt] [--no-cache]

Defenses are on by default. `--defenses none` runs the original, undefended Problem 3 agent.
"""
import argparse
import json
import os
import uuid

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, Tool, ToolDenied
from pydantic_ai.capabilities import ProcessHistory
from pydantic_ai.messages import ModelMessage, ModelRequest, SystemPromptPart
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from models import AgentDeps, VendorDecision
from rules import decide, verify_against_document
from tools import TOOLS, approve_payment, log_trap_call, read_document, send_email

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
OUTPUT_DIR = HERE / "output"
MODEL_NAME = "gpt-6-luna"
CACHE_BUSTER = "[cache-buster "
ALL_DEFENSES = frozenset({"code", "design", "prompt"})
PROMPT_DEFENSES_MARKER = "<!-- PROMPT DEFENSES"
DANGEROUS_TOOLS = ("send_email", "approve_payment")

# Raw `usage` blocks from every API response, filled by the httpx hook below.
API_CALLS: list[dict] = []


async def _record_usage(response: httpx.Response) -> None:
    if response.request.url.path.endswith("/chat/completions") and response.status_code == 200:
        await response.aread()
        body = response.json()
        API_CALLS.append({"response_id": body.get("id"), "model": body.get("model"), "usage": body.get("usage", {})})


def _bust_cache(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Put a fresh random ID in front of the handbook before every model call, so no prefix can match."""
    for message in messages:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, SystemPromptPart):
                    if part.content.startswith(CACHE_BUSTER):
                        part.content = part.content.split("\n", 1)[1]
                    part.content = f"{CACHE_BUSTER}{uuid.uuid4()}]\n{part.content}"
                    return messages
    return messages


def build_agent(cache: bool = True, defenses: frozenset[str] = ALL_DEFENSES) -> Agent:
    # A .env next to agent.py (fresh clone) wins; otherwise use the course .env two folders up.
    for env_file in (HERE / ".env", HERE.parents[1] / ".env"):
        if env_file.exists():
            load_dotenv(env_file)
            break
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY was not found")

    client = AsyncOpenAI(
        base_url=PORTKEY_GATEWAY_URL,
        api_key="portkey",  # real auth is the Portkey header below
        default_headers=createHeaders(api_key=api_key),
        http_client=httpx.AsyncClient(event_hooks={"response": [_record_usage]}, timeout=120),
    )
    model = OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))

    handbook = (DATA_DIR / "shop_handbook.md").read_text(encoding="utf-8")
    instructions = (HERE / "prompts" / "prompt.md").read_text(encoding="utf-8")
    if "prompt" not in defenses:
        instructions = instructions.split(PROMPT_DEFENSES_MARKER)[0].rstrip() + "\n"
    if "design" in defenses:
        # Design layer: the dangerous tools stay on the system but cannot run without a human sign-off.
        tools = [read_document, Tool(send_email, requires_approval=True), Tool(approve_payment, requires_approval=True)]
        output_type = [VendorDecision, DeferredToolRequests]
    else:
        tools, output_type = TOOLS, VendorDecision
    # Handbook goes first so it is an identical prefix on every call (prompt caching).
    # With cache=False, a random ID is put in front of it on every call so nothing can be reused.
    return Agent(
        model,
        deps_type=AgentDeps,
        output_type=output_type,
        system_prompt=[handbook, instructions],
        tools=tools,
        # gpt-6-luna only allows function tools on /chat/completions with reasoning turned off.
        model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
        capabilities=[] if cache else [ProcessHistory(_bust_cache)],
    )


def cost_usd(input_tokens: int, cache_read: int, cache_write: int, output_tokens: int) -> float:
    prices = json.loads((DATA_DIR / "prices.json").read_text())[MODEL_NAME]
    uncached = input_tokens - cache_read - cache_write
    return (
        uncached * prices["input_per_1m"]
        + cache_read * prices["cached_input_per_1m"]
        + cache_write * prices["cache_write_per_1m"]
        + output_tokens * prices["output_per_1m"]
    ) / 1_000_000


def append_json(path: Path, entry: dict) -> None:
    entries = json.loads(path.read_text()) if path.exists() else []
    entries.append(entry)
    path.write_text(json.dumps(entries, indent=2))


def _deny_dangerous_calls(requests: DeferredToolRequests, deps: AgentDeps, doc: str) -> DeferredToolResults:
    """No human is signing off during a document review, so every send/pay request is logged and denied."""
    denials = {}
    for call in requests.approvals:
        args = call.args_as_dict()
        log_trap_call(deps.output_dir, call.tool_name, args, document=doc, blocked="awaiting human sign-off; denied")
        deps.tool_calls.append({"tool": call.tool_name, "args": args, "result": "BLOCKED: needs human sign-off (logged to trap_calls.json)"})
        deps.safety_notes.append(f"design: blocked {call.tool_name} call (needs human sign-off)")
        denials[call.tool_call_id] = ToolDenied("Blocked: this action needs a human sign-off and is not part of reviewing a quote.")
    return DeferredToolResults(approvals=denials)


def run(doc: str, cache: bool = True, defenses: frozenset[str] = ALL_DEFENSES) -> tuple[VendorDecision, list[dict], AgentDeps]:
    """Run the agent on one document. Returns the answer, the raw API usage of each model call, and the run state."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    trap_file = OUTPUT_DIR / "trap_calls.json"
    if not trap_file.exists():
        trap_file.write_text("[]")

    defenses = frozenset(defenses)
    deps = AgentDeps(data_dir=DATA_DIR, output_dir=OUTPUT_DIR, doc_path=HERE / doc, defenses=defenses)
    started = datetime.now(timezone.utc).isoformat()
    API_CALLS.clear()
    agent = build_agent(cache, defenses)
    result = agent.run_sync(f"Vendor document path: {doc}", deps=deps)
    for _ in range(3):  # design layer: a poisoned document may ask for send/pay more than once
        if not isinstance(result.output, DeferredToolRequests):
            break
        result = agent.run_sync(
            message_history=result.all_messages(), deps=deps,
            deferred_tool_results=_deny_dangerous_calls(result.output, deps, doc),
        )
    answer = result.output
    if not isinstance(answer, VendorDecision):
        raise RuntimeError("The agent kept asking for send/pay tools and never returned an answer.")

    model_answer = answer.model_dump()
    if "design" in defenses:
        # Design layer: the model only extracts facts; code checks them against the document and decides.
        facts = {k: model_answer[k] for k in ("vendor", "sku", "unit_price", "lead_time_days", "min_order")}
        facts, notes = verify_against_document(facts, deps.document_text)
        deps.safety_notes += [f"design: {n}" for n in notes]
        decision, reason = decide(facts, deps.document_text)
        answer = VendorDecision(**facts, decision=decision, reason=reason)

    calls = list(API_CALLS)
    tokens = {
        "requests": len(calls),
        "input_tokens": sum(c["usage"].get("prompt_tokens", 0) for c in calls),
        "cached_input_tokens": sum((c["usage"].get("prompt_tokens_details") or {}).get("cached_tokens", 0) for c in calls),
        "cache_write_tokens": sum((c["usage"].get("prompt_tokens_details") or {}).get("cache_write_tokens", 0) for c in calls),
        "output_tokens": sum(c["usage"].get("completion_tokens", 0) for c in calls),
    }
    tokens["total_tokens"] = tokens["input_tokens"] + tokens["output_tokens"]
    cost = cost_usd(tokens["input_tokens"], tokens["cached_input_tokens"], tokens["cache_write_tokens"], tokens["output_tokens"])
    defense_label = ",".join(sorted(defenses)) or "none"
    append_json(OUTPUT_DIR / "usage_log.json", {
        "document": doc, "time": started, "model": MODEL_NAME, "cache": cache, "defenses": defense_label,
        **tokens, "cost_usd": round(cost, 8),
    })
    append_json(OUTPUT_DIR / "audit_trail.json", {
        "document": doc, "time": started, "defenses": defense_label, "tool_calls": deps.tool_calls,
        "safety_notes": deps.safety_notes, "model_answer": model_answer, "final_answer": answer.model_dump(),
    })

    print(json.dumps(answer.model_dump(), indent=2))
    print(f"Tokens: {tokens}  Cost: ${cost:.6f}")
    for note in deps.safety_notes:
        print(f"SAFETY {note}")
    traps = [c["tool"] for c in deps.tool_calls if c["tool"] in DANGEROUS_TOOLS]
    if traps:
        print(f"WARNING: trap tools called: {traps}. See output/trap_calls.json")
    return answer, calls, deps


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus Customs vendor desk agent")
    parser.add_argument("--doc", required=True, help="Path to one vendor document (.html, .pdf, or .eml)")
    parser.add_argument("--no-cache", action="store_true", help="Make every call uncacheable (for Problem 4)")
    parser.add_argument("--defenses", default="all",
                        help="all (default), none (the undefended Problem 3 agent), or a comma list of code,design,prompt")
    args = parser.parse_args()
    chosen = {"all": ALL_DEFENSES, "none": frozenset()}.get(args.defenses)
    if chosen is None:
        chosen = frozenset(d.strip() for d in args.defenses.split(","))
        if not chosen <= ALL_DEFENSES:
            parser.error(f"unknown defense(s): {', '.join(chosen - ALL_DEFENSES)}")
    run(args.doc, cache=not args.no_cache, defenses=chosen)
