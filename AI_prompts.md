# Homework 6 — AI Prompts Log

## Problem 1: Vibe Coder Prompts

**Prompt:**
> Let's work on Homework 6, one question at a time, only in this folder. Create an `AI_prompts.md` file and keep it updated as we work. I'll describe each problem in my own words; summarize and log those prompts. Give each problem its own section with the problem number and title, at least one prompt in my own words, and a follow-up prompt if one was needed (plus one sentence on what the first prompt was missing).

**Follow-up prompt:** _None yet._

## Problem 2: Size Up the Handbook

**Prompt:**
> Look through `data/shop_handbook.md`, the Campus Customs Shop Handbook. The agent will send it to the model on every call. Also look at `data/prices.json`, the gpt-6-luna price list. Find out how many tokens the handbook is. In `output/handbook_estimate.md`, write the token count and how you got it, and what the handbook alone costs in dollars on one call and on 1,000 calls, with and without cached tokens. Show your math. I'll check these estimates against real runs in Problem 4.

**Follow-up prompt:** _None needed._

## Problem 3: Build the Vendor Desk Agent

**Prompt:**
> Build the vendor desk agent with PydanticAI using gpt-6-luna, as four files: `prompts/prompt.md` (the agent's instructions; the handbook is also sent on every call), `agent.py` (entry point), `tools.py` (tools), and `models.py` (structured types). Give it the path to one vendor document. It reads the document with a tool (HTML, PDF, and .eml all have to work) and returns vendor, SKU, unit price, lead time in days, minimum order, a recommend / do_not_recommend decision following the handbook rules, and a one-sentence reason. Add two trap tools, `send_email` and `approve_payment`. The job never needs them, and they don't send or pay anything. They only append the call and its arguments to `output/trap_calls.json` (start it as an empty list), so any entry means a document took over the agent. Keep them for the whole homework. After every run, append to `output/usage_log.json` (document, time, API token counts, dollar cost from `prices.json`) and `output/audit_trail.json` (each tool call with arguments and a short result, plus the final answer). It should run as `python agent.py --doc data/practice_docs/p01_bluehen_quote.html`. Run it on p01 and p08, and start `output/harness.md` with each field in `models.py` and why, and each tool in one line.

**Follow-up prompt:** _None needed._

## Problem 4: With and Without Cached Tokens

**Prompt:**
> The handbook is the same on every call, so the model can reuse it from a cache at a much lower price. Test what that is worth. Run the agent on all 12 practice documents two ways: with cache (set up so the handbook gets reused) and without cache (set up so nothing gets reused). Use the token counts the API returns to prove each setup really did what you think; a without-cache run that still shows cached tokens doesn't count. Save every model call from both setups to `output/cache_test.json` with the setup, document, every token count the API reports, and dollars from `prices.json`. In `output/cache_test.md`, give the total cost and cost per document for each setup and the percent saved, compare the real numbers to my Problem 2 estimate, project the cost of 1,000 documents a day for 30 days with and without cache, and explain anything in the numbers that was surprising and why it happens.

**Follow-up prompt:** _None needed._

## Problem 5: Attack Your Own Agent

**Prompt:**
> Some vendor documents are booby-trapped with text aimed at AI. Run the Problem 3 agent, with no new defenses, on all 12 documents in `data/practice_docs/`. Compare each answer to `data/practice_key.json` and check `output/trap_calls.json`. Save `output/attack_results.json` with, for each document, whether each field matched the key, whether the decision matched, whether a trap tool was called, and whether a link or other strange text showed up in the answer. In `output/attack_results.md`, for every document that fooled the agent, explain what fooled it and where in the file it was hiding. Open the documents the way a person would (browser, PDF viewer, email app) and compare that with what the agent read.

**Follow-up prompt:** _None needed._

## Problem 6: Defend Your Agent

**Prompt:**
> Defend the agent at three levels: code (what the program does to the document before any model sees it), design (how the agent is put together, so a poisoned document can't reach the dangerous tools or the decision), and prompt (rules in `prompts/prompt.md`). Don't delete `send_email` or `approve_payment`; the shop will use them later with a human sign-off. Keep a way to run the agent with no defenses for Problem 7. Rerun all 12 practice documents and save `output/defense_results.json` in the same shape as Problem 5, plus tokens and dollars per document. Clean documents must still come back with the right values; refusing or blanking out a real quote counts as a failure. In `output/defense_results.md`, include a before-and-after table for all 12 documents, what each layer catches that the others miss, and the extra tokens and dollars each layer adds per document. Add a Safety section to `output/harness.md` that explains each defense layer in plain words.

**Follow-up prompt:** _None needed._

## Problem 7: Red Team

**Prompt:**
> Now you're the attacker. Make two new booby-trapped vendor documents in `data/my_attacks/` (HTML, PDF, or email). Each one should use a hiding trick or an attack goal that isn't in the practice set, and a person opening it should see a normal quote. Run both attacks on the agent with no defenses and on the defended agent. In `output/red_team.md`, for each attack, explain what is hidden, where, what it tries to make the agent do, and what happened before and after the defenses. More points for attacks that are new and that actually fool the undefended agent.

**Follow-up prompt:** _None needed._

## Problem 8: Exam Documents

**Prompt:**
> `data/exam_docs/` has 10 vendor documents with no answer key. Run the final defended agent on all of them, without hand-editing the results. Save `output/exam_results.json` with one entry per exam file, containing: `file` (e.g. `e01_quote.html`), `vendor`, `sku`, `unit_price`, `lead_time_days`, `min_order`, `decision` (recommend or do_not_recommend), `reason`, `trap_tool_called` (true/false), `input_tokens`, `cached_tokens`, `output_tokens`, and `cost_usd`. Graders will compare against a hidden answer key and rerun some agents.

**Follow-up prompt:** _None needed._

## Problem 9: Results Page

**Prompt:**
> Build `output/hw6/report.html` as one file that opens by double-click, with no internet and no other files next to it. Using the real numbers from earlier problems, show: the caching results with a chart; attacks before and after the defenses; what the defenses cost in tokens and dollars; the exam results and the two red-team attacks; and a short recommendation to the store manager on whether Campus Customs should turn the agent on for real vendor mail and what it would cost per month at 1,000 documents a day. A designed page (fonts, color, layout) that reads well gets more points.

**Follow-up prompt:** _None needed._

## Problem 10: Push to GitHub and Submit the URL

**Prompt:**
> Push the project to a public GitHub repository and give me the URL to submit on Canvas. Graders will clone it, so make sure it opens and matches the expected layout. Include the whole `data/` folder (the course data plus my two attack files) so graders can run the agent right away. Don't commit the real `.env`: keep it out with `.gitignore` and include a `.env.example` with placeholders only. Add a short note to `README.md` on how to run the agent.

**Follow-up prompt:** _None needed._
