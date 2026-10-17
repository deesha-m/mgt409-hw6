"""Count the tokens in the shop handbook and estimate what it costs per call."""
import json
from pathlib import Path

import tiktoken

HERE = Path(__file__).parent
text = (HERE / "data" / "shop_handbook.md").read_text(encoding="utf-8")
prices = json.loads((HERE / "data" / "prices.json").read_text())["gpt-6-luna"]

tokens = len(tiktoken.get_encoding("o200k_base").encode(text))
uncached = tokens * prices["input_per_1m"] / 1_000_000
cache_read = tokens * prices["cached_input_per_1m"] / 1_000_000
cache_write = tokens * prices["cache_write_per_1m"] / 1_000_000

print(f"Handbook tokens (o200k_base): {tokens:,}")
print(f"Uncached:  1 call ${uncached:.8f}   1,000 calls ${uncached * 1000:.4f}")
print(f"Cache write (first call): ${cache_write:.8f}")
print(f"Cache read:  1 call ${cache_read:.8f}   1,000 calls ${cache_read * 1000:.4f}")
print(f"1,000 calls with caching (1 write + 999 reads): ${cache_write + 999 * cache_read:.4f}")
