# Problem 2: Size Up the Handbook

## Token count

**The handbook is 10,058 tokens.**

How I got it:

- I counted the full text of `data/shop_handbook.md` with OpenAI's `tiktoken` library, using the `o200k_base` encoding. That is the tokenizer used by OpenAI's current GPT models, so it is the best local stand-in for `gpt-6-luna`.
- Script: `count_handbook_tokens.py` (run with `.venv/bin/python count_handbook_tokens.py`).
- Sanity check: the file is 28,903 characters and 6,127 words. That works out to about 2.9 characters per token, or 1.6 tokens per word. This is in the normal range for English with markdown and numbers. The older `cl100k_base` tokenizer gives a similar 10,184.

## Prices (from `data/prices.json`, gpt-6-luna, per 1M tokens)

| Token type | Price per 1M tokens |
|---|---|
| Input (uncached) | $0.10 |
| Cached input (cache read) | $0.01 |
| Cache write | $0.125 |
| Output | $0.50 (not used here: the handbook is input only) |

Formula: cost = tokens × (price per 1M) ÷ 1,000,000

## Cost of the handbook alone

### Without caching (every call pays full input price)

- **1 call:** 10,058 × $0.10 ÷ 1,000,000 = **$0.0010058** (about 0.1¢)
- **1,000 calls:** 1,000 × $0.0010058 = **$1.0058** (about $1.01)

### With caching

The first call writes the handbook into the cache. Each later call reads it from the cache.

- **Cache write (first call):** 10,058 × $0.125 ÷ 1,000,000 = **$0.00125725**
- **Cache read (each later call):** 10,058 × $0.01 ÷ 1,000,000 = **$0.00010058** (about 0.01¢)
- **1 call:**
  - If the cache is already warm: **$0.00010058**
  - If this call writes the cache: **$0.00125725**
- **1,000 calls (1 write + 999 reads):**
  $0.00125725 + 999 × $0.00010058
  = $0.00125725 + $0.10047942
  = **$0.1017** (about 10¢)
  - If all 1,000 calls were reads, it would be 1,000 × $0.00010058 = $0.1006.

### Summary

| Scenario | 1 call | 1,000 calls |
|---|---|---|
| No caching | $0.0010058 | $1.0058 |
| With caching | $0.00010058 (warm) / $0.00125725 (first, cache write) | $0.1017 |

Caching cuts the handbook's cost by about **90%** (from $1.01 to $0.10 per 1,000 calls). The only extra cost is the one-time cache write.

## What to watch for when checking against real runs (Problem 4)

- **The measured input count will be a bit higher than 10,058.** The API adds a few tokens of formatting per chat message. Each call also includes the vendor document and instructions, so `prompt_tokens` covers more than the handbook.
- **Caching only works if the handbook comes first.** The handbook has to be an identical prefix at the start of the prompt. Also, OpenAI caches in blocks (prompts of 1,024+ tokens, in 128-token steps). So `cached_tokens` may be a bit below the full handbook count, for example 9,984 or 10,112 depending on where the prefix ends.
- **The cache can expire.** It empties after a few minutes of inactivity. If calls are spread out, the cache may be written more than once, so real cached costs could be slightly above the estimate.
