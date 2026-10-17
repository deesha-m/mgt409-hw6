# Problem 4: With and Without Cached Tokens

I ran the vendor desk agent on all 12 practice documents in two setups. Every document takes **2 model calls**:
1. The model asks to read the document.
2. The model returns the answer.

That makes 24 calls per setup and **48 calls in total**. Every call is logged in `output/cache_test.json`. The script is `cache_test.py`.

## The two setups

| Setup | How it works |
|---|---|
| **With cache** | The handbook is the first thing in the prompt, followed by the instructions and tools. Every call therefore starts with the same text, so the API can reuse that opening from its cache. |
| **Without cache** | Before every call, a new random ID (`[cache-buster <uuid>]`) is put in front of the handbook. Caching only matches a prompt that begins exactly like an earlier one, so a new ID on every call means no call can match any earlier call. |

### Proof each setup did what I intended (token counts the API reported)

| | With cache | Without cache |
|---|---|---|
| Calls | 24 | 24 |
| Input (prompt) tokens | 263,870 | 264,552 |
| **Cached tokens (read from cache)** | **237,259** (90% of input) | **0 on all 24 calls** |
| Cache write tokens | 23,587 | 261,528 |
| Uncached input tokens | 3,024 | 3,024 |
| Output tokens | 1,502 | 1,466 |
| Reasoning tokens | 0 | 0 |

- **Without cache:** every one of the 24 calls shows `cached_tokens = 0`. `cache_test.py` stops with an error if any call shows otherwise, so this run counts.
- **With cache:**
  - From p03 onward, both calls on every document read about 10,790 tokens from the cache. That is the handbook, the instructions, and the tool definitions.
  - Only p01's first call and p02's first call found nothing in the cache. They wrote it instead (see "Surprises" below).
- The without-cache setup has about 28 extra input tokens per call. That is the random ID.

## Cost

Prices come from `data/prices.json`: input $0.10, cached input $0.01, cache write $0.125, and output $0.50, all per 1M tokens.

| | With cache | Without cache |
|---|---|---|
| **Total, 12 documents** | **$0.006374** | **$0.033726** |
| **Per document (average)** | **$0.000531** | **$0.002811** |
| Per document once the cache is warm (p03–p12) | $0.000324 | $0.002811 |
| **Saved by caching** | **81.1%** overall; **88.5%** once warm | — |

### Where the money goes per document (warm cache vs. no cache)

| Token type | With cache (warm) | Without cache |
|---|---|---|
| Cached input | 21,567 × $0.01/1M = $0.000216 | 0 |
| Cache write | 168 × $0.125/1M = $0.000021 | 21,794 × $0.125/1M = $0.002724 |
| Uncached input | 252 × $0.10/1M = $0.000025 | 252 × $0.10/1M = $0.000025 |
| Output | 124 × $0.50/1M = $0.000062 | 122 × $0.50/1M = $0.000061 |
| **Total** | **$0.000324** | **$0.002811** |

## How the real numbers compare to my Problem 2 estimate

| | Problem 2 estimate | Real |
|---|---|---|
| Handbook tokens | 10,058 (counted with `tiktoken`) | **10,059**. I measured this with one extra API call containing a short tag plus the handbook (10,086 tokens), minus a call with the tag alone (27 tokens). |
| Input tokens per model call | 10,058 (handbook only) | about 10,920 on call 1 and 11,040–11,120 on call 2. The extra ~860 tokens are the instructions, tool definitions, and answer format, plus the document on call 2. |
| Model calls per document | 1 (assumed) | **2** |
| Handbook cost per document, cached | $0.00010058 | 2 × $0.00010058 = $0.00020 |
| Handbook cost per document, not cached | $0.0010058 (at $0.10) | 2 × 10,058 × $0.125/1M = $0.00251, because it is billed as a cache write |
| 1,000 documents, cached | $0.1017 | **$0.32** in total ($0.53 including cold starts) |
| 1,000 documents, not cached | $1.0058 | **$2.81** in total |

**Bottom line:**
- The token count was right to within 1 token.
- The **percent saved** is close to what I predicted: I estimated about 90%, and the real figure is 88.5% once the cache is warm.
- The **dollar amounts** came out about **2.8× higher** than the handbook-only estimate, for three reasons:
  1. Each document takes 2 calls, so the handbook is sent twice.
  2. The instructions and tool definitions add about 860 tokens per call.
  3. In the without-cache setup, input is billed at the cache-write price instead of the plain input price.

## Projection: 1,000 documents a day for 30 days (30,000 documents)

| Setup | Per day | 30 days |
|---|---|---|
| Without cache (as measured) | $2.81 | **$84.32** |
| With cache, warm (steady flow of documents through the day) | $0.32 | **$9.71** |
| With cache, at this test's average (includes cold starts) | $0.53 | $15.94 |
| *Reference: no caching at all, input billed at plain $0.10* | *$2.27* | *$67.97* |

At 1,000 documents a day, a document arrives every 30–40 seconds during business hours. That is often enough to keep the cache warm, so the realistic monthly cost is about **$10 with caching vs. about $84 without**. That saves roughly **$75 a month (about 88%)**.

The cost is small either way at this volume. But the gap grows in direct proportion to volume and to the size of the handbook. At 100× the volume, the gap would be about $7,500 a month.

## Surprises, and why they happen

1. **"Without cache" costs more than having no caching at all.**
   - The API writes every long prompt into the cache automatically and bills those tokens at the cache-write price ($0.125/1M). That is 25% more than plain input ($0.10/1M).
   - I could stop the agent from *reading* the cache, but not from *writing* to it. As a result, every without-cache call paid the most expensive input price.
   - Practical lesson: if a prompt accidentally changes at the start on every call (a timestamp, a user name, or the document placed before the handbook), you pay more than you would with no caching at all. That is why the handbook goes first and anything that changes goes last.

2. **The handbook is sent twice per document.**
   - The agent works in two steps: (1) call the `read_document` tool, then (2) answer. Each step is a separate model call, and each call re-sends the whole conversation so far.
   - So the number of steps multiplies cost. Caching matters even more for agents than for single calls, because the second call almost entirely re-sends the first.

3. **The first two documents both missed the cache.**
   - p01 was cold because the cache from the last run, 5 days earlier, had expired.
   - p02's first call also missed, even though p01 had written the same opening about 2 seconds earlier. The likely reason is that cached prompts are stored on individual servers, and p02's call went to a different server than p01's. Each run's *second* call did hit the cache its first call had just written, so the cache was working.
   - So caching is "usually" rather than "guaranteed," and the first few calls after a quiet period pay full price.

4. **Exactly 126 input tokens per call are never cached or written, in both setups.** The API leaves this final stretch of each prompt out of the cache. It is small (about $0.000013 per call) but it never goes away.

5. **Output barely matters.** Output costs 5× more per token than input, but the agent writes only about 120 tokens per document against about 22,000 input tokens. Output is about 2% of the without-cache bill. Even with caching, it is under 20% of the bill. The input side, meaning the handbook, is what costs money.

6. **Caching did not change the answers. But the agent is inconsistent on documents with hidden instructions.**
   - 10 of 12 answers matched the key in the without-cache setup, and 11 of 12 with cache.
   - The misses were on documents that contain hidden "revised price" or "corrected lead time" text:
     - p12 got the price wrong in both setups.
     - p07 got the lead time wrong once.
     - p02 got the price wrong in an earlier single run but was right in both setups here.
   - The differences come from the without-cache setup, not from caching itself. The model is deterministic: identical input gives identical output. I checked this in Problem 6 by sending the same request twice; Portkey reported a cache `MISS` both times, gave each a new response ID, and the answer was identical. The without-cache setup adds a random ID to the prompt, and even that tiny change in input was enough to flip the answer on these borderline, booby-trapped documents.
   - The prompt-injection weakness itself needs a separate fix (Problem 6).
