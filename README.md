# Campus Customs Vendor Desk Agent (MGT 409, Homework 6)

A PydanticAI agent (`gpt-6-luna` via Portkey) that:
- reads one vendor document (HTML, PDF, or `.eml` email)
- pulls out the vendor, SKU, unit price, lead time, and minimum order
- decides **recommend / do_not_recommend** using the Campus Customs Shop Handbook

It has three layers of defense against booby-trapped documents (code, design, prompt). It also has two trap tools, `send_email` and `approve_payment`. They never send or pay anything; they only log to `output/trap_calls.json`.

**Results page:** open `output/hw6_report.html` by double-clicking it. It works offline.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then put your PORTKEY_API_KEY in .env
```

## Run the agent

```bash
# Defended agent (all defenses on, the default)
python agent.py --doc data/practice_docs/p01_bluehen_quote.html

# Undefended agent (the original Problem 3 agent)
python agent.py --doc data/practice_docs/p01_bluehen_quote.html --defenses none

# Any mix of layers, or turn prompt caching off
python agent.py --doc data/exam_docs/e01_quote.html --defenses code,prompt
python agent.py --doc data/exam_docs/e01_quote.html --no-cache
```

**What a run prints:** the answer as JSON, the token counts, the cost, and any safety notes.

**What a run appends to:**
- `output/usage_log.json`: tokens and dollars
- `output/audit_trail.json`: every tool call, the safety notes, and the final answer

## Rerun each problem

| Problem | Command | Writes |
|---|---|---|
| 2: handbook size | `python count_handbook_tokens.py` | `output/handbook_estimate.md` (written by hand from this output) |
| 4: caching | `python cache_test.py` | `output/cache_test.json` |
| 5: attacks, no defenses | `python attack_test.py` | `output/attack_results.json` |
| 6: defenses | `python defense_test.py` | `output/defense_results.json`, `output/defense_layers.json` |
| 7: red team | `python red_team_test.py` | `output/red_team_results.json` |
| 8: exam | `python exam_test.py` | `output/exam_results.json` |
| 9: results page | `python build_report.py` | `output/hw6_report.html` (and `output/hw6/report.html`) |

## Files

| File | Role |
|---|---|
| `agent.py` | Entry point |
| `tools.py` | The document reader and the two trap tools |
| `models.py` | Structured output and run state |
| `prompts/prompt.md` | Instructions, including the prompt-layer safety rules |
| `sanitize.py` | Code-layer defense: keeps only the text a person would see |
| `rules.py` | Design-layer defense: the handbook checks run in code |

- **Course data:** `data/`
- **Our two attack documents:** `data/my_attacks/`
- **Written results:** `output/*.md`. `output/harness.md` describes the agent and its Safety section.
- **Prompt log:** `AI_prompts.md`

The handbook is sent with every model call, so the model is billed for it each time; prompt caching makes those repeats about 10× cheaper.

`.env` is never committed (see `.gitignore`).
